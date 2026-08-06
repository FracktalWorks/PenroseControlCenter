import time

import os
from PyQt5 import uic
from PyQt5 import QtGui, QtCore
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QWidget, QPushButton, QSpinBox, QTabWidget, QToolButton, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QLabel
from utils.helpers import check_ui_elements
from utils.logger import get_logger
from utils.printer_ui_config import apply_nozzle_config_to_screen, is_dual_nozzle_printer, is_hybrid_printer
from utils import dialog

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


logger = get_logger(__name__)

class ControlScreen(QWidget):
    def __init__(self, main_window):
        super(ControlScreen, self).__init__()
        self.main_window = main_window
        self.octoprint_client = main_window.octoprint_client

        # Use centralized logger
        self.logger = get_logger(self.__class__.__name__)

        # Load the UI
        try:
            # Use relative path from the current module's directory
            ui_file_path = os.path.join(os.path.dirname(__file__), "control_screen.ui")
            uic.loadUi(ui_file_path, self)
            self.logger.info("ControlScreen UI loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load ControlScreen UI file: {e}", exc_info=True)

        # Initialize UI components
        self.controlTabWidget = self.findChild(QTabWidget, "controlTabWidget")
        self.controlBackButton = self.findChild(QPushButton, "controlBackButton")

        # Tab widgets
        self.tuneTab = self.findChild(QWidget, "tuneTab")
        self.temperatureTab = self.findChild(QWidget, "temperatureTab")
        self.motionTab = self.findChild(QWidget, "motionTab")
        self.preferencesTab = self.findChild(QWidget, "preferencesTab")

        # Feed rate controls (now in tuneTab)
        self.feedRateSpinBox = self.findChild(QSpinBox, "feedRateSpinBox")
        self.setFeedRateButton = self.findChild(QPushButton, "setFeedRateButton")
        self.moveZPBabyStep = self.findChild(QPushButton, "moveZPBabyStep")
        self.moveZMBabyStep = self.findChild(QPushButton, "moveZMBabyStep")

        # Flow rate controls (now in tuneTab)
        self.flowRateSpinBox = self.findChild(QSpinBox, "flowRateSpinBox")
        self.setFlowRateButton = self.findChild(QPushButton, "setFlowRateButton")

        # Preferences controls
        self.togglePelletSensorT0Button = self.findChild(QPushButton, "togglePelletSensorT0Button")
        self.togglePelletSensorT1Button = self.findChild(QPushButton, "togglePelletSensorT1Button")
        self.toggleAutoResumeButton = self.findChild(QPushButton, "toggleAutoResumeButton")
        self.toggleCheckPrintCompatibilityButton = self.findChild(QPushButton, "toggleCheckPrintCompatibilityButton")
        self.togglePrintRestoreButton = self.findChild(QPushButton, "togglePrintRestoreButton")

        # Temperature controls
        self.fanOnButton = self.findChild(QPushButton, "fanOnButton")
        self.fanOffButton = self.findChild(QPushButton, "fanOffButton")
        self.cooldownButton = self.findChild(QPushButton, "cooldownButton")
        self.toolTempSpinBox = self.findChild(QSpinBox, "toolTempSpinBox")
        self.setToolTempButton = self.findChild(QPushButton, "setToolTempButton")
        self.bedTempSpinBox = self.findChild(QSpinBox, "bedTempSpinBox")
        self.setBedTempButton = self.findChild(QPushButton, "setBedTempButton")
        self.toolToggleTemperatureButton = self.findChild(QPushButton, "toolToggleTemperatureButton")
        self.tool180PreheatButton = self.findChild(QPushButton, "tool180PreheatButton")
        self.tool250PreheatButton = self.findChild(QPushButton, "tool250PreheatButton")
        self.bed60PreheatButton = self.findChild(QPushButton, "bed60PreheatButton")
        self.bed100PreheatButton = self.findChild(QPushButton, "bed100PreheatButton")

        # Ring heater temperature controls (legacy - may not exist)
        self.ringTempSpinBox = self.findChild(QSpinBox, "ringTempSpinBox")
        self.setRingTempButton = self.findChild(QPushButton, "setRingTempButton")
        self.ring200PreheatButton = self.findChild(QPushButton, "ring200PreheatButton")
        self.ring250PreheatButton = self.findChild(QPushButton, "ring250PreheatButton")
        self.ringStatusLabel = self.findChild(QLabel, "ringStatusLabel")
        
        # Secondary Heater H0 temperature controls (Penrose)
        self.H0TempSpinBox = self.findChild(QSpinBox, "H0TempSpinBox")
        self.setH0TempButton = self.findChild(QPushButton, "setH0TempButton")
        self.H050PreheatButton = self.findChild(QPushButton, "H050PreheatButton")
        self.H090PreheatButton = self.findChild(QPushButton, "H090PreheatButton")

        # Secondary Heater H1 temperature controls (Penrose)
        self.H1TempSpinBox = self.findChild(QSpinBox, "H1TempSpinBox")
        self.setH1TempButton = self.findChild(QPushButton, "setH1TempButton")
        self.H140PreheatButton = self.findChild(QPushButton, "H140PreheatButton")
        self.H160PreheatButton = self.findChild(QPushButton, "H160PreheatButton")

        # Motion controls
        self.step1mmButton = self.findChild(QPushButton, "step1mmButton")
        self.step10mmButton = self.findChild(QPushButton, "step10mmButton")
        self.step100mmButton = self.findChild(QPushButton, "step100mmButton")
        self.moveXPButton = self.findChild(QPushButton, "moveXPButton")
        self.moveXMButton = self.findChild(QPushButton, "moveXMButton")
        self.moveYPButton = self.findChild(QPushButton, "moveYPButton")
        self.moveYMButton = self.findChild(QPushButton, "moveYMButton")
        self.motorOffButton = self.findChild(QPushButton, "motorOffButton")
        self.homeXYButton = self.findChild(QPushButton, "homeXYButton")
        self.moveZMButton = self.findChild(QPushButton, "moveZMButton")
        self.moveZPButton = self.findChild(QPushButton, "moveZPButton")
        self.homeZButton = self.findChild(QPushButton, "homeZButton")
        self.toolToggleMotionButton = self.findChild(QPushButton, "toolToggleMotionButton")
        self.extruderButton = self.findChild(QPushButton, "extruderButton")
        self.retractButton = self.findChild(QPushButton, "retractButton")
        self.purgeMaterialButton = self.findChild(QPushButton, "purgeMaterialButton")

        # Purge material continuous extrusion state
        self._purge_timer = QtCore.QTimer(self)
        self._purge_timer.setInterval(200)  # 200ms between commands: 2mm chunks at F500 take 240ms each
        self._purge_timer.timeout.connect(self._purge_extrude_tick)
        self._purging = False

        # Validate UI components (only mandatory elements)
        check_ui_elements(self, [
            self.controlTabWidget, self.controlBackButton, self.feedRateSpinBox,
            self.setFeedRateButton, self.moveZPBabyStep, self.moveZMBabyStep,
            self.fanOnButton, self.fanOffButton, self.cooldownButton,
            self.toolTempSpinBox, self.setToolTempButton, self.bedTempSpinBox,
            self.setBedTempButton,
            self.step1mmButton, self.step10mmButton,
            self.step100mmButton, self.moveXPButton, self.moveXMButton,
            self.moveYPButton, self.moveYMButton, self.flowRateSpinBox,
            self.setFlowRateButton, 
            self.tuneTab, self.temperatureTab, self.motionTab, self.preferencesTab,
            self.togglePelletSensorT0Button, self.togglePelletSensorT1Button,
            self.toggleAutoResumeButton, self.toggleCheckPrintCompatibilityButton,
            self.togglePrintRestoreButton
        ], "ControlScreen")

        # set the active extruder to 0 initially
        self.setActiveExtruder(0)  # Default to extruder 0

        # Feed Rate Buttons Signal Connections
        self.controlBackButton.clicked.connect(lambda: self.main_window.switch_to_home_screen())
        self.setFeedRateButton.clicked.connect(self.setFeedRate)
        self.moveZPBabyStep.clicked.connect(
            lambda: self.octoprint_client.gcode(command='M290 Z0.025')
        )
        self.moveZMBabyStep.clicked.connect(
            lambda: self.octoprint_client.gcode(command='M290 Z-0.025')
        )

        # Temperature Buttons Signal Connections
        self.fanOnButton.clicked.connect(lambda: self.octoprint_client.gcode(command='M106 S255'))
        self.fanOffButton.clicked.connect(lambda: self.octoprint_client.gcode(command='M107'))
        self.cooldownButton.clicked.connect(self.coolDownAction)
        self.setToolTempButton.clicked.connect(self.setToolTemp)
        self.setBedTempButton.clicked.connect(lambda: self.octoprint_client.setBedTemperature(self.bedTempSpinBox.value()))
        self.bed60PreheatButton.pressed.connect(lambda: self.preheatBedTemp(60))
        self.bed100PreheatButton.pressed.connect(lambda: self.preheatBedTemp(100))
        self.tool180PreheatButton.pressed.connect(lambda: self.preheatToolTemp(180))
        self.tool250PreheatButton.pressed.connect(lambda: self.preheatToolTemp(250))
        self.toolToggleTemperatureButton.pressed.connect(self.selectToolTemperature)

        # Ring heater signal connections (optional - may not exist in all UI versions)
        if self.setRingTempButton:
            self.setRingTempButton.clicked.connect(self.setRingTemp)
        if self.ring200PreheatButton:
            self.ring200PreheatButton.pressed.connect(lambda: self.preheatRingTemp(200))
        if self.ring250PreheatButton:
            self.ring250PreheatButton.pressed.connect(lambda: self.preheatRingTemp(250))
        
        # Secondary Heater H0 signal connections (Penrose)
        if self.setH0TempButton:
            self.setH0TempButton.clicked.connect(self.setH0Temp)
        if self.H050PreheatButton:
            self.H050PreheatButton.pressed.connect(lambda: self.preheatH0Temp(150))
        if self.H090PreheatButton:
            self.H090PreheatButton.pressed.connect(lambda: self.preheatH0Temp(190))

        # Secondary Heater H1 signal connections (Penrose)
        if self.setH1TempButton:
            self.setH1TempButton.clicked.connect(self.setH1Temp)
        if self.H140PreheatButton:
            self.H140PreheatButton.pressed.connect(lambda: self.preheatH1Temp(150))
        if self.H160PreheatButton:
            self.H160PreheatButton.pressed.connect(lambda: self.preheatH1Temp(190))

        # Motion Buttons Signal Connections
        self.step1mmButton.clicked.connect(lambda: self.setStep(1))
        self.step10mmButton.clicked.connect(lambda: self.setStep(10))
        self.step100mmButton.clicked.connect(lambda: self.setStep(100))
        self.moveXPButton.clicked.connect(lambda: self.octoprint_client.jog(x=self.step, speed=2000))
        self.moveXMButton.clicked.connect(lambda: self.octoprint_client.jog(x=-self.step, speed=2000))
        self.moveYPButton.clicked.connect(lambda: self.octoprint_client.jog(y=self.step, speed=2000))
        self.moveYMButton.clicked.connect(lambda: self.octoprint_client.jog(y=-self.step, speed=2000))
        self.motorOffButton.clicked.connect(lambda: self.octoprint_client.gcode(command='M18'))
        self.homeXYButton.clicked.connect(lambda: self.octoprint_client.home(['x', 'y']))
        self.moveZMButton.clicked.connect(lambda: self.octoprint_client.jog(z=-self.step, speed=2000))
        self.moveZPButton.clicked.connect(lambda: self.octoprint_client.jog(z=self.step, speed=2000))
        self.homeZButton.clicked.connect(lambda: self.octoprint_client.home(['z']))
        self.toolToggleMotionButton.clicked.connect(self.selectToolMotion)
        self.extruderButton.clicked.connect(self._extrude_step)
        self.retractButton.clicked.connect(self._retract_step)

        # Purge Material Button - continuous extrusion while held
        if self.purgeMaterialButton:
            self.purgeMaterialButton.pressed.connect(self._purge_start)
            self.purgeMaterialButton.released.connect(self._purge_stop)

        # Pellet Sensor Buttons Signal Connections
        self.setFlowRateButton.clicked.connect(self.setFlowRate)

        self.togglePelletSensorT0Button.clicked.connect(self.togglePelletSensorT0)

        self.togglePelletSensorT1Button.clicked.connect(self.togglePelletSensorT1)

        # Preferences Signal Connections
        self.toggleAutoResumeButton.clicked.connect(self.toggleAutoResume)
        self.toggleCheckPrintCompatibilityButton.clicked.connect(self.toggleCheckPrintCompatibility)
        self.togglePrintRestoreButton.clicked.connect(self.togglePrintRestore)

        # Configure spinboxes
        for spinbox in [self.feedRateSpinBox, self.toolTempSpinBox, self.bedTempSpinBox, self.flowRateSpinBox, 
                       self.ringTempSpinBox, self.H0TempSpinBox, self.H1TempSpinBox]:
            if spinbox:
                spinbox.lineEdit().setReadOnly(True)
                # spinbox.lineEdit().setDisabled(True)
                # Prevent text selection/highlighting by disabling focus
                spinbox.setFocusPolicy(QtCore.Qt.NoFocus)
                spinbox.lineEdit().setFocusPolicy(QtCore.Qt.NoFocus)
                # Make the highlight color match the background
                palette = QPalette()
                palette.setColor(QPalette.Highlight, QColor(255, 255, 255))
                palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
                spinbox.lineEdit().setPalette(palette)

        self.setStep(1)

        # Reflect persistent pellet sensor preferences in toggle buttons
        try:
            t0_sensor_enabled = bool(self.main_window.printer_model.pellet_sensor_t0_enabled)
            self.togglePelletSensorT0Button.setChecked(t0_sensor_enabled)
            if is_hybrid_printer():
                # T1 is a filament extruder - its toggle drives the runout switch
                t1_sensor_enabled = bool(self.main_window.printer_model.extruder_runout_enabled)
            else:
                t1_sensor_enabled = bool(self.main_window.printer_model.pellet_sensor_t1_enabled)
            self.togglePelletSensorT1Button.setChecked(t1_sensor_enabled)
            # Initialize print compatibility check button
            compatibility_enabled = bool(self.main_window.printer_model.print_compatibility_check_enabled)
            self.toggleCheckPrintCompatibilityButton.setChecked(compatibility_enabled)
            # Initialize print restore preferences
            print_restore_enabled = bool(self.main_window.printer_model.print_restore_enabled)
            self.togglePrintRestoreButton.setChecked(print_restore_enabled)
            auto_resume_enabled = bool(self.main_window.printer_model.auto_resume_enabled)
            self.toggleAutoResumeButton.setChecked(auto_resume_enabled)
            # Set auto resume button state based on print restore being enabled
            self.toggleAutoResumeButton.setEnabled(print_restore_enabled)
        except Exception as e:
            self.logger.warning(f"Failed initializing toggle buttons: {e}")

        # Connect to printer model for status updates
        self.main_window.printer_model.status_updated.connect(self.buttonStatusUpdate)
        self.main_window.printer_model.active_extruder_changed.connect(self.setActiveExtruder)
        self.logger.debug("Connected ControlScreen to printer model status updates")

        # Initialize spinboxes with current values from printer model
        try:
            if hasattr(self.main_window.printer_model, 'current_feed_rate'):
                self.feedRateSpinBox.setValue(self.main_window.printer_model.current_feed_rate)
            if hasattr(self.main_window.printer_model, 'current_flow_rate'):
                self.flowRateSpinBox.setValue(self.main_window.printer_model.current_flow_rate)
        except Exception as e:
            self.logger.debug(f"Could not initialize spinboxes from model: {e}")

        # Apply nozzle configuration
        self.apply_nozzle_configuration()

    def showEvent(self, event):
        """Update spinbox values when the control screen is shown."""
        super().showEvent(event)
        self._update_spinboxes_from_home_screen()

    def _update_spinboxes_from_home_screen(self):
        """Update all temperature spinboxes with current target values from home screen."""
        try:
            home_screen = self.main_window.home_screen
            
            # Update tool temperature spinbox (based on current toggle state)
            if self.toolToggleTemperatureButton.isChecked():
                temp_text = home_screen.tool1TargetTemperature.text().replace("°C", "").strip()
            else:
                temp_text = home_screen.tool0TargetTemperature.text().replace("°C", "").strip()
            if temp_text and temp_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                self.toolTempSpinBox.setProperty("value", float(temp_text))
            
            # Update bed temperature spinbox
            bed_temp_text = home_screen.bedTargetTemperature.text().replace("°C", "").strip()
            if bed_temp_text and bed_temp_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                self.bedTempSpinBox.setProperty("value", float(bed_temp_text))
            
            # Update H0 secondary heater temperature spinbox
            if self.H0TempSpinBox and hasattr(home_screen, 'H0TargetTemperature'):
                H0_temp_text = home_screen.H0TargetTemperature.text().replace("°C", "").strip()
                if H0_temp_text and H0_temp_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                    self.H0TempSpinBox.setProperty("value", float(H0_temp_text))
            
            # Update H1 secondary heater temperature spinbox
            if self.H1TempSpinBox and hasattr(home_screen, 'H1TargetTemperature'):
                H1_temp_text = home_screen.H1TargetTemperature.text().replace("°C", "").strip()
                if H1_temp_text and H1_temp_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                    self.H1TempSpinBox.setProperty("value", float(H1_temp_text))
                    
        except Exception as e:
            self.logger.debug(f"Could not update spinboxes from home screen: {e}")

    def apply_nozzle_configuration(self):
        """Hide dual nozzle elements and apply styling for single nozzle configuration."""
        apply_nozzle_config_to_screen(self, 'control_screen')
        
        # Apply border radius styling for single nozzle mode
        if not is_dual_nozzle_printer():
            self._apply_single_nozzle_styling()

    def _apply_single_nozzle_styling(self):
        """Apply custom styling for single nozzle configuration."""
        # Set border radius for top corners of setToolTempButton and extruderButton
        if hasattr(self, 'setToolTempButton') and self.setToolTempButton:
            current_style = self.setToolTempButton.styleSheet()
            # Create proper CSS structure for QPushButton
            border_style = "QPushButton { border-top-right-radius: 15px; }"
            # Combine existing style with new border style
            new_style = current_style + " " + border_style if current_style else border_style
            self.setToolTempButton.setStyleSheet(new_style)
            
        if hasattr(self, 'extruderButton') and self.extruderButton:
            current_style = self.extruderButton.styleSheet()
            # Create proper CSS structure for QPushButton
            border_style = "QPushButton { border-top-left-radius: 15px; border-top-right-radius: 15px; }"
            # Combine existing style with new border style
            new_style = current_style + " " + border_style if current_style else border_style
            self.extruderButton.setStyleSheet(new_style)
            
        # Set border radius for toolTempSpinBox
        if hasattr(self, 'toolTempSpinBox') and self.toolTempSpinBox:
            current_style = self.toolTempSpinBox.styleSheet()
            # Create proper CSS structure for QSpinBox
            border_style = "QSpinBox { border-top-left-radius: 15px; border-bottom-left-radius: 15px; }"
            # Combine existing style with new border style
            new_style = current_style + " " + border_style if current_style else border_style
            self.toolTempSpinBox.setStyleSheet(new_style)

    def coolDownAction(self):
        """'
        Turns all heaters and fans off
        """
        logger.info("ControlScreen.coolDownAction started")
        try:
            self.octoprint_client.gcode(command='M107')
            if is_dual_nozzle_printer():
                self.octoprint_client.setToolTemperature({"tool0": 0, "tool1": 0})
            else:
                self.octoprint_client.setToolTemperature({"tool0": 0})
            self.octoprint_client.setBedTemperature(0)
            # Turn off all heaters
            self.octoprint_client.gcode(command='M144')  # Ring heater off (M144)
            if self.H0TempSpinBox:
                self.octoprint_client.gcode(command='M104 H0 S0')  # Secondary heater H0
            if self.H1TempSpinBox and is_dual_nozzle_printer():
                self.octoprint_client.gcode(command='M104 H1 S0')  # Secondary heater H1
            
            # Update UI spinboxes
            self.toolTempSpinBox.setProperty("value", 0)
            self.bedTempSpinBox.setProperty("value", 0)
            if self.ringTempSpinBox:
                self.ringTempSpinBox.setProperty("value", 0)
            if self.H0TempSpinBox:
                self.H0TempSpinBox.setProperty("value", 0)
            if self.H1TempSpinBox:
                self.H1TempSpinBox.setProperty("value", 0)
            
            # Update printer model to propagate to home screen
            self.main_window.printer_model.update_ring_heater_power(0)
        except Exception as e:
            logger.error("Error in ControlScreen.coolDownAction: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.coolDownAction: {}".format(e), overlay=True)

    def setFeedRate(self):
        """Set the feed rate via OctoPrint and update the printer model."""
        logger.info("ControlScreen.setFeedRate started")
        try:
            feed_rate = self.feedRateSpinBox.value()
            self.octoprint_client.feedrate(feed_rate)
            # Update the printer model to emit signal for home screen
            self.main_window.printer_model.update_feed_rate(feed_rate)
        except Exception as e:
            logger.error("Error in ControlScreen.setFeedRate: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setFeedRate: {}".format(e), overlay=True)

    def setFlowRate(self):
        """Set the flow rate via OctoPrint and update the printer model."""
        logger.info("ControlScreen.setFlowRate started")
        try:
            flow_rate = self.flowRateSpinBox.value()
            self.octoprint_client.flowrate(flow_rate)
            # Update the printer model to emit signal for home screen
            self.main_window.printer_model.update_flow_rate(flow_rate)
        except Exception as e:
            logger.error("Error in ControlScreen.setFlowRate: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setFlowRate: {}".format(e), overlay=True)

    def setToolTemp(self):
        """
        Sets the temperature of the tool, depending on the tool selected
        """
        logger.info("ControlScreen.setToolTemp started")
        try:
            if self.toolToggleTemperatureButton.isChecked():
                self.octoprint_client.gcode(command='M104 T1 S' + str(self.toolTempSpinBox.value()))
                # octopiclient.setToolTemperature({"tool1": self.toolTempSpinBox.value()})
            else:
                self.octoprint_client.gcode(command='M104 T0 S' + str(self.toolTempSpinBox.value()))
                # octopiclient.setToolTemperature({"tool0": self.toolTempSpinBox.value()})
        except Exception as e:
            logger.error("Error in ControlScreen.setToolTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setToolTemp: {}".format(e), overlay=True)

    def preheatBedTemp(self, temp):
        """
        Preheats the bed to the given temperature
        param temp: temperature to preheat to
        """
        logger.info("ControlScreen.preheatBedTemp started")
        try:
            self.octoprint_client.gcode(command='M140 S' + str(temp))
            self.bedTempSpinBox.setProperty("value", temp)
        except Exception as e:
            logger.error("Error in ControlScreen.preheatBedTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.preheatBedTemp: {}".format(e), overlay=True)

    def preheatToolTemp(self, temp):
        """
        Preheats the tool to the given temperature
        param temp: temperature to preheat to
        """
        logger.info("ControlScreen.preheatToolTemp started")
        try:
            if self.toolToggleTemperatureButton.isChecked():
                self.octoprint_client.gcode(command='M104 T1 S' + str(temp))
            else:
                self.octoprint_client.gcode(command='M104 T0 S' + str(temp))
            self.toolTempSpinBox.setProperty("value", temp)
        except Exception as e:
            logger.error("Error in ControlScreen.preheatToolTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.preheatToolTemp: {}".format(e), overlay=True)

    def setRingTemp(self):
        """
        Sets the power level of the ring heater using M143 command (legacy)
        Ring heater uses PWM control (0-255), where 255 = 50% max power
        Converts percentage (0-100%) from UI spinbox to PWM value (0-255)
        """
        logger.info("ControlScreen.setRingTemp started")
        try:
            # Get percentage from spinbox (0-100%)
            percentage = self.ringTempSpinBox.value()
            # Convert percentage to PWM value (0-255)
            # 100% = 255, so multiply by 2.55
            pwm_value = int(percentage * 2.55)
            # Clamp to 0-255 range
            pwm_value = max(0, min(255, pwm_value))
            
            self.octoprint_client.gcode(command=f'M143 S{pwm_value}')
            # Update printer model to propagate to home screen (store percentage)
            self.main_window.printer_model.update_ring_heater_power(percentage)
        except Exception as e:
            logger.error("Error in ControlScreen.setRingTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setRingTemp: {}".format(e), overlay=True)
    
    def setH0Temp(self):
        """
        Sets the temperature of the H0 secondary heater using M104 H0 command
        """
        logger.info("ControlScreen.setH0Temp started")
        try:
            temp = self.H0TempSpinBox.value()
            self.octoprint_client.gcode(command=f'M104 H0 S{temp}')
        except Exception as e:
            logger.error("Error in ControlScreen.setH0Temp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setH0Temp: {}".format(e), overlay=True)

    def preheatRingTemp(self, temp):
        """
        Sets the ring heater to a preset power level using M143 command (legacy)
        param temp: power level (0-255) to set the ring heater to
        """
        logger.info("ControlScreen.preheatRingTemp started")
        try:
            # M143 controls ring heater PWM (0-255, limited to 50% max power)
            self.octoprint_client.gcode(command=f'M143 S{temp}')
            if self.ringTempSpinBox:
                self.ringTempSpinBox.setProperty("value", temp)
            # Update printer model to propagate to home screen
            self.main_window.printer_model.update_ring_heater_power(temp)
        except Exception as e:
            logger.error("Error in ControlScreen.preheatRingTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.preheatRingTemp: {}".format(e), overlay=True)
    
    def preheatH0Temp(self, temp):
        """
        Preheats the H0 secondary heater to the given temperature using M104 H0 command
        param temp: temperature to preheat to
        """
        logger.info(f"ControlScreen.preheatH0Temp started with {temp}C")
        try:
            self.octoprint_client.gcode(command=f'M104 H0 S{temp}')
            if self.H0TempSpinBox:
                self.H0TempSpinBox.setProperty("value", temp)
        except Exception as e:
            logger.error("Error in ControlScreen.preheatH0Temp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.preheatH0Temp: {}".format(e), overlay=True)

    def setH1Temp(self):
        """
        Sets the temperature of the H1 secondary heater using M104 H1 command
        """
        logger.info("ControlScreen.setH1Temp started")
        try:
            temp = self.H1TempSpinBox.value()
            self.octoprint_client.gcode(command=f'M104 H1 S{temp}')
        except Exception as e:
            logger.error("Error in ControlScreen.setH1Temp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setH1Temp: {}".format(e), overlay=True)

    def preheatH1Temp(self, temp):
        """
        Preheats the H1 secondary heater to the given temperature using M104 H1 command
        param temp: temperature to preheat to
        """
        logger.info(f"ControlScreen.preheatH1Temp started with {temp}C")
        try:
            self.octoprint_client.gcode(command=f'M104 H1 S{temp}')
            if self.H1TempSpinBox:
                self.H1TempSpinBox.setProperty("value", temp)
        except Exception as e:
            logger.error("Error in ControlScreen.preheatH1Temp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.preheatH1Temp: {}".format(e), overlay=True)

    def selectToolTemperature(self):
        """
        Selects the tool whose temperature needs to be changed.
        It accordingly changes the button text.it also updates the status of the other toggle buttons.
        """
        logger.info("ControlScreen.selectToolTemperature started")
        try:
            # self.toolToggleTemperatureButton.setText(
            #     "1") if self.toolToggleTemperatureButton.isChecked() else self.toolToggleTemperatureButton.setText("0")
            if self.toolToggleTemperatureButton.isChecked():
                print("extruder 1 Temperature")
                temp_text = self.main_window.home_screen.tool1TargetTemperature.text().replace("°C", "").strip()
                # Handle empty string or non-numeric values
                if temp_text and temp_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                    self.toolTempSpinBox.setProperty("value", float(temp_text))
                else:
                    self.toolTempSpinBox.setProperty("value", 0)
            else:
                print("extruder 0 Temperature")
                temp_text = self.main_window.home_screen.tool0TargetTemperature.text().replace("°C", "").strip()
                # Handle empty string or non-numeric values
                if temp_text and temp_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                    self.toolTempSpinBox.setProperty("value", float(temp_text))
                else:
                    self.toolTempSpinBox.setProperty("value", 0)
        except Exception as e:
            logger.error("Error in ControlScreen.selectToolTemperature: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.selectToolTemperature: {}".format(e), overlay=True)

    def selectToolMotion(self):
        """
        Selects the tool whose temperature needs to be changed. It accordingly changes the button text. it also updates the status of the other toggle buttons
        """
        logger.info("ControlScreen.selectToolMotion started")
        try:
            if self.toolToggleMotionButton.isChecked():
                self.octoprint_client.selectTool(1)
                self.setActiveExtruder(1)

            else:
                self.octoprint_client.selectTool(0)
                self.setActiveExtruder(0)
        except Exception as e:
            logger.error("Error in ControlScreen.selectToolMotion: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.selectToolMotion: {}".format(e), overlay=True)

    def setStep(self, stepRate):
        """
        Sets the class variable "Step" which would be needed for movement and joging
        :param stepRate: step multiplier for movement in the move
        :return: nothing
        """
        logger.info("ControlScreen.setStep started")
        try:
            if stepRate == 100:
                self.step100mmButton.setFlat(True)
                self.step1mmButton.setFlat(False)
                self.step10mmButton.setFlat(False)
                self.step = 100
            if stepRate == 1:
                self.step100mmButton.setFlat(False)
                self.step1mmButton.setFlat(True)
                self.step10mmButton.setFlat(False)
                self.step = 1
            if stepRate == 10:
                self.step100mmButton.setFlat(False)
                self.step1mmButton.setFlat(False)
                self.step10mmButton.setFlat(True)
                self.step = 10
        except Exception as e:
            logger.error("Error in ControlScreen.setStep: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setStep: {}".format(e), overlay=True)

    def setActiveExtruder(self, activeNozzle):
        """
        Sets the active extruder, and changes the UI accordingly
        """
        logger.info("control_screen.setActiveExtruder started")
        try:
            if activeNozzle == 0:
                self.toolToggleMotionButton.setChecked(False)
                self.toolToggleMotionButton.setText("0")
                self.activeExtruder = 0
            elif activeNozzle == 1:
                self.toolToggleMotionButton.setChecked(True)
                self.toolToggleMotionButton.setText("1")
                self.activeExtruder = 1
        except Exception as e:
            logger.error("Error in control_screen.setActiveExtruder: {}".format(e))
            dialog.WarningOk(self, "Error in control_screen.setActiveExtruder: {}".format(e), overlay=True)

    # ── Extrude / Retract with explicit feedrate ────────────────
    def _extrude_step(self):
        """Extrude by current step amount at F500 using raw gcode."""
        try:
            self.octoprint_client.gcode(
                command=f'G92 E0\nG1 E{self.step} F500'
            )
        except Exception as e:
            self.logger.error(f"Error extruding: {e}")

    def _retract_step(self):
        """Retract by current step amount at F500 using raw gcode."""
        try:
            self.octoprint_client.gcode(
                command=f'G92 E0\nG1 E-{self.step} F500'
            )
        except Exception as e:
            self.logger.error(f"Error retracting: {e}")

    # ── Purge Material (hold-to-extrude) ──────────────────────────
    def _purge_start(self):
        """Begin continuous extrusion on press: start timer that sends repeated extrude commands."""
        try:
            self._purging = True
            # Send the first extrude command immediately
            self._purge_extrude_tick()
            # Start repeating timer for subsequent commands
            self._purge_timer.start()
            self.logger.info("Purge started at F500")
        except Exception as e:
            self.logger.error(f"Error starting purge: {e}")

    def _purge_stop(self):
        """Stop continuous extrusion on release."""
        try:
            self._purging = False
            self._purge_timer.stop()
            self.logger.info("Purge stopped")
        except Exception as e:
            self.logger.error(f"Error stopping purge: {e}")

    def _purge_extrude_tick(self):
        """Send a small extrude command via raw gcode. Called every 200ms.

        Uses absolute extrusion with G92 E0 reset after each move:
          1. G92 E0    — reset E position to zero
          2. G1 E2 F500 — extrude 2mm at 500 mm/min

        At F500 (500 mm/min ≈ 8.33 mm/s), a 2mm move takes ~240ms.
        Sending 2mm every 200ms keeps exactly one move buffered so the
        extruder runs continuously but stops almost instantly on release.
        """
        if not self._purging:
            return
        try:
            self.octoprint_client.gcode(command='G92 E0\nG1 E2 F500')
        except Exception as e:
            self.logger.error(f"Error during purge tick: {e}")
    # ─────────────────────────────────────────────────────────────

    def buttonStatusUpdate(self, status):
        """Update ControlScreen UI elements based on printer status"""
        try:
            # Disable motion controls during printing
            if status == "Printing":
                self.motionTab.setDisabled(True)
            else:  # Paused, Offline, Operational, etc.
                self.motionTab.setDisabled(False)
            
            # TODO: Add other control-specific UI updates based on status
            # For example: disable certain temperature controls, etc.
        except Exception as e:
            logger.error(f"Error updating ControlScreen UI for status {status}: {e}")
            dialog.WarningOk(self, f"Error updating ControlScreen UI for status {status}: {e}", overlay=True)

    def togglePelletSensorT0(self):
        """Toggle T0 (Left) pellet level sensor persistent preference and apply live state."""
        logger.info("ControlScreen.togglePelletSensorT0 started")
        try:
            enabled = self.togglePelletSensorT0Button.isChecked()
            # Update model preference (persists)
            self.main_window.printer_model.set_pellet_sensor_t0_pref(enabled, persist=True)
            # Apply immediate state to Klipper
            self.main_window.controller.apply_extruder_sensors()
        except Exception as e:
            logger.error(f"Error in ControlScreen.togglePelletSensorT0: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.togglePelletSensorT0: {e}", overlay=True)

    def togglePelletSensorT1(self):
        """Toggle the T1 (Right) sensor and apply live state.

        On a Hybrid IDEX the right tool is a filament extruder, so this button
        drives its runout switch. Elsewhere T1 is a second pellet hopper with
        a level sensor.
        """
        logger.info("ControlScreen.togglePelletSensorT1 started")
        try:
            enabled = self.togglePelletSensorT1Button.isChecked()
            if is_hybrid_printer():
                self.main_window.printer_model.set_extruder_runout_pref(enabled, persist=True)
            else:
                self.main_window.printer_model.set_pellet_sensor_t1_pref(enabled, persist=True)
            self.main_window.controller.apply_extruder_sensors()
        except Exception as e:
            logger.error(f"Error in ControlScreen.togglePelletSensorT1: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.togglePelletSensorT1: {e}", overlay=True)

    def toggleAutoResume(self):
        """Toggle auto-resume on power outage"""
        logger.info("ControlScreen.toggleAutoResume started")
        try:
            enabled = self.toggleAutoResumeButton.isChecked()
            # Update model preference (persists)
            self.main_window.printer_model.set_auto_resume_pref(enabled, persist=True)
            # Apply the setting to OctoPrint via the PenrosePrintRestore plugin
            self.main_window.octoprint_client.savePrintRestoreSettings(
                autoRestore=enabled,
                enabled=self.main_window.printer_model.print_restore_enabled,
                interval=1  # Default interval of 1 second
            )
            self.logger.info(f"Auto-resume {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            logger.error(f"Error in ControlScreen.toggleAutoResume: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.toggleAutoResume: {e}", overlay=True)

    def togglePrintRestore(self):
        """Toggle print restore functionality"""
        logger.info("ControlScreen.togglePrintRestore started")
        try:
            enabled = self.togglePrintRestoreButton.isChecked()
            # Update model preference (persists)
            self.main_window.printer_model.set_print_restore_pref(enabled, persist=True)
            # Enable/disable the auto-resume button based on print restore state
            self.toggleAutoResumeButton.setEnabled(enabled)
            # If print restore is disabled, also disable auto-resume
            if not enabled:
                self.toggleAutoResumeButton.setChecked(False)
                self.main_window.printer_model.set_auto_resume_pref(False, persist=True)
            # Apply the setting to OctoPrint via the PenrosePrintRestore plugin
            self.main_window.octoprint_client.savePrintRestoreSettings(
                autoRestore=self.main_window.printer_model.auto_resume_enabled,
                enabled=enabled,
                interval=1  # Default interval of 1 second
            )
            self.logger.info(f"Print restore {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            logger.error(f"Error in ControlScreen.togglePrintRestore: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.togglePrintRestore: {e}", overlay=True)

    def toggleCheckPrintCompatibility(self):
        """Toggle check print compatibility preference and persist the setting."""
        logger.info("ControlScreen.toggleCheckPrintCompatibility started")
        try:
            enabled = self.toggleCheckPrintCompatibilityButton.isChecked()
            # Update model preference (persists)
            self.main_window.printer_model.set_print_compatibility_check_pref(enabled, persist=True)
            self.logger.info(f"Print compatibility check {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            logger.error(f"Error in ControlScreen.toggleCheckPrintCompatibility: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.toggleCheckPrintCompatibility: {e}", overlay=True)
