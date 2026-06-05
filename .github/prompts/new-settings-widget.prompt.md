---
mode: 'agent'
tools: ['codebase']
description: 'Create a new settings widget for the ControlCenter project'
---

# Create Settings Widget

Your goal is to create a new settings widget for the ControlCenter 3D printer interface.

## Requirements

Ask for the settings widget name and specific configuration type if not provided.

The settings widget should include:
* Settings loading and saving functionality
* Input validation and error handling
* Back button navigation to main settings
* Proper UI component initialization with `check_ui_elements()`
* Integration with settings_screen.py

## File Structure
Create both Python and UI files in: `octoprint_PenroseControlCenter/ui/settings_screen/[widget_name]/`
* `[widget_name].py` - Python implementation
* `[widget_name].ui` - Qt Designer UI file

## Implementation Pattern
Follow the settings widget pattern from `.github/instructions.md`:
* Constructor accepts `parent` and `settings_screen` parameters
* Implement `_initialize_components()`, `_connect_signals()`, `_load_settings()`, `_save_settings()`
* Include `go_back()` method for navigation
* Use centralized error handling with dialog notifications

## Key Features
* Configuration loading from model/config files
* Input validation for network settings, system parameters, etc.
* Real-time validation feedback
* Apply/save with confirmation dialogs
* Error handling for invalid configurations

## UI Design
Follow UI conventions:
* 800x480 fixed size with dark theme
* Form layouts for configuration inputs
* Clear labels and input validation
* Back button for navigation
* Apply/save buttons with confirmation

## Manual Integration Required
After creation, manually integrate by:
1. Import in `settings_screen.py`
2. Add UI button to `settings_screen.ui`
3. Initialize in `_initialize_sub_screens()`
4. Add navigation method
5. Connect button signal

Use the existing codebase patterns and ensure proper error handling for all configuration operations.
