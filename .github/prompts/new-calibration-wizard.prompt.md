---
mode: 'agent'
tools: ['codebase']
description: 'Create a new calibration wizard for the ControlCenter project'
---

# Create Calibration Wizard

Your goal is to create a new calibration wizard for the ControlCenter 3D printer interface following the established wizard development patterns.

## Requirements

Ask for the wizard name and specific calibration type if not provided.

The calibration wizard should include:
* Multi-step interface using QStackedWidget with goto_step navigation pattern
* Proper step constants (STEP_NAME = index) and TOTAL_STEPS
* Position control and movement commands using machineBuildSize for bed center
* Temperature monitoring if needed
* Single/dual nozzle support using `is_dual_nozzle_printer()`
* Signal/slot management with dynamic connection pattern
* M503 command on showEvent for latest printer configuration
* Proper error handling and logging with _show_error method
* Integration with calibrate_screen.py

## Wizard Architecture Pattern

Follow the standardized wizard pattern from `.github/instructions.md`:

### Core Class Structure
```python
class WizardName(QWidget):
    # Step indices as class constants
    STEP_WELCOME = 0
    STEP_OPERATION = 1
    TOTAL_STEPS = 2
    
    def __init__(self, main_window):
        # Standard initialization pattern
        
    def _init_state_variables(self):
        # State tracking variables
        
    def _load_ui(self):
        # UI file loading with error handling
        
    def _init_ui_components(self):
        # UI component initialization and validation
        
    def _connect_signals(self):
        # Signal/slot connections
```

### Navigation System
- Implement `goto_step(index)` method with bounds checking
- Use step-specific setup methods (`_setup_step1()`, etc.)
- Include `_update_step_label()` for progress indication
- Implement `on_next_clicked()` with step-based logic
- Include `on_cancel_clicked()` with proper cleanup

### Signal Management
- Use dynamic signal connection pattern (connect only when needed)
- Implement `_connect_tracking()` and `_disconnect_tracking()` methods
- Track connection state with `_signal_tracking_connected` variable
- Follow pattern from ZtoolOffsetWizard and cameraToolOffsetCalibration

### State Management
- Implement `showEvent()` with M503 command and initialization
- Include `_reset_wizard_state()` for proper cleanup
- Use `_reset_data()` for wizard-specific data reset
- Proper resource cleanup on cancel/completion

## File Structure
Create both Python and UI files in: `octoprint_PenroseControlCenter/ui/calibrate_screen/[wizard_name]/`
* `[wizard_name].py` - Python implementation
* `[wizard_name].ui` - Qt Designer UI file

## UI Design Requirements
Follow UI conventions from instructions:
* Fixed 800x480 resolution with min/max constraints
* Dark theme: `background-color: rgb(40, 40, 40);`
* Proper element naming (camelCase, descriptive suffixes)
* QStackedWidget for multi-step navigation
* Touch-friendly design (44px minimum height)
* Note: Cancel button often named "cancelButton1" in UI files

## Required UI Components
- QStackedWidget: "stackedWidget"
- Step pages: "welcomePage", "operationPage", etc.
- Navigation buttons: "nextButton", "cancelButton1"
- Status labels: "stepLabel", "statusLabel" or operation-specific labels
- Validation with check_ui_elements()

## Printer Configuration Integration
- Use `machineBuildSize` for bed center calculations (not calibrationPosition)
- Access via `self.model.machineBuildSize` with fallback defaults
- Calculate center as: `int(build_size.get('X', 300) / 2)`
- Include detailed logging of bed size and positions

## Error Handling Pattern
- Wrap all operations in try-catch blocks
- Use `_show_error(title, message)` method for consistent error display
- Include fallback behaviors for failed operations
- Log all errors with appropriate context
- Disconnect signals on errors to prevent memory leaks

## Integration Steps
1. Import in `calibrate_screen.py`
2. Add to `_initialize_sub_screens()` method
3. Connect button in `__init__` method
4. Add navigation method
5. Update main calibrate UI with new button

## Example Method Signatures
```python
def showEvent(self, event):
    # Reset wizard, send M503, initialize printer state
    
def goto_step(self, index: int):
    # Navigate with bounds checking and step setup
    
def on_next_clicked(self):
    # Step-based navigation logic
    
def on_cancel_clicked(self):
    # Cleanup and return to main screen
    
def _connect_tracking(self):
    # Dynamic signal connection
    
def _disconnect_tracking(self):
    # Signal disconnection with error handling
```

Use the existing codebase patterns from ZtoolOffsetWizard and cameraToolOffsetCalibration, ensuring compatibility with both single and dual nozzle printer configurations.
