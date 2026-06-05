---
mode: 'agent'
tools: ['codebase']
description: 'Create a new filament management wizard for the ControlCenter project'
---

# Create Filament Management Wizard

Your goal is to create a new filament loading/unloading wizard for the ControlCenter 3D printer interface.

## Requirements

Ask for the wizard type (loading/unloading) and specific functionality if not provided.

The filament wizard should include:
* Tool selection (tool0/tool1) with single nozzle compliance using `force_single_tool()`
* Heating sequence with progress feedback
* Continuous extrusion/retraction with async operations using `@run_async`
* User interaction steps with clear instructions
* Proper cleanup and return navigation
* Inactivity timer for safety (5 minutes)

## File Structure
Create both Python and UI files in: `octoprint_PenroseControlCenter/ui/filament_management_screen/[wizard_name]/`
* `[wizard_name].py` - Python implementation
* `[wizard_name].ui` - Qt Designer UI file

## Implementation Pattern
Follow the filament management wizard pattern from `.github/instructions.md`:
* Inherit from QWidget
* Include `setup(params)` method for tool selection
* Implement temperature monitoring with signal connections
* Use async operations for continuous extrusion
* Include inactivity timer with event filtering

## Key Features
* Temperature management with progress bars
* Real-time temperature updates via signal connections
* Async continuous operations using `@run_async` decorator
* Safety checks and error handling
* Tool parameter validation

## UI Design
Follow UI conventions:
* QStackedWidget for multi-step interface
* 800x480 fixed size with dark theme
* Progress bars for heating feedback
* Clear step-by-step instructions
* Touch-friendly button layout

## Integration Steps
1. Import in `filamentManagementScreen.py`
2. Add to `_initialize_sub_screens()` method
3. Setup wizard with tool parameters
4. Connect to main screen navigation

Use the existing codebase patterns and ensure proper async operation cleanup.
