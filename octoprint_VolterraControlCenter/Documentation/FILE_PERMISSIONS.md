# Klipper Configuration File Permissions

## Problem
When configuration files are copied to the Klipper config directory (`/home/pi/`), they may have restrictive permissions that prevent editing through:
- OctoPrint web interface
- Command line editors (nano, vim)
- Other web-based configuration tools

## Root Cause
The `shutil.copy2()` function preserves the original file permissions from the source files. If the source files have restrictive permissions (like `644` - read-only for group/others), the copied files will also be read-only for web interfaces.

## Solution
The updated `KlipperConfigManager` now:

1. **Sets proper permissions during file copying** (`copy_firmware_files`)
   - Uses `os.chmod(file, 0o664)` after copying each file
   - Permission `664` = `rw-rw-r--` allows both owner and group to write

2. **Sets proper permissions when updating printer.cfg** (`update_printer_cfg`)
   - Ensures the main printer.cfg has write permissions
   - Allows both pi user and web interfaces to modify the file

3. **Provides permission fixing utility** (`fix_config_permissions`)
   - Can fix permissions on existing files without re-copying
   - Returns status for each file processed

## Permission Model

### Target Permissions: 664 (rw-rw-r--)
- **Owner (pi)**: read + write
- **Group (www-data)**: read + write  
- **Others**: read only

### Why 664?
- **OctoPrint** runs as `www-data` group, needs write access
- **Klipper** service needs read access only
- **SSH/nano editing** works with pi user write access
- **Security**: Others can only read, not modify

## Manual Fix
If you have existing files with wrong permissions:

```bash
# Fix all at once using the utility
python fix_klipper_permissions.py

# Or manually fix individual files
chmod 664 /home/pi/printer.cfg
chmod 664 /home/pi/PRINTER_*.cfg
chmod 664 /home/pi/*.cfg
```

## Verification
Check current permissions:
```bash
ls -la /home/pi/*.cfg
```

Should show: `-rw-rw-r--` for all configuration files.

## Troubleshooting

### "Permission denied" in OctoPrint
- File permissions are too restrictive
- Run: `python fix_klipper_permissions.py`

### "Read-only file system" error
- Filesystem may be mounted read-only
- Check: `mount | grep /home`

### nano says "File is read-only"
- Wrong file permissions or ownership
- Run: `sudo chown pi:pi /home/pi/*.cfg && python fix_klipper_permissions.py`

## Prevention
The updated configuration manager automatically sets correct permissions for new deployments, preventing this issue in the future.
