"""
Nozzle Change Wizard
====================

3-step wizard for nozzle replacement: Heat → Remove → Install + Select → Exit.
No Klipper restart required.
"""

import os
from PyQt5 import uic, QtCore
from PyQt5.QtWidgets import QWidget, QPushButton, QStackedWidget, QLabel, QProgressBar, QComboBox

from utils.helpers import check_ui_elements
from utils.logger import get_logger
from utils.printer_ui_config import force_single_tool
from utils import dialog

# Default temperature (°C) for heating nozzle before removal
NOZZLE_CHANGE_TEMP = 200


class NozzleChangeWizard(QWidget):
	"""3-step nozzle replacement wizard: Heat → Remove → Install + Select → Exit."""

	# Step indices (0-based)
	STEP_HEAT = 0
	STEP_REMOVE = 1
	STEP_SELECT = 2
	TOTAL_STEPS = 3

	# Map logical step → stacked widget page index (reuse existing .ui pages)
	# Heat → step5Page (idx 4), Remove → step3Page (idx 2), Select → step4Page (idx 3)
	_PAGE_MAP = {0: 4, 1: 2, 2: 3}

	def __init__(self, main_window):
		super().__init__()
		self.main_window = main_window
		self.model = main_window.printer_model
		self.octoprint_client = getattr(main_window, "octoprint_client", None)
		self.active_tool = "tool0"
		self._heating_started = False

		self.logger = get_logger(self.__class__.__name__)
		self.logger.info("Initializing NozzleChangeWizard")

		# Load UI
		try:
			ui_file_path = os.path.join(os.path.dirname(__file__), "nozzleChangeWizard.ui")
			uic.loadUi(ui_file_path, self)
			self.logger.debug("nozzleChangeWizard UI loaded")
		except Exception as e:
			self.logger.error(f"Failed to load nozzleChangeWizard UI: {e}", exc_info=True)
			dialog.WarningOk(self, f"Failed to load Nozzle Change Wizard UI: {e}", overlay=True)
			return

		# Bind UI elements
		self.stackedWidget: QStackedWidget = self.findChild(QStackedWidget, "stackedWidget")
		self.stepLabel: QLabel = self.findChild(QLabel, "stepLabel")

		# Reused pages (mapped via _PAGE_MAP)
		self.step3Page: QWidget = self.findChild(QWidget, "step3Page")
		self.step4Page: QWidget = self.findChild(QWidget, "step4Page")
		self.step5Page: QWidget = self.findChild(QWidget, "step5Page")

		# Heat page widgets (from step5Page in the .ui)
		self.step5Label: QLabel = self.findChild(QLabel, "step5Label")
		self.nozzleCheckProgressBar: QProgressBar = self.findChild(QProgressBar, "nozzleCheckProgressBar")

		# GIF labels to hide
		self.step3Gif: QLabel = self.findChild(QLabel, "step3Gif")
		self.step4Gif: QLabel = self.findChild(QLabel, "step4Gif")

		# Nozzle selection combo
		self.changeNozzleComboBox: QComboBox = self.findChild(QComboBox, "changeNozzleComboBox")

		# Buttons
		self.nextButton: QPushButton = self.findChild(QPushButton, "step1NextButton")
		self.cancelButton: QPushButton = self.findChild(QPushButton, "step1CancelButton")

		# Validate required elements
		required = [
			self.stackedWidget, self.stepLabel,
			self.step3Page, self.step4Page, self.step5Page,
			self.nozzleCheckProgressBar,
			self.changeNozzleComboBox,
			self.nextButton, self.cancelButton,
		]
		check_ui_elements(self, required, "NozzleChangeWizard")

		# State
		self._current_step = 0
		self._heat_target = NOZZLE_CHANGE_TEMP

		# Heating monitor timer
		self._heat_timer = QtCore.QTimer(self)
		self._heat_timer.setInterval(1000)
		self._heat_timer.timeout.connect(self._heat_check_tick)

		# Hide GIF labels (not used in simplified flow)
		for gif in (self.step3Gif, self.step4Gif):
			if gif:
				gif.hide()

		# Wire signals
		self.nextButton.clicked.connect(self.on_next_clicked)
		self.cancelButton.clicked.connect(self.on_cancel_clicked)

		# Start at step 1
		self.goto_step(self.STEP_HEAT)

	# ----- Public API for parent screen -----------------------------------
	def setup(self, params=None):
		"""Prepare wizard with optional parameters."""
		try:
			tool = None
			if isinstance(params, dict):
				tool = params.get("tool")
			elif isinstance(params, str):
				tool = params
			tool = force_single_tool(tool)
			if tool in ("tool0", "tool1"):
				self.active_tool = tool
			self.logger.info(f"NozzleChangeWizard.setup: active_tool={self.active_tool}")
			self.changeNozzle()
		except Exception as e:
			self.logger.error(f"Error in NozzleChangeWizard.setup: {e}")

	def changeNozzle(self):
		"""Initialize the nozzle change flow."""
		self.logger.info("NozzleChange.changeNozzle() started")
		self._heating_started = False
		try:
			tool_str = self.active_tool or "tool0"
			if not self._check_filament_unloaded(tool_str):
				return
			self.goto_step(self.STEP_HEAT)
		except Exception as e:
			self.logger.error(f"Error initializing nozzle change: {e}")

	# ----- Navigation -----------------------------------------------------
	def goto_step(self, index: int):
		"""Switch to the given step index and run step-entry hooks."""
		index = max(0, min(index, self.TOTAL_STEPS - 1))
		self._current_step = index

		# Map logical step to UI page index
		page_idx = self._PAGE_MAP.get(index, 0)
		if self.stackedWidget:
			self.stackedWidget.setCurrentIndex(page_idx)
		self._update_step_label()

		# Step-specific entry logic
		if index == self.STEP_HEAT:
			self._enter_heat_step()
		elif index == self.STEP_REMOVE:
			self._stop_heat_timer()
			self._enable_next(True)
		elif index == self.STEP_SELECT:
			self._stop_heat_timer()
			self._prepare_nozzle_selection()

		# Button text
		if self.nextButton:
			self.nextButton.setText("Done" if index == self.STEP_SELECT else "Next")

	def on_next_clicked(self):
		"""Handle Next/Done button clicks."""
		try:
			if self._current_step >= self.STEP_SELECT:
				self._finish_wizard()
				return
			self.goto_step(self._current_step + 1)
		except Exception as e:
			self.logger.error(f"Error advancing to next step: {e}")

	def on_cancel_clicked(self):
		"""Cancel the wizard and return to the Material/Nozzle screen."""
		try:
			self._stop_heat_timer()
			self._cool_down()
			self.main_window.filament_management_screen.show_material_nozzle_screen()
			self.goto_step(0)
		except Exception as e:
			self.logger.error(f"Error cancelling nozzle change wizard: {e}")

	def _finish_wizard(self):
		"""Persist nozzle selection, cool down, and exit."""
		try:
			nozzle = self.changeNozzleComboBox.currentText()
			try:
				self.model.update_tool_bay_state(self.active_tool, nozzle=nozzle, persist=True)
				self.logger.info(f"Persisted nozzle '{nozzle}' for {self.active_tool}")
			except Exception as e:
				self.logger.warning(f"Unable to persist nozzle selection: {e}")
			self._cool_down()
			self.main_window.filament_management_screen.show_material_nozzle_screen()
			self.goto_step(0)
		except Exception as e:
			self.logger.error(f"Error finishing nozzle change wizard: {e}")

	def _update_step_label(self):
		"""Update the step counter label."""
		try:
			if self.stepLabel:
				self.stepLabel.setText(f"Step {self._current_step + 1}/{self.TOTAL_STEPS}")
		except Exception:
			pass

	# ----- Step 1: Heat ---------------------------------------------------
	def _enter_heat_step(self):
		"""Start heating the active nozzle and monitor temperature."""
		try:
			self._heat_target = self._get_heat_target()
			if self.step5Label:
				self.step5Label.setText(f"Heating nozzle to {self._heat_target:.0f}°C for removal...")
			if self.nozzleCheckProgressBar:
				self.nozzleCheckProgressBar.setValue(0)
			self._enable_next(False)
			self._start_heating()
			self._heat_timer.start()
		except Exception as e:
			self.logger.error(f"Error entering heat step: {e}")

	def _get_heat_target(self):
		"""Use current tool target if already set high enough, else default."""
		try:
			tool_idx = self._get_tool_index(self.active_tool)
			temps = getattr(self.model, 'temperatures', {}) or {}
			target = temps.get(f'tool{tool_idx}Target', 0)
			if target and float(target) >= 150:
				return float(target)
		except Exception:
			pass
		return NOZZLE_CHANGE_TEMP

	def _start_heating(self):
		"""Send gcode to heat the active tool."""
		if not self.octoprint_client or self._heating_started:
			return
		try:
			tool_idx = self._get_tool_index(self.active_tool)
			self.octoprint_client.selectTool(tool_idx)
			self.octoprint_client.gcode(f"M104 S{int(self._heat_target)}")
			self._heating_started = True
			self.logger.info(f"Heating tool{tool_idx} to {self._heat_target}°C")
		except Exception as e:
			self.logger.warning(f"Failed to send heat command: {e}")

	def _heat_check_tick(self):
		"""Periodically check temperature and update progress."""
		try:
			tool_idx = self._get_tool_index(self.active_tool)
			temps = getattr(self.model, 'temperatures', {}) or {}
			actual = temps.get(f'tool{tool_idx}Actual', 0)
			try:
				actual_val = float(actual) if actual is not None else 0
			except Exception:
				actual_val = 0

			# Update progress bar
			if self._heat_target > 0:
				progress = min(100, max(0, int((actual_val / self._heat_target) * 100)))
			else:
				progress = 100
			if self.nozzleCheckProgressBar:
				self.nozzleCheckProgressBar.setValue(progress)
			if self.step5Label:
				self.step5Label.setText(f"Heating nozzle: {actual_val:.0f}°C / {self._heat_target:.0f}°C")

			# Enable Next when close enough
			if actual_val >= self._heat_target - 5:
				self._heat_timer.stop()
				self._enable_next(True)
				if self.step5Label:
					self.step5Label.setText(f"Nozzle at {actual_val:.0f}°C — click Next to continue.")
				if self.nozzleCheckProgressBar:
					self.nozzleCheckProgressBar.setValue(100)
		except Exception as e:
			self.logger.warning(f"Heat check error: {e}")

	def _stop_heat_timer(self):
		"""Stop the heating monitor timer."""
		try:
			if self._heat_timer.isActive():
				self._heat_timer.stop()
		except Exception:
			pass


	# ----- Step 3: Nozzle Selection ----------------------------------------
	def _prepare_nozzle_selection(self):
		"""Populate nozzle options and enforce selection before Done."""
		try:
			try:
				self.changeNozzleComboBox.currentIndexChanged.disconnect(self._on_nozzle_choice_changed)
			except Exception:
				pass

			self.changeNozzleComboBox.clear()
			self.changeNozzleComboBox.addItem("Select Size")
			options = list(getattr(self.model, 'nozzle_options', []) or [])
			if not options:
				options = ["0.6", "0.8", "1.0", "1.5", "2.0", "3.0"]
			for opt in options:
				self.changeNozzleComboBox.addItem(str(opt))

			self._enable_next(self.changeNozzleComboBox.currentIndex() > 0)
			self.changeNozzleComboBox.currentIndexChanged.connect(self._on_nozzle_choice_changed)
		except Exception as e:
			self.logger.warning(f"Failed to prepare nozzle selection: {e}")

	def _on_nozzle_choice_changed(self, idx: int):
		"""Enable Done only when a valid nozzle size is selected."""
		try:
			self._enable_next(idx > 0)
		except Exception:
			pass

	# ----- Helpers --------------------------------------------------------
	def _enable_next(self, enabled: bool):
		"""Safely enable/disable the Next button."""
		try:
			if self.nextButton:
				self.nextButton.setEnabled(bool(enabled))
		except Exception:
			pass

	def _cool_down(self):
		"""Turn off the heater for the active tool."""
		if not self.octoprint_client or not self._heating_started:
			return
		try:
			self.octoprint_client.gcode("M104 S0")
			self._heating_started = False
			self.logger.info("Sent M104 S0 to cool down")
		except Exception as e:
			self.logger.warning(f"Failed to send cooldown command: {e}")

	def _get_tool_index(self, tool: str) -> int:
		"""Extract numeric index from a tool name like 'tool0'."""
		try:
			return int((tool or "tool0").replace('tool', '') or 0)
		except Exception:
			return 0

	def _check_filament_unloaded(self, tool: str) -> bool:
		"""Warn and exit if filament is still loaded."""
		try:
			state = self.model.get_bay_state(tool) or {}
			if str(state.get('status')) == 'Loaded':
				dialog.WarningOk(self, "Filament is loaded. Please unload filament before changing the nozzle.", overlay=True)
				fms = getattr(self.main_window, "filament_management_screen", None)
				if fms and hasattr(fms, "show_material_nozzle_screen"):
					QtCore.QTimer.singleShot(0, lambda: fms.show_material_nozzle_screen())
				return False
			return True
		except Exception:
			return True

