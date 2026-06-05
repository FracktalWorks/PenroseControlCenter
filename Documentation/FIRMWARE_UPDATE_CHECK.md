# Firmware Update Check Feature

## Overview

The Firmware Update Check feature provides automatic detection and optional updating of printer firmware configurations during application startup. This ensures users always have access to the latest printer configurations and improvements without manual intervention.

## How It Works

### Version Detection

The system uses version comments in `printer.cfg` files to determine if updates are available:

```cfg
########################################
# printer.cfg
# Main configuration used by Klipper
# Author: Vijay Raghav Varada
# Version: 2
########################################
```

The version is specified as `# Version: X` where X is an integer version number.

### Update Check Process

1. **Startup Check**: During application startup, after Klipper configuration validation
2. **Version Comparison**: Compares the version in `/home/pi/printer.cfg` with the template in `octoprint_PenroseControlCenter/firmware/printer.cfg`
3. **User Prompt**: If a newer version is detected, shows a dialog asking if the user wants to update
4. **Update Process**: If accepted, performs the firmware update while preserving user data

### Data Preservation During Updates

The firmware update process is designed to preserve critical user data:

#### MCU Configuration Preservation
- **CAN Bus UUIDs**: Hardware identifiers for main MCU and toolhead MCUs
- **Serial Port Settings**: Communication parameters for connected hardware
- **Hardware-Specific Settings**: Any custom MCU configuration

#### SAVE_CONFIG Section Preservation  
- **Probe Calibration**: Z-offset values and probe accuracy settings
- **Bed Mesh Data**: Auto bed leveling mesh points and calibration
- **Temperature Calibration**: PID tuning values for hotends and heated bed
- **Stepper Calibration**: Steps per mm and other motor calibration data
- **All Klipper Auto-Generated Settings**: Any configuration automatically saved by Klipper

#### Update Process Flow
1. **Extract User Data**: Parse and preserve both MCU Config and SAVE_CONFIG sections from current file
2. **Apply New Firmware**: Copy latest firmware template with new features and improvements  
3. **Merge Preserved Data**: Intelligently merge user's hardware and calibration data into new firmware
4. **Restart System**: Apply updated configuration while maintaining all user customizations

This ensures users get the latest firmware features without losing their hardware setup or calibration work.

### File Locations

- **Active Configuration**: `/home/pi/printer.cfg` - The currently active printer configuration
- **Firmware Template**: `octoprint_PenroseControlCenter/firmware/printer.cfg` - The latest firmware template
- **Printer Configs**: `octoprint_PenroseControlCenter/firmware/PRINTER_*.cfg` - Individual printer configuration files

## User Interface

### Toggle Control

Users can enable/disable firmware update checking via the **Firmware Update** toggle button in:
- **Control Screen** → **Preferences Tab** → **Firmware Update Button**

The button shows the current state:
- ✅ **Green/Checked**: Firmware update checking is enabled (default)
- ❌ **Gray/Unchecked**: Firmware update checking is disabled

### Update Dialog

When a firmware update is available, the system shows a dialog with:
- Current version number
- New version number  
- Printer name being updated
- Warning about printer restart
- **OK/Cancel** options

Example dialog:
```
Firmware Update Available!

Current version: 2
New version: 3

This will update the configuration for 'Dragon 400' and restart the printer.

Do you want to update now?
[OK] [Cancel]
```

## Developer Implementation

### Code Architecture

The feature is implemented across several components:

#### 1. Version Checking (`utils/printer_config_manager.py`)

```python
def get_config_version(config_path: str) -> Optional[int]:
    """Extract version number from a printer.cfg file."""

def is_firmware_update_available() -> bool:
    """Check if firmware template has a newer version than current config."""
```

#### 2. User Preferences (`utils/printer_preference_store.py`)

```python
"preferences": {
    "firmware_update_check_enabled": True,  # Default to enabled
}
```

#### 3. Main Controller Integration (`controller/main_controller.py`)

```python
def check_firmware_update(self):
    """Check if firmware update is available and prompt user if enabled."""

def perform_firmware_update(self, current_printer: str, printer_display_name: str):
    """Perform the firmware update by copying files and restarting."""
```

#### 4. UI Controls (`ui/control_screen/control_screen.py`)

```python
def toggleFirmwareUpdate(self):
    """Toggle firmware update check preference and persist the setting."""
```

### Integration Points

- **Startup Flow**: Called in `handleStartupSuccess()` after Klipper configuration check
- **Preference Storage**: Persisted in printer preference store
- **UI State**: Synchronized with toggle button in control screen
- **Update Process**: Uses existing `copy_firmware_files()` and `restore_octoprint_configs()` methods

## Configuration Management

### Adding New Firmware Versions

To release a new firmware version:

1. **Update Version Number**: Increment the version in `octoprint_PenroseControlCenter/firmware/printer.cfg`
   ```cfg
   # Version: 3  # Increment from previous version
   ```

2. **Update Configuration**: Make necessary changes to the firmware configuration files

3. **Deploy**: The next time users start the application, they'll be prompted to update

### Version Numbering

- Use **integer version numbers** (1, 2, 3, etc.)
- **Increment sequentially** for each release
- **No decimal versions** (use 3, not 2.1)

### Backward Compatibility

The feature is designed to be backward compatible:
- Works even if UI toggle button doesn't exist
- Gracefully handles missing version comments
- Falls back to no-update-available if version parsing fails

## Testing

### Manual Testing

1. **Enable Feature**:
   - Go to Control Screen → Preferences Tab
   - Ensure Firmware Update button is checked (green)

2. **Test Update Available**:
   - Modify `octoprint_PenroseControlCenter/firmware/printer.cfg` to have a higher version number
   - Restart the application
   - Verify update dialog appears

3. **Test Update Process**:
   - Accept the update dialog
   - Verify printer configuration is updated
   - Verify Klipper restarts

4. **Test Disable Feature**:
   - Uncheck Firmware Update button
   - Restart application with newer firmware version
   - Verify no update dialog appears

### Automated Testing

```python
# Test version parsing
def test_version_parsing():
    manager = PrinterConfigManager()
    version = manager.get_config_version("test_printer.cfg")
    assert version == 2

# Test update availability
def test_update_availability():
    assert is_firmware_update_available() == True  # When firmware newer
    assert is_firmware_update_available() == False  # When up to date
```

## Troubleshooting

### Common Issues

#### Update Check Not Running
- **Cause**: Feature disabled in preferences
- **Solution**: Enable via Control Screen → Preferences → Firmware Update button

#### Version Not Detected
- **Cause**: Missing or malformed version comment
- **Solution**: Ensure `# Version: X` format in printer.cfg

#### Update Process Fails
- **Cause**: File permissions or missing printer configuration
- **Solution**: Check logs, verify printer selection, ensure firmware files exist

### Log Messages

Monitor these log messages for debugging:

```
INFO: Firmware update available: v2 -> v3
INFO: User accepted firmware update
INFO: Performing firmware update for DRAGON_400
INFO: Firmware files updated successfully
```

### Error Handling

The system includes comprehensive error handling:
- **File access errors**: Graceful fallback to no-update-available
- **Permission errors**: Clear error messages to user
- **Network errors**: Retry mechanisms for printer restart
- **Configuration errors**: Validation and backup restoration

## Security Considerations

### File System Access

- Updates only modify configuration files in designated directories
- No system-level file modifications
- Backup and restoration mechanisms protect against corruption

### User Consent

- **Explicit user consent** required for all updates
- **Clear information** about what will be updated
- **Option to decline** updates without affecting functionality

### Validation

- Version number validation prevents downgrade attacks
- Configuration file validation ensures integrity
- Printer configuration validation prevents invalid setups

## Future Enhancements

### Planned Features

1. **Release Notes**: Display changelog information in update dialog
2. **Selective Updates**: Allow users to choose which configurations to update
3. **Scheduled Checks**: Optional periodic update checking beyond startup
4. **Update History**: Track applied updates and allow rollback
5. **Network Updates**: Download updates from remote server

### API Extensions

```python
# Future API additions
def get_update_changelog(from_version: int, to_version: int) -> str:
    """Get changelog for version range."""

def rollback_firmware_update(target_version: int) -> bool:
    """Rollback to previous firmware version."""
```

## Related Documentation

- [Dynamic Printer Configuration](DYNAMIC_PRINTER_CONFIG.md) - How printer configurations are managed
- [Single/Dual Nozzle Configuration](SINGLE_DUAL_NOZZLE_CONFIGURATION.md) - Printer-specific configurations
- [Manual Testing Guide](MANUAL_TESTING_GUIDE.md) - General testing procedures

## Support

For issues related to firmware updates:

1. Check application logs for error messages
2. Verify printer configuration files exist and are readable
3. Ensure adequate disk space for backup operations
4. Contact support at care.fracktal.in with log files if problems persist
