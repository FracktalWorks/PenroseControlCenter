# Single/Dual Nozzle Configuration Guide

This guide explains how to configure new UI elements or pages to work with both single and dual nozzle printer configurations.

## Overview

The ControlCenter project supports both single and dual nozzle printers. The configuration is controlled by:
- **Main Config**: `config.py` - `IS_DUAL_NOZZLE` boolean flag (dynamically loaded from Klipper)
- **UI Config Module**: `utils/printer_ui_config.py` - Handles UI element hiding and tool forcing
- **Configuration Manager**: `utils/printer_config_manager.py` - Manages printer configuration from Klipper firmware files
- **Dynamic Loading**: Configuration is automatically loaded from active `PRINTER_<NAME>.cfg` files

### How It Works

1. **Klipper Configuration**: Each printer firmware file (`PRINTER_DRAGON_400.cfg`, etc.) contains a `PRINTER_VARIABLES` macro with `variable_is_dual_nozzle: 0` (single) or `1` (dual)
2. **Dynamic Loading**: `PrinterConfigManager` parses the active printer configuration and updates `config.IS_DUAL_NOZZLE`
3. **UI Adaptation**: `printer_ui_config.py` reads the current value and shows/hides UI elements accordingly
4. **Real-time Updates**: Configuration is reloaded when printer type changes or on WebSocket connection

## Quick Setup for New UI Elements

### 1. For New UI Screens/Pages

When adding a new screen that has dual nozzle specific elements:

```python
# In your new screen file (e.g., ui/new_screen/new_screen.py)
from utils.printer_ui_config import apply_nozzle_config_to_screen

class NewScreen(QWidget):
    def __init__(self):
        super().__init__()
        # ... your UI setup code ...
        
        # Apply nozzle configuration (add this line)
        self.apply_nozzle_configuration()
    
    def apply_nozzle_configuration(self):
        """Apply nozzle configuration for this screen"""
        apply_nozzle_config_to_screen(self, 'new_screen')
```

### 2. For Individual UI Elements

If you have specific dual nozzle elements to hide:

```python
# In your UI file
from utils.printer_ui_config import hide_dual_nozzle_elements

# Hide specific elements
dual_elements = ['tool1Button', 'tool1Label', 'tool1Widget']
hide_dual_nozzle_elements(self, dual_elements)
```

### 3. For Custom Single Nozzle Styling

If you need custom styling for single nozzle mode (like border radius):

```python
# In your screen file
from utils.printer_ui_config import is_dual_nozzle_printer

def apply_nozzle_configuration(self):
    """Apply nozzle configuration and styling"""
    apply_nozzle_config_to_screen(self, 'your_screen')
    
    # Apply custom styling for single nozzle mode
    if not is_dual_nozzle_printer():
        self._apply_single_nozzle_styling()

def _apply_single_nozzle_styling(self):
    """Apply custom styling for single nozzle configuration."""
    if hasattr(self, 'someButton') and self.someButton:
        current_style = self.someButton.styleSheet()
        # Create proper CSS structure for QPushButton
        border_style = "QPushButton { border-top-left-radius: 15px; border-top-right-radius: 15px; }"
        # Combine existing style with new border style
        new_style = current_style + " " + border_style if current_style else border_style
        self.someButton.setStyleSheet(new_style)
        
    # Example for spinbox styling
    if hasattr(self, 'someSpinBox') and self.someSpinBox:
        current_style = self.someSpinBox.styleSheet()
        # Create proper CSS structure for QSpinBox
        border_style = "QSpinBox { border-bottom-left-radius: 15px; }"
        # Combine existing style with new border style
        new_style = current_style + " " + border_style if current_style else border_style
        self.someSpinBox.setStyleSheet(new_style)
```

### 4. For Tool Selection Logic

When handling tool selection in wizards or dialogs:

```python
# In wizard/dialog files
from utils.printer_ui_config import force_single_tool, is_dual_nozzle_printer

# Force tool1 to tool0 for single nozzle printers
selected_tool = force_single_tool(requested_tool)

# Check printer configuration
if is_dual_nozzle_printer():
    # Show dual nozzle options
else:
    # Hide or disable dual nozzle features
```

## Configuration Steps

### Step 1: Update Element Dictionary

Add your screen's dual nozzle elements to `utils/printer_ui_config.py`:

```python
DUAL_NOZZLE_ELEMENTS = {
    'home_screen': [
        'tool1Label', 'tool1LoadedNozzle', 'tool1LoadedFilament',
        'tool1TargetTemperature', 'tool1TempBar', 'tool1ActualTemperature', 'tool1TextLabel', 'toolSeperationLine'
    ],
    'control_screen': [
        'toolToggleTemperatureButton', 'toolToggleMotionButton',
        'togglePelletSensorT1Button',
        'H1TempSpinBox', 'setH1TempButton', 'H140PreheatButton', 'H160PreheatButton'
    ],
    'filament_management_screen': [
        'changeTool1MaterialBayX', 'tool1Frame', 'editTool1MaterialBayX',
        'tool11MaterialBayXStateColor', 'tool1MaterialBayXStateLabel', 'changeTool1Button',
        'tool1MaterialBayXLabel'
    ],
    'calibrate_screen': [
        'idexCalibrationWizardButton', 'toolOffsetZButton', 'toolOffsetXYButton',
        'cameraToolOffsetCalibrateButton', 'toolZOffsetWizardButton'
    ],
    # Add your new screen here
    'your_new_screen': [
        'tool1Button',
        'tool1Label', 
        'tool1Frame',
        'tool1TempDisplay',
        # Add all tool1/T1/dual-specific element names
    ]
}
```

**Note**: The current implementation uses `getattr(widget, element_name, None)` to find elements, so ensure your element names match the actual attribute names on your widget.

### Step 2: Import and Apply Configuration

In your screen file, import and apply the configuration:

```python
from utils.printer_ui_config import apply_nozzle_config_to_screen

# In your __init__ or setup method:
self.apply_nozzle_configuration()

def apply_nozzle_configuration(self):
    """Apply nozzle configuration for this screen"""
    apply_nozzle_config_to_screen(self, 'your_screen_name')
```

## GitHub Copilot Automation Prompts

### For New UI Screens

```
Add single/dual nozzle configuration to this new UI screen. 
1. Import apply_nozzle_config_to_screen from utils.printer_ui_config
2. Add apply_nozzle_configuration() method that calls apply_nozzle_config_to_screen(self, 'screen_name')
3. Call self.apply_nozzle_configuration() in __init__ after UI setup
4. Identify all tool1/T1/dual nozzle UI elements in this screen
```

### For Element Dictionary Updates

```
Update the DUAL_NOZZLE_ELEMENTS dictionary in utils/printer_ui_config.py to include these new dual nozzle elements for 'screen_name': [list of element names that should be hidden for single nozzle printers]. Look for elements with 'tool1', 'T1', or dual-specific naming.
```

### For Custom Single Nozzle Styling

```
Add custom styling for single nozzle mode to this screen:
1. Import is_dual_nozzle_printer from utils.printer_ui_config
2. Modify apply_nozzle_configuration() to check if not is_dual_nozzle_printer() and call _apply_single_nozzle_styling()
3. Create _apply_single_nozzle_styling() method that applies custom CSS styling (like border-radius) to specific UI elements for single nozzle mode
4. Use proper CSS structure with selectors like "QPushButton { property: value; }" or "QSpinBox { property: value; }"
5. Combine existing styles with new styles using string concatenation and conditional logic
```

### For Wizard/Tool Selection Logic

```
Add single nozzle support to this wizard/dialog:
1. Import force_single_tool and is_dual_nozzle_printer from utils.printer_ui_config
2. Use force_single_tool() when selecting tools to convert tool1 to tool0 for single nozzle
3. Use is_dual_nozzle_printer() to conditionally show/hide dual nozzle options
4. Hide tool selection UI for single nozzle configuration
```

### For Finding Missing Elements

```
Search this UI file for any dual nozzle elements (containing 'tool1', 'T1', or dual-specific names) that should be hidden for single nozzle printers. Check both findChild() calls and direct element references. List them in the format needed for DUAL_NOZZLE_ELEMENTS dictionary.
```

## Testing Your Implementation

### Test Single Nozzle Mode
1. **Automatic Detection**: Configuration is automatically read from active `PRINTER_<NAME>.cfg` file
2. **For Manual Testing**: Temporarily modify `variable_is_dual_nozzle: 0` in the active printer config file
3. Launch the application
4. Verify dual nozzle elements are hidden
5. Test tool selection defaults to tool0

### Test Dual Nozzle Mode  
1. **Automatic Detection**: Configuration is automatically read from active `PRINTER_<NAME>.cfg` file
2. **For Manual Testing**: Temporarily modify `variable_is_dual_nozzle: 1` in the active printer config file
3. Launch the application
4. Verify all elements are visible
5. Test tool selection works for both tools

### Test Configuration Loading
```python
# Test current configuration
from utils.printer_config_manager import get_printer_config_from_klipper
config = get_printer_config_from_klipper()
print(f"Dual nozzle: {config['IS_DUAL_NOZZLE'] if config else 'Failed to load'}")

# Test specific printer
from utils.printer_config_manager import get_printer_config_manager
manager = get_printer_config_manager()
dragon_config = manager.get_printer_config_from_variables("DRAGON_400")
print(f"Dragon 400 dual nozzle: {dragon_config['is_dual']}")
```

## Workflow Adaptations

### Calibration Workflows
The system automatically adapts calibration workflows for single nozzle mode:

**Bed Leveling (`bedLevelingPage.py`)**:
- ✅ **Single Nozzle**: Skips nozzle height calibration step, goes directly to completion
- ✅ **Dual Nozzle**: Performs full dual nozzle height calibration workflow
- ✅ **Heater Management**: Only heats/cools relevant extruders based on configuration
- ✅ **Tool Offset**: Skips tool offset calculations for single nozzle mode

### Implementation Example
```python
# In calibration workflow
if not is_dual_nozzle_printer():
    self.logger.info("Single nozzle mode detected - skipping dual nozzle steps")
    self.skip_to_completion()
    return
```

## Common Element Patterns

### UI Elements to Hide (Examples)
- `tool1*` - Any element starting with tool1
- `*T1*` - Any element containing T1
- `*Dual*` - Any element with dual in the name
- `idex*` - IDEX-specific elements
- `toolOffset*` - Tool offset calibration
- `toolToggle*` - Tool toggle buttons

### Elements to Keep Visible
- `tool0*` - Primary tool elements
- `*Bed*` - Bed-related elements
- `*Print*` - Print job elements
- Generic controls and displays

## File Structure

```
octoprint_PenroseControlCenter/
├── config.py                          # Dynamic configuration data (IS_DUAL_NOZZLE loaded from Klipper)
├── utils/
│   ├── printer_ui_config.py          # UI configuration module with is_dual_nozzle_printer()
│   └── printer_config_manager.py     # Manages printer configuration from Klipper files
├── firmware/                          # Printer configuration files
│   ├── PRINTER_PENROSE_600_DUAL.cfg  # Dual nozzle IDEX printer (is_dual_nozzle: 1)
│   ├── PRINTER_PENROSE_600_SINGLE.cfg # Single nozzle printer (is_dual_nozzle: 0)
│   ├── BASE_PENROSE_DUAL.cfg         # IDEX hardware base config (dual carriage, extruder1, H1)
│   ├── BASE_PENROSE_SINGLE.cfg      # Single nozzle hardware base config (no dual carriage)
│   ├── PELLET_RELAY_CONTROL_DUAL.cfg # Pellet feeder system - both LEFT and RIGHT valves
│   ├── PELLET_RELAY_CONTROL_SINGLE.cfg # Pellet feeder system - LEFT valve only
│   ├── T0_PELLET_LEVEL_SENSOR.cfg   # Left pellet level sensor
│   └── T1_PELLET_LEVEL_SENSOR.cfg   # Right pellet level sensor (dual nozzle only)
└── ui/
    ├── main_window.py                 # Uses apply_nozzle_config_to_all_screens()
    ├── home_screen/
    ├── control_screen/
    ├── calibrate_screen/
    ├── filament_management_screen/
    └── your_new_screen/               # Your new screen here
```

## Architecture Design

### Clean Separation of Concerns
- **`config.py`**: Dynamic configuration data (automatically updated from Klipper)
- **`utils/printer_config_manager.py`**: Configuration loading and parsing logic
- **`utils/printer_ui_config.py`**: UI configuration logic and management functions
- **UI Files**: Import from `printer_ui_config` for all configuration needs

### Configuration Flow
```python
# Klipper firmware files - Source of truth
# PRINTER_DRAGON_400.cfg: variable_is_dual_nozzle: 0
# PRINTER_TWINDRAGON_600.cfg: variable_is_dual_nozzle: 1

# utils/printer_config_manager.py - Loading logic
def get_printer_config_from_klipper():
    variables = parse_printer_variables_from_file(active_printer_file)
    return extract_printer_configuration(variables)

# config.py - Dynamic data (updated at runtime)
IS_DUAL_NOZZLE = False  # Updated by load_printer_config_from_klipper()

# utils/printer_ui_config.py - UI logic
def is_dual_nozzle_printer():
    return config.IS_DUAL_NOZZLE

# UI files - Usage
from utils.printer_ui_config import is_dual_nozzle_printer
```

### Dynamic Configuration Loading

The system automatically loads configuration in these scenarios:
1. **Application Startup**: PrinterModel initialization loads config from Klipper
2. **WebSocket Connection**: MainController triggers config reload when connected to Klipper
3. **Printer Type Change**: Printer setup triggers config reload when printer type is changed
4. **Manual Reload**: `printer_model.reload_printer_configuration()` can be called manually

## Best Practices

1. **Dynamic Configuration**: Don't hardcode `IS_DUAL_NOZZLE` values - let the system load them from Klipper
2. **Consistent Naming**: Use `tool1*` prefix for dual nozzle elements
3. **Element Discovery**: Use `getattr(widget, element_name, None)` pattern for finding elements
4. **Single Method**: Use `apply_nozzle_config_to_screen()` for simplicity
5. **Complete Lists**: Include all dual nozzle elements in the DUAL_NOZZLE_ELEMENTS dictionary
6. **Test Both Modes**: Always test with both Dragon (single) and TwinDragon (dual) printer configurations
7. **Tool Forcing**: Use `force_single_tool()` in wizards and tool selection logic
8. **Configuration Signals**: Listen to `printer_config_updated` signal for dynamic updates
9. **Error Handling**: Always check if elements exist before trying to hide them
10. **Logging**: Use the logger to debug element hiding issues

### Performance Considerations

- **Lazy Loading**: UI elements are only hidden when `is_dual_nozzle_printer()` returns False
- **Cached Access**: `is_dual_nozzle_printer()` directly accesses `config.IS_DUAL_NOZZLE` (no file I/O)
- **Batch Operations**: `apply_nozzle_config_to_all_screens()` processes all screens efficiently
- **Error Resilience**: Failed element hiding doesn't crash the application

### Integration Points

The single/dual nozzle system integrates with:
- **PrinterModel**: Automatic configuration loading and updates
- **MainController**: Configuration reload on WebSocket connection  
- **Printer Setup**: Configuration reload when printer type changes
- **Calibration Workflows**: Automatic workflow adaptation for single nozzle mode
- **Filament Management**: Tool-specific UI element management

## Quick Validation

Run this test to verify your configuration works:

```bash
# Test imports
cd octoprint_PenroseControlCenter
python -c "from utils.printer_ui_config import *; print('✅ Configuration working')"

# Test configuration loading
python -c "from utils.printer_config_manager import get_printer_config_from_klipper; config = get_printer_config_from_klipper(); print(f'✅ Config loaded: IS_DUAL_NOZZLE = {config[\"IS_DUAL_NOZZLE\"] if config else \"Failed to load\"}')"

# Test specific printer configurations
python -c "
from utils.printer_config_manager import get_printer_config_manager
manager = get_printer_config_manager()
for printer in manager.get_available_printers():
    config = manager.get_printer_config_from_variables(printer)
    print(f'{printer}: dual_nozzle = {config[\"is_dual\"]}')
"
```

### Configuration Debugging

If configuration isn't working as expected:

```python
# Debug current configuration
import config
from utils.printer_ui_config import is_dual_nozzle_printer
from utils.printer_config_manager import get_current_printer_selection

print(f"Current config.IS_DUAL_NOZZLE: {config.IS_DUAL_NOZZLE}")
print(f"is_dual_nozzle_printer(): {is_dual_nozzle_printer()}")
print(f"Active printer: {get_current_printer_selection()}")

# Force reload configuration
success = config.load_printer_config_from_klipper()
print(f"Config reload success: {success}")
print(f"After reload IS_DUAL_NOZZLE: {config.IS_DUAL_NOZZLE}")
```

---

**Need Help?** If you encounter issues:
1. Check that element names in `DUAL_NOZZLE_ELEMENTS` match exactly with `findChild()` calls
2. Verify imports are correct
3. Ensure `apply_nozzle_configuration()` is called after UI setup
4. Test configuration loading with the debug scripts above
5. Verify the active printer configuration file contains correct `variable_is_dual_nozzle` value
6. Check that `PrinterConfigManager` can successfully parse the active printer file

### Common Issues and Solutions

**Issue**: UI elements not hiding for single nozzle printer
- **Solution**: Check that `config.IS_DUAL_NOZZLE` is correctly loaded from Klipper
- **Debug**: Run `python -c "import config; print(config.IS_DUAL_NOZZLE)"` to verify value

**Issue**: Configuration not updating after printer change
- **Solution**: Ensure `printer_model.reload_printer_configuration()` is called after printer selection
- **Debug**: Check that WebSocket connection triggers configuration reload

**Issue**: Parser cannot find PRINTER_VARIABLES
- **Solution**: Verify `PRINTER_<NAME>.cfg` file exists in firmware directory and contains valid `[gcode_macro PRINTER_VARIABLES]` section
- **Debug**: Use `manager.parse_printer_variables_from_file()` to test specific files
