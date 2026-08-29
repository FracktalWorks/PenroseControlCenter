"""
Printer Configuration Manager
Unified utility for managing both Klipper and OctoPrint configuration files, 
printer selection, variable parsing, and backup operations.
"""
import os
import shutil
import glob
import re
import json
import subprocess
import sys
import time
from typing import List, Dict, Optional, Any

try:
    import yaml
except ImportError:
    print("PyYAML not found. Attempting to install...")
    try:
        # Try to install PyYAML automatically
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyYAML'])
        import yaml
        print("✓ PyYAML installed successfully!")
    except subprocess.CalledProcessError:
        # If pip install fails, try with sudo
        try:
            subprocess.check_call(['sudo', 'pip', 'install', 'PyYAML'])
            import yaml
            print("✓ PyYAML installed successfully with sudo!")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise ImportError(
                "Failed to automatically install PyYAML. "
                "Please install it manually with: pip install PyYAML or sudo pip install PyYAML"
            ) from e

# Some fleet images ship a broken 'yaml' package (all modules 0 bytes) in
# /usr/local/lib/python3.7/dist-packages which shadows a real PyYAML
# installed elsewhere. Import succeeds but safe_load/safe_dump are missing,
# so every OctoPrint config update failed with:
#   module 'yaml' has no attribute 'safe_load'
# Detect that state, try to reinstall a real PyYAML over it, and fall back
# to older-style loaders for any remaining gaps.
if not hasattr(yaml, 'safe_load') or not hasattr(yaml, 'safe_dump'):
    print("yaml module is incomplete - reinstalling PyYAML...")
    for install_cmd in (
        [sys.executable, '-m', 'pip', 'install', '--force-reinstall', '-U', 'PyYAML'],
        ['sudo', sys.executable, '-m', 'pip', 'install', '--force-reinstall', '-U', 'PyYAML'],
    ):
        try:
            subprocess.check_call(install_cmd)
            break
        except Exception:
            continue
    try:
        import importlib
        yaml = importlib.reload(yaml)
    except Exception:
        pass


def _yaml_safe_load(f):
    """yaml.safe_load with fallbacks for incomplete/old PyYAML installs."""
    if hasattr(yaml, 'safe_load'):
        return yaml.safe_load(f)
    loader = getattr(yaml, 'SafeLoader', None)
    if loader is not None:
        return yaml.load(f, Loader=loader)
    return yaml.load(f)


def _yaml_safe_dump(data, f, **kwargs):
    """yaml.safe_dump with fallbacks for incomplete/old PyYAML installs."""
    if hasattr(yaml, 'safe_dump'):
        return yaml.safe_dump(data, f, **kwargs)
    dumper = getattr(yaml, 'SafeDumper', None)
    if dumper is not None:
        return yaml.dump(data, f, Dumper=dumper, **kwargs)
    return yaml.dump(data, f, **kwargs)

try:
    from packaging import version
except ImportError:
    print("packaging not found. Attempting to install...")
    try:
        # Try to install packaging automatically
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'packaging'])
        from packaging import version
        print("✓ packaging installed successfully!")
    except subprocess.CalledProcessError:
        # If pip install fails, try with sudo
        try:
            subprocess.check_call(['sudo', 'pip', 'install', 'packaging'])
            from packaging import version
            print("✓ packaging installed successfully with sudo!")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("Warning: packaging module not available. Version comparison will use string comparison as fallback.")
            version = None

from utils.logger import get_logger

logger = get_logger(__name__)

# Configuration paths
FIRMWARE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "firmware")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
PRINTER_CFG_PATH = '/home/pi/printer.cfg'
KLIPPER_CONFIG_PATH = '/home/pi/'
OCTOPRINT_CONFIG_PATH = '/home/pi/.octoprint/'
BACKUP_CFG_PATTERN = '/home/pi/printer-*.cfg'

# Klipper's [save_variables] target (CORE_GCODE_MACROS.cfg). Holds the
# tool offsets and babystep. (The extruder mode is NOT stored here any
# more - it is which MODE_*.cfg printer.cfg includes.)
KLIPPER_VARIABLES_PATH = '/home/pi/.octoprint/data/klipper/variables.cfg'

# ---------------------------------------------------------------------------
# Hybrid extruder mode (config-swap model)
#
# The printing head is selected by which MODE_*.cfg printer.cfg includes.
# Klipper therefore sees a single-extruder printer in either mode, and the
# two modes are free to define the SAME section names ([stepper_x],
# [extruder], ...) with different pins.
#
# That freedom is exactly why calibration has to be stored per mode: both
# modes have a section literally called [extruder], but a pellet auger on an
# AC band heater and a TD-01 hotend need completely different PID values,
# and their nozzles sit at different heights so [stepper_z] position_endstop
# differs too. A single shared SAVE_CONFIG block would let each mode switch
# silently overwrite the other mode's calibration.
# ---------------------------------------------------------------------------
EXTRUDER_MODES = ('pellet', 'filament')
MODE_CFG_FILES = {
    'pellet': 'MODE_PELLET.cfg',
    'filament': 'MODE_FILAMENT.cfg',
}
# Where the per-mode and shared halves of the SAVE_CONFIG block are kept
# between switches.
MODE_STATE_DIR = '/home/pi/.penrose'

# SAVE_CONFIG sections that belong to the PRINT HEAD and must therefore be
# stored separately per mode. Everything else is a property of the machine
# and is SHARED.
#
# Head-specific sections stored per mode:
#   [extruder]    - heater PID. A pellet auger on an AC band heater and a
#                   TD-01 hotend need completely different values, and
#                   both modes call that section literally "[extruder]".
#   [probe]       - z_offset, one per nozzle. The pellet value comes from
#                   the bed probe (only the pellet nozzle triggers it); the
#                   filament value is seeded with PROBE_Z_OFFSET_SEED and
#                   set manually via M851 - the TD-01 cannot auto-probe.
# Default-to-shared is deliberate beyond this list: anything not named is
# preserved across modes rather than silently discarded.
#
# What must NOT be per-mode:
#   [bed_mesh *]  - the bed's shape. Only the pellet nozzle triggers the
#                   probe, so filament mode depends on inheriting it.
#   [stepper_z]   - the Z endstop position, a gantry property.
# The filament nozzle's different height/position is corrected by
# tool_offset_x/y/z applied as a gcode offset (_APPLY_HEAD_OFFSET),
# exactly as the old IDEX config did - NOT by re-zeroing the machine.
PER_MODE_SAVE_CONFIG_PREFIXES = ('extruder', 'tmc2209', 'tmc5160', 'probe')

# OctoPrint temperature presets for the Hybrid IDEX filament head. The
# pellet presets are the ones shipped in the template config.yaml (the
# pellet machine is the base configuration), so only the filament set
# needs defining here. Whichever set matches the active extruder mode is
# what the OctoPrint web UI offers - see get_temperature_profiles_for_mode.
FILAMENT_TEMP_PRESETS = [
    {'name': 'PLA Filament', 'extruder': 210, 'bed': 60, 'chamber': None},
    {'name': 'PETG Filament', 'extruder': 240, 'bed': 80, 'chamber': None},
    {'name': 'ABS Filament', 'extruder': 245, 'bed': 100, 'chamber': None},
]

# Fallback values when configuration cannot be read
FALLBACK_CONFIG = {
    'name': 'Unknown Printer',
    'extruder_count': 2,
    'bed_width': 200,
    'bed_depth': 200,
    'bed_height': 200,
    'is_dual': True
}


class PrinterConfigManager:
    """Unified manager for all printer configuration operations."""
    
    def __init__(self):
        self.firmware_path = FIRMWARE_PATH
        self.config_path = CONFIG_PATH
        self.printer_cfg_path = PRINTER_CFG_PATH
        self.klipper_config_path = KLIPPER_CONFIG_PATH
        self.octoprint_config_path = OCTOPRINT_CONFIG_PATH
        self.backup_pattern = BACKUP_CFG_PATTERN

    # ========================================================================
    # PRINTER DISCOVERY AND MANAGEMENT
    # ========================================================================
    
    def get_available_printers(self) -> List[str]:
        """Get list of available printer configurations from the firmware folder."""
        available_printers = []
        
        try:
            if os.path.exists(self.firmware_path):
                for file in os.listdir(self.firmware_path):
                    if file.startswith("PRINTER_") and file.endswith(".cfg"):
                        printer_name = file[8:-4]  # Remove "PRINTER_" prefix and ".cfg" suffix
                        available_printers.append(printer_name)
                        
                logger.debug(f"Found {len(available_printers)} printer configurations")
            else:
                logger.warning(f"Firmware path not found: {self.firmware_path}")
                
        except Exception as e:
            logger.error(f"Error getting available printers: {e}")
            
        return sorted(available_printers)
    
    def get_printer_display_name(self, printer_name: str) -> str:
        """Convert printer name to display name by extracting from Klipper config."""
        # Try to get name from printer configuration variables
        config_file = os.path.join(self.firmware_path, f"PRINTER_{printer_name}.cfg")
        if os.path.exists(config_file):
            # Extract a reasonable display name from the printer name
            # Special handling for specific printer names
            if printer_name == "VOLTERRA_ALF":
                return "Volterra-ALF"
            
            # Convert DRAGON_400 -> Dragon 400, TWINDRAGON_600 -> Twin Dragon 600, etc.
            display_name = printer_name.replace("_", " ").title()
            if display_name.startswith("Twindragon"):
                display_name = display_name.replace("Twindragon", "Twin Dragon")
            return display_name
        
        # Fallback to simple conversion
        return printer_name.replace("_", " ").title()
    
    def get_printer_filename(self, printer_name: str) -> str:
        """Convert printer name back to filename format."""
        return f"PRINTER_{printer_name}.cfg"
    
    def get_firmware_files(self) -> List[str]:
        """Get list of all firmware configuration files."""
        firmware_files = []
        
        try:
            if os.path.exists(self.firmware_path):
                firmware_files = [f for f in os.listdir(self.firmware_path) if f.endswith('.cfg')]
                logger.debug(f"Found {len(firmware_files)} firmware files")
            else:
                logger.warning(f"Firmware path not found: {self.firmware_path}")
                
        except Exception as e:
            logger.error(f"Error getting firmware files: {e}")
            
        return firmware_files

    # ========================================================================
    # PRINTER.CFG PARSING AND MANAGEMENT
    # ========================================================================
    
    def get_current_printer_selection(self) -> Optional[str]:
        """Get the currently active printer configuration from printer.cfg."""
        try:
            if os.path.exists(self.printer_cfg_path):
                with open(self.printer_cfg_path, 'r') as f:
                    content = f.read()
                    
                # Look for active include statements
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('[include PRINTER_') and not line.startswith('#'):
                        match = re.search(r'PRINTER_(\w+)\.cfg', line)
                        if match:
                            return match.group(1)
                            
        except Exception as e:
            logger.error(f"Error getting current printer selection: {e}")
            
        return None

    # ========================================================================
    # PRINTER_VARIABLES PARSING
    # ========================================================================
    
    def parse_printer_variables_from_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse PRINTER_VARIABLES macro from a specific configuration file."""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                return None
                
            with open(file_path, 'r') as f:
                content = f.read()
                
            variables = {}
            in_printer_variables = False
            
            for line in content.split('\n'):
                line = line.strip()
                
                if line.startswith('[gcode_macro PRINTER_VARIABLES]'):
                    in_printer_variables = True
                    continue
                    
                if in_printer_variables:
                    if line.startswith('[') and not line.startswith('[gcode_macro'):
                        break
                        
                    if line.startswith('variable_'):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            var_name = parts[0].replace('variable_', '').strip()
                            var_value = parts[1].split('#')[0].strip()  # Remove comments
                            variables[var_name] = self._parse_variable_value(var_value)
                            
            return variables if variables else None
            
        except Exception as e:
            logger.error(f"Error parsing PRINTER_VARIABLES from {file_path}: {e}")
            return None
    
    def _parse_variable_value(self, value_str: str) -> Any:
        """Parse a variable value string into its appropriate Python type."""
        value_str = value_str.strip()
        
        # Handle string values (quoted)
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]
        
        # Handle numeric values first (before boolean check)
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Handle boolean values (only if not numeric)
        if value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        
        # Default to string if we can't parse it
        return value_str
    
    def get_printer_variables_from_active_config(self) -> Optional[Dict[str, Any]]:
        """Get PRINTER_VARIABLES from the currently active printer configuration."""
        current_printer = self.get_current_printer_selection()
        if current_printer:
            # First try the deployed Klipper config directory (where Klipper actually reads from)
            klipper_config_file = os.path.join(self.klipper_config_path, f"PRINTER_{current_printer}.cfg")
            if os.path.exists(klipper_config_file):
                logger.debug(f"Reading PRINTER_VARIABLES from deployed Klipper config: {klipper_config_file}")
                return self.parse_printer_variables_from_file(klipper_config_file)
            
            # Fallback to firmware directory if not deployed yet
            firmware_config_file = os.path.join(self.firmware_path, f"PRINTER_{current_printer}.cfg")
            if os.path.exists(firmware_config_file):
                logger.warning(f"Klipper config not found, falling back to firmware directory: {firmware_config_file}")
                return self.parse_printer_variables_from_file(firmware_config_file)
            
            logger.error(f"Could not find PRINTER_{current_printer}.cfg in either Klipper config or firmware directories")
        return None

    def get_printer_config_from_variables(self, printer_name: str) -> Dict[str, Any]:
        """Get printer configuration by parsing PRINTER_VARIABLES from the printer config file."""
        # First try the deployed Klipper config directory (where Klipper actually reads from)
        klipper_config_file = os.path.join(self.klipper_config_path, f"PRINTER_{printer_name}.cfg")
        firmware_config_file = os.path.join(self.firmware_path, f"PRINTER_{printer_name}.cfg")
        
        variables = None
        config_source = None
        
        # Try Klipper config directory first
        if os.path.exists(klipper_config_file):
            variables = self.parse_printer_variables_from_file(klipper_config_file)
            config_source = "deployed Klipper config"
        
        # Fallback to firmware directory
        if not variables and os.path.exists(firmware_config_file):
            variables = self.parse_printer_variables_from_file(firmware_config_file)
            config_source = "firmware directory"
        
        if not variables:
            logger.warning(f"No PRINTER_VARIABLES found for {printer_name}, using fallback config")
            return FALLBACK_CONFIG.copy()
        
        logger.debug(f"Loaded {printer_name} configuration from {config_source}")
        
        # Extract configuration from variables
        config = {
            'name': self.get_printer_display_name(printer_name),
            'bed_width': variables.get('bed_x_max', FALLBACK_CONFIG['bed_width']) - variables.get('bed_x_min', 0),
            'bed_depth': variables.get('bed_y_max', FALLBACK_CONFIG['bed_depth']) - variables.get('bed_y_min', 0),
            'bed_height': variables.get('bed_z_max', FALLBACK_CONFIG['bed_height']) - variables.get('bed_z_min', 0),
            'is_dual': bool(variables.get('is_dual_nozzle', 1)),
            'extruder_count': 2 if bool(variables.get('is_dual_nozzle', 1)) else 1,
            # Store raw variables for further use
            'variables': variables
        }
        
        logger.debug(f"Extracted config for {printer_name}: {config}")
        return config

    # ========================================================================
    # CONFIGURATION EXTRACTION AND TRANSFORMATION
    # ========================================================================
    
    def extract_printer_configuration(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Extract configuration from PRINTER_VARIABLES in the format expected by config.py."""
        if not variables:
            return {}
            
        config = {
            # Bed size information
            'bed_size': {
                'x_min': variables.get('bed_x_min', 0),
                'x_max': variables.get('bed_x_max', 200),
                'y_min': variables.get('bed_y_min', 0),
                'y_max': variables.get('bed_y_max', 200),
                'z_min': variables.get('bed_z_min', 0),
                'z_max': variables.get('bed_z_max', 200),
            },
            'is_dual_nozzle': bool(variables.get('is_dual_nozzle', 1)),
            'is_hybrid': bool(variables.get('is_hybrid', 0)),
            'has_heater_ring': bool(variables.get('has_heater_ring', 0)),
            'has_heated_chamber': bool(variables.get('has_heated_chamber', 0)),
            'has_spool_heater': bool(variables.get('has_spool_heater', 0)),
            'has_chamber_cooling': 'fan1' in variables,
            
            # Machine build size (compatible with config.py format)
            'machineBuildSize': {
                'X': variables.get('bed_x_max', 200) - variables.get('bed_x_min', 0),
                'Y': variables.get('bed_y_max', 200) - variables.get('bed_y_min', 0),
                'Z': variables.get('bed_z_max', 200) - variables.get('bed_z_min', 0),
            },
            
            # Calibration positions
            'calibrationPosition': {
                'X1': variables.get('bed_calibration_x1', 50),
                'Y1': variables.get('bed_calibration_y1', 50),
                'X2': variables.get('bed_calibration_x2', 150),
                'Y2': variables.get('bed_calibration_y2', 50),
                'X3': variables.get('bed_calibration_x3', 100),
                'Y3': variables.get('bed_calibration_y3', 150),
                'X4': variables.get('bed_calibration_x4', 100),
                'Y4': variables.get('bed_calibration_y4', 100),
            },
            
            # Tool positions
            'tool0PurgePosition': {
                'X': variables.get('tool0_pause_position_x', -30),
                'Y': variables.get('tool0_pause_position_y', -77),
            },
            'tool1PurgePosition': {
                'X': variables.get('tool1_pause_position_x', 655),
                'Y': variables.get('tool1_pause_position_y', -77),
            },
            
            # Other settings
            'ptfeTubeLength': variables.get('ptfe_tube_length', 1500),
            'IS_DUAL_NOZZLE': bool(variables.get('is_dual_nozzle', 1)),
            # Hybrid IDEX: T0 is a pellet auger, T1 is a filament extruder
            'IS_HYBRID': bool(variables.get('is_hybrid', 0)),
            'HAS_HEATER_RING': bool(variables.get('has_heater_ring', 0)),
            'HAS_HEATED_CHAMBER': bool(variables.get('has_heated_chamber', 0)),
            'HAS_SPOOL_HEATER': bool(variables.get('has_spool_heater', 0)),
        }
        
        # Calculate bed dimensions for backwards compatibility
        config['bed_width'] = config['machineBuildSize']['X']
        config['bed_depth'] = config['machineBuildSize']['Y']
        config['bed_height'] = config['machineBuildSize']['Z']
        
        return config
    
    def get_printer_config_from_klipper(self) -> Optional[Dict[str, Any]]:
        """Get complete printer configuration from active Klipper config."""
        variables = self.get_printer_variables_from_active_config()
        if variables:
            return self.extract_printer_configuration(variables)
        return None

    # ========================================================================
    # OCTOPRINT CONFIGURATION MANAGEMENT
    # ========================================================================
    
    def get_saved_extruder_mode(self) -> str:
        """Return the active Hybrid extruder mode from printer.cfg.

        The mode is whichever ``[include MODE_*.cfg]`` line is uncommented -
        the same mechanism ``get_current_printer_selection()`` uses for the
        SKU. Reading the file (rather than querying Klipper) means this works
        while Klipper is down or restarting, which is exactly when the
        OctoPrint configs are regenerated.

        Returns:
            'pellet' or 'filament' ('pellet' when no mode include is active,
            matching the firmware default and the pre-swap behaviour)
        """
        try:
            if not os.path.exists(self.printer_cfg_path):
                return 'pellet'
            with open(self.printer_cfg_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('#') or not stripped.startswith('[include MODE_'):
                        continue
                    match = re.search(r'MODE_(\w+)\.cfg', stripped)
                    if match:
                        mode = match.group(1).lower()
                        if mode in EXTRUDER_MODES:
                            return mode
        except Exception as e:
            logger.warning(f"Could not read extruder mode from printer.cfg: {e}")
        return 'pellet'

    # ------------------------------------------------------------------
    # Per-mode SAVE_CONFIG storage
    # ------------------------------------------------------------------

    def _mode_state_path(self, name: str) -> str:
        """Path of a stored SAVE_CONFIG fragment ('shared', 'pellet', ...)."""
        return os.path.join(MODE_STATE_DIR, f'saveconfig_{name}.cfg')

    @staticmethod
    def _parse_save_config_sections(block: str) -> List[tuple]:
        """Split a SAVE_CONFIG block into [(section_name, [lines]), ...].

        Operates on the raw ``#*#``-prefixed text. Header lines (everything
        before the first ``#*# [section]``) are dropped - they are re-added
        by _compose_save_config.
        """
        sections: List[tuple] = []
        current_name = None
        current_lines: List[str] = []
        for raw in block.split('\n'):
            stripped = raw.lstrip()
            if not stripped.startswith('#*#'):
                continue
            # Heal double-prefixed lines (#*##*# [probe]) left behind by
            # the old compose bug, so a corrupted block parses again.
            while stripped.startswith('#*#'):
                stripped = stripped[3:].lstrip()
            # Body keeps its original indentation relative to the '#*#'
            # prefix: multi-line values like bed_mesh `points =` need the
            # continuation rows to stay indented, or configparser rejects
            # the rebuilt block at Klipper startup.
            body = raw[raw.index('#*#') + 3:]
            body_clean = body.strip()
            if body_clean.startswith('[') and body_clean.endswith(']'):
                if current_name is not None:
                    sections.append((current_name, current_lines))
                current_name = body_clean[1:-1].strip()
                current_lines = []
            elif current_name is not None and body_clean:
                current_lines.append(body)
        if current_name is not None:
            sections.append((current_name, current_lines))
        return sections

    @classmethod
    def _render_sections(cls, sections: List[tuple]) -> str:
        """Render [(name, lines)] back to ``#*#``-prefixed text."""
        out: List[str] = []
        for name, lines in sections:
            out.append(f'#*# [{name}]')
            for line in lines:
                out.append(f'#*# {line}')
            out.append('#*#')
        return '\n'.join(out)

    @classmethod
    def _is_shared_section(cls, name: str) -> bool:
        """True for SAVE_CONFIG sections that belong to the machine, not the head.

        Inverted logic on purpose: anything not explicitly head-specific is
        shared, so a Klipper section nobody anticipated defaults to being
        preserved across modes rather than silently discarded.
        """
        head = name.split()[0].lower() if name else ''
        return head not in PER_MODE_SAVE_CONFIG_PREFIXES

    def split_save_config_block(self, block: str) -> tuple:
        """Split a SAVE_CONFIG block into (shared_text, per_mode_text)."""
        sections = self._parse_save_config_sections(block)
        shared = [s for s in sections if self._is_shared_section(s[0])]
        per_mode = [s for s in sections if not self._is_shared_section(s[0])]
        return self._render_sections(shared), self._render_sections(per_mode)

    def compose_save_config_block(self, shared_text: str, per_mode_text: str) -> str:
        """Rebuild a full SAVE_CONFIG block from its two halves.

        The header ends with a bare ``#*#`` line and no newline - the
        separator below is load-bearing. Without it the first body line
        concatenates into ``#*##*# [probe]``, which Klipper's save-config
        parser cannot apply, the seeded probe offset is lost, and Klipper
        halts on "Option 'z_offset' in section 'probe' must be specified".

        EVERY line of the body must carry the ``#*#`` prefix. Klipper's
        _find_autosave_data discards the WHOLE block the moment one line
        does not - it cannot tell a stray blank line from an operator
        editing the autosave region - and that takes [probe] z_offset with
        it, halting Klipper with the same message. A stored fragment
        written by an older build ends with a newline, and joining those
        with '\\n' put exactly such a bare blank line between the per-mode
        and shared halves (seen on .176: filament -> pellet left the
        machine unable to start). So filter blank lines out here rather
        than trusting the two inputs to be clean.
        """
        lines: List[str] = []
        for part in (per_mode_text, shared_text):
            if not part.strip():
                continue
            lines.extend(line for line in part.split('\n') if line.strip())
        if not lines:
            return ''
        body = '\n'.join(lines)
        return self.SAVE_CONFIG_HEADER + '\n' + body + '\n'

    def store_mode_calibration(self, mode: str) -> bool:
        """Split the live SAVE_CONFIG block and file it away for `mode`.

        Called BEFORE swapping the mode include, so the calibration the
        outgoing mode just had is preserved for when it comes back.
        """
        try:
            if not os.path.exists(self.printer_cfg_path):
                return False
            with open(self.printer_cfg_path, 'r', encoding='utf-8') as f:
                content = f.read()
            marker = content.find(self.SAVE_CONFIG_MARKER)
            if marker == -1:
                logger.info("No SAVE_CONFIG block to store")
                return True
            shared_text, per_mode_text = self.split_save_config_block(content[marker:])

            os.makedirs(MODE_STATE_DIR, exist_ok=True)
            with open(self._mode_state_path('shared'), 'w', encoding='utf-8') as f:
                f.write(shared_text)
            with open(self._mode_state_path(mode), 'w', encoding='utf-8') as f:
                f.write(per_mode_text)
            logger.info(
                f"Stored calibration for '{mode}' mode "
                f"({len(per_mode_text.splitlines())} lines) + shared bed data "
                f"({len(shared_text.splitlines())} lines)"
            )
            return True
        except Exception as e:
            logger.error(f"Error storing calibration for mode '{mode}': {e}")
            return False

    def load_mode_calibration(self, mode: str) -> str:
        """Return the SAVE_CONFIG block for `mode` (shared bed data + its own).

        Returns an empty string when nothing is stored yet - the caller then
        falls back to whatever the deployed printer.cfg already had, and
        _seed_probe_z_offset() still guarantees the machine can boot.
        """
        try:
            shared_text = ''
            per_mode_text = ''
            shared_path = self._mode_state_path('shared')
            mode_path = self._mode_state_path(mode)
            if os.path.exists(shared_path):
                with open(shared_path, 'r', encoding='utf-8') as f:
                    shared_text = f.read()
            if os.path.exists(mode_path):
                with open(mode_path, 'r', encoding='utf-8') as f:
                    per_mode_text = f.read()
            if not shared_text.strip() and not per_mode_text.strip():
                logger.info(f"No stored calibration for '{mode}' mode yet")
                return ''
            return self.compose_save_config_block(shared_text, per_mode_text)
        except Exception as e:
            logger.error(f"Error loading calibration for mode '{mode}': {e}")
            return ''

    def set_extruder_mode(self, mode: str) -> bool:
        """Switch the Hybrid machine between pellet and filament mode.

        Rewrites the ``[include MODE_*.cfg]`` selector in printer.cfg, files
        away the outgoing mode's calibration, restores the incoming mode's,
        and toggles ``[mcu E1]`` to match (the CAN toolhead is referenced
        only by filament mode, and Klipper errors on an unreferenced MCU).

        The caller is responsible for running PREPARE_EXTRUDER_MODE_SWITCH
        beforehand (home + park + heaters off + flush SAVE_CONFIG) and for
        restarting Klipper afterwards.

        Args:
            mode: 'pellet' or 'filament'

        Returns:
            True on success
        """
        if mode not in EXTRUDER_MODES:
            logger.error(f"Invalid extruder mode: {mode}")
            return False
        try:
            previous = self.get_saved_extruder_mode()
            if not os.path.exists(self.printer_cfg_path):
                logger.error("printer.cfg not found - cannot switch extruder mode")
                return False

            # The machine's CURRENT Z zero, read before anything is rewritten.
            # Used only as the fallback for a mode that has nothing stored -
            # see the note at _seed_probe_z_offset. Without it, the first
            # switch after [probe] became per-mode replaces one head's
            # calibrated value with the hardcoded seed, and which head that
            # is depends on the mode the machine happened to be in.
            live_probe_z = self._read_live_probe_z_offset()

            # 1. File away the calibration belonging to the mode we are
            #    leaving, BEFORE the block gets rewritten.
            self.store_mode_calibration(previous)

            with open(self.printer_cfg_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 2. Flip the include lines.
            out_lines: List[str] = []
            seen = {m: False for m in EXTRUDER_MODES}
            for line in content.split('\n'):
                bare = line.lstrip().lstrip('#').lstrip()
                match = re.match(r'\[include MODE_(\w+)\.cfg\]', bare)
                if match:
                    this_mode = match.group(1).lower()
                    if this_mode in EXTRUDER_MODES:
                        seen[this_mode] = True
                        out_lines.append(bare if this_mode == mode else '#' + bare)
                        continue
                out_lines.append(line)
            content = '\n'.join(out_lines)

            # A machine whose printer.cfg predates the config-swap model has
            # neither include line - add the block after the SKU selector.
            if not any(seen.values()):
                anchor = '[include PRINTER_PENROSE_600_HYBRID.cfg]'
                insert = (
                    '\n########################################\n'
                    '# Select Extruder Mode - HYBRID IDEX ONLY\n'
                    '########################################\n'
                    + ''.join(
                        f"{'' if m == mode else '#'}[include {MODE_CFG_FILES[m]}]\n"
                        for m in EXTRUDER_MODES
                    )
                    + '########################################\n'
                )
                for candidate in (anchor, '#' + anchor):
                    if candidate in content:
                        content = content.replace(candidate, candidate + insert, 1)
                        break
                else:
                    content = content.rstrip('\n') + '\n' + insert
                logger.info("Inserted MODE_* include block into printer.cfg")

            # 3. Swap in the incoming mode's calibration.
            marker = content.find(self.SAVE_CONFIG_MARKER)
            restored = self.load_mode_calibration(mode)
            if restored:
                content = (content[:marker].rstrip('\n') + '\n\n' + restored
                           if marker != -1 else
                           content.rstrip('\n') + '\n\n' + restored)
                logger.info(f"Restored stored calibration for '{mode}' mode")
            elif marker != -1 and previous != mode:
                # Nothing stored for the incoming mode yet (first switch).
                # Keep only the shared bed data - carrying the OTHER mode's
                # PID and Z zero across would be worse than having none.
                shared_text, _ = self.split_save_config_block(content[marker:])
                rebuilt = self.compose_save_config_block(shared_text, '')
                content = content[:marker].rstrip('\n') + ('\n\n' + rebuilt if rebuilt else '\n')
                logger.info(
                    f"No stored calibration for '{mode}' mode - kept shared bed "
                    "data only; recalibrate PID and Z offset for this head"
                )

            # 4. The CAN toolhead is referenced by filament mode only.
            content = self._sync_toolhead_mcu_for_mode(content, mode)

            # 5. Klipper refuses to start without [probe] z_offset.
            content = self._seed_probe_z_offset(content, seed=live_probe_z)

            with open(self.printer_cfg_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Extruder mode switched: {previous} -> {mode}")
            return True
        except Exception as e:
            logger.error(f"Error switching extruder mode to '{mode}': {e}")
            return False

    def _ensure_mode_include(self, content: str, selected_printer: str) -> str:
        """Guarantee exactly one MODE_*.cfg include is active on a hybrid SKU.

        Non-hybrid SKUs are left untouched: they never include
        BASE_PENROSE_HYBRID.cfg, so a stray commented mode line is inert.

        Args:
            content: the printer.cfg text about to be written
            selected_printer: SKU name being deployed

        Returns:
            content with the correct mode include uncommented (and
            [mcu E1] set to match)
        """
        if 'HYBRID' not in (selected_printer or '').upper():
            return content
        try:
            # Preserve the mode the machine is already in; a machine being
            # migrated for the first time has none, so start in pellet.
            mode = self.get_saved_extruder_mode()

            out_lines: List[str] = []
            found = False
            for line in content.split('\n'):
                bare = line.lstrip().lstrip('#').lstrip()
                match = re.match(r'\[include MODE_(\w+)\.cfg\]', bare)
                if match and match.group(1).lower() in EXTRUDER_MODES:
                    this_mode = match.group(1).lower()
                    found = True
                    out_lines.append(bare if this_mode == mode else '#' + bare)
                    continue
                out_lines.append(line)
            content = '\n'.join(out_lines)

            if not found:
                # Template predates the mode selector - append the block
                block = (
                    '\n########################################\n'
                    '# Select Extruder Mode - HYBRID ONLY\n'
                    '########################################\n'
                    + ''.join(
                        f"{'' if m == mode else '#'}[include {MODE_CFG_FILES[m]}]\n"
                        for m in EXTRUDER_MODES
                    )
                    + '########################################\n'
                )
                content = content.rstrip('\n') + '\n' + block
                logger.info("Added MODE_* include block to printer.cfg")

            # The CAN toolhead is referenced by filament mode only
            content = self._sync_toolhead_mcu_for_mode(content, mode)
            logger.info(f"Hybrid SKU deployed in '{mode}' extruder mode")
            return content
        except Exception as e:
            logger.error(f"Error ensuring mode include: {e}")
            return content

    def _sync_toolhead_mcu_for_mode(self, content: str, mode: str) -> str:
        """Comment/uncomment ``[mcu E1]`` for the given extruder mode.

        Filament mode drives the TD-01 over CAN and needs it; pellet mode
        references nothing on that MCU, and Klipper errors on an MCU no
        section uses. Reuses the printer-level toggler by passing a name it
        reads as hybrid-or-not.
        """
        return self._sync_toolhead_mcu(content, 'HYBRID' if mode == 'filament' else 'PELLET_MODE')

    @staticmethod
    def get_mode_profile_name(base_name: str, mode: str) -> str:
        """Name the OctoPrint printer profile after the active extruder mode.

        The web UI shows this in its printer selector, so it is how a
        remote operator can tell which head the machine will print with.

        Args:
            base_name: The SKU display name (e.g. "Penrose 600 Hybrid")
            mode: 'pellet' or 'filament'
        """
        suffix = 'Filament' if mode == 'filament' else 'Pellet'
        # Strip any previously applied suffix so repeated switches do not
        # accumulate "(Pellet) (Filament)"
        cleaned = re.sub(r'\s*\((?:Pellet|Filament)\)\s*$', '', base_name)
        return f"{cleaned} ({suffix})"

    def get_temperature_profiles_for_mode(self, mode: str) -> List[Dict[str, Any]]:
        """Return the OctoPrint temperature presets for a Hybrid extruder mode.

        The machine presents as a single-extruder printer in either mode, so
        the web UI should only offer the presets that make sense for the head
        that is actually printing - pellet temperatures on a filament hotend
        (up to 300 C) would be a real hazard.

        Args:
            mode: 'pellet' or 'filament'

        Returns:
            List of OctoPrint temperature profile dicts
        """
        if mode == 'filament':
            return [dict(preset) for preset in FILAMENT_TEMP_PRESETS]
        # Pellet presets are the template's own (pellet machine is the base)
        try:
            source_config = os.path.join(self.config_path, 'config.yaml')
            with open(source_config, 'r') as f:
                template = _yaml_safe_load(f) or {}
            profiles = (template.get('temperature') or {}).get('profiles') or []
            return [dict(p) for p in profiles if isinstance(p, dict)]
        except Exception as e:
            logger.error(f"Could not read pellet temperature presets: {e}")
            return []

    def update_octoprint_config(self, printer_name: str) -> bool:
        """Update OctoPrint config.yaml with printer-specific settings."""
        try:
            source_config = os.path.join(self.config_path, 'config.yaml')
            dest_config = os.path.join(self.octoprint_config_path, 'config.yaml')
            
            if not os.path.exists(source_config):
                logger.error(f"Source config not found: {source_config}")
                return False
                
            # Load the template config
            with open(source_config, 'r') as f:
                config_data = _yaml_safe_load(f)
                
            # Update appearance name with current printer
            if 'appearance' not in config_data:
                config_data['appearance'] = {}

            config_data['appearance']['name'] = self.get_printer_display_name(printer_name)

            # Hybrid IDEX (pellet T0 + filament T1): the machine presents as a
            # single-extruder printer in whichever extruder mode is active, so
            # the OctoPrint web UI gets only that mode's temperature presets.
            # (A merged list would offer 300 C pellet presets while a filament
            # hotend is the printing head.) Runtime mode switches push the
            # other set live over the REST API - see
            # MainController.apply_extruder_mode_to_octoprint.
            printer_config = self.get_printer_config_from_variables(printer_name)
            if bool(printer_config.get('variables', {}).get('is_hybrid', 0)):
                mode = self.get_saved_extruder_mode()
                temp_section = config_data.setdefault('temperature', {})
                temp_section['profiles'] = self.get_temperature_profiles_for_mode(mode)
                logger.info(f"Seeded OctoPrint temperature presets for '{mode}' mode")

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_config), exist_ok=True)
            
            # Write updated config
            with open(dest_config, 'w') as f:
                _yaml_safe_dump(config_data, f, default_flow_style=False)
                
            logger.info(f"Updated OctoPrint config with printer: {printer_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating OctoPrint config: {e}")
            return False
    
    def update_octoprint_printer_profile(self, printer_name: str) -> bool:
        """Update OctoPrint printer profile with printer-specific settings."""
        try:
            source_profile = os.path.join(self.config_path, '_default.profile')
            dest_profile = os.path.join(self.octoprint_config_path, 'printerProfiles', '_default.profile')
            
            if not os.path.exists(source_profile):
                logger.error(f"Source profile not found: {source_profile}")
                return False
                
            # Load the template profile
            with open(source_profile, 'r') as f:
                profile_data = _yaml_safe_load(f)
                
            # Get printer configuration from Klipper variables
            printer_config = self.get_printer_config_from_variables(printer_name)

            # If the variables could not be parsed (deploy race while the
            # PRINTER_*.cfg is being copied, truncated file, ...) the
            # fallback config is the generic 200x200x200. Writing THAT into
            # the profile makes OctoPrint's model-size check reject every
            # real print ("Object exceeds print volume"). Keep the
            # template's own volume instead - it is SKU-correct.
            if not printer_config.get('variables'):
                logger.warning(
                    f"PRINTER_VARIABLES unavailable for {printer_name} - "
                    "keeping template volume in the OctoPrint profile")
                printer_config = dict(printer_config)
                printer_config['bed_width'] = float(profile_data['volume']['width'])
                printer_config['bed_depth'] = float(profile_data['volume']['depth'])
                printer_config['bed_height'] = float(profile_data['volume']['height'])

            # Update profile with dynamic configuration
            profile_data['name'] = printer_config['name']
            # Hybrid: since the config-swap model, Klipper genuinely has one
            # [extruder] in either mode, so variable_is_dual_nozzle is 0 and
            # this resolves to 1. That is now honest - OctoPrint's single
            # Tool control maps to the only extruder that exists.
            #
            # (Under the old runtime-switch model this had to stay 2: a
            # 1-extruder profile emitted T0, which in filament mode heated
            # the *pellet* nozzle. That hazard is gone with the swap.)
            profile_data['extruder']['count'] = printer_config['extruder_count']
            profile_data['volume']['width'] = float(printer_config['bed_width'])
            profile_data['volume']['depth'] = float(printer_config['bed_depth'])
            profile_data['volume']['height'] = float(printer_config['bed_height'])
            
            # Update offsets for dual extruder
            if printer_config['extruder_count'] == 2:
                profile_data['extruder']['offsets'] = [
                    [0.0, 0.0],
                    [0.0, 0.0]
                ]
            else:
                profile_data['extruder']['offsets'] = [
                    [0.0, 0.0]
                ]

            # Hybrid IDEX: name the profile after the active extruder mode so
            # a web-UI operator can see which head the machine will print with
            if bool(printer_config.get('variables', {}).get('is_hybrid', 0)):
                mode = self.get_saved_extruder_mode()
                profile_data['name'] = self.get_mode_profile_name(printer_config['name'], mode)

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_profile), exist_ok=True)
            
            # Write updated profile
            with open(dest_profile, 'w') as f:
                _yaml_safe_dump(profile_data, f, default_flow_style=False)
                
            logger.info(f"Updated OctoPrint printer profile for: {printer_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating OctoPrint printer profile: {e}")
            return False
    
    def restore_octoprint_configs(self, printer_name: str) -> bool:
        """Restore all OctoPrint configuration files for the selected printer."""
        try:
            success = True
            
            # Copy basic config files
            config_files = [
                ('users.yaml', 'users.yaml'),
                ('dhcpcd.conf', '/etc/dhcpcd.conf')
            ]
            
            for source_file, dest_path in config_files:
                source = os.path.join(self.config_path, source_file)
                if os.path.exists(source):
                    try:
                        if dest_path.startswith('/etc/'):
                            # System files need sudo
                            os.system(f'sudo cp -f "{source}" "{dest_path}"')
                        else:
                            # OctoPrint files
                            dest = os.path.join(self.octoprint_config_path, dest_path)
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            shutil.copy2(source, dest)
                        logger.debug(f"Copied {source_file} to {dest_path}")
                    except Exception as e:
                        logger.error(f"Error copying {source_file}: {e}")
                        success = False
                        
            # Update printer-specific configs
            if not self.update_octoprint_config(printer_name):
                success = False
                
            if not self.update_octoprint_printer_profile(printer_name):
                success = False
                
            # Clean up old files and create default gcode scripts
            try:
                os.system('sudo rm -rf /home/pi/.octoprint/scripts/gcode')
                os.system('sudo rm -rf /home/pi/.octoprint/print_restore.json')
                
                # Create gcode scripts directory
                gcode_scripts_dir = '/home/pi/.octoprint/scripts/gcode'
                os.makedirs(gcode_scripts_dir, exist_ok=True)
                # Set proper ownership for the directory
                os.system(f'sudo chown -R pi:pi "{os.path.dirname(gcode_scripts_dir)}"')
                
                # Create default gcode script files to override existing ones
                # Check if printer is dual nozzle to include T1 cooldown commands
                printer_config = self.get_printer_config_from_variables(printer_name)
                is_dual = printer_config.get('is_dual', True)
                is_hybrid = bool(printer_config.get('variables', {}).get('is_hybrid', 0))

                if is_hybrid:
                    # Hybrid is a SINGLE-extruder machine in either mode
                    # (the mode is a config file), so there is no T1 to cool
                    # and no tool to activate. What DOES differ is the heater
                    # count: pellet mode has the nozzle AND the H0 barrel
                    # heater, filament mode has only the nozzle. Emitting
                    # M104 H0 in filament mode would error, and omitting it
                    # in pellet mode would leave the barrel cooking after
                    # every print - so generate the right one per mode.
                    mode = self.get_saved_extruder_mode()
                    cooldown_lines = [
                        'G28  ; Home all axes',
                        'M107  ; Turn off part cooling fan',
                        'M104 S0  ; Cool down nozzle',
                    ]
                    if mode == 'pellet':
                        cooldown_lines.append('M104 H0 S0  ; Cool down pellet barrel heater')
                    cooldown_lines += [
                        'M140 S0  ; Cool down bed',
                        'M84  ; Disable motors',
                    ]
                    after_print_cooldown = '\n'.join(cooldown_lines)

                    # PELLET_PREPRINT_CHECK only exists in pellet mode - the
                    # pellet feeder config is not included in filament mode.
                    before_lines = []
                    if mode == 'pellet':
                        before_lines.append(
                            'PELLET_PREPRINT_CHECK  ; Refill hopper if empty')
                    before_print_started = '\n'.join(before_lines)
                    # No M514 door macros on the hybrid - the firmware has
                    # none, so the old scripts spammed "Unknown command".
                    resume_script = 'RESUME'
                    pause_script = 'PAUSE'
                    logger.info(f"Generated OctoPrint gcode scripts for '{mode}' mode")
                else:
                    if is_dual:
                        after_print_cooldown = 'G28  ; Home all axes\nM107  ; Turn off part cooling fan\nM104 T0 S0  ; Cool down tool0 nozzle\nM104 T1 S0  ; Cool down tool1 nozzle\nM140 S0  ; Cool down bed\nM84  ; Disable motors\nM514 S0  ; Close door/chamber'
                    else:
                        after_print_cooldown = 'G28  ; Home all axes\nM107  ; Turn off part cooling fan\nM104 T0 S0  ; Cool down tool0 nozzle\nM140 S0  ; Cool down bed\nM84  ; Disable motors\nM514 S0  ; Close door/chamber'
                    before_print_started = 'M514 S1  ; Open door/chamber on print start'
                    resume_script = 'RESUME\nM514 S1  ; Resume print and open door/chamber'
                    pause_script = 'PAUSE\nM514 S0  ; Pause print and close door/chamber'

                default_scripts = {
                    'beforePrintStarted': before_print_started,
                    'beforePrintResumed': resume_script,
                    'afterPrintPaused': pause_script,
                    'afterPrintDone': after_print_cooldown,
                    'afterPrintCancelled': after_print_cooldown
                }
                
                for script_name, script_content in default_scripts.items():
                    script_path = os.path.join(gcode_scripts_dir, script_name)
                    try:
                        with open(script_path, 'w') as f:
                            f.write(script_content)
                        # Set proper ownership for the script file
                        os.system(f'sudo chown pi:pi "{script_path}"')
                        logger.debug(f"Created default gcode script: {script_name}")
                    except Exception as e:
                        logger.error(f"Error creating gcode script {script_name}: {e}")
                        success = False
                        
            except Exception as e:
                logger.warning(f"Error cleaning up old files and creating gcode scripts: {e}")
                success = False
                
            return success
            
        except Exception as e:
            logger.error(f"Error restoring OctoPrint configs: {e}")
            return False

    # ========================================================================
    # FILE DEPLOYMENT AND MANAGEMENT
    # ========================================================================

    # Fleet-typical inductive probe trigger offset, used only to SEED a
    # machine whose SAVE_CONFIG block has no [probe] z_offset entry (e.g.
    # its previous config had no [probe] section at all). Without the
    # entry Klipper refuses to start: "Option 'z_offset' in section
    # 'probe' must be specified". The seed makes the machine bootable;
    # the Z Probe Offset wizard overwrites it with the calibrated value.
    #
    # Deliberately NOT shipped in the BASE_*.cfg [probe] sections: a value
    # in an included file silently overrides the SAVE_CONFIG calibration
    # at startup (Klipper strips autosave duplicates in favour of the
    # regular config) and makes the wizard's SAVE_CONFIG fail with
    # "conflicts with included value".
    PROBE_Z_OFFSET_SEED = "-0.575"
    SAVE_CONFIG_MARKER = "#*# <---------------------- SAVE_CONFIG ---------------------->"
    SAVE_CONFIG_HEADER = (
        "#*# <---------------------- SAVE_CONFIG ---------------------->\n"
        "#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.\n"
        "#*#"
    )

    def _read_live_probe_z_offset(self) -> Optional[str]:
        """The [probe] z_offset currently in the deployed printer.cfg, if any."""
        try:
            with open(self.printer_cfg_path, 'r', encoding='utf-8') as f:
                content = f.read()
            marker_pos = content.find(self.SAVE_CONFIG_MARKER)
            if marker_pos == -1:
                return None
            in_probe = False
            for line in content[marker_pos:].split('\n'):
                stripped = line.strip()
                if not stripped.startswith('#*#'):
                    continue
                # Loop, so a block still carrying the old welded
                # '#*##*#' seam is read rather than skipped over.
                while stripped.startswith('#*#'):
                    stripped = stripped[3:].strip()
                if stripped.startswith('['):
                    in_probe = (stripped == '[probe]')
                elif in_probe and stripped.startswith('z_offset'):
                    return stripped.split('=', 1)[1].strip()
            return None
        except Exception as e:
            logger.error(f"Error reading live probe z_offset: {e}")
            return None

    def _seed_probe_z_offset(self, content: str, seed: str = None) -> str:
        """Ensure the SAVE_CONFIG block contains a [probe] z_offset entry.

        Handles three machine states:
        - SAVE_CONFIG block present with [probe] z_offset -> unchanged
        - SAVE_CONFIG block present without it -> entry inserted after the header
        - no SAVE_CONFIG block at all -> a minimal block is appended

        Args:
            content: the printer.cfg text
            seed: value to insert when there is none. Defaults to
                PROBE_Z_OFFSET_SEED; a mode switch passes the machine's live
                value so a calibrated Z zero is carried across rather than
                replaced by the hardcoded default.
        """
        seed = seed or self.PROBE_Z_OFFSET_SEED
        try:
            marker_pos = content.find(self.SAVE_CONFIG_MARKER)
            if marker_pos == -1:
                # No SAVE_CONFIG block at all (e.g. preserved MCU section
                # truncated the template tail) - append a minimal one
                content = (content.rstrip('\n') + "\n\n" + self.SAVE_CONFIG_HEADER +
                           "\n#*# [probe]\n#*# z_offset = " + seed + "\n")
                logger.info("Seeded new SAVE_CONFIG block with [probe] z_offset")
                return content

            # Scan the existing block for a [probe] section with z_offset
            tail = content[marker_pos:]
            in_probe = False
            has_z_offset = False
            for line in tail.split('\n'):
                stripped = line.strip()
                while stripped.startswith('#*#'):
                    stripped = stripped[3:].strip()
                if stripped.startswith('['):
                    in_probe = (stripped == '[probe]')
                elif in_probe and stripped.startswith('z_offset'):
                    has_z_offset = True
                    break
            if has_z_offset:
                return content

            # Insert right after the block header (marker line, the
            # "DO NOT EDIT" line if present, and any bare '#*#' spacer)
            lines = tail.split('\n')
            insert_at = 1
            if insert_at < len(lines) and 'DO NOT EDIT' in lines[insert_at]:
                insert_at += 1
            if insert_at < len(lines) and lines[insert_at].strip() == '#*#':
                insert_at += 1
            seed_lines = ['#*# [probe]', '#*# z_offset = ' + seed, '#*#']
            lines[insert_at:insert_at] = seed_lines
            logger.info("Seeded [probe] z_offset into existing SAVE_CONFIG block")
            return content[:marker_pos] + '\n'.join(lines)
        except Exception as e:
            logger.error(f"Error seeding probe z_offset: {e}")
            return content

    def update_printer_cfg(self, source_path: str, dest_path: str, selected_printer: str, preserve_mcu: bool = True) -> bool:
        """Update printer.cfg with new printer selection while preserving MCU config and SAVE_CONFIG sections."""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}")
                return False
                
            # Read the template
            with open(source_path, 'r') as f:
                template_content = f.read()
                
            # If preserve_mcu is True and destination file exists, extract MCU config from current file
            existing_mcu_section = ""
            existing_save_config_section = ""
            
            if preserve_mcu and os.path.exists(dest_path):
                logger.info(f"Attempting to preserve MCU config from existing file: {dest_path}")
                try:
                    with open(dest_path, 'r') as f:
                        existing_content = f.read()
                    
                    # Extract MCU Config section.
                    #
                    # Match only the FIRST TWO lines of the header. The
                    # three-line form used to be required, which broke the
                    # moment a comment was added between "# MCU Config" and
                    # the closing hash-line: the marker missed, nothing was
                    # preserved, and the template's placeholder serial: /
                    # canbus_uuid was written over the machine's real one -
                    # leaving it unable to reach its MCU at all.
                    # (Carried over from the Hybrid-Penrose-600 branch.)
                    mcu_start_marker = "########################################\n# MCU Config"
                    save_config_marker = "#*# <---------------------- SAVE_CONFIG ---------------------->"

                    logger.debug(f"Looking for MCU marker in existing file...")
                    logger.debug(f"MCU marker found: {mcu_start_marker in existing_content}")
                    logger.debug(f"SAVE_CONFIG marker found: {save_config_marker in existing_content}")

                    save_config_start = existing_content.find(save_config_marker)
                    mcu_start = existing_content.find(mcu_start_marker)

                    if mcu_start == -1:
                        # Fallback for deployments predating the header: find
                        # [mcu] itself, and take the comment block immediately
                        # above it if there is one close by.
                        mcu_direct = existing_content.find('\n[mcu]\n')
                        if mcu_direct != -1:
                            last_hash = existing_content[:mcu_direct].rfind(
                                '########################################')
                            if last_hash != -1 and (mcu_direct - last_hash) < 600:
                                mcu_start = last_hash
                            else:
                                mcu_start = mcu_direct + 1  # start at [mcu] itself
                            logger.warning(
                                "MCU Config header not found; falling back to the "
                                f"[mcu] section at position {mcu_start}")
                        else:
                            logger.warning("Could not locate an [mcu] section in the existing file")

                    if mcu_start != -1:
                        logger.debug(f"MCU section starts at {mcu_start}")
                        if save_config_start != -1 and mcu_start < save_config_start:
                            # MCU Config marker up to just before SAVE_CONFIG
                            existing_mcu_section = existing_content[mcu_start:save_config_start].rstrip()
                            logger.info(f"Preserved MCU config section ({len(existing_mcu_section)} chars)")
                        else:
                            existing_mcu_section = existing_content[mcu_start:].rstrip()
                            if save_config_start != -1:
                                logger.warning("SAVE_CONFIG found before MCU marker, extracting MCU to end of file")
                            else:
                                logger.info(f"No SAVE_CONFIG found, preserved MCU config to end ({len(existing_mcu_section)} chars)")

                    # SAVE_CONFIG is preserved INDEPENDENTLY of the MCU block.
                    # It used to be extracted inside the MCU branch above, so a
                    # machine whose header did not match lost its probe
                    # z_offset, bed mesh and PID along with its MCU serial.
                    if save_config_start != -1:
                        existing_save_config_section = existing_content[save_config_start:].rstrip()
                        logger.info(f"Preserved SAVE_CONFIG section ({len(existing_save_config_section)} chars)")
                    
                except Exception as e:
                    logger.warning(f"Could not extract existing MCU config and SAVE_CONFIG: {e}")
                    # Continue without preserving sections
                    existing_mcu_section = ""
                    existing_save_config_section = ""

            # Enable the CAN toolhead MCU only for Hybrid IDEX printers.
            # Done on the *preserved* section so the operator's canbus_uuid
            # survives every printer switch and firmware update.
            if existing_mcu_section:
                existing_mcu_section = self._sync_toolhead_mcu(existing_mcu_section, selected_printer)
            else:
                if not preserve_mcu:
                    logger.info("MCU and SAVE_CONFIG preservation disabled")
                else:
                    logger.info(f"Destination file does not exist: {dest_path}")
            
            # Update the include statement to point to the selected printer
            template_lines = template_content.split('\n')
            updated_lines = []
            
            # Process template content, updating printer includes
            for line in template_lines:
                if 'PRINTER_' in line and '.cfg' in line:
                    if line.strip().startswith('#'):
                        # This is a commented printer config
                        if f'PRINTER_{selected_printer}.cfg' in line:
                            # Uncomment this line and remove any leading spaces after #
                            uncommented = line.replace('#', '', 1).lstrip()
                            updated_lines.append(uncommented)
                        else:
                            # Keep other printer configs commented
                            updated_lines.append(line)
                    else:
                        # This is an active include, comment it out unless it's our target
                        if f'PRINTER_{selected_printer}.cfg' in line:
                            updated_lines.append(line)
                        else:
                            updated_lines.append('#' + line)
                else:
                    updated_lines.append(line)
            
            # Reconstruct the final content
            final_content = '\n'.join(updated_lines)
            
            # If we have preserved sections, replace the template sections with the existing ones
            if existing_mcu_section or existing_save_config_section:
                logger.info("Replacing template sections with preserved ones")
                # Two-line marker, matching the extraction above.
                mcu_start_marker = "########################################\n# MCU Config"
                save_config_marker = "#*# <---------------------- SAVE_CONFIG ---------------------->"
                
                if existing_mcu_section and mcu_start_marker in final_content:
                    mcu_start = final_content.find(mcu_start_marker)
                    logger.debug(f"MCU marker position in template: {mcu_start}")
                    
                    if save_config_marker in final_content:
                        # Template has both MCU and SAVE_CONFIG sections
                        # Replace everything from MCU marker to end with preserved sections
                        final_content = final_content[:mcu_start] + existing_mcu_section
                        
                        # Add preserved SAVE_CONFIG if we have it
                        if existing_save_config_section:
                            final_content += "\n\n" + existing_save_config_section
                        logger.info("Replaced template MCU and SAVE_CONFIG with preserved sections")
                    else:
                        # Template has MCU but no SAVE_CONFIG
                        # Replace from MCU marker to end with preserved MCU
                        final_content = final_content[:mcu_start] + existing_mcu_section
                        
                        # Append preserved SAVE_CONFIG if we have it
                        if existing_save_config_section:
                            final_content += "\n\n" + existing_save_config_section
                        logger.info("Replaced template MCU and appended preserved SAVE_CONFIG")
                        
                elif existing_save_config_section:
                    # We only have SAVE_CONFIG to preserve (no MCU section to preserve)
                    if save_config_marker in final_content:
                        # Replace template SAVE_CONFIG with preserved one
                        save_config_start = final_content.find(save_config_marker)
                        final_content = final_content[:save_config_start] + existing_save_config_section
                        logger.info("Replaced template SAVE_CONFIG with preserved section")
                    else:
                        # No SAVE_CONFIG in template, append preserved one
                        final_content += "\n\n" + existing_save_config_section
                        logger.info("Appended preserved SAVE_CONFIG section")
            
            # If we only have SAVE_CONFIG section preserved and it's not already included, append it
            elif existing_save_config_section and "#*# <---------------------- SAVE_CONFIG ---------------------->" not in final_content:
                final_content += "\n\n" + existing_save_config_section
                logger.info("Appended preserved SAVE_CONFIG section")
                    
            # No preserved MCU block (first deployment): toggle the CAN
            # toolhead MCU straight on the template content instead.
            if not existing_mcu_section:
                final_content = self._sync_toolhead_mcu(final_content, selected_printer)

            # HYBRID ONLY: guarantee exactly one MODE_*.cfg is active.
            #
            # The shipped printer.cfg has BOTH mode includes commented out,
            # because they are meaningless on every other SKU. On a hybrid
            # that would leave Klipper with no [stepper_x], no [extruder] and
            # no EXTRUDER_MODE_VARIABLES - it would not start at all. So on
            # selecting the hybrid SKU, carry the machine's existing mode
            # over, or default to pellet on a first deployment (pellet is the
            # mode that can bed level, so it is the right place to start).
            final_content = self._ensure_mode_include(final_content, selected_printer)

            # Klipper refuses to start without [probe] z_offset; make sure
            # the SAVE_CONFIG block provides one (no-op when already there)
            final_content = self._seed_probe_z_offset(final_content)

            # Write the updated content
            with open(dest_path, 'w') as f:
                f.write(final_content)
                
            # Log success with details about what was preserved
            preserved_sections = []
            if existing_mcu_section:
                preserved_sections.append("MCU configuration")
            if existing_save_config_section:
                preserved_sections.append("SAVE_CONFIG calibration data")
                
            if preserved_sections:
                logger.info(f"Updated printer.cfg for {selected_printer} while preserving: {', '.join(preserved_sections)}")
            else:
                logger.info(f"Updated printer.cfg for {selected_printer}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating printer.cfg: {e}")
            return False

    # CAN toolhead MCU block, inserted into printer.cfg on machines whose
    # deployed config predates the Hybrid IDEX variant.
    TOOLHEAD_MCU_TEMPLATE = (
        "\n# CAN toolhead (E1) - used only by the Hybrid IDEX filament head (T1).\n"
        "# The Printer Setup UI auto-comments/uncomments this block when you\n"
        "# switch printer variants. Fill the UUID in once and it is preserved\n"
        "# across all future printer changes and firmware updates.\n"
        "#   ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0\n"
        "#[mcu E1]\n"
        "#canbus_uuid: XXXXXXXXXXXX\n"
    )

    def _sync_toolhead_mcu(self, mcu_section: str, selected_printer: str) -> str:
        """Enable ``[mcu E1]`` for Hybrid IDEX printers, disable it otherwise.

        The filament extruder on the Hybrid IDEX lives on a CAN toolhead board
        aliased ``E1``. Klipper errors out on an MCU that no config section
        references, so the block must be commented for every non-hybrid
        variant. The operator's ``canbus_uuid`` value is never rewritten, only
        commented/uncommented, so it survives printer switches and firmware
        updates.

        The mainboard's own ``[mcu]`` section is never touched.

        Adds the commented block if the section does not have one yet (machines
        whose deployed printer.cfg predates this variant).
        """
        want_uncommented = 'HYBRID' in (selected_printer or '').upper()

        if '[mcu E1]' not in mcu_section:
            if not want_uncommented:
                # Nothing to toggle and nothing to enable - leave as-is.
                return mcu_section
            mcu_section = mcu_section.rstrip() + '\n' + self.TOOLHEAD_MCU_TEMPLATE
            logger.info("Inserted [mcu E1] block into MCU config for Hybrid IDEX")

        out_lines: List[str] = []
        in_block = False
        for line in mcu_section.split('\n'):
            bare = line.lstrip().lstrip('#').lstrip()
            if bare.startswith('[mcu E1]'):
                in_block = True
                out_lines.append(bare if want_uncommented else '#' + bare)
                continue
            if in_block:
                # End of block: blank line or the start of another section
                if bare == '' or (bare.startswith('[') and not bare.startswith('[mcu E1]')):
                    in_block = False
                    out_lines.append(line)
                    continue
                # Only toggle config directives (``key: value``); leave any
                # explanatory comments the operator added untouched.
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*:', bare):
                    out_lines.append(line)
                    continue
                out_lines.append(bare if want_uncommented else '#' + bare)
            else:
                out_lines.append(line)

        action = 'enabled' if want_uncommented else 'disabled'
        logger.info(f"CAN toolhead MCU {action} for printer '{selected_printer}'")
        return '\n'.join(out_lines)

    def copy_firmware_files(self, selected_printer: str) -> bool:
        """Copy all firmware files and update printer selection."""
        try:
            if not os.path.exists(self.firmware_path):
                logger.error(f"Firmware path not found: {self.firmware_path}")
                return False
                
            # Copy all .cfg files to Klipper config directory (excluding printer.cfg which needs special handling)
            firmware_files = self.get_firmware_files()
            for file in firmware_files:
                if file == 'printer.cfg':
                    # Skip printer.cfg - it will be handled separately with MCU preservation
                    logger.debug(f"Skipping {file} - will be handled with MCU preservation")
                    continue
                    
                source = os.path.join(self.firmware_path, file)
                dest = os.path.join(self.klipper_config_path, file)
                try:
                    shutil.copy2(source, dest)
                    logger.debug(f"Copied {file} to Klipper config")
                except Exception as e:
                    logger.error(f"Error copying {file}: {e}")
                    return False
                    
            # Update printer.cfg with the selected printer (with MCU preservation)
            source_printer_cfg = os.path.join(self.firmware_path, 'printer.cfg')
            dest_printer_cfg = self.printer_cfg_path
            
            if not self.update_printer_cfg(source_printer_cfg, dest_printer_cfg, selected_printer):
                return False
                
            # Update OctoPrint configurations
            if not self.restore_octoprint_configs(selected_printer):
                logger.warning("Failed to update OctoPrint configs, but Klipper config was successful")
                
            logger.info(f"Successfully configured printer: {selected_printer}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying firmware files: {e}")
            return False

    # ========================================================================
    # BACKUP AND RECOVERY OPERATIONS
    # ========================================================================
    
    def is_config_valid(self, config_path: str = None) -> bool:
        """Check if configuration file is valid."""
        if config_path is None:
            config_path = self.printer_cfg_path
            
        try:
            # Basic checks: file exists and has content
            if not os.path.exists(config_path) or os.path.getsize(config_path) == 0:
                return False
            
            # Additional validation for Klipper config files
            return self._validate_klipper_config_structure(config_path)
            
        except Exception as e:
            logger.error(f"Error checking config validity: {e}")
            return False
    
    def _validate_klipper_config_structure(self, config_path: str) -> bool:
        """Validate basic Klipper configuration file structure.
        
        Args:
            config_path: Path to the configuration file to validate
            
        Returns:
            True if the config has basic valid structure, False otherwise
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for basic Klipper config structure
            # At minimum, a valid config should have some section headers [xxx]
            has_sections = '[' in content and ']' in content
            
            # Check it's not just whitespace or comments
            non_comment_lines = [line.strip() for line in content.split('\n') 
                               if line.strip() and not line.strip().startswith('#')]
            has_content = len(non_comment_lines) > 0
            
            # Check for common Klipper corruption indicators
            has_null_bytes = '\x00' in content
            has_binary_data = any(ord(char) > 127 for char in content[:1000])  # Check first 1KB
            
            is_valid = has_sections and has_content and not has_null_bytes and not has_binary_data
            
            if not is_valid:
                logger.debug(f"Config validation failed for {config_path}: "
                           f"has_sections={has_sections}, has_content={has_content}, "
                           f"has_null_bytes={has_null_bytes}, has_binary_data={has_binary_data}")
            
            return is_valid
            
        except Exception as e:
            logger.warning(f"Error validating config structure for {config_path}: {e}")
            return False
    
    def get_backup_files(self, pattern: str = None) -> List[str]:
        """Get list of backup configuration files."""
        if pattern is None:
            pattern = self.backup_pattern
            
        try:
            return sorted(glob.glob(pattern), reverse=True)
        except Exception as e:
            logger.error(f"Error getting backup files: {e}")
            return []
    
    def get_valid_backup_files(self, pattern: str = None) -> List[str]:
        """Get list of valid backup configuration files.
        
        This method checks each backup file for validity and returns only
        the valid ones, sorted by date (newest first).
        
        Args:
            pattern: Glob pattern for backup files. If None, uses default backup pattern.
            
        Returns:
            List of paths to valid backup files, sorted newest first
        """
        if pattern is None:
            pattern = self.backup_pattern
            
        try:
            all_backups = self.get_backup_files(pattern)
            valid_backups = []
            
            for backup_file in all_backups:
                if self.is_config_valid(backup_file):
                    valid_backups.append(backup_file)
                else:
                    logger.debug(f"Invalid backup file skipped: {backup_file}")
            
            logger.info(f"Found {len(valid_backups)} valid backup files out of {len(all_backups)} total")
            return valid_backups
            
        except Exception as e:
            logger.error(f"Error getting valid backup files: {e}")
            return []
    
    def restore_backup_config(self, config_path: str = None, backup_pattern: str = None) -> bool:
        """Restore configuration from the most recent valid backup.
        
        This method iterates through backup files (sorted by date, newest first)
        and restores from the first valid backup found. This ensures that if
        recent backups are corrupted, older valid backups can still be used.
        """
        if config_path is None:
            config_path = self.printer_cfg_path
        if backup_pattern is None:
            backup_pattern = self.backup_pattern
            
        try:
            backups = self.get_backup_files(backup_pattern)
            if not backups:
                logger.warning("No backup files found")
                return False
            
            logger.info(f"Found {len(backups)} backup files, checking for validity...")
            
            # Iterate through backups to find the latest valid one
            for i, backup_file in enumerate(backups):
                logger.debug(f"Checking backup {i+1}/{len(backups)}: {backup_file}")
                
                # Validate the backup file
                if self.is_config_valid(backup_file):
                    logger.info(f"Found valid backup: {backup_file}")
                    try:
                        # Create a backup of current config before restoring (if it exists)
                        if os.path.exists(config_path):
                            backup_current = f"{config_path}.pre-restore-{int(time.time())}"
                            shutil.copy2(config_path, backup_current)
                            logger.debug(f"Backed up current config to: {backup_current}")
                        
                        # Restore from the valid backup
                        shutil.copy2(backup_file, config_path)
                        logger.info(f"Successfully restored config from backup: {backup_file}")
                        
                        # Verify the restoration was successful
                        if self.is_config_valid(config_path):
                            logger.info("Backup restoration completed and verified")
                            return True
                        else:
                            logger.error("Restored config is invalid, restoration failed")
                            return False
                            
                    except Exception as e:
                        logger.error(f"Error restoring from backup {backup_file}: {e}")
                        continue
                else:
                    logger.warning(f"Backup file is invalid: {backup_file}")
                    
            # If we get here, no valid backup was found
            logger.error("No valid backup files found for restoration")
            return False
            
        except Exception as e:
            logger.error(f"Error in backup restoration process: {e}")
            return False
    
    def cleanup_old_backups(self, keep: int = 5, backup_pattern: str = None) -> None:
        """Remove old backup files, keeping only the specified number."""
        if backup_pattern is None:
            backup_pattern = self.backup_pattern
            
        try:
            backups = self.get_backup_files(backup_pattern)
            if len(backups) > keep:
                for backup in backups[keep:]:
                    os.remove(backup)
                    logger.debug(f"Removed old backup: {backup}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
    
    def check_klipper_config_files(self) -> Dict[str, bool]:
        """Check if all required Klipper configuration files exist."""
        required_files = [
            'printer.cfg',
            'CORE_GCODE_MACROS.cfg',
            'variables.cfg'
        ]
        
        status = {}
        for file in required_files:
            file_path = os.path.join(self.klipper_config_path, file)
            status[file] = os.path.exists(file_path)
            
        return status
    
    def get_missing_config_files(self) -> List[str]:
        """Get list of missing configuration files."""
        status = self.check_klipper_config_files()
        return [file for file, exists in status.items() if not exists]

    # ========================================================================
    # VERSION CHECKING AND FIRMWARE UPDATE MANAGEMENT
    # ========================================================================
    
    def get_config_version(self, config_path: str) -> Optional[str]:
        """Extract version number from a printer.cfg file.
        
        Args:
            config_path: Path to the printer.cfg file
            
        Returns:
            Version number as string, or None if not found/invalid
        """
        try:
            if not os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}")
                return None
                
            with open(config_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if line.startswith('# Version:'):
                        # Extract version number from "# Version: 2.1" or "# Version: 2.2.2"
                        try:
                            version_str = line.split(':')[1].strip()
                            # Validate that it's a reasonable version format
                            if re.match(r'^\d+(\.\d+)*$', version_str):
                                logger.debug(f"Found version {version_str} in {config_path}")
                                return version_str
                            else:
                                logger.warning(f"Invalid version format at line {line_num} in {config_path}: {line} - version must be numeric (e.g., '2', '2.1', '2.2.2')")
                                return None
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Invalid version format at line {line_num} in {config_path}: {line} - {e}")
                            return None
                            
            logger.debug(f"No version found in {config_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error reading config version from {config_path}: {e}")
            return None
    
    def get_current_config_version(self) -> Optional[str]:
        """Get version of currently active printer.cfg."""
        return self.get_config_version(self.printer_cfg_path)
    
    def get_firmware_config_version(self) -> Optional[str]:
        """Get version of firmware template printer.cfg."""
        firmware_config_path = os.path.join(self.firmware_path, "printer.cfg")
        return self.get_config_version(firmware_config_path)
    
    def is_firmware_update_available(self) -> bool:
        """Check if firmware template has a newer version than current config.
        
        Returns:
            True if firmware version is newer than current version
        """
        try:
            current_version = self.get_current_config_version()
            firmware_version = self.get_firmware_config_version()
            
            # If either version is missing, assume no update needed
            if current_version is None or firmware_version is None:
                logger.debug(f"Version check skipped - current: {current_version}, firmware: {firmware_version}")
                return False
            
            # Use packaging.version for proper semantic version comparison
            if version is not None:
                try:
                    current_ver = version.Version(current_version)
                    firmware_ver = version.Version(firmware_version)
                    is_newer = firmware_ver > current_ver
                except Exception as e:
                    logger.warning(f"Error parsing versions with packaging module: {e}. Falling back to string comparison.")
                    # Fallback to string comparison (works for simple cases like "2.1" vs "2.0")
                    is_newer = self._compare_version_strings(firmware_version, current_version)
            else:
                # Fallback to string comparison when packaging module is not available
                is_newer = self._compare_version_strings(firmware_version, current_version)
            
            if is_newer:
                logger.info(f"Firmware update available: current version {current_version}, firmware version {firmware_version}")
            else:
                logger.debug(f"Firmware up to date: current version {current_version}, firmware version {firmware_version}")
                
            return is_newer
            
        except Exception as e:
            logger.error(f"Error checking firmware update availability: {e}")
            return False
    
    def _compare_version_strings(self, version1: str, version2: str) -> bool:
        """Compare two version strings using basic semantic version logic.
        
        Args:
            version1: First version string (e.g., "2.1" or "2.2.2")
            version2: Second version string (e.g., "2.0" or "2.1.1")
            
        Returns:
            True if version1 is greater than version2
        """
        try:
            # Split versions into components and pad with zeros if needed
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            # Compare component by component
            for i in range(max_len):
                if v1_parts[i] > v2_parts[i]:
                    return True
                elif v1_parts[i] < v2_parts[i]:
                    return False
            
            # Versions are equal
            return False
            
        except Exception as e:
            logger.error(f"Error comparing version strings {version1} and {version2}: {e}")
            # Fallback to simple string comparison
            return version1 > version2


# ============================================================================
# SINGLETON INSTANCE AND CONVENIENCE FUNCTIONS
# ============================================================================

# Create singleton instance
_printer_config_manager = None

def get_printer_config_manager() -> PrinterConfigManager:
    """Get singleton instance of PrinterConfigManager."""
    global _printer_config_manager
    if _printer_config_manager is None:
        _printer_config_manager = PrinterConfigManager()
    return _printer_config_manager


# Convenience functions for backwards compatibility
def get_available_printers() -> List[str]:
    """Get list of available printer configurations."""
    return get_printer_config_manager().get_available_printers()

def get_printer_display_name(printer_name: str) -> str:
    """Convert printer name to display name."""
    return get_printer_config_manager().get_printer_display_name(printer_name)

def get_printer_filename(printer_name: str) -> str:
    """Convert printer name back to filename format."""
    return get_printer_config_manager().get_printer_filename(printer_name)

def get_current_printer_selection() -> Optional[str]:
    """Get the currently active printer configuration."""
    return get_printer_config_manager().get_current_printer_selection()

def copy_firmware_files(selected_printer: str) -> bool:
    """Copy all firmware files and update printer selection."""
    return get_printer_config_manager().copy_firmware_files(selected_printer)

def get_printer_config_from_klipper() -> Optional[Dict[str, Any]]:
    """Get complete printer configuration from active Klipper config."""
    return get_printer_config_manager().get_printer_config_from_klipper()

def parse_printer_variables_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Parse PRINTER_VARIABLES from a specific file."""
    return get_printer_config_manager().parse_printer_variables_from_file(file_path)

def extract_printer_configuration(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Extract configuration from PRINTER_VARIABLES."""
    return get_printer_config_manager().extract_printer_configuration(variables)

def restore_octoprint_configs(printer_name: str) -> bool:
    """Restore all OctoPrint configuration files for the selected printer."""
    return get_printer_config_manager().restore_octoprint_configs(printer_name)

def is_firmware_update_available() -> bool:
    """Check if firmware template has a newer version than current config."""
    return get_printer_config_manager().is_firmware_update_available()

def get_current_config_version() -> Optional[str]:
    """Get version of currently active printer.cfg."""
    return get_printer_config_manager().get_current_config_version()

def get_firmware_config_version() -> Optional[str]:
    """Get version of firmware template printer.cfg."""
    return get_printer_config_manager().get_firmware_config_version()

def get_valid_backup_files(pattern: str = None) -> List[str]:
    """Get list of valid backup configuration files."""
    return get_printer_config_manager().get_valid_backup_files(pattern)

def restore_backup_config(config_path: str = None, backup_pattern: str = None) -> bool:
    """Restore configuration from the most recent valid backup."""
    return get_printer_config_manager().restore_backup_config(config_path, backup_pattern)
