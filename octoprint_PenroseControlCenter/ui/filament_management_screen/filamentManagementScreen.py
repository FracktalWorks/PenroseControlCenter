import os
from PyQt5.QtWidgets import QWidget, QToolButton, QPushButton, QStackedWidget, QLabel
from PyQt5 import QtWidgets, QtCore
from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5 import uic
from utils.helpers import check_ui_elements
from utils.logger import get_logger
from utils.printer_ui_config import (apply_nozzle_config_to_screen, is_dual_nozzle_printer,
                                     is_hybrid_printer, is_filament_tool, get_extruder_mode)
from utils import dialog
from utils import styles
import config
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QFormLayout, QComboBox, QHBoxLayout

# Import sub-screens (nozzle change wizard always; filament wizard for filament heads)
from ui.filament_management_screen.nozzleChangeWizard.nozzleChangeWizard import NozzleChangeWizard
from ui.filament_management_screen.changeFilamentWizard.changeFilamentWizard import ChangeFilamentWizard

logger = get_logger(__name__)

# Hybrid IDEX extruder types shown in the customer-facing selector on this
# screen. The data value is the MODE= argument for SET_EXTRUDER_MODE.
EXTRUDER_TYPES = [
    ("Pellet Extruder", "pellet"),
    ("Filament Extruder", "filament"),
]

class filamentManagementScreen(QWidget):
    def __init__(self, main_window):
        """Initialize the combined Filament/Nozzle screen, create sub-screens,
        wire up controls, and set initial UI state.

        Args:
            main_window: Reference to the main window to access shared services and navigation.
        """
        super(filamentManagementScreen, self).__init__()
        self.main_window = main_window
        self.octoprint_client = main_window.octoprint_client
        self.logger = get_logger(self.__class__.__name__)

        # Load the UI
        try:
            # Use relative path from the current module's directory
            ui_file_path = os.path.join(os.path.dirname(__file__), "filamentManagementScreen.ui")
            uic.loadUi(ui_file_path, self)
            self.logger.info("filamentManagementScreen UI loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load filamentManagementScreen UI file: {e}")

        # Initialize UI components
        self.material_nozzle_stacked_widget = self.findChild(QStackedWidget, "mainMaterialNozzleStackedWidget")
        self.main_material_nozzle_page = self.findChild(QWidget, "mainMaterialNozzlePage")

        # Material buttons (simplified: one per tool)
        self.changeTool0MaterialBayA = self.findChild(QToolButton, "changeTool0MaterialBayA")
        self.changeTool1MaterialBayX = self.findChild(QToolButton, "changeTool1MaterialBayX")

        # Nozzle buttons
        self.changeTool0Button = self.findChild(QToolButton, "changeTool0Button")
        self.changeTool1Button = self.findChild(QToolButton, "changeTool1Button")

        # Labels and state indicators
        self.tool0MaterialBayALabel = self.findChild(QLabel, "tool0MaterialBayALabel")
        self.tool1MaterialBayXLabel = self.findChild(QLabel, "tool1MaterialBayXLabel")
        self.tool0MaterialBayAStateLabel = self.findChild(QLabel, "tool0MaterialBayAStateLabel")
        self.tool1MaterialBayXStateLabel = self.findChild(QLabel, "tool1MaterialBayXStateLabel")
        self.tool0MaterialBayAStateColor = self.findChild(QLabel, "tool0MaterialBayAStateColor")
        self.tool11MaterialBayXStateColor = self.findChild(QLabel, "tool11MaterialBayXStateColor")

        # Edit buttons
        self.editTool0MaterialBayA = self.findChild(QPushButton, "editTool0MaterialBayA")
        # UI now corrected to editTool1MaterialBayX as per user
        self.editTool1MaterialBayX = self.findChild(QPushButton, "editTool1MaterialBayX") or \
                                     self.findChild(QPushButton, "editTool0MaterialBayX")

        # Back button
        self.materialNozzleBackButton = self.findChild(QPushButton, "materialNozzleBackButton")

        # Validate UI components
        # Validate only elements that exist (labels showing loaded filament were removed from the UI)
        check_ui_elements(self, [
            self.material_nozzle_stacked_widget, self.main_material_nozzle_page,
            self.changeTool0MaterialBayA, self.changeTool1MaterialBayX,
            self.changeTool0Button, self.changeTool1Button,
            self.materialNozzleBackButton,
            self.tool0MaterialBayAStateLabel, self.tool1MaterialBayXStateLabel,
            self.tool0MaterialBayAStateColor, self.tool11MaterialBayXStateColor,
            self.editTool0MaterialBayA, self.editTool1MaterialBayX
        ], "filamentManagementScreen")

        # Initialize all sub-screens
        self.screens = {}
        self._initialize_sub_screens()

        # Material buttons route by head type: pellet heads get the line vac
        # load dialog, filament heads get the load/unload wizard.
        self.changeTool0MaterialBayA.clicked.connect(lambda: self._on_material_button_clicked("tool0"))
        self.changeTool1MaterialBayX.clicked.connect(lambda: self._on_material_button_clicked("tool1"))

        self.changeTool0Button.clicked.connect(
            lambda: self.show_material_nozzle_screen(target_screen="nozzle_change", params={"tool": "tool0"})
        )
        self.changeTool1Button.clicked.connect(
            lambda: self.show_material_nozzle_screen(target_screen="nozzle_change", params={"tool": "tool1"})
        )

        # Edit handlers
        if self.editTool0MaterialBayA:
            self.editTool0MaterialBayA.clicked.connect(lambda: self._open_edit_dialog("tool0"))
        if self.editTool1MaterialBayX:
            self.editTool1MaterialBayX.clicked.connect(lambda: self._open_edit_dialog("tool1"))

        self.materialNozzleBackButton.clicked.connect(lambda: self.main_window.switch_to_menu_screen())

        # Hybrid IDEX: customer-facing extruder type selector (Pellet/Filament)
        self.extruderTypeComboBox = None
        self._setup_extruder_type_selector()

        # Show the main material/nozzle page initially
        self.material_nozzle_stacked_widget.setCurrentWidget(self.main_material_nozzle_page)
        self.logger.debug("Set current widget to mainMaterialNozzlePage")
        self._loading_dialog = None
        
        # Bind to printer model signals for state updates
        try:
            self.main_window.printer_model.tool_bay_states_loaded.connect(self._on_tool_states_loaded)
            self.main_window.printer_model.tool_bay_state_changed.connect(self._on_tool_state_changed)
            # Also react to printer status to enable/disable change buttons
            self.main_window.printer_model.status_updated.connect(self._on_status_updated)
            # Connect to pellet sensor state signal for real-time updates
            self.main_window.printer_model.pellet_sensor_state.connect(self._on_pellet_sensor_state)
        except Exception as e:
            self.logger.error(f"Failed connecting tool state signals: {e}")
        # Apply current state immediately in case the signal fired before this screen connected
        try:
            if hasattr(self.main_window.printer_model, 'tools'):
                self._on_tool_states_loaded(self.main_window.printer_model.tools)
        except Exception as e:
            self.logger.debug(f"Unable to apply initial tool state: {e}")
        # Apply current printer status to buttons immediately
        try:
            self._on_status_updated(self.main_window.printer_model.printer_status)
        except Exception as e:
            self.logger.debug(f"Unable to apply initial status to buttons: {e}")

        # Apply nozzle configuration
        self.apply_nozzle_configuration()

    def apply_nozzle_configuration(self):
        """Hide dual nozzle elements for single nozzle configuration."""
        apply_nozzle_config_to_screen(self, 'filament_management_screen')

    def _on_status_updated(self, status: str):
        """Enable/disable change buttons based on printer status.

        Printing/Paused: disable only nozzle change; keep material change enabled.
        Offline: disable both types. Operational: enable all.
        The extruder type selector is idle-only: switching moves carriages
        and cools the deactivated head, so it locks during a print too.
        """
        nozzle_disabled = status in ("Printing", "Paused", "Offline")
        material_disabled = status == "Offline"

        self.changeTool0Button.setDisabled(nozzle_disabled)
        self.changeTool1Button.setDisabled(nozzle_disabled)
        self.changeTool0MaterialBayA.setDisabled(material_disabled)
        self.changeTool1MaterialBayX.setDisabled(material_disabled)
        if self.extruderTypeComboBox is not None:
            self.extruderTypeComboBox.setDisabled(status in ("Printing", "Paused", "Offline"))

    # --- Hybrid IDEX: extruder type selector (Pellet / Filament) ---
    def _setup_extruder_type_selector(self):
        """Add the always-visible extruder type selector to the header.

        Hybrid IDEX only. The machine presents as a single-extruder
        printer - this dropdown is how the customer switches it between
        "single pellet printer" and "single filament printer". Switching
        is a runtime action (SET_EXTRUDER_MODE): no firmware copy, no
        Klipper restart, no reboot - the firmware cools the deactivated
        head, swaps carriages and the UI re-skins live.
        """
        if not is_hybrid_printer():
            return
        try:
            header_layout = self.findChild(QHBoxLayout, "horizontalLayout_4")
            if header_layout is None:
                self.logger.error("Header layout not found - extruder type selector not added")
                return

            combo = QComboBox(self)
            combo.setObjectName("extruderTypeComboBox")
            combo.setFont(dialog.font(size=14))
            combo.setMinimumSize(QtCore.QSize(280, 50))
            combo.setStyleSheet(
                """
                QComboBox#extruderTypeComboBox {
                    background-color: #ffffff; color: #000000;
                    border: 1px solid #c7c7c7; border-radius: 12px;
                    padding: 4px 12px; padding-right: 36px;
                }
                QComboBox#extruderTypeComboBox::drop-down {
                    background-color: #f0f0f0; border-left: 1px solid #c7c7c7; width: 32px;
                    border-top-right-radius: 12px; border-bottom-right-radius: 12px;
                }
                QComboBox#extruderTypeComboBox::down-arrow {
                    image: url(:/Navigation/img/Navigation/arrows-5.png);
                    width: 14px; height: 14px;
                }
                QComboBox#extruderTypeComboBox QAbstractItemView {
                    background-color: #ffffff; color: #000000;
                    selection-background-color: #0078D7; selection-color: #ffffff;
                }
                QComboBox#extruderTypeComboBox:disabled {
                    background-color: #d9d9d9; color: #777777;
                }
                """
            )
            for display_name, mode in EXTRUDER_TYPES:
                combo.addItem(display_name, mode)
            # 'activated' fires only on user interaction, so programmatic
            # refreshes never trigger a mode change
            combo.activated.connect(self._on_extruder_type_selected)
            # Between the title label (stretch 4) and the back button (stretch 1)
            header_layout.insertWidget(1, combo, 2)
            self.extruderTypeComboBox = combo

            # Single-extruder presentation: name the bays by head type,
            # not by tool number
            if self.findChild(QLabel, "calibrateLabel_6"):
                self.findChild(QLabel, "calibrateLabel_6").setText("Pellet Extruder")
            if self.findChild(QLabel, "calibrateLabel_7"):
                self.findChild(QLabel, "calibrateLabel_7").setText("Filament Extruder")

            self._refresh_extruder_type_selection()
            self.logger.info("Extruder type selector added to material/nozzle screen")
        except Exception as e:
            self.logger.error(f"Error setting up extruder type selector: {e}")

    def _refresh_extruder_type_selection(self, mode=None):
        """Point the selector at the active extruder mode without firing signals."""
        if self.extruderTypeComboBox is None:
            return
        try:
            if mode is None:
                model = getattr(self.main_window, 'printer_model', None)
                mode = getattr(model, 'extruder_mode', None) or get_extruder_mode()
            for i in range(self.extruderTypeComboBox.count()):
                if self.extruderTypeComboBox.itemData(i) == mode:
                    if self.extruderTypeComboBox.currentIndex() != i:
                        self.extruderTypeComboBox.blockSignals(True)
                        self.extruderTypeComboBox.setCurrentIndex(i)
                        self.extruderTypeComboBox.blockSignals(False)
                    break
        except Exception as e:
            self.logger.error(f"Error refreshing extruder type selection: {e}")

    def _on_extruder_type_selected(self, index):
        """Handle a customer selection in the extruder type dropdown."""
        try:
            selected_mode = self.extruderTypeComboBox.itemData(index)
            selected_display = self.extruderTypeComboBox.itemText(index)
            model = self.main_window.printer_model
            current_mode = getattr(model, 'extruder_mode', 'pellet')

            if selected_mode == current_mode:
                return

            # Idle-only. The firmware refuses a busy switch too - this
            # guard just gives a friendlier message before anything is sent.
            status = getattr(model, 'printer_status', None)
            if status in ("Printing", "Paused"):
                dialog.WarningOk(
                    self,
                    "The extruder type cannot be changed while a print is "
                    "running or paused.\n\nFinish or cancel the print first.",
                    overlay=True
                )
                self._refresh_extruder_type_selection(current_mode)
                return
            if status == "Offline":
                dialog.WarningOk(self, "Printer is offline - cannot switch extruder type.", overlay=True)
                self._refresh_extruder_type_selection(current_mode)
                return

            other = "Filament" if selected_mode == "pellet" else "Pellet"
            if not dialog.WarningYesNo(
                self,
                f"Switch the printer to {selected_display} mode?\n\n"
                f"The {other} extruder will be parked and its heaters turned "
                "off. The printer will home first, then reconfigure and "
                "restart.\n\n"
                "Make sure the bed is clear. This takes about a minute.",
                overlay=True
            ):
                self._refresh_extruder_type_selection(current_mode)
                return

            self._perform_extruder_mode_switch(selected_mode, selected_display, current_mode)
        except Exception as e:
            self.logger.error(f"Error switching extruder type: {e}")
            dialog.WarningOk(self, f"Error switching extruder type: {e}", overlay=True)

    def _perform_extruder_mode_switch(self, mode, display_name, previous_mode):
        """Swap the Klipper config to the requested extruder mode and restart.

        Ordered so the machine is never left in a state where the parked
        carriage could be hit:

          1. PREPARE_EXTRUDER_MODE_SWITCH - refuses if busy, homes so BOTH
             carriages sit on their own endstops, kills the heaters and
             flushes live calibration into the SAVE_CONFIG block.
          2. set_extruder_mode() - files the outgoing mode's calibration
             away, flips the MODE_*.cfg include, restores the incoming
             mode's calibration and toggles [mcu E1].
          3. restore_octoprint_configs() - regenerates the printer profile
             and the per-mode gcode scripts (the cooldown script differs:
             pellet has an H0 barrel heater to switch off, filament does not).
          4. FIRMWARE_RESTART - Klipper comes back as the other machine.

        Step 1 is gcode and therefore asynchronous; the wait below gives it
        time to finish homing before the config is rewritten underneath it.
        """
        from utils.printer_config_manager import (
            get_printer_config_manager, get_current_printer_selection,
            restore_octoprint_configs,
        )
        progress = None
        try:
            self.extruderTypeComboBox.setDisabled(True)
            progress = dialog.dialog(
                self,
                f"Switching to {display_name}...\n\n"
                "Homing and parking, then reconfiguring.\n"
                "Please do not power off the printer.",
                buttons=QtWidgets.QMessageBox.NoButton,
                overlay=True,
                format_text=False,
            )
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents)

            # 1. Safe state. Blocking-ish: the gcode queue drains through
            #    M400 inside the macro, and we give it a generous window.
            self.octoprint_client.gcode(command='PREPARE_EXTRUDER_MODE_SWITCH')
            self._wait_ms(45000, "homing and parking")

            # 1b. RE-CHECK before touching printer.cfg.
            #
            # PREPARE_EXTRUDER_MODE_SWITCH refuses if the machine is busy,
            # but it does so asynchronously - gcode() is fire-and-forget, so
            # a refusal (or a failed G28) does not surface here. Without
            # this guard the config would be rewritten regardless, which in
            # the worst case means swapping the machine's kinematics out
            # from under a print that started in the window between the
            # status check above and the macro actually running.
            #
            # Only proceed from a clean idle state. Anything else - a print
            # that slipped in, or Klipper faulting on a failed home - aborts
            # with the previous configuration untouched.
            status = getattr(self.main_window.printer_model, 'printer_status', None)
            if status != "Operational":
                raise RuntimeError(
                    f"printer is not idle after homing (state: {status or 'unknown'}). "
                    "Nothing was changed - check the printer and try again."
                )

            # 2. Swap the config
            manager = get_printer_config_manager()
            if not manager.set_extruder_mode(mode):
                raise RuntimeError("failed to rewrite printer.cfg")

            # 3. Regenerate OctoPrint's profile + per-mode gcode scripts
            current_printer = get_current_printer_selection()
            if current_printer:
                restore_octoprint_configs(current_printer)

            # 4. Restart Klipper into the new configuration
            controller = getattr(self.main_window, 'controller', None)
            if controller is not None:
                # Suppress the transient MCU-reset errors a restart emits
                controller._klipper_restart_in_progress = True
            self.octoprint_client.gcode(command='FIRMWARE_RESTART')
            self._wait_ms(15000, "restarting Klipper")

            # Refresh the plugin's cached view of the machine
            self.main_window.printer_model.reload_printer_configuration()
            self.main_window.printer_model.update_extruder_mode(mode)

            if progress:
                progress.hide()
                progress.deleteLater()
                progress = None
            dialog.WarningOk(
                self,
                f"Now configured as a {display_name} printer.\n\n"
                "Home the machine before printing.",
                overlay=True,
            )
        except Exception as e:
            self.logger.exception(f"Extruder mode switch failed: {e}")
            if progress:
                progress.hide()
                progress.deleteLater()
                progress = None
            dialog.WarningOk(
                self,
                f"Could not switch extruder type:\n\n{e}\n\n"
                "The printer has been left in its previous configuration.",
                overlay=True,
            )
            self._refresh_extruder_type_selection(previous_mode)
        finally:
            if progress:
                progress.hide()
                progress.deleteLater()
            self.extruderTypeComboBox.setDisabled(False)

    def _wait_ms(self, milliseconds, what):
        """Keep the UI responsive while waiting for a slow printer action."""
        self.logger.info(f"Waiting up to {milliseconds}ms: {what}")
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(milliseconds, loop.quit)
        loop.exec_()

    def on_extruder_mode_applied(self, mode):
        """Keep the selector in sync when the mode is applied/re-applied.

        Called by apply_extruder_mode_to_all_screens; the bay frames are
        already shown/hidden by the mode visibility pass.
        """
        self._refresh_extruder_type_selection(mode)

    def showEvent(self, event):
        """Reset to main_material_nozzle_page whenever this widget is shown from main window navigation."""
        super().showEvent(event)
        try:
            self.material_nozzle_stacked_widget.setCurrentWidget(self.main_material_nozzle_page)
            self.logger.debug("Reset stacked widget to main_material_nozzle_page on show")
            # Poll pellet sensors when screen is shown
            self._poll_pellet_sensors()
            # Re-query the extruder mode so the selector reflects
            # variables.cfg even if the mode was changed outside the UI
            if is_hybrid_printer() and self.extruderTypeComboBox is not None:
                self._refresh_extruder_type_selection()
                self.octoprint_client.gcode(command='QUERY_EXTRUDER_MODE')
        except Exception as e:
            self.logger.error(f"Error in showEvent: {e}")

    def _initialize_sub_screens(self):
        """Initialize all filament/nozzle sub-screens"""
        try:
            # Nozzle change wizard is always available; pellet loading uses a
            # dialog, while filament heads need the load/unload wizard.
            self.screens["nozzle_change"] = NozzleChangeWizard(self.main_window)
            if is_hybrid_printer():
                self.screens["change_filament"] = ChangeFilamentWizard(self.main_window)

            # Add each screen to the stacked widget
            for name, screen in self.screens.items():
                self.material_nozzle_stacked_widget.addWidget(screen)
                self.logger.info(f"Added {name} screen to material/nozzle stacked widget")
            
        except Exception as e:
            self.logger.exception(f"Error initializing sub-screens: {e}")

    def _open_loading_dialog(self, message="Please wait, loading..."):
        """Show a lightweight non-blocking loading dialog using utils.dialog.

        Args:
            message: Message shown to the user while the sub-UI initializes.
        """
        try:
            if self._loading_dialog:
                return
            # Use centralized dialog helper (non-blocking, no buttons, with overlay)
            self._loading_dialog = dialog.dialog(
                self,
                message,
                buttons=QtWidgets.QMessageBox.NoButton,
                overlay=False,
                format_text=False
            )
            # Force a paint so the dialog is visible before doing heavy work
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents)
        except Exception as e:
            self.logger.error(f"Failed to show loading dialog: {e}")

    def _close_loading_dialog(self):
        """Safely hide and destroy the loading dialog if it is visible."""
        try:
            if self._loading_dialog:
                self._loading_dialog.hide()
                self._loading_dialog.deleteLater()
                self._loading_dialog = None
        except Exception as e:
            self.logger.error(f"Failed to close loading dialog: {e}")

    def _navigate_to_screen(self, screen, params, target_screen):
        """Finish navigation after the loading dialog has painted.

        Calls the sub-screen setup (if available), switches the stacked widget,
        and then closes the loading dialog.

        Args:
            screen: The QWidget sub-screen instance to show.
            params: Optional parameters forwarded to the sub-screen setup().
            target_screen: Name of the target screen for logging purposes.
        """
        try:
            if params and hasattr(screen, 'setup'):
                screen.setup(params)
            self.material_nozzle_stacked_widget.setCurrentWidget(screen)
            self.logger.info(f"Navigated to {target_screen}")
        except Exception as e:
            self.logger.exception(f"Failed navigating to {target_screen}: {e}")
        finally:
            self._close_loading_dialog()

    def show_material_nozzle_screen(self, target_screen=None, params=None):
        """Show the main page or navigate to a specific sub-screen."""
        self.logger.debug(f"show_material_nozzle_screen called with target_screen={target_screen}, params={params}")

        if self.main_window.current_screen != self:
            self.main_window.switch_screen(self)

        if not target_screen:
            self.material_nozzle_stacked_widget.setCurrentWidget(self.main_material_nozzle_page)
            self.logger.debug("Showing main material/nozzle page")
            return

        screen = self.screens.get(target_screen)
        if not screen:
            self.logger.error(f"Requested screen '{target_screen}' not found in available screens")
            return

        self._open_loading_dialog("Please wait, loading...")
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents)
        QtCore.QTimer.singleShot(0, lambda: self._navigate_to_screen(screen, params, target_screen))

    # --- New: UI state updates from model ---
    def _status_to_style(self, status: str) -> str:
        # Mapping: Loaded=green, Unknown=red, Empty=amber, Staged=blue
        if status == "Loaded":
            return styles.printer_status_green
        if status == "Unknown":
            return styles.printer_status_red
        if status == "Empty":
            return styles.printer_status_amber
        if status == "Staged":
            return styles.printer_status_blue
        return styles.printer_status_amber

    def _apply_tool_ui(self, tool: str, data: dict):
        filament = data.get("filament") or "Unknown"
        status = data.get("status", "Unknown")
        display_filament = "-" if status == "Empty" else str(filament)
        nozzle = data.get("nozzle", "Unknown")
        if tool == "tool0":
            # Show currently loaded material on the button itself
            if self.changeTool0MaterialBayA:
                self.changeTool0MaterialBayA.setText(display_filament)
            if self.tool0MaterialBayAStateLabel:
                self.tool0MaterialBayAStateLabel.setText(str(status))
            if self.tool0MaterialBayAStateColor:
                self.tool0MaterialBayAStateColor.setStyleSheet(self._status_to_style(status))
            if self.changeTool0Button:
                self.changeTool0Button.setText("Unknown" if nozzle == "Unknown" or not nozzle else f"{nozzle} mm")
        elif tool == "tool1":
            if self.changeTool1MaterialBayX:
                self.changeTool1MaterialBayX.setText(display_filament)
            if self.tool1MaterialBayXStateLabel:
                self.tool1MaterialBayXStateLabel.setText(str(status))
            if self.tool11MaterialBayXStateColor:
                self.tool11MaterialBayXStateColor.setStyleSheet(self._status_to_style(status))
            if self.changeTool1Button:
                self.changeTool1Button.setText("Unknown" if nozzle == "Unknown" or not nozzle else f"{nozzle} mm")

    def _on_tool_states_loaded(self, states: dict):
        # Use primary bays for current UI
        m = self.main_window.printer_model
        t0 = m.get_bay_state("tool0")
        t1 = m.get_bay_state("tool1")
        self._apply_tool_ui("tool0", t0)
        self._apply_tool_ui("tool1", t1)

    def _on_tool_state_changed(self, tool: str, bay: str, data: dict):
        # For now, reflect only primary bay changes on screen
        if bay == self.main_window.printer_model.get_default_bay(tool):
            self._apply_tool_ui(tool, data)

    # --- Pellet Sensor Polling & Display ---
    def _poll_pellet_sensors(self):
        """Poll the pellet sensor states by sending QUERY_FILAMENT_SENSOR commands.
        
        Sends G-code commands to Klipper to query the pellet sensor states.
        The responses are parsed by the websocket client and update the
        pellet_sensor_state_map in printer_model.
        """
        try:
            # Send query commands to Klipper - responses are parsed by websocket_client.
            # pellet_sensor_right only exists on dual *pellet* printers: single nozzle
            # machines have no right hopper, and the Hybrid IDEX has a filament head there.
            has_right_hopper = is_dual_nozzle_printer() and not is_hybrid_printer()
            if has_right_hopper:
                self.octoprint_client.gcode(
                    command='QUERY_FILAMENT_SENSOR SENSOR=pellet_sensor_left\n'
                            'QUERY_FILAMENT_SENSOR SENSOR=pellet_sensor_right'
                )
            else:
                self.octoprint_client.gcode(
                    command='QUERY_FILAMENT_SENSOR SENSOR=pellet_sensor_left'
                )
            self.logger.debug("Sent pellet sensor query commands")

            # Also update UI from current state map (may have been updated by previous responses)
            model = self.main_window.printer_model
            sensor_map = getattr(model, 'pellet_sensor_state_map', {})

            # Get sensor states (True = pellets detected, False = empty)
            left_detected = sensor_map.get('pellet_sensor_left', None)

            # Update UI for tool0 (left)
            self._update_pellet_sensor_display("tool0", left_detected)

            # Update UI for tool1 (right) — dual pellet nozzle only. On a Hybrid
            # IDEX tool1's label shows its filament bay state instead.
            if has_right_hopper:
                right_detected = sensor_map.get('pellet_sensor_right', None)
                self._update_pellet_sensor_display("tool1", right_detected)
                self.logger.debug(f"Pellet sensors state - Left: {left_detected}, Right: {right_detected}")
            else:
                self.logger.debug(f"Pellet sensors state - Left: {left_detected} (no right hopper)")
        except Exception as e:
            self.logger.error(f"Error polling pellet sensors: {e}")

    def _on_pellet_sensor_state(self, sensor: str, is_ok: bool):
        """Handle real-time pellet sensor state changes from printer_model signal.
        
        Args:
            sensor: Sensor name ('pellet_sensor_left' or 'pellet_sensor_right')
            is_ok: True if pellets detected, False if empty
        """
        try:
            if sensor == 'pellet_sensor_left':
                self._update_pellet_sensor_display("tool0", is_ok)
            elif sensor == 'pellet_sensor_right' and not is_filament_tool("tool1"):
                self._update_pellet_sensor_display("tool1", is_ok)
            self.logger.debug(f"Pellet sensor state changed - {sensor}: {is_ok}")
        except Exception as e:
            self.logger.error(f"Error handling pellet sensor state: {e}")

    def _update_pellet_sensor_display(self, tool: str, pellets_detected):
        """Update the UI to show pellet sensor state for a given tool.
        
        Args:
            tool: "tool0" or "tool1"
            pellets_detected: True if pellets present, False if empty, None if unknown
        """
        if pellets_detected is None:
            status_text = "Unknown"
            status_style = styles.printer_status_red
        elif pellets_detected:
            status_text = "Pellets OK"
            status_style = styles.printer_status_green
        else:
            status_text = "Empty"
            status_style = styles.printer_status_amber
        
        if tool == "tool0":
            if self.tool0MaterialBayAStateLabel:
                self.tool0MaterialBayAStateLabel.setText(status_text)
            if self.tool0MaterialBayAStateColor:
                self.tool0MaterialBayAStateColor.setStyleSheet(status_style)
        elif tool == "tool1":
            if self.tool1MaterialBayXStateLabel:
                self.tool1MaterialBayXStateLabel.setText(status_text)
            if self.tool11MaterialBayXStateColor:
                self.tool11MaterialBayXStateColor.setStyleSheet(status_style)

    # --- Material change routing ---
    def _on_material_button_clicked(self, tool: str):
        """Route a material change to the right flow for the tool's extruder head.

        Pellet heads open the line vac load dialog; filament heads (T1 on a
        Hybrid IDEX) open the filament load/unload wizard.
        """
        if is_filament_tool(tool):
            self.show_material_nozzle_screen(target_screen="change_filament", params={"tool": tool})
        else:
            self._show_pellet_load_dialog(tool)

    # --- Pellet Loading Dialog ---
    def _show_pellet_load_dialog(self, tool: str):
        """Show a dialog to control the line vac for loading pellets into the hopper.

        Args:
            tool: "tool0" or "tool1"
        """
        if is_filament_tool(tool):
            self.logger.error(f"Pellet load dialog requested for filament head {tool} - ignoring")
            return

        tool_num = "0" if tool == "tool0" else "1"
        tool_name = "Left (T0)" if tool == "tool0" else "Right (T1)"
        vac_pin = "pellet_vac_left" if tool == "tool0" else "pellet_vac_right"

        self.logger.info(f"Opening pellet load dialog for {tool}")
        
        # Track vac state
        self._pellet_vac_on = False
        
        # Create dialog
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Load Pellets - {tool_name}")
        dlg.setMinimumSize(400, 200)
        dlg.setModal(True)
        
        # Apply styling
        base_font = dialog.font(size=14)
        dlg.setFont(base_font)
        dlg.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #ffffff; font-size: 14px; }
            QPushButton { 
                background-color: #3d3d3d; 
                color: #ffffff; 
                border: 1px solid #555555; 
                border-radius: 8px; 
                padding: 15px 30px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:pressed { background-color: #5d5d5d; }
            QPushButton:checked { background-color: #4CAF50; border-color: #4CAF50; }
        """)
        
        layout = QVBoxLayout(dlg)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Instructions
        instructions = QLabel(f"Press and hold the button below to turn on\nthe line vac and load pellets into {tool_name}.")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)
        
        # Toggle button for line vac
        self._vac_button = QPushButton("Hold to Load Pellets")
        self._vac_button.setCheckable(True)
        self._vac_button.setMinimumHeight(60)
        
        def on_vac_pressed():
            """Turn on vac when button pressed (VALUE=1 = relay ON with inverted pin)"""
            try:
                self.octoprint_client.gcode(command=f'SET_PIN PIN={vac_pin} VALUE=1')
                self._vac_button.setText("Loading... (Release to Stop)")
                self._pellet_vac_on = True
                self.logger.info(f"Line vac ON for {tool}")
            except Exception as e:
                self.logger.error(f"Failed to turn on line vac: {e}")
        
        def on_vac_released():
            """Turn off vac when button released (VALUE=0 = relay OFF with inverted pin)"""
            try:
                self.octoprint_client.gcode(command=f'SET_PIN PIN={vac_pin} VALUE=0')
                self._vac_button.setText("Hold to Load Pellets")
                self._vac_button.setChecked(False)
                self._pellet_vac_on = False
                self.logger.info(f"Line vac OFF for {tool}")
                # Poll sensors after loading to update status
                self._poll_pellet_sensors()
            except Exception as e:
                self.logger.error(f"Failed to turn off line vac: {e}")
        
        self._vac_button.pressed.connect(on_vac_pressed)
        self._vac_button.released.connect(on_vac_released)
        layout.addWidget(self._vac_button)
        
        # Done button
        btn_layout = QHBoxLayout()
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(dlg.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(done_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Ensure vac is off when dialog closes (VALUE=0 = relay OFF with inverted pin)
        def on_dialog_finished():
            if self._pellet_vac_on:
                try:
                    self.octoprint_client.gcode(command=f'SET_PIN PIN={vac_pin} VALUE=0')
                    self.logger.info(f"Line vac OFF (dialog closed) for {tool}")
                except Exception as e:
                    self.logger.error(f"Failed to turn off line vac on close: {e}")
        
        dlg.finished.connect(on_dialog_finished)
        
        dlg.exec_()

    # --- New: Edit dialog to sync reality without wizard ---
    def _open_edit_dialog(self, tool: str):
        model = self.main_window.printer_model
        current = model.get_bay_state(tool)
        filament_names = list(getattr(model, 'filaments', config.filaments).keys())

        dialog_widget = QDialog(self)
        dialog_widget.setObjectName("EditToolStateDialog")
        # Title: Edit Tool * Material Bay ** (e.g., Tool 0, Bay A/X)
        try:
            default_bay = model.get_default_bay(tool)
            if default_bay:
                bay_letter = default_bay.split("_")[-1].upper()
            else:
                bay_letter = "A" if tool == "tool0" else "X"
            tool_num = tool.replace("tool", "") if isinstance(tool, str) else str(tool)
            dialog_widget.setWindowTitle(f"Edit Tool {tool_num} Material Bay {bay_letter}")
        except Exception:
            dialog_widget.setWindowTitle(f"Edit Tool State")
        # Make dialog larger and easier to read
        dialog_widget.setMinimumSize(450, 250)
        # Use shared dialog font (Gotham) for consistency with other dialogs (bumped +1pt)
        base_font = dialog.font(size=15)
        dialog_widget.setFont(base_font)
        # Keep the dialog visible above to avoid getting lost behind other widgets
        try:
            dialog_widget.setWindowFlags(dialog_widget.windowFlags() | Qt.WindowStaysOnTopHint)
            dialog_widget.setModal(True)
        except Exception:
            pass
        # Apply a light palette to avoid inherited dark theme artifacts
        try:
            pal = dialog_widget.palette()
            pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#ffffff"))
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#ffffff"))
            pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#f5f5f5"))
            pal.setColor(QtGui.QPalette.Text, QtGui.QColor("#000000"))
            pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#000000"))
            pal.setColor(QtGui.QPalette.Button, QtGui.QColor("#f5f5f5"))
            pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#000000"))
            pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#0078D7"))
            pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
            dialog_widget.setPalette(pal)
            dialog_widget.setAutoFillBackground(True)
        except Exception:
            pass
        # Ensure strong contrast with a white background while keeping native look
        try:
            dialog_widget.setStyleSheet(
                """
                #EditToolStateDialog, #EditToolStateDialog QWidget, #EditToolStateDialog QFrame { background-color: #ffffff; color: #000000; }
                #EditToolStateDialog QLabel { color: #000000; background-color: transparent; }
                #EditToolStateDialog QLineEdit, #EditToolStateDialog QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #c7c7c7; border-radius: 4px; padding: 4px; padding-right: 30px; }
                #EditToolStateDialog QComboBox:!editable { background-color: #ffffff; }
                #EditToolStateDialog QComboBox::drop-down { background-color: #f0f0f0; border-left: 1px solid #c7c7c7; width: 30px; }
                #EditToolStateDialog QComboBox::down-arrow { image: url(:/Navigation/img/Navigation/arrows-5.png); width: 12px; height: 12px; }
                #EditToolStateDialog QComboBox QAbstractItemView, #EditToolStateDialog QComboBox QListView { background-color: #ffffff; color: #000000; selection-background-color: #0078D7; selection-color: #ffffff; }
                #EditToolStateDialog QListView { background-color: #ffffff; color: #000000; }
                #EditToolStateDialog QListView::item { padding: 6px 8px; }
                #EditToolStateDialog QPushButton { background-color: #f5f5f5; color: #000000; border: 1px solid #c7c7c7; border-radius: 4px; padding: 10px 18px; }
                #EditToolStateDialog QPushButton:disabled { color: #888888; }
                #EditToolStateDialog QDialogButtonBox QPushButton { min-width: 120px; }
                """
            )
        except Exception:
            pass
        form = QFormLayout(dialog_widget)
        try:
            form.setHorizontalSpacing(20)
            form.setVerticalSpacing(14)
            form.setContentsMargins(20, 20, 20, 12)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        except Exception:
            pass

        cb_filament = QComboBox(dialog_widget)
        cb_filament.setFont(base_font)
        try:
            cb_filament.setMinimumWidth(220)
        except Exception:
            pass
        try:
            cb_filament.setStyleSheet("QComboBox { background-color: #ffffff; color: #000000; } QComboBox QAbstractItemView, QComboBox QListView { background-color: #ffffff; color: #000000; selection-background-color: #0078D7; selection-color: #ffffff; }")
        except Exception:
            pass
        try:
            lv_f = QtWidgets.QListView(dialog_widget)
            lv_f.setFont(base_font)
            lv_f.setStyleSheet("QListView { background-color: #ffffff; color: #000000; } QListView::item:selected { background: #0078D7; color: #ffffff; }")
            pal_list = lv_f.palette()
            pal_list.setColor(QtGui.QPalette.Base, QtGui.QColor("#ffffff"))
            pal_list.setColor(QtGui.QPalette.Text, QtGui.QColor("#000000"))
            lv_f.setPalette(pal_list)
            cb_filament.setView(lv_f)
        except Exception:
            pass
        cb_filament.addItem("(None)")
        for f in filament_names:
            cb_filament.addItem(f)
        if current.get("filament"):
            idx = cb_filament.findText(current.get("filament"))
            if idx >= 0:
                cb_filament.setCurrentIndex(idx)

        cb_status = QComboBox(dialog_widget)
        cb_status.setFont(base_font)
        try:
            cb_status.setMinimumWidth(220)
        except Exception:
            pass
        try:
            cb_status.setStyleSheet("QComboBox { background-color: #ffffff; color: #000000; } QComboBox QAbstractItemView, QComboBox QListView { background-color: #ffffff; color: #000000; selection-background-color: #0078D7; selection-color: #ffffff; }")
        except Exception:
            pass
        try:
            lv_s = QtWidgets.QListView(dialog_widget)
            lv_s.setFont(base_font)
            lv_s.setStyleSheet("QListView { background-color: #ffffff; color: #000000; } QListView::item:selected { background: #0078D7; color: #ffffff; }")
            pal_list2 = lv_s.palette()
            pal_list2.setColor(QtGui.QPalette.Base, QtGui.QColor("#ffffff"))
            pal_list2.setColor(QtGui.QPalette.Text, QtGui.QColor("#000000"))
            lv_s.setPalette(pal_list2)
            cb_status.setView(lv_s)
        except Exception:
            pass
        for s in getattr(model, 'status_options', ["Empty", "Unknown", "Loaded", "Staged"]):
            cb_status.addItem(s)
        idx = cb_status.findText(current.get("status", "Unknown"))
        if idx >= 0:
            cb_status.setCurrentIndex(idx)

        cb_nozzle = QComboBox(dialog_widget)
        cb_nozzle.setFont(base_font)
        try:
            cb_nozzle.setMinimumWidth(220)
        except Exception:
            pass
        try:
            cb_nozzle.setStyleSheet("QComboBox { background-color: #ffffff; color: #000000; } QComboBox QAbstractItemView, QComboBox QListView { background-color: #ffffff; color: #000000; selection-background-color: #0078D7; selection-color: #ffffff; }")
        except Exception:
            pass
        try:
            lv_n = QtWidgets.QListView(dialog_widget)
            lv_n.setFont(base_font)
            lv_n.setStyleSheet("QListView { background-color: #ffffff; color: #000000; } QListView::item:selected { background: #0078D7; color: #ffffff; }")
            pal_list3 = lv_n.palette()
            pal_list3.setColor(QtGui.QPalette.Base, QtGui.QColor("#ffffff"))
            pal_list3.setColor(QtGui.QPalette.Text, QtGui.QColor("#000000"))
            lv_n.setPalette(pal_list3)
            cb_nozzle.setView(lv_n)
        except Exception:
            pass
        cb_nozzle.addItem("Unknown")
        for n in model.nozzle_options_for_tool(tool):
            cb_nozzle.addItem(n)
        idx = cb_nozzle.findText(current.get("nozzle", "Unknown"))
        if idx >= 0:
            cb_nozzle.setCurrentIndex(idx)

        # Create explicit labels so we can enforce the same font size as the dialog
        lab_filament = QLabel("Filament", dialog_widget)
        lab_filament.setFont(base_font)
        lab_status = QLabel("Status", dialog_widget)
        lab_status.setFont(base_font)
        lab_nozzle = QLabel("Nozzle", dialog_widget)
        lab_nozzle.setFont(base_font)

        form.addRow(lab_filament, cb_filament)
        form.addRow(lab_status, cb_status)
        form.addRow(lab_nozzle, cb_nozzle)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog_widget)
        try:
            buttons.setFont(base_font)
            # Set OK/Cancel button fonts to an absolute 14px
            for btn in buttons.buttons():
                f = btn.font()
                try:
                    f.setPixelSize(14)
                except Exception:
                    try:
                        f.setPointSize(14)
                    except Exception:
                        pass
                btn.setFont(f)
        except Exception:
            pass
        form.addRow(buttons)
        buttons.accepted.connect(dialog_widget.accept)
        buttons.rejected.connect(dialog_widget.reject)

        # Center the dialog relative to the parent, similar to SelfCenteringMessageBox
        try:
            dialog_widget.adjustSize()
            frameGm = dialog_widget.frameGeometry()
            centerPoint = self.frameGeometry().center()
            frameGm.moveCenter(centerPoint)
            dialog_widget.move(frameGm.topLeft())
        except Exception:
            pass

        if dialog_widget.exec_() == QDialog.Accepted:
            filament = cb_filament.currentText()
            if filament == "(None)":
                filament = None
            status = cb_status.currentText()
            nozzle = cb_nozzle.currentText()
            try:
                model.update_tool_bay_state(tool, filament=filament, status=status, nozzle=nozzle, persist=True)
            except Exception as e:
                self.logger.error(f"Failed to set tool state: {e}")


