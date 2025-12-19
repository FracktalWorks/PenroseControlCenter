import time

import os
from PyQt5 import uic
from PyQt5 import QtGui, QtCore
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QWidget, QPushButton, QSpinBox, QTabWidget, QToolButton, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QLabel
from utils.helpers import check_ui_elements
from utils.logger import get_logger
from utils.printer_ui_config import apply_nozzle_config_to_screen, is_dual_nozzle_printer
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
        self.toggleFilamentRunoutButton = self.findChild(QPushButton, "toggleFilamentRunoutButton")
        self.toggleFilamentJamButton = self.findChild(QPushButton, "toggleFilamentJamButton")
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

        # Ring heater temperature controls
        self.ringTempSpinBox = self.findChild(QSpinBox, "ringTempSpinBox")
        self.setRingTempButton = self.findChild(QPushButton, "setRingTempButton")
        self.ring200PreheatButton = self.findChild(QPushButton, "ring200PreheatButton")
        self.ring250PreheatButton = self.findChild(QPushButton, "ring250PreheatButton")
        self.ringStatusLabel = self.findChild(QLabel, "ringStatusLabel")

        # Unified temperature control widgets
        self.temperatureStatusLabel = self.findChild(QLabel, "temperatureStatusLabel")
        self.unifiedTempSpinBox = self.findChild(QSpinBox, "universalTempSpinBox")
        self.unifiedTempSetButton = self.findChild(QPushButton, "setUniversalTempButton")
        self.ringButton = self.findChild(QPushButton, "ringSelectButton")
        self.chamberButton = self.findChild(QPushButton, "chamberSelectButton")
        self.spoolButton = self.findChild(QPushButton, "spoolSelectButton")
        
        # Unified preset temperature buttons
        self.unifiedPreset1Button = self.findChild(QPushButton, "preset1Button")
        self.unifiedPreset2Button = self.findChild(QPushButton, "preset2Button")
        
        # Initialize selected heater
        self.selectedHeater = "Ring"  # Default to Ring heater

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
            self.toggleFilamentRunoutButton, self.toggleFilamentJamButton,
            self.toggleAutoResumeButton, self.toggleCheckPrintCompatibilityButton,
            self.togglePrintRestoreButton
        ], "ControlScreen")
        
        # Log optional widgets status
        self.logger.debug(f"Optional widgets - ringTempSpinBox: {self.ringTempSpinBox is not None}, "
                         f"unifiedTempSpinBox: {self.unifiedTempSpinBox is not None}, "
                         f"temperatureStatusLabel: {self.temperatureStatusLabel is not None}")

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

        # Unified temperature control signal connections (optional - may not exist in all UI versions)
        if self.unifiedTempSetButton:
            self.unifiedTempSetButton.clicked.connect(self.setUnifiedTemp)
        if self.ringButton:
            self.ringButton.clicked.connect(lambda: self.selectHeater("Ring"))
        if self.chamberButton:
            self.chamberButton.clicked.connect(lambda: self.selectHeater("Chamber"))
        if self.spoolButton:
            self.spoolButton.clicked.connect(lambda: self.selectHeater("Spool"))
        if self.unifiedPreset1Button:
            self.unifiedPreset1Button.clicked.connect(self.setUnifiedPreset1)
        if self.unifiedPreset2Button:
            self.unifiedPreset2Button.clicked.connect(self.setUnifiedPreset2)

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
        self.extruderButton.clicked.connect(lambda: self.octoprint_client.extrude(self.step))
        self.retractButton.clicked.connect(lambda: self.octoprint_client.extrude(-self.step))

        # Filament Buttons Signal Connections
        self.setFlowRateButton.clicked.connect(self.setFlowRate)

        self.toggleFilamentRunoutButton.clicked.connect(self.toggleFilamentRunout)

        self.toggleFilamentJamButton.clicked.connect(self.toggleFilamentJam)

        # Preferences Signal Connections
        self.toggleAutoResumeButton.clicked.connect(self.toggleAutoResume)
        self.toggleCheckPrintCompatibilityButton.clicked.connect(self.toggleCheckPrintCompatibility)
        self.togglePrintRestoreButton.clicked.connect(self.togglePrintRestore)

        # Configure spinboxes
        for spinbox in [self.feedRateSpinBox, self.toolTempSpinBox, self.bedTempSpinBox, self.flowRateSpinBox, self.ringTempSpinBox, self.unifiedTempSpinBox]:
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

        # Reflect persistent filament sensor preferences in toggle buttons
        try:
            runout_enabled = bool(self.main_window.printer_model.filament_runout_sensor_persistent_state)
            self.toggleFilamentRunoutButton.setChecked(runout_enabled)
            jam_enabled = bool(self.main_window.printer_model.filament_jam_sensor_persistent_state)
            self.toggleFilamentJamButton.setChecked(jam_enabled)
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

        # Initialize unified temperature control
        try:
            # Set default heater selection to Ring
            self.selectHeater("Ring")
            # Initialize temperature status display
            self.updateTemperatureStatusLabel()
        except Exception as e:
            self.logger.warning(f"Failed initializing unified temperature control: {e}")


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
            self.octoprint_client.setToolTemperature({"tool0": 0, "tool1": 0})
            # octopiclient.setToolTemperature({"tool0": 0})
            self.octoprint_client.setBedTemperature(0)
            # Turn off ring heater - you'll need to provide the correct M-code here
            self.octoprint_client.gcode(command='M104 P2 S0')  # Ring heater
            self.octoprint_client.gcode(command='M104 P3 S0')  # Chamber heater
            self.octoprint_client.gcode(command='M104 P4 S0')  # Spool heater
            
            # Update UI spinboxes
            self.toolTempSpinBox.setProperty("value", 0)
            self.bedTempSpinBox.setProperty("value", 0)
            if self.ringTempSpinBox:
                self.ringTempSpinBox.setProperty("value", 0)
            if self.unifiedTempSpinBox:
                self.unifiedTempSpinBox.setProperty("value", 0)
                
            # Update temperature status
            self.updateTemperatureStatusLabel()
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
        Sets the temperature of the ring heater
        """
        logger.info("ControlScreen.setRingTemp started")
        try:
            # You'll need to provide the correct G/M-code for ring heater here
            # This is a placeholder - update with the correct command for your ring heater
            self.octoprint_client.gcode(command='M104 P2 S' + str(self.ringTempSpinBox.value()))
        except Exception as e:
            logger.error("Error in ControlScreen.setRingTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.setRingTemp: {}".format(e), overlay=True)

    def preheatRingTemp(self, temp):
        """
        Preheats the ring heater to the given temperature
        param temp: temperature to preheat to
        """
        logger.info("ControlScreen.preheatRingTemp started")
        try:
            # You'll need to provide the correct G/M-code for ring heater here
            # This is a placeholder - update with the correct command for your ring heater
            self.octoprint_client.gcode(command='M104 P2 S' + str(temp))
            if self.ringTempSpinBox:
                self.ringTempSpinBox.setProperty("value", temp)
        except Exception as e:
            logger.error("Error in ControlScreen.preheatRingTemp: {}".format(e))
            dialog.WarningOk(self, "Error in ControlScreen.preheatRingTemp: {}".format(e), overlay=True)

    def selectHeater(self, heater_name):
        """
        Select which heater to control with the unified temperature control.
        Updates button states and preset button texts.
        """
        logger.info(f"ControlScreen.selectHeater: {heater_name}")
        try:
            # Check if unified temperature control widgets exist
            if not all([self.ringButton, self.chamberButton, self.spoolButton, 
                       self.unifiedPreset1Button, self.unifiedPreset2Button, self.unifiedTempSpinBox]):
                self.logger.debug("Unified temperature control widgets not available")
                return
                
            self.selectedHeater = heater_name
            
            # Update button checked states
            self.ringButton.setChecked(heater_name == "Ring")
            self.chamberButton.setChecked(heater_name == "Chamber")
            self.spoolButton.setChecked(heater_name == "Spool")
            
            # Update preset button texts and values based on selected heater
            if heater_name == "Ring":
                self.unifiedPreset1Button.setText("180°C")
                self.unifiedPreset2Button.setText("250°C")
                # Set spinbox to current ring temperature if available
                if hasattr(self.main_window.printer_model, 'temperatures'):
                    ring_temp = self.main_window.printer_model.temperatures.get("ring", 0)
                    self.unifiedTempSpinBox.setValue(int(ring_temp))
            elif heater_name == "Chamber":
                self.unifiedPreset1Button.setText("50°C")
                self.unifiedPreset2Button.setText("80°C")
                # Set spinbox to current chamber temperature if available
                if hasattr(self.main_window.printer_model, 'temperatures'):
                    chamber_temp = self.main_window.printer_model.temperatures.get("chamber", 0)
                    self.unifiedTempSpinBox.setValue(int(chamber_temp))
            elif heater_name == "Spool":
                self.unifiedPreset1Button.setText("50°C")
                self.unifiedPreset2Button.setText("80°C")
                # Set spinbox to current spool temperature if available
                if hasattr(self.main_window.printer_model, 'temperatures'):
                    spool_temp = self.main_window.printer_model.temperatures.get("spool", 0)
                    self.unifiedTempSpinBox.setValue(int(spool_temp))
            
            # Update the temperature status display
            self.updateTemperatureStatusLabel()
            
        except Exception as e:
            logger.error(f"Error in ControlScreen.selectHeater: {e}")

    def setUnifiedTemp(self):
        """
        Set the temperature for the currently selected heater.
        """
        logger.info(f"ControlScreen.setUnifiedTemp for {self.selectedHeater}")
        try:
            if not self.unifiedTempSpinBox:
                return
                
            temp = self.unifiedTempSpinBox.value()
            
            if self.selectedHeater == "Ring":
                # Ring heater G-code (update with correct command)
                self.octoprint_client.gcode(command=f'M104 P2 S{temp}')
            elif self.selectedHeater == "Chamber":
                # Chamber heater G-code (update with correct command)
                self.octoprint_client.gcode(command=f'M104 P3 S{temp}')
            elif self.selectedHeater == "Spool":
                # Spool heater G-code (update with correct command)
                self.octoprint_client.gcode(command=f'M104 P4 S{temp}')
                
        except Exception as e:
            logger.error(f"Error in ControlScreen.setUnifiedTemp: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.setUnifiedTemp: {e}", overlay=True)

    def setUnifiedPreset1(self):
        """
        Set the first preset temperature for the currently selected heater.
        """
        logger.info(f"ControlScreen.setUnifiedPreset1 for {self.selectedHeater}")
        try:
            if not self.unifiedTempSpinBox:
                return
                
            if self.selectedHeater == "Ring":
                temp = 180
            elif self.selectedHeater == "Chamber":
                temp = 50
            elif self.selectedHeater == "Spool":
                temp = 50
            else:
                return
            
            self.unifiedTempSpinBox.setValue(temp)
            self.setUnifiedTemp()
            
        except Exception as e:
            logger.error(f"Error in ControlScreen.setUnifiedPreset1: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.setUnifiedPreset1: {e}", overlay=True)

    def setUnifiedPreset2(self):
        """
        Set the second preset temperature for the currently selected heater.
        """
        logger.info(f"ControlScreen.setUnifiedPreset2 for {self.selectedHeater}")
        try:
            if not self.unifiedTempSpinBox:
                return
                
            if self.selectedHeater == "Ring":
                temp = 250
            elif self.selectedHeater == "Chamber":
                temp = 80
            elif self.selectedHeater == "Spool":
                temp = 80
            else:
                return
                
            self.unifiedTempSpinBox.setValue(temp)
            self.setUnifiedTemp()
            
        except Exception as e:
            logger.error(f"Error in ControlScreen.setUnifiedPreset2: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.setUnifiedPreset2: {e}", overlay=True)

    def updateTemperatureStatusLabel(self):
        """
        Update the unified temperature status label with current temperatures.
        """
        try:
            # Check if the label exists
            if not self.temperatureStatusLabel:
                return
                
            if hasattr(self.main_window.printer_model, 'temperatures'):
                temps = self.main_window.printer_model.temperatures
                ring_temp = temps.get("ring", 0)
                chamber_temp = temps.get("chamber", 0)
                spool_temp = temps.get("spool", 0)
                
                status_text = f"Ring: {ring_temp}°C | Chamber: {chamber_temp}°C | Spool: {spool_temp}°C"
                self.temperatureStatusLabel.setText(status_text)
            else:
                self.temperatureStatusLabel.setText("Ring: --°C | Chamber: --°C | Spool: --°C")
        except Exception as e:
            logger.error(f"Error in ControlScreen.updateTemperatureStatusLabel: {e}")
            if self.temperatureStatusLabel:
                self.temperatureStatusLabel.setText("Ring: --°C | Chamber: --°C | Spool: --°C")

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

    def buttonStatusUpdate(self, status):
        """Update ControlScreen UI elements based on printer status"""
        try:
            # Disable motion controls during printing
            if status == "Printing":
                self.motionTab.setDisabled(True)
            else:  # Paused, Offline, Operational, etc.
                self.motionTab.setDisabled(False)
                    
            # Update unified temperature status display
            self.updateTemperatureStatusLabel()
            
            # TODO: Add other control-specific UI updates based on status
            # For example: disable certain temperature controls, etc.
        except Exception as e:
            logger.error(f"Error updating ControlScreen UI for status {status}: {e}")
            dialog.WarningOk(self, f"Error updating ControlScreen UI for status {status}: {e}", overlay=True)

    def toggleFilamentRunout(self):
        """Toggle filament runout sensor persistent preference and apply live state."""
        logger.info("ControlScreen.toggleFilamentRunout started")
        try:
            enabled = self.toggleFilamentRunoutButton.isChecked()
            # Update model preference (persists)
            self.main_window.printer_model.set_filament_runout_pref(enabled, persist=True)
            # Apply immediate state depending on current print status
            self.main_window.controller.apply_filament_sensor_state()
        except Exception as e:
            logger.error(f"Error in ControlScreen.toggleFilamentRunout: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.toggleFilamentRunout: {e}", overlay=True)

    def toggleFilamentJam(self):
        """Toggle filament jam sensor persistent preference and apply live state."""
        logger.info("ControlScreen.toggleFilamentJam started")
        try:
            enabled = self.toggleFilamentJamButton.isChecked()
            self.main_window.printer_model.set_filament_jam_pref(enabled, persist=True)
            self.main_window.controller.apply_filament_sensor_state()
        except Exception as e:
            logger.error(f"Error in ControlScreen.toggleFilamentJam: {e}")
            dialog.WarningOk(self, f"Error in ControlScreen.toggleFilamentJam: {e}", overlay=True)

    def toggleAutoResume(self):
        """Toggle auto-resume on power outage"""
        logger.info("ControlScreen.toggleAutoResume started")
        try:
            enabled = self.toggleAutoResumeButton.isChecked()
            # Update model preference (persists)
            self.main_window.printer_model.set_auto_resume_pref(enabled, persist=True)
            # Apply the setting to OctoPrint via the TwinDragonPrintRestore plugin
            self.main_window.octoprint_client.savePrintRestoreSettings(
                restore=enabled,
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
            # Apply the setting to OctoPrint via the TwinDragonPrintRestore plugin
            self.main_window.octoprint_client.savePrintRestoreSettings(
                restore=self.main_window.printer_model.auto_resume_enabled,
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
