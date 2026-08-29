"""
Printer Model Module
Handles printer state, temperature monitoring, and operations
"""
import time
from PyQt5.QtCore import QObject, pyqtSignal
from utils.logger import get_logger
logger = get_logger(__name__)
from utils import dialog
# Use configuration from config.py
import config
from utils.printer_preference_store import PrinterPreferenceStore

class PrinterModel(QObject):
    """
    Model class for printer state and operations
    Handles maintaining state of the printer including temperatures,
    file information, and print status
    """
    # Signal definitions
    # this one should have signal slot connections probably
    temperatures_updated = pyqtSignal(dict)  # done
    status_updated = pyqtSignal(str)  # done
    print_status_updated = pyqtSignal('PyQt_PyObject')  # ! done
    active_extruder_changed = pyqtSignal(int)  # ! done
    z_probe_offset_updated = pyqtSignal(str)  # ! done
    tool_offset_data = pyqtSignal(str)  # done
    printer_error_signal = pyqtSignal(str)  # done
    pellet_sensor_state = pyqtSignal(str, bool)  # Pellet level sensor state (sensor_name, is_ok)
    z_probing_failed = pyqtSignal()  # done
    update_started_signal = pyqtSignal('PyQt_PyObject')
    update_log_signal = pyqtSignal('PyQt_PyObject')  # ! REMAINING
    update_log_result_signal = pyqtSignal('PyQt_PyObject')  # ! REMAINING
    update_failed_signal = pyqtSignal('PyQt_PyObject')  # ! REMAINING
    connected_signal = pyqtSignal()  # done
    # Klipper state propagated from websocket via controller
    klipper_state_changed = pyqtSignal(str)
    # Signals for tool-bay state persistence and UI sync
    tool_bay_states_loaded = pyqtSignal(dict)      # {'tool0': {...}, 'tool1': {...}}
    tool_bay_state_changed = pyqtSignal(str, str, dict) # tool, bay, bay_state
    # Signals for feed rate and flow rate updates
    feed_rate_updated = pyqtSignal(int)  # Feed rate percentage
    flow_rate_updated = pyqtSignal(int)  # Flow rate percentage
    ring_heater_power_updated = pyqtSignal(int)  # Ring heater power 0-255
    # Signal for printer configuration changes
    printer_config_updated = pyqtSignal(dict)  # Emitted when printer configuration changes
    
    # Position tracking signals
    current_position_updated = pyqtSignal(dict)  # {'x': float, 'y': float, 'z': float}

    # Probe accuracy results for calibration wizards
    probe_accuracy_result_received = pyqtSignal(str, dict)  # (tool_name, probe_data)

    # Hybrid IDEX extruder mode ("pellet" or "filament") - which tool a
    # print job uses when the sliced gcode has no explicit T0/T1 commands
    extruder_mode_changed = pyqtSignal(str)

    def __init__(self):
        super(PrinterModel, self).__init__()
        self.logger = get_logger(self.__class__.__name__)
        
        # Initialize printer configuration from Klipper
        self._load_printer_configuration()
        
        self.temperatures = {
            'tool0Actual': 0, 'tool0Target': 0,
            'tool1Actual': 0, 'tool1Target': 0,
            'bedActual': 0, 'bedTarget': 0
        }
        self.printer_status = "Offline"
        self.active_extruder = 0
        self.current_file = None
        self.current_image = None
        self.z_probe_offset = 0.0
        self.tool_offsets = {'X': 0, 'Y': 0, 'Z': 0}
        
        # Current hotend position tracking
        self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.position_timestamp = 0.0  # When position was last updated
        
        self.print_progress = 0
        self.print_time = 0
        self.print_time_left = 0
        self.updateData = {}
        self.filaments = config.filaments
        
        # Printer configuration properties (loaded dynamically from Klipper)
        self.calibrationPosition = config.calibrationPosition
        self.tool0PurgePosition = config.tool0PurgePosition
        self.tool1PurgePosition = config.tool1PurgePosition
        self.ptfeTubeLength = config.ptfeTubeLength
        self.machineBuildSize = config.machineBuildSize
        self.IS_DUAL_NOZZLE = config.IS_DUAL_NOZZLE
        self.IS_HYBRID = config.IS_HYBRID
        # Hybrid IDEX extruder mode - source of truth lives in Klipper's
        # variables.cfg (extruder_mode); this cache is refreshed from the
        # EXTRUDER_MODE: websocket messages. 'pellet' matches the macro
        # default in BASE_PENROSE_HYBRID.cfg.
        self.extruder_mode = "pellet"
        # Klipper state cache
        self.klipper_state = "unknown"
        # Tool state persistence
        # self.status_options = ["Empty", "Unknown", "Loaded", "Staged"]
        self.status_options = ["Empty", "Loaded"]
        # Nozzle sizes differ per extruder head type. Use nozzle_options_for_tool()
        # so a Hybrid IDEX offers filament sizes on T1 and pellet sizes on T0.
        self._pellet_nozzle_options = ["0.6", "0.8", "1.0", "1.5", "2.0", "3.0"]
        # The filament head ships with the large-format range only - the fine
        # 0.25/0.4 tips are not offered on this machine.
        self._filament_nozzle_options = ["0.6", "0.8", "1.0", "1.2"]
        # Nested per-bay structure per tool; defaults reflect current A/B mapping
        self.tools = {
            "tool0": {
                "material_bay_a": {"filament": None, "status": "Unknown", "nozzle": "Unknown"}
            },
            "tool1": {
                "material_bay_x": {"filament": None, "status": "Unknown", "nozzle": "Unknown"}
            },
        }
        self._config_store = PrinterPreferenceStore()
        # Load full cached state once
        try:
            state = self._config_store.load_full()
        except Exception as e:
            self.logger.error(f"Failed to load printer config store: {e}")
            state = {"tools": {}, "preferences": {}}
        # Initialize tools from cached state
        self._init_tools_from_store(state.get("tools", {}))
        # Pellet sensor states & preferences (for Penrose pellet extruder)
        prefs = state.get("preferences", {})
        self.pellet_sensor_t0_enabled = bool(prefs.get("pellet_sensor_t0_enabled", True))  # Default to enabled
        self.pellet_sensor_t1_enabled = bool(prefs.get("pellet_sensor_t1_enabled", True))  # Default to enabled
        # Filament runout switch on the Hybrid IDEX T1 head (no flow sensor fitted)
        self.extruder_runout_enabled = bool(prefs.get("extruder_runout_enabled", True))  # Default to enabled
        self.print_compatibility_check_enabled = bool(prefs.get("print_compatibility_check_enabled", True))  # Default to enabled
        
        # Print restore preferences
        self.print_restore_enabled = bool(prefs.get("print_restore_enabled", True))  # Default to enabled
        self.auto_resume_enabled = bool(prefs.get("auto_resume_enabled", False))  # Default to disabled
        
        # Firmware update preferences
        self.firmware_update_check_enabled = bool(prefs.get("firmware_update_check_enabled", True))  # Default to enabled
        
        # Advanced debugging mode preference
        self.advanced_debugging_enabled = bool(prefs.get("advanced_debugging_enabled", False))  # Default to disabled
        
        # Initialize the logging mode based on the preference
        from utils.logger import set_advanced_debug_mode
        set_advanced_debug_mode(self.advanced_debugging_enabled)
        
        self.pellet_sensor_state_map = {}  # {sensor: bool}
        
        # Note: Printer configuration now managed by printer.cfg file directly
        # No need to store selected_printer_config in memory
        
        # Feed rate and flow rate storage
        self.current_feed_rate = 100  # Default 100%
        self.current_flow_rate = 100  # Default 100%
        
        # Ring heater power storage
        self.ring_heater_power = 0  # Default 0 (0-255 range)

    # --- Nozzle options ---------------------------------------------------
    def nozzle_options_for_tool(self, tool):
        """Return the selectable nozzle sizes for a tool's extruder head.

        Args:
            tool: Tool identifier - "tool0"/"tool1", or 0/1
        """
        try:
            from utils.printer_ui_config import tool_head_type
            if tool_head_type(tool) == 'filament':
                return list(self._filament_nozzle_options)
        except Exception as e:
            self.logger.error(f"Failed to resolve extruder head type for {tool}: {e}")
        return list(self._pellet_nozzle_options)

    @property
    def nozzle_options(self):
        """All nozzle sizes valid on this machine, across both extruder heads.

        Prefer nozzle_options_for_tool() - this union exists so callers that
        only validate a size (with no tool in hand) keep working.
        """
        merged = list(self._pellet_nozzle_options)
        try:
            from utils.printer_ui_config import is_hybrid_printer
            if is_hybrid_printer():
                merged += [n for n in self._filament_nozzle_options if n not in merged]
        except Exception as e:
            self.logger.error(f"Failed to resolve hybrid printer state: {e}")
        return merged

    # --- Pellet sensor preference setters (called by controller/UI) -------
    def set_pellet_sensor_t0_pref(self, enabled: bool, persist: bool = True):
        """Set T0 (Left) pellet level sensor preference and persist if requested."""
        prev = self.pellet_sensor_t0_enabled
        self.pellet_sensor_t0_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('pellet_sensor_t0_enabled', bool(enabled))

    def set_pellet_sensor_t1_pref(self, enabled: bool, persist: bool = True):
        """Set T1 (Right) pellet level sensor preference and persist if requested."""
        prev = self.pellet_sensor_t1_enabled
        self.pellet_sensor_t1_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('pellet_sensor_t1_enabled', bool(enabled))

    def set_extruder_runout_pref(self, enabled: bool, persist: bool = True):
        """Set T1 filament runout sensor preference and persist if requested."""
        prev = self.extruder_runout_enabled
        self.extruder_runout_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('extruder_runout_enabled', bool(enabled))

    def update_extruder_mode(self, mode: str):
        """Cache the Hybrid IDEX extruder mode reported by Klipper.

        Klipper's variables.cfg is the source of truth (persisted there by
        SET_EXTRUDER_MODE); this just mirrors it for the UI. Emits
        extruder_mode_changed on change.
        """
        mode = str(mode).lower()
        if mode not in ("pellet", "filament"):
            self.logger.warning(f"Ignoring invalid extruder mode: {mode}")
            return
        if mode != self.extruder_mode:
            self.extruder_mode = mode
            # Mirror into the config module so the UI-visibility helpers
            # (printer_ui_config) can read it dynamically like IS_HYBRID
            config.EXTRUDER_MODE = mode
            self.logger.info(f"Extruder mode updated: {mode}")
            self.extruder_mode_changed.emit(mode)

    def set_print_compatibility_check_pref(self, enabled: bool, persist: bool = True):
        """Set print compatibility check preference and persist if requested."""
        prev = self.print_compatibility_check_enabled
        self.print_compatibility_check_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('print_compatibility_check_enabled', bool(enabled))

    def set_print_restore_pref(self, enabled: bool, persist: bool = True):
        """Set print restore enabled preference and persist if requested."""
        prev = self.print_restore_enabled
        self.print_restore_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('print_restore_enabled', bool(enabled))

    def set_auto_resume_pref(self, enabled: bool, persist: bool = True):
        """Set auto resume preference and persist if requested."""
        prev = self.auto_resume_enabled
        self.auto_resume_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('auto_resume_enabled', bool(enabled))

    def set_firmware_update_check_pref(self, enabled: bool, persist: bool = True):
        """Set firmware update check preference and persist if requested."""
        prev = self.firmware_update_check_enabled
        self.firmware_update_check_enabled = bool(enabled)
        if persist and prev != enabled:
            self._config_store.set_preference('firmware_update_check_enabled', bool(enabled))

    def set_advanced_debugging_pref(self, enabled: bool, persist: bool = True):
        """Set advanced debugging mode preference and persist if requested."""
        from utils.logger import set_advanced_debug_mode
        prev = self.advanced_debugging_enabled
        self.advanced_debugging_enabled = bool(enabled)
        # Immediately apply the debugging mode to the logging system
        set_advanced_debug_mode(bool(enabled))
        if persist and prev != enabled:
            self._config_store.set_preference('advanced_debugging_enabled', bool(enabled))

    def update_print_restore_settings_from_octoprint(self, settings_data):
        """Update print restore settings from OctoPrint plugin response."""
        try:
            if isinstance(settings_data, dict):
                # Update print restore enabled state
                if 'enabled' in settings_data:
                    new_enabled = bool(settings_data['enabled'])
                    if new_enabled != self.print_restore_enabled:
                        self.set_print_restore_pref(new_enabled, persist=True)
                
                # Update auto resume state
                if 'autoRestore' in settings_data:
                    new_restore = bool(settings_data['autoRestore'])
                    if new_restore != self.auto_resume_enabled:
                        self.set_auto_resume_pref(new_restore, persist=True)
                
                self.logger.info(f"Updated print restore settings from OctoPrint: enabled={self.print_restore_enabled}, auto_resume={self.auto_resume_enabled}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to update print restore settings: {e}")
        return False

    def update_feed_rate(self, rate: int):
        """Update the current feed rate and emit signal."""
        try:
            self.current_feed_rate = max(1, min(500, int(rate)))  # Clamp between 1-500%
            self.feed_rate_updated.emit(self.current_feed_rate)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid feed rate value: {rate}")

    def update_flow_rate(self, rate: int):
        """Update the current flow rate and emit signal."""
        try:
            self.current_flow_rate = max(1, min(500, int(rate)))  # Clamp between 1-500%
            self.flow_rate_updated.emit(self.current_flow_rate)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid flow rate value: {rate}")
    
    def update_ring_heater_power(self, power: int):
        """Update the current ring heater power and emit signal."""
        try:
            self.ring_heater_power = max(0, min(255, int(power)))  # Clamp between 0-255
            self.ring_heater_power_updated.emit(self.ring_heater_power)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid ring heater power value: {power}")

    def update_current_position(self, position_data: dict):
        """
        Update the current hotend position from M114 response.
        
        Args:
            position_data: Dictionary with 'x', 'y', 'z' keys (any subset is acceptable)
        """
        import time
        
        try:
            # Validate and update position data
            updated = False
            valid_data_received = False
            
            for axis in ['x', 'y', 'z']:
                if axis in position_data:
                    try:
                        new_value = float(position_data[axis])
                        valid_data_received = True
                        if self.current_position[axis] != new_value:
                            self.current_position[axis] = new_value
                            updated = True
                        else:
                            # Even if position didn't change, we still received valid data
                            self.current_position[axis] = new_value
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid {axis} position value: {position_data[axis]}")
            
            # Always emit signal when valid position data is received, regardless of whether it changed
            # This ensures calibration wizards receive position confirmations even when printer is stationary
            if valid_data_received:
                self.position_timestamp = time.time()
                if updated:
                    self.logger.debug(f"Position updated: {self.current_position}")
                else:
                    self.logger.debug(f"Position confirmed (unchanged): {self.current_position}")
                self.current_position_updated.emit(self.current_position.copy())
                
        except Exception as e:
            self.logger.error(f"Error updating current position: {e}")

    def get_current_position(self) -> dict:
        """Get the current hotend position."""
        return self.current_position.copy()

    def get_position_age(self) -> float:
        """Get how old the current position data is in seconds."""
        import time
        return time.time() - self.position_timestamp

    def updateTemperature(self, temp_data):
        """ Updates the temperature data. Is a slot for the temperatures_updated signal. """
        if temp_data['tool0Actual'] is None:
            temp_data['tool0Actual'] = 0
        if temp_data['tool0Target'] is None:
            temp_data['tool0Target'] = 0
        if temp_data['tool1Actual'] is None:
            temp_data['tool1Actual'] = 0
        if temp_data['tool1Target'] is None:
            temp_data['tool1Target'] = 0
        if temp_data['bedActual'] is None:
            temp_data['bedActual'] = 0
        if temp_data['bedTarget'] is None:
            temp_data['bedTarget'] = 0
        self.temperatures = temp_data
        self.temperatures_updated.emit(temp_data)

    def updateStatus(self, status):
        self.printer_status = status
        self.status_updated.emit(status)

    def updatePrintStatus(self, file_info):
        """Updates print job status"""
        if file_info["job"] is None:
            self.current_file = None
            self.current_image = None
            self.print_progress = 0
            self.print_time = 0
            self.print_time_left = 0
        else:
            self.current_file = file_info.get('job', {}).get('file', {}).get('name')
            if file_info.get('progress', {}).get('completion') is not None:
                self.print_progress = file_info['progress']['completion']

            if file_info.get('progress', {}).get('printTime') is not None:
                self.print_time = file_info['progress']['printTime']

            if file_info.get('progress', {}).get('printTimeLeft') is not None:
                self.print_time_left = file_info['progress']['printTimeLeft']

        self.print_status_updated.emit(file_info)

    def setActiveExtruder(self, extruder):
        """Sets the active extruder"""
        try:
            self.active_extruder = int(extruder)
            self.active_extruder_changed.emit(int(self.active_extruder))
        except ValueError:
            self.logger.error(f"Invalid extruder value: {extruder}")

    def updateEEPROMProbeOffset(self, offset):
        """ Updates the Z probe offset in EEPROM """
        try:
            self.z_probe_offset = offset
            self.z_probe_offset_updated.emit(self.z_probe_offset)
        except ValueError:
            self.logger.error(f"Invalid Z probe offset value: {offset}")
            dialog.WarningOk(self, "Invalid Z probe offset value: {}".format(offset), overlay=True)

    def handle_probe_accuracy_result(self, message_text):
        """
        Handle probe accuracy results from Klipper and emit signal to calibration wizards.
        
        Args:
            message_text (str): The probe accuracy message from Klipper
        """
        try:
            self.logger.info(f"PrinterModel received probe accuracy message: {message_text}")
            
            # Parse the probe result from the message
            if 'probe accuracy results:' in message_text.lower():
                import re
                
                # Parse essential probe accuracy values
                probe_data = {}
                
                patterns = {
                    'average': r'average\s+([-+]?\d+\.?\d*)',
                    'standard_deviation': r'standard deviation\s+([-+]?\d+\.?\d*)'
                }
                
                # Extract values
                for key, pattern in patterns.items():
                    match = re.search(pattern, message_text, re.IGNORECASE)
                    if match:
                        probe_data[key] = float(match.group(1))
                    else:
                        self.logger.warning(f"Could not find {key} in probe results")
                
                # Only proceed if we have at least the average value
                if 'average' in probe_data:
                    self.logger.info(f"Parsed probe data: {probe_data}")
                    
                    # Determine which tool based on current active extruder
                    tool_name = f"tool{self.active_extruder}"
                    
                    # Emit the signal to any listening calibration wizards
                    self.probe_accuracy_result_received.emit(tool_name, probe_data)
                    self.logger.info(f"Emitted probe accuracy result signal for {tool_name}")
                else:
                    self.logger.warning("Could not parse probe accuracy data - missing average value")
            else:
                self.logger.debug("Message does not contain probe accuracy results")
                
        except Exception as e:
            self.logger.error(f"Error handling probe accuracy result: {e}")

    def setToolOffset(self, M218Data):
        """ Set the tool offsets from M218 response """
        try:
            if 'X' in M218Data:
                self.tool_offsets['X'] = M218Data[M218Data.index('X') + 1:].split(' ', 1)[0]
            if 'Y' in M218Data:
                self.tool_offsets['Y'] = M218Data[M218Data.index('Y') + 1:].split(' ', 1)[0]
            if 'Z' in M218Data:
                self.tool_offsets['Z'] = M218Data[M218Data.index('Z') + 1:].split(' ', 1)[0]
            self.tool_offset_data.emit(M218Data)
        except Exception as e:
            self.logger.error("Error in PrinterModel.setToolOffset: {}".format(e))
            dialog.WarningOk(self, "Error in PrinterModel.setToolOffset: {}".format(e), overlay=True)

    def pelletSensorState(self, sensor, is_ok):
        """
        Handles pellet level sensor state events (Penrose pellet extruder).
        :param sensor: Sensor identifier (e.g., 'pellet_sensor_left', 'pellet_sensor_right').
        :param is_ok: Boolean indicating pellet level is OK (True) or LOW (False).
        """
        # Store in map for UI access
        self.pellet_sensor_state_map[sensor] = bool(is_ok)
        self.pellet_sensor_state.emit(sensor, is_ok)

    # Use the softwareUpdateProgress function to send data about software updates
    def softwareUpdateProgress(self, update_info):
        self.updateData = update_info
        self.update_started_signal.emit(update_info)

    def softwareUpdateProgressLog(self, update_info):
        self.updateData = update_info
        self.update_log_signal.emit(update_info)

    def softwareUpdateResult(self, update_info):
        self.updateData = update_info
        self.update_log_result_signal.emit(update_info)

    def updateFailed(self, update_info):
        self.updateData = update_info
        self.update_failed_signal.emit(update_info)

    # --- Tool state persistence helpers ---
    def _sanitize_bay_state(self, v: dict, tool: str = None) -> dict:
        filament = v.get("filament")
        status = v.get("status", "Unknown")
        nozzle = v.get("nozzle", "Unknown")
        if status not in self.status_options:
            status = "Unknown"
        valid_nozzles = self.nozzle_options_for_tool(tool) if tool else self.nozzle_options
        if nozzle not in valid_nozzles and nozzle != "Unknown":
            nozzle = "Unknown"
        return {"filament": filament, "status": status, "nozzle": nozzle}

    def _init_tools_from_store(self, tools_state: dict):
        try:
            for tool_id in ("tool0", "tool1"):
                raw = tools_state.get(tool_id, {})
                # Already upgraded by store; just validate & copy
                cleaned = {}
                for bay, v in raw.items():
                    cleaned[bay] = self._sanitize_bay_state(v, tool_id)
                if not cleaned:
                    cleaned = {("material_bay_a" if tool_id == "tool0" else "material_bay_x"): {"filament": None, "status": "Unknown", "nozzle": "Unknown"}}
                self.tools[tool_id] = cleaned
            self.tool_bay_states_loaded.emit(self.tools.copy())
        except Exception as e:
            self.logger.error(f"Failed initializing tool state: {e}")
            self.tool_bay_states_loaded.emit(self.tools.copy())

    def update_tool_bay_state(self, tool: str, bay: str = None, filament=None, status=None, nozzle=None, persist=True):
        if tool not in ("tool0", "tool1"):
            self.logger.error(f"Invalid tool: {tool}")
            return
        bay = bay or ("material_bay_a" if tool == "tool0" else "material_bay_x")
        # Validate inputs
        if status is not None and status not in self.status_options:
            status = "Unknown"
        if nozzle is not None and (nozzle not in self.nozzle_options_for_tool(tool) and nozzle != "Unknown"):
            nozzle = "Unknown"
        cur = self._config_store.set_tool_state(tool, bay=bay, filament=filament if filament is not None else None,
                                                status=status if status is not None else None,
                                                nozzle=nozzle if nozzle is not None else None)
        # Mirror into in-memory tools dict
        if tool not in self.tools:
            self.tools[tool] = {}
        self.tools[tool][bay] = cur
        self.tool_bay_state_changed.emit(tool, bay, cur.copy())

    # Backward-compatible wrapper
    def set_tool_state(self, tool: str, bay: str = None, filament=None, status=None, nozzle=None, persist=True):
        return self.update_tool_bay_state(tool, bay, filament, status, nozzle, persist)

    # Convenience getters for primary bays used by current UI
    def get_default_bay(self, tool: str) -> str:
        return "material_bay_a" if tool == "tool0" else "material_bay_x"
    def get_bay_state(self, tool: str, bay: str = None) -> dict:
        bay = bay or self.get_default_bay(tool)
        return self.tools.get(tool, {}).get(bay, {"filament": None, "status": "Unknown", "nozzle": "Unknown"})

    def get_current_tool_config(self):
        """
        Get current nozzle and material configuration for both tools.
        Returns dictionary with current setup for validation against GCODE metadata.
        """
        config = {}
        for tool in ["tool0", "tool1"]:
            bay_state = self.get_bay_state(tool)
            config[tool] = {
                'nozzle': bay_state.get('nozzle', 'Unknown'),
                'material': bay_state.get('filament', None)
            }
        return config

    # --- Klipper state updater ---
    def update_klipper_state(self, state: str):
        try:
            norm = str(state).strip().lower() if state is not None else "unknown"
            # Only emit if changed to avoid UI churn
            if getattr(self, 'klipper_state', None) != norm:
                self.klipper_state = norm
                self.klipper_state_changed.emit(norm)
        except Exception:
            # Ensure we don't crash signal flow
            self.klipper_state = str(state)
            self.klipper_state_changed.emit(self.klipper_state)

    # --- Printer configuration methods ---
    # Note: Printer selection now managed by printer.cfg file directly
    # Use get_current_printer_selection() from printer_config_manager for current printer info
    
    def _load_printer_configuration(self):
        """Load printer configuration from Klipper PRINTER_VARIABLES."""
        try:
            # Load configuration from Klipper
            success = config.load_printer_config_from_klipper()
            
            if success:
                # Update our local configuration properties
                self.calibrationPosition = config.calibrationPosition
                self.tool0PurgePosition = config.tool0PurgePosition
                self.tool1PurgePosition = config.tool1PurgePosition 
                self.ptfeTubeLength = config.ptfeTubeLength
                self.machineBuildSize = config.machineBuildSize
                self.IS_DUAL_NOZZLE = config.IS_DUAL_NOZZLE
                self.IS_HYBRID = config.IS_HYBRID
                self.HAS_HEATER_RING = config.HAS_HEATER_RING
                self.HAS_HEATED_CHAMBER = config.HAS_HEATED_CHAMBER
                self.HAS_SPOOL_HEATER = config.HAS_SPOOL_HEATER
                
                self.logger.info("Successfully loaded printer configuration from Klipper")
                self.logger.debug(f"Machine build size: {self.machineBuildSize}")
                self.logger.debug(f"Dual nozzle: {self.IS_DUAL_NOZZLE}")
                
                # Emit signal with updated configuration
                self.printer_config_updated.emit(self.get_printer_configuration())
                
            else:
                self.logger.warning("Failed to load printer configuration from Klipper, using defaults")
                
        except Exception as e:
            self.logger.error(f"Error loading printer configuration: {e}")

    def reload_printer_configuration(self):
        """Reload printer configuration from Klipper (public method for external calls)."""
        self._load_printer_configuration()
        
    def get_printer_configuration(self) -> dict:
        """Get current printer configuration as a dictionary."""
        return {
            'calibrationPosition': self.calibrationPosition,
            'machineBuildSize': self.machineBuildSize,
            'tool0PurgePosition': self.tool0PurgePosition,
            'tool1PurgePosition': self.tool1PurgePosition,
            'ptfeTubeLength': self.ptfeTubeLength,
            'IS_DUAL_NOZZLE': self.IS_DUAL_NOZZLE,
            'IS_HYBRID': getattr(self, 'IS_HYBRID', False),
            'HAS_HEATER_RING': getattr(self, 'HAS_HEATER_RING', False),
            'HAS_HEATED_CHAMBER': getattr(self, 'HAS_HEATED_CHAMBER', False),
            'HAS_SPOOL_HEATER': getattr(self, 'HAS_SPOOL_HEATER', False)
            # Note: selected_printer_config removed - use get_current_printer_selection() instead
        }
