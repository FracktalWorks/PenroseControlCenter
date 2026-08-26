IGNORED_PRINTER_ERRORS = [
    "Move out of range:"
]
# Critical printer errors that require immediate attention, can cancel the print using mainController.showPrinterError
# NOTE: These are substring matches — be specific to avoid false positives.
CRITICAL_PRINTER_ERRORS = [
    # Existing critical errors
    "Can not update MCU",
    "Probe triggered prior to movement",
    "PROBING_FAILED",
    "Error during homing move",
    "still triggered after retract",
    "'mcu' must be specified",
    "Unable to connect",
    "Shutdown due to M112",
    "Printer is not ready",
    "not heating at expected rate",
    # Klipper MCU firmware shutdown errors (invoke_shutdown / try_shutdown)
    "Timer too close",
    "ADC out of range",
    "Lost communication with MCU",
    "Missed scheduling of next",
    "Rescheduled timer in the past",
    "Stepper too far in past",
    "Move queue overflow",
    "TMC reports error",
]
from collections import OrderedDict

# Configuration settings
ip = '0.0.0.0'
apiKey = 'B508534ED20348F090B4D0AD637D3660'   

# Screen resolution settings
# For 5-inch display: 800x480
# For 7-inch display: 1024x600
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

file_name = ''

filaments = [
    ("PEEK", 400),
    ("PLA", 190),
    ("ABS", 220),
    ("PETG", 220),
    ("PVA", 210),
    ("TPU", 230),
    ("Nylon", 220),
    ("PC", 240),
    ("HIPS", 220),
    ("WoodFill", 220),
    ("MetalFill", 200)
]

filaments = OrderedDict(filaments)

# Default/fallback printer configuration
# These values are used as fallback when Klipper configuration cannot be read
DEFAULT_CALIBRATION_POSITION = {'X1': 110, 'Y1': 18,
                                'X2': 510, 'Y2': 18,
                                'X3': 310, 'Y3': 308,
                                'X4': 310, 'Y4': 178
                                }

DEFAULT_MACHINE_BUILD_SIZE = {'X': 600, 'Y': 300, 'Z': 400}
DEFAULT_TOOL0_PURGE_POSITION = {'X': -30, 'Y': -77}
DEFAULT_TOOL1_PURGE_POSITION = {'X': 655, 'Y': -77}
DEFAULT_PTFE_TUBE_LENGTH = 1500  # 2400 for 600x600, 1500 for 600x300 keep as multiples of 300 only
DEFAULT_IS_DUAL_NOZZLE = True  # Set to False for single nozzle printers
DEFAULT_IS_HYBRID = False  # True for Hybrid IDEX (T0 pellet auger, T1 filament extruder)
DEFAULT_HAS_HEATER_RING = False  # Set to True for Volterra ALF printers with heater ring
DEFAULT_HAS_HEATED_CHAMBER = False  # Set to True for printers with heated chamber/enclosure
DEFAULT_HAS_SPOOL_HEATER = False  # Set to True for printers with filament spool heater/dryer

# Dynamic printer configuration (loaded from Klipper at runtime)
# These will be populated by load_printer_config_from_klipper()
calibrationPosition = DEFAULT_CALIBRATION_POSITION.copy()
machineBuildSize = DEFAULT_MACHINE_BUILD_SIZE.copy() 
tool0PurgePosition = DEFAULT_TOOL0_PURGE_POSITION.copy()
tool1PurgePosition = DEFAULT_TOOL1_PURGE_POSITION.copy()
ptfeTubeLength = DEFAULT_PTFE_TUBE_LENGTH
IS_DUAL_NOZZLE = DEFAULT_IS_DUAL_NOZZLE
IS_HYBRID = DEFAULT_IS_HYBRID
# Hybrid extruder mode ('pellet' or 'filament').
#
# SOURCE OF TRUTH is which MODE_*.cfg printer.cfg includes - the mode is a
# config-level property, not runtime state. This module-level value is a
# cache so the UI-visibility helpers can read it cheaply and dynamically
# (same pattern as IS_HYBRID). It is refreshed from:
#   - load_printer_config_from_klipper()  (startup / after a mode switch)
#   - PrinterModel.update_extruder_mode() (the firmware's EXTRUDER_MODE:
#     announcement, emitted by the STARTUP delayed_gcode)
# 'pellet' matches the firmware default when no mode include is active.
EXTRUDER_MODE = 'pellet'
HAS_HEATER_RING = DEFAULT_HAS_HEATER_RING
HAS_HEATED_CHAMBER = DEFAULT_HAS_HEATED_CHAMBER
HAS_SPOOL_HEATER = DEFAULT_HAS_SPOOL_HEATER


def load_printer_config_from_klipper():
    """
    Load printer configuration from Klipper PRINTER_VARIABLES.
    Updates the global configuration variables with values from the active printer.
    
    Returns:
        bool: True if configuration was successfully loaded, False if fallback values used
    """
    try:
        from utils.printer_config_manager import get_printer_config_from_klipper
        
        config = get_printer_config_from_klipper()
        if not config:
            return False
            
        global calibrationPosition, machineBuildSize, tool0PurgePosition
        global tool1PurgePosition, ptfeTubeLength, IS_DUAL_NOZZLE, HAS_HEATER_RING
        global HAS_HEATED_CHAMBER, HAS_SPOOL_HEATER, IS_HYBRID, EXTRUDER_MODE
        
        # Update global variables with extracted configuration
        if 'calibrationPosition' in config:
            calibrationPosition = config['calibrationPosition']
            
        if 'machineBuildSize' in config:
            machineBuildSize = config['machineBuildSize']
            
        if 'tool0PurgePosition' in config:
            tool0PurgePosition = config['tool0PurgePosition']
            
        if 'tool1PurgePosition' in config:
            tool1PurgePosition = config['tool1PurgePosition']
            
        if 'ptfeTubeLength' in config:
            ptfeTubeLength = config['ptfeTubeLength']
            
        if 'IS_DUAL_NOZZLE' in config:
            IS_DUAL_NOZZLE = config['IS_DUAL_NOZZLE']

        if 'IS_HYBRID' in config:
            IS_HYBRID = config['IS_HYBRID']

        # The extruder mode lives in printer.cfg's include selector rather
        # than in PRINTER_VARIABLES, so read it straight from the config
        # manager. Doing it here means every reload_printer_configuration()
        # picks up a mode switch without needing Klipper to be up.
        if IS_HYBRID:
            try:
                from utils.printer_config_manager import get_printer_config_manager
                from utils.logger import get_logger
                EXTRUDER_MODE = get_printer_config_manager().get_saved_extruder_mode()
                get_logger(__name__).info(f"Active extruder mode: {EXTRUDER_MODE}")
            except Exception as e:
                try:
                    from utils.logger import get_logger
                    get_logger(__name__).warning(f"Could not determine extruder mode: {e}")
                except Exception:
                    print(f"Could not determine extruder mode: {e}")

        if 'HAS_HEATER_RING' in config:
            HAS_HEATER_RING = config['HAS_HEATER_RING']

        if 'HAS_HEATED_CHAMBER' in config:
            HAS_HEATED_CHAMBER = config['HAS_HEATED_CHAMBER']

        if 'HAS_SPOOL_HEATER' in config:
            HAS_SPOOL_HEATER = config['HAS_SPOOL_HEATER']
            
        return True
        
    except Exception as e:
        # Log error but don't crash - use fallback values
        try:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Failed to load printer configuration from Klipper, using defaults: {e}")
        except:
            print(f"Failed to load printer configuration from Klipper, using defaults: {e}")
        return False


def get_printer_config():
    """
    Get current printer configuration as a dictionary.
    
    Returns:
        dict: Current printer configuration values
    """
    return {
        'calibrationPosition': calibrationPosition,
        'machineBuildSize': machineBuildSize,
        'tool0PurgePosition': tool0PurgePosition,
        'tool1PurgePosition': tool1PurgePosition,
        'ptfeTubeLength': ptfeTubeLength,
        'IS_DUAL_NOZZLE': IS_DUAL_NOZZLE,
        'IS_HYBRID': IS_HYBRID,
        'HAS_HEATER_RING': HAS_HEATER_RING,
        'HAS_HEATED_CHAMBER': HAS_HEATED_CHAMBER,
        'HAS_SPOOL_HEATER': HAS_SPOOL_HEATER
    }