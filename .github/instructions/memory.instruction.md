---
applyTo: '**'
---

# PenroseControlCenter - AI Development Memory

## Project Overview

**PenroseControlCenter** is an OctoPrint plugin that provides a PyQt5-based touchscreen interface for controlling Penrose series pellet IDEX 3D printers. The plugin runs on Raspberry Pi hardware with an 800x480 touchscreen display.

### Key Technologies
- **Framework**: PyQt5 with Qt Designer for UI files
- **Architecture**: Model-View-Presenter (MVP)
- **Backend**: OctoPrint REST API and WebSocket communication
- **Firmware**: Klipper with dynamic configuration system
- **Hardware**: Raspberry Pi with 800x480 touchscreen
- **Printer Type**: Cartesian IDEX (Independent Dual Extrusion) with pellet feeders

---

## Printer Hardware Architecture

### Penrose Printer Family
Penrose is a line of large-format pellet IDEX 3D printers manufactured by Fracktal Works.

**Current Models:**
- **Penrose 600**: 600x600x625mm build volume

### Kinematics
- **Type**: Cartesian with IDEX (dual_carriage)
- **X-Axis**: Dual independent carriages (T0 and T1)
- **Y-Axis**: Dual motor configuration (stepper_y and stepper_y1)
- **Z-Axis**: Single motor with bed leveling

### IDEX Configuration
```
T0 (Primary Carriage):
- position_min: -30  (park position)
- position_max: 600  (travel limit)

T1 (Dual Carriage):
- position_min: 0    (travel limit)
- position_max: 630  (park position)

Safe Distance: 60mm (minimum spacing between carriages)
```

### Stepper Motors
All steppers use **external DM542 drivers** requiring:
- `step_pulse_duration: 0.000005` (5µs)
- `microsteps: 8`
- `rotation_distance: 20`
- `full_steps_per_rotation: 200`

---

## Pellet Extrusion System

### Overview
Unlike traditional filament printers, Penrose uses **pellet feeders** that transport plastic pellets from bulk hoppers to the extruders using a **pneumatic line vac system**.

### Components

#### 1. Line Vac Solenoid Valves
Solenoid valves control pneumatic flow for pellet transport:
```
T0 Solenoid: PD14 (output_pin pellet_vac_left)
T1 Solenoid: PD15 (output_pin pellet_vac_right) - Changed from PE9 to avoid boot activation

Logic: Active-LOW relays with pin inversion (!)
- VALUE=1 → Valve OPEN → Pellets flowing
- VALUE=0 → Valve CLOSED → No flow

MUTUAL EXCLUSION: Only one vac can be on at a time
```

#### 2. Capacitive Pellet Level Sensors
Detect when hoppers need refilling:
```
T0 Sensor: PF4 (filament_switch_sensor pellet_level_T0)
T1 Sensor: PC15 (filament_switch_sensor pellet_level_T1)

Trigger Logic:
- filament_detected=True → Pellets OK → Line vac OFF
- filament_detected=False → Pellets LOW → Line vac ON
```

#### 3. Control Flow
```
[Sensor detects LOW pellets] 
    → runout_gcode: LINEVAC_Tx_ON
    → Pellets transport via line vac
    → Sensor detects pellets OK
    → insert_gcode: LINEVAC_Tx_OFF
```

### Key Macros
- `LINEVAC_T0_ON/OFF` - Control T0 line vac
- `LINEVAC_T1_ON/OFF` - Control T1 line vac
- `LINEVAC_ALL_ON/OFF` - Control both simultaneously
- `SET_PELLET_SENSOR S=<0|1> T=<0|1>` - Enable/disable sensors
- `QUERY_PELLET_SYSTEM` - Status report

---

## Klipper Firmware Structure

### Configuration Files
Located in `octoprint_PenroseControlCenter/firmware/`:

| File | Purpose |
|------|---------|
| `printer.cfg` | Main entry point, includes all other configs |
| `BASE_PENROSE.cfg` | Common hardware: steppers, MCU pins, heaters |
| `PRINTER_PENROSE_600.cfg` | Model-specific: dimensions, PRINTER_VARIABLES |
| `CORE_GCODE_MACROS.cfg` | Marlin-compatible G-codes (M104, M218, M503, etc.) |
| `PELLET_RELAY_CONTROL.cfg` | Pellet feeder solenoids and control macros |
| `T0_PELLET_LEVEL_SENSOR.cfg` | T0 capacitive sensor config |
| `T1_PELLET_LEVEL_SENSOR.cfg` | T1 capacitive sensor config |
| `variables.cfg` | Runtime variables storage |

### PRINTER_VARIABLES Macro
Contains printer-specific settings accessed via `printer["gcode_macro PRINTER_VARIABLES"]`:

```python
# Key variables for Penrose 600:
variable_bed_x_max: 600
variable_bed_y_max: 600
variable_bed_z_max: 625
variable_is_dual_nozzle: 1
variable_fan0_0: 'extruder_CF_0'    # T0 part cooling fan 1
variable_fan0_1: 'extruder_CF_1'    # T0 part cooling fan 2
variable_fan1_0: 'extruder1_CF_0'   # T1 part cooling fan 1
variable_fan1_1: 'extruder1_CF_1'   # T1 part cooling fan 2
variable_autopark: 1                 # Enable IDEX auto-parking
variable_z_hop: 0.6                  # Z-hop during tool change
variable_movespeed: 300              # Travel speed mm/s
```

### MCU Configuration
- **Main MCU**: STM32 (Octopus-style board)
- **Communication**: Serial via `/dev/serial/by-id/usb-Klipper_*`
- **Restart Method**: `command`

---

## OctoPrint Plugin Structure

### Package Layout
```
octoprint_PenroseControlCenter/
├── __init__.py          # Plugin entry point, OctoPrint hooks
├── _version.py          # Versioneer generated
├── main.py              # PyQt5 application entry
├── config.py            # Configuration management
├── controller/          # Application controllers
├── models/              # Data models (printer_model.py)
├── octoprint_client/    # OctoPrint API wrapper
├── ui/                  # PyQt5 UI screens
└── firmware/            # Klipper configuration files
```

### Plugin Class
```python
class PenroseControlCenter(octoprint.plugin.StartupPlugin,
                           octoprint.plugin.SoftwareUpdatePlugin):
```

### Update Mechanism
Uses GitHub releases via OctoPrint's software update:
```python
type="github_release"
user="FracktalWorks"
repo="PenroseControlCenter"
```

---

## UI Development

### Screen Resolution
- **Fixed**: 800x480 pixels
- **Touch Targets**: Minimum 44px height

### UI File Pattern
```
[screen_name]/
├── [screen_name].py    # Python logic
└── [screen_name].ui    # Qt Designer file
```

### Key UI Screens
- `home_screen` - Main dashboard
- `control_screen` - Manual printer control
- `calibrate_screen` - Calibration wizards
- `filament_management_screen` - Pellet/filament operations
- `settings_screen` - Configuration options
- `print_from_location` - File browser
- `loading_screen` - Startup/transition

### Signal Connections
```python
# Temperature updates
self.main_window.printer_model.temperature_updated.connect(...)

# Position updates
self.main_window.printer_model.current_position_updated.connect(...)

# Status updates
self.main_window.printer_model.status_updated.connect(...)
```

---

## Common Development Tasks

### Adding a New Calibration Wizard
1. Create folder: `ui/calibrate_screen/[wizard_name]/`
2. Create `[wizard_name].py` and `[wizard_name].ui`
3. Follow wizard pattern in `.github/instructions.md`
4. Register in `calibrate_screen.py._initialize_sub_screens()`

### Adding Klipper Macros
1. Add to appropriate `.cfg` file
2. Use `RESPOND TYPE=echo MSG="..."` for user feedback
3. Include `description:` for documentation
4. Test via OctoPrint terminal

### Modifying IDEX Behavior
1. Update `PRINTER_VARIABLES` in `PRINTER_PENROSE_600.cfg`
2. Modify macros in `CORE_GCODE_MACROS.cfg`
3. Test T0/T1 tool changes: `T0`, `T1`
4. Test IDEX modes: `M605 S0` (full control), `M605 S1` (auto-park)

### Pellet System Modifications
1. Update `PELLET_RELAY_CONTROL.cfg` for solenoid logic
2. Update `T0/T1_PELLET_LEVEL_SENSOR.cfg` for sensor behavior
3. Test with `QUERY_PELLET_SYSTEM`
4. Verify with `SET_PELLET_SENSOR S=1/0`

---

## Version Management

### Versioneer
Uses `versioneer` for git-based versioning:
- Version format: `PEP440`
- Source: `octoprint_PenroseControlCenter/_version.py`
- `.gitattributes` has `export-subst` for version injection

### Known Issues
- **Python 3.12+**: `SafeConfigParser` deprecated, use `ConfigParser` instead
- If version shows `0+unknown`, ensure:
  1. `.gitattributes` points to correct `_version.py`
  2. Git tags exist (`git tag -a v1.0.0 -m "Release"`)
  3. Run `versioneer install` after path changes

---

## Testing Guidelines

### Hardware Testing
- Test on actual Penrose printer when possible
- Verify IDEX movements with `M605 S0/S1/S2`
- Test pellet sensors with physical pellets
- Check all temperature sensors

### UI Testing
- Test on 800x480 touchscreen
- Verify touch targets are ≥44px
- Test all navigation paths
- Check error dialogs with `dialog.WarningOk()`

### Firmware Testing
- Use OctoPrint terminal for G-code testing
- Check `~/.klippy.log` for errors
- Verify with `FIRMWARE_RESTART` after config changes

---

## Important Reminders

1. **Always use absolute paths** in configuration files
2. **DM542 drivers require 5µs step pulse** - never change `step_pulse_duration`
3. **Pellet sensors use active-LOW logic** - LOW means pellets present
4. **Line vac solenoids use active-LOW relays** - 0=OPEN, 1=CLOSED
5. **IDEX safe distance is 60mm** - never reduce this
6. **4 part cooling fans per printer** - 2 per toolhead
7. **Test both T0 and T1** - IDEX issues often affect only one side
8. **NEVER save .cfg files with UTF-8 BOM** - Klipper cannot parse files with BOM (`\ufeff`). Always save as UTF-8 without BOM.

---

## Related Documentation

- [.github/instructions.md](.github/instructions.md) - Detailed wizard development patterns
- [Documentation/](Documentation/) - Feature-specific documentation
- [OctoPrint Plugin Development](https://docs.octoprint.org/en/master/plugins/)
- [Klipper Configuration Reference](https://www.klipper3d.org/Config_Reference.html)
