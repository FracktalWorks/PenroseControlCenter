# Custom Instructions for ControlCenter Development

## Project Context
This project is a PyQt5-based touchscreen interface for 3D printer control, specifically designed for OctoPrint and Klipper firmware integration. The application runs on Raspberry Pi hardware with an 800x480 touchscreen display.

## Architecture
- **Framework**: PyQt5 with Qt Designer for UI files
- **Pattern**: Model-View-Presenter (MVP) architecture
- **Integration**: OctoPrint REST API and WebSocket communication
- **Target Hardware**: Raspberry Pi with 800x480 touchscreen
- **Firmware**: Klipper with dynamic configuration system

## Coding Style
- Use camelCase for UI element names in Qt Designer
- Use PascalCase for class names
- Use snake_case for Python variables and functions
- Always include proper error handling with try-catch blocks
- Use centralized logging with `get_logger(self.__class__.__name__)`
- Prefer descriptive variable names over short abbreviations

## File Structure
- Python files: `[module_name].py`
- UI files: `[module_name].ui` (matching Python class name)
- Place UI files in same directory as Python files
- Use relative paths for loading UI files: `os.path.join(os.path.dirname(__file__), "file.ui")`

## UI Design Standards
- **Fixed Resolution**: Always 800x480 pixels with min/max size constraints
- **Theme**: Dark theme with `background-color: rgb(40, 40, 40);`
- **Touch Targets**: Minimum 44px height for interactive elements
- **Navigation**: Include back/cancel buttons for all screens
- **Wizards**: Use QStackedWidget for multi-step interfaces

## UI Element Naming Conventions
```
QStackedWidget: stackedWidget, [purpose]StackedWidget
QPushButton: backButton, nextButton, cancelButton1, [action]Button
QLabel: [content]Label, [purpose]Label, statusLabel
QProgressBar: progressBar, [operation]ProgressBar
QSpinBox: [parameter]SpinBox, temperatureSpinBox
QWidget (pages): mainPage, [step]Page, [purpose]Page
```

## Error Handling
- Wrap all OctoPrint operations in try-catch blocks
- Use `dialog.WarningOk()` for user notifications
- Use `dialog.WarningYesNo()` for confirmations
- Log all errors with appropriate context
- Provide fallback behaviors for failed operations

## Wizard Development Pattern

### Core Wizard Structure
All wizards should follow this standardized pattern for consistency and maintainability:

```python
class WizardName(QWidget):
    """
    Brief description of wizard purpose.
    
    This wizard uses a N-step process:
    1. Step Name - Description
    2. Step Name - Description
    ...
    
    Uses MVP architecture - receives data via model signals from printer_model.
    Properly handles existing configurations by adding/updating current values.
    """

    # Step indices for clarity and maintainability
    STEP_NAME1 = 0
    STEP_NAME2 = 1
    TOTAL_STEPS = 2

    def __init__(self, main_window):
        """Initialize the Wizard with UI and connections."""
        super().__init__()
        self.main_window = main_window
        self.model = main_window.printer_model
        self.octoprint_client = main_window.octoprint_client
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info("Initializing Wizard")

        # Initialize state variables
        self._init_state_variables()
        
        # Load UI and initialize components
        self._load_ui()
        self._init_ui_components()
        self._connect_signals()

        self.logger.info("Wizard initialized successfully")
```

### Required State Management Methods
```python
def _init_state_variables(self):
    """Initialize all state tracking variables."""
    # Data storage
    self.wizard_data = {}
    self.operation_complete = False

    # Signal connection tracking
    self._signal_tracking_connected = False

    # Wizard navigation state
    self._current_step = 0

def _reset_wizard_state(self):
    """Reset all wizard state variables to initial values."""
    # Disconnect any tracking if connected
    self._disconnect_tracking()
    
    # Reset to first step
    self.goto_step(0)
    
    # Reset data
    self._reset_data()

def _reset_data(self):
    """Reset wizard-specific data variables."""
    self.wizard_data = {}
    self.operation_complete = False
```

### Navigation System (goto_step Pattern)
```python
def goto_step(self, index: int):
    """
    Switch to the specified step with proper bounds checking and setup.
    
    Args:
        index (int): Step index to navigate to
    """
    index = max(0, min(index, self.TOTAL_STEPS - 1))
    prev_step = getattr(self, "_current_step", 0)

    self._current_step = index
    
    # Update UI to show correct page
    if self.stackedWidget:
        if index == self.STEP_NAME1:
            self.stackedWidget.setCurrentWidget(self.step1Page)
        elif index == self.STEP_NAME2:
            self.stackedWidget.setCurrentWidget(self.step2Page)
    
    # Update step indicator
    self._update_step_label()

    # Execute step-specific setup
    if index == self.STEP_NAME1:
        self._setup_step1()
    elif index == self.STEP_NAME2:
        self._setup_step2()

    self.logger.info(f"Switched to step {index + 1}/{self.TOTAL_STEPS}")

def _update_step_label(self):
    """Update the step progress indicator."""
    if not self.stepLabel:
        return
    
    try:
        self.stepLabel.setText(f"Step {self._current_step + 1}/{self.TOTAL_STEPS}")
    except Exception as e:
        self.logger.error(f"Error updating step label: {e}")
```

### Button Handler Pattern
```python
def on_next_clicked(self):
    """Handle next button clicks with step-based navigation."""
    self.logger.info("Next button clicked")
    try:
        if self._current_step == self.STEP_NAME1:
            # Move to next step or perform validation
            self.goto_step(self.STEP_NAME2)
        elif self._current_step == self.STEP_NAME2:
            # Final step - complete wizard
            if self.operation_complete:
                self.finish_wizard()
            else:
                dialog.WarningOk(self, "Please wait for operation to complete.", overlay=True)
                
    except Exception as e:
        self.logger.error(f"Error in on_next_clicked: {e}")
        self._show_error("Navigation Error", str(e))

def on_cancel_clicked(self):
    """Handle cancel button - reset wizard and return to main screen."""
    self.logger.info("Cancel button clicked")
    try:
        # Reset wizard state
        self._reset_wizard_state()
        
        # Return to safe state
        if self.octoprint_client:
            self.octoprint_client.gcode(command='T0')  # Return to T0
            self.octoprint_client.home(['x', 'y', 'z'])  # Home axes
        
        # Return to main screen
        if hasattr(self.main_window, 'calibrate_screen'):
            self.main_window.calibrate_screen.show_calibrate_screen()
        
    except Exception as e:
        self.logger.error(f"Error in on_cancel_clicked: {e}")
        # Still try to return to main screen even if there's an error
        if hasattr(self.main_window, 'calibrate_screen'):
            self.main_window.calibrate_screen.show_calibrate_screen()
```

### Signal/Slot Management Pattern
```python
def _connect_signals(self):
    """Connect all signal handlers."""
    # Button connections
    if self.nextButton:
        self.nextButton.clicked.connect(self.on_next_clicked)
    if self.cancelButton:
        self.cancelButton.clicked.connect(self.on_cancel_clicked)

    # Note: Model signals are connected only when needed
    # during operations, not permanently

def _connect_tracking(self):
    """Connect tracking when needed for receiving updates."""
    if not self._signal_tracking_connected and self.model:
        self.model.signal_name.connect(self.on_signal_received)
        self._signal_tracking_connected = True
        self.logger.debug("Signal tracking connected")

def _disconnect_tracking(self):
    """Disconnect tracking when no longer needed."""
    if self._signal_tracking_connected and self.model:
        try:
            self.model.signal_name.disconnect(self.on_signal_received)
            self._signal_tracking_connected = False
            self.logger.debug("Signal tracking disconnected")
        except TypeError:
            # Signal was already disconnected
            self._signal_tracking_connected = False
```

### Initialization Pattern
```python
def showEvent(self, event):
    """Reset wizard state when widget is shown."""
    super().showEvent(event)
    try:
        # Reset to first step
        self.goto_step(0)
        
        self.logger.info("Wizard started - getting latest configuration")
        
        # Get latest configuration from printer (if needed)
        if self.octoprint_client:
            self.octoprint_client.gcode(command='M503')
            
        # Initialize printer state (if needed)
        if self.octoprint_client:
            self.octoprint_client.home(['x', 'y', 'z'])
        
    except Exception as e:
        self.logger.error(f"Error in showEvent: {e}")
```

### Utility Methods Pattern
```python
def _show_error(self, title, message):
    """Show error dialog with consistent styling."""
    self.logger.error(f"{title}: {message}")
    dialog.WarningOk(self, f"{title}\n\n{message}", overlay=True)

def _get_current_config_value(self, key, default=0.0):
    """Get current configuration value from printer model."""
    try:
        if self.model and hasattr(self.model, 'config_data'):
            value = float(self.model.config_data.get(key, default))
            self.logger.debug(f"Current {key} from model: {value}")
            return value
        else:
            self.logger.warning(f"No printer model or config available for {key}, using {default}")
            return default
    except (ValueError, AttributeError) as e:
        self.logger.warning(f"Error getting {key}: {e}, using {default}")
        return default
```

### UI Component Validation
```python
def _init_ui_components(self):
    """Initialize and validate all UI components."""
    # Main navigation components
    self.stackedWidget = self.findChild(QStackedWidget, "stackedWidget")
    self.step1Page = self.findChild(QWidget, "step1Page")
    self.step2Page = self.findChild(QWidget, "step2Page")
    
    # Labels for user feedback
    self.stepLabel = self.findChild(QLabel, "stepLabel")
    self.statusLabel = self.findChild(QLabel, "statusLabel")

    # Navigation buttons
    self.nextButton = self.findChild(QPushButton, "nextButton")
    self.cancelButton = self.findChild(QPushButton, "cancelButton1")  # Note: Often cancelButton1 in UI

    # Validate all required UI components exist
    required_components = [
        self.stackedWidget, self.step1Page, self.step2Page,
        self.nextButton, self.cancelButton, self.stepLabel, self.statusLabel
    ]
    check_ui_elements(self, required_components, "WizardName")
```

## Integration Patterns
### Calibrate Screen Integration
1. Import in `octoprint_PenroseControlCenter/ui/calibrate_screen/calibrate_screen.py`
2. Add to `_initialize_sub_screens()` method
3. Connect button in `__init__` method
4. Add navigation method

### Settings Screen Integration
1. Import in `octoprint_PenroseControlCenter/ui/settings_screen/settings_screen.py`
2. Add UI button to `settings_screen.ui`
3. Initialize in `_initialize_sub_screens()`
4. Add navigation method
5. Connect button signal

### Filament Management Integration
1. Import in `octoprint_PenroseControlCenter/ui/filament_management_screen/filamentManagementScreen.py`
2. Add to `_initialize_sub_screens()` method
3. Setup wizard with appropriate parameters

## Printer Configuration
- Support both single and dual nozzle configurations
- Use `is_dual_nozzle_printer()` for conditional logic
- Use `force_single_tool()` for tool parameter validation
- Access configuration via `self.main_window.printer_model`
- Read positions from `calibrationPosition` dictionary

## OctoPrint Communication
```python
# G-code commands
self.octoprint_client.gcode("G28")  # Home all axes
self.octoprint_client.gcode("M104 S200")  # Set temperature

# Movement commands
self.octoprint_client.jog(x=10, y=10, z=1, absolute=True, speed=1500)
self.octoprint_client.home(['x', 'y', 'z'])

# Extrusion
self.octoprint_client.extrude(amount=5, speed=300)
```

## Signal/Slot Patterns
```python
# Connect to model updates
self.main_window.printer_model.temperature_updated.connect(self.on_temperature_updated)
self.main_window.printer_model.status_updated.connect(self.on_status_updated)
self.main_window.printer_model.current_position_updated.connect(self.on_position_updated)

# Button connections
self.backButton.clicked.connect(self.go_back)
self.startButton.clicked.connect(self.start_operation)
```

## Async Operations
```python
from utils.helpers import run_async

@run_async
def continuous_operation(self):
    """Example async operation for long-running tasks."""
    self.operation_active = True
    try:
        while self.operation_active:
            # Perform operation
            time.sleep(1)
    except Exception as e:
        self.logger.error(f"Error in continuous operation: {e}")
    finally:
        self.operation_active = False
```

## Testing
- Test on both single and dual nozzle configurations
- Verify UI responsiveness on 800x480 touchscreen
- Test printer communication with actual hardware
- Validate error handling with disconnected printer
- Check navigation flows between screens

## Required Imports
```python
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget, QPushButton, QStackedWidget, QLabel
from utils.helpers import check_ui_elements, run_async
from utils.logger import get_logger
from utils.printer_ui_config import is_dual_nozzle_printer, force_single_tool
from utils import dialog
```

## UI File Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>[ClassName]</class>
 <widget class="QWidget" name="[ClassName]">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>800</width>
    <height>480</height>
   </rect>
  </property>
  <property name="minimumSize">
   <size>
    <width>800</width>
    <height>480</height>
   </size>
  </property>
  <property name="maximumSize">
   <size>
    <width>800</width>
    <height>480</height>
   </size>
  </property>
  <property name="styleSheet">
   <string notr="true">background-color: rgb(40, 40, 40);</string>
  </property>
  <!-- Add UI components here -->
 </widget>
</ui>
```
