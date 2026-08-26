# Penrose 600 Hybrid — Pellet / Filament, config-swapped

Branch: `Hybrid-IDEX-Penrose-600`

## What this machine is

A Penrose 600 with **two carriages on one X rail**: a pellet auger on the
left and a Dragon TD-01 filament extruder on a CAN toolhead on the right.

**Only one is configured at a time.** The printing head is chosen by which
config file `printer.cfg` includes, so **Klipper always sees a plain
single-extruder cartesian printer**. There is no `[dual_carriage]`, no tool
changing, no `T0`/`T1`, and no COPY/MIRROR.

The carriage that is not printing is held parked on its own endstop by a
`[manual_stepper]` — it is physically on the same rail and must stay
powered so it cannot drift into the printing head.

| | Penrose 600 Dual | Penrose Single | **Penrose 600 Hybrid** |
|---|---|---|---|
| Carriages | 2 (both pellet) | 1 | 2, one active at a time |
| Klipper extruders | 2 | 1 | **1** |
| Head choice | fixed | swap physically | config swap, from the UI |
| Barrel heaters | H0 + H1 | H0 | **H0 in pellet mode only** |
| CAN toolhead | none | none | filament mode only |
| Bed levelling | either tool | yes | **pellet mode only** |

## Config files

```
printer.cfg                        v18  SKU include + MODE include + [mcu] + [mcu E1]
PRINTER_PENROSE_600_HYBRID.cfg     v2   kinematics, PRINTER_VARIABLES, bed mesh
BASE_PENROSE_HYBRID.cfg            v3   SHARED: Y/Z, bed, probe, mode-adaptive macros
MODE_PELLET.cfg                    v1   X=left carriage, auger + H0, pellet feeder
MODE_FILAMENT.cfg                  v1   X=right carriage, TD-01 + side feeder
PELLET_RELAY_CONTROL_HYBRID.cfg         included by MODE_PELLET.cfg only
CORE_GCODE_MACROS.cfg                   shared Marlin-compat macros
```

Only `printer.cfg`'s `# Version:` gates the in-app firmware update prompt —
bump it whenever any of the above changes.

`printer.cfg` carries the mode selector:

```ini
#[include MODE_PELLET.cfg]
#[include MODE_FILAMENT.cfg]
```

Exactly one is uncommented. **That line is the source of truth for the
mode** — the plugin reads it the same way it reads the SKU include.

## The two modes

| | Pellet mode | Filament mode |
|---|---|---|
| `[stepper_x]` | M1, endstop `^PF0` | M2, endstop `^PF3` |
| Travel | −85 … 600 (parks −85) | 0 … 640 (parks 640) |
| Parked carriage | filament, held at 640 | pellet, held at −85 |
| `[extruder]` | M6 auger, `PA1` heater | TD-01 CAN, `E1: gpio20` |
| **Heaters** | **two — nozzle + H0 barrel** | **one — nozzle** |
| Part fans | `extruder_CF_0` + `_1` | `extruder1_CF` |
| Sensor | hopper level (`pellet_sensor_left`) | runout (`switch_sensor_E1`) |
| `[mcu E1]` | commented out | uncommented |
| Bed levelling | **yes** | no — uses the stored mesh |

### Kinematics are carried over unchanged

Every `[stepper_x]` value in each mode file is a **verbatim copy** of the
old IDEX config — pins, microsteps, rotation distance, endstop, homing
speed, and the travel limits. The rail did not move; only Klipper's view of
it did.

**Carriage separation** was previously enforced dynamically by
`[dual_carriage] safe_distance: 60`. With no `dual_carriage` there is no
dynamic check, so separation is now purely static geometry:

| | printing carriage reaches | other carriage held at | gap |
|---|---|---|---|
| Pellet mode | 600 | 640 | **40 mm** |
| Filament mode | 0 | −85 | 85 mm |

40 mm is what the machine already had at full travel, but it is below the
old 60 mm dynamic limit — meaning the previous config would have *rejected*
pellet moves past X=580 while the other carriage sat at 640.
**Commissioning check:** jog the pellet carriage to X=600 with the filament
carriage parked and measure the clearance. If they foul, reduce
`position_max` to 580 in `MODE_PELLET.cfg`.

### Head offset

The two heads are not mounted at the same point on their carriages. The old
IDEX config corrected this with `SET_GCODE_OFFSET` every time T1 was
activated, using `tool_offset_x/y/z` from `variables.cfg`.

There is no tool activation any more, so `_APPLY_HEAD_OFFSET` does it
instead: **the pellet head is the zero reference** (the probe and Z endstop
are calibrated to it) and filament mode gets the stored offset. It is
applied at boot and **re-applied after every home**, because
`homing_override` clears gcode offsets.

The values carry over untouched from IDEX commissioning. To change them:

```
SET_HEAD_OFFSET X=0.4 Y=-0.2 Z=0.15     # persisted, applies to filament mode
QUERY_HEAD_OFFSET                        # stored + live values
```

The old IDEX XY/camera calibration wizards used `M605` COPY/MIRROR and are
hidden on this machine — measure by printing a single-wall square in each
mode and comparing displacement.

## Bed levelling

**`G29` works in pellet mode only** — only the pellet nozzle triggers the
bed probe. In filament mode `G29` reports that it is skipping and re-asserts
the stored mesh with `M420 S1` rather than aborting, so a filament job whose
start gcode calls `G29` still prints.

The mesh is stored as profile `p1` and is **shared between modes**: it lives
in the shared half of the `SAVE_CONFIG` block (below) and `M420 S1` in
`CORE_GCODE_MACROS.cfg` loads it in either mode. The mesh describes the bed,
which does not change; the filament nozzle's different height is handled by
`tool_offset_z`.

**Level in pellet mode.**

## Per-mode calibration (`SAVE_CONFIG`)

Both modes define a section literally called `[extruder]`, but a pellet
auger on an AC band heater and a TD-01 hotend need completely different PID
values. The plugin therefore splits the `SAVE_CONFIG` block on every switch:

| Stored | Sections | Why |
|---|---|---|
| **Per mode** | `[extruder]`, `[tmc2209]`, `[tmc5160]` | genuinely different hardware |
| **Shared** | everything else — `[bed_mesh *]`, `[stepper_z]`, `[probe]` | properties of the machine, calibrated against the pellet head |

Files live in `/home/pi/.penrose/`. Default-to-shared is deliberate: an
unanticipated section is preserved rather than silently dropped.

First switch into a mode with nothing stored keeps the shared data and drops
the other head's PID — **re-run `PID_CALIBRATE HEATER=extruder` once per
mode**.

## Switching modes

Settings → Printer Setup is **factory-only** (SKU selection). The customer
switch is the **Extruder Type dropdown on the Material/Nozzle screen**.

Sequence, ordered so the parked carriage can never be hit:

1. `PREPARE_EXTRUDER_MODE_SWITCH` — refuses if printing/paused, **homes so
   both carriages sit on their own endstops**, heaters off (`M104 S0` plus
   `M104 H0 S0` in pellet mode), `M400`, flush `SAVE_CONFIG`.
2. Plugin: store the outgoing mode's calibration, flip the include, restore
   the incoming mode's calibration, toggle `[mcu E1]`.
3. Regenerate OctoPrint's profile and per-mode gcode scripts.
4. `FIRMWARE_RESTART`.

Takes roughly a minute. **Unlike the old runtime switch this requires a
Klipper restart** — that is the cost of Klipper genuinely seeing one
extruder.

## G-code

| Command | Behaviour |
|---|---|
| `M104 S…` / `M109 S…` | The nozzle. `T` is accepted and ignored — one tool. |
| `M104 S… H0` | Pellet barrel heater. **Errors in filament mode.** |
| `M106` / `M107` | The active mode's part fan(s). `P` ignored. |
| `G29` | Pellet mode only (see above). |
| `M420 S1` | Load the shared mesh. |
| `M701` / `M702` | Filament load/unload — filament mode only. |
| `PELLET_PREPRINT_CHECK`, `MIX_HOPPER` | Pellet mode only. |
| `QUERY_EXTRUDER_MODE` | Report mode and heater count. |
| `ASSERT_EXTRUDER_MODE MODE=…` | Slicer guard — cancels on mismatch. |
| `SET_HEAD_OFFSET` / `QUERY_HEAD_OFFSET` | Filament head offset. |
| `PREPARE_EXTRUDER_MODE_SWITCH` | Run by the UI before a swap. |
| `SET_EXTRUDER_MODE` | **Removed** — errors, directing you to the UI. |
| `T0`/`T1`, `M605`, `FULL_CONTROL` | **Gone** — no second tool exists. |

## UI and OctoPrint

The SKU sets `variable_is_dual_nozzle: 0`, so the existing single-nozzle
path hides every tool1 row, the H1 column and the T0/T1 toggles
automatically. **The only thing that varies between modes is the heater
count:**

- **Pellet** — nozzle rows **and** H0 barrel rows on Home; H0 column on
  Control; sensor toggle reads "Pellet Level Sensor"; bay reads "Pellet
  Extruder".
- **Filament** — nozzle rows only; H0 hidden everywhere; toggle reads
  "Filament Runout Sensor"; bay reads "Filament Extruder".

**OctoPrint:**

- `extruder.count = 1` — now honest, because Klipper really has one.
- H0 reaches the web UI's temperature stream natively via `gcode_id: H0`
  → `M105`.
- **Cooldown scripts are generated per mode**: pellet's includes
  `M104 H0 S0` (otherwise the barrel keeps heating after every print),
  filament's omits it (it would error).
- `beforePrintStarted` includes `PELLET_PREPRINT_CHECK` in pellet mode only.
- Temperature presets and the profile name follow the mode.

## Wrong-file protection

Two independent layers:

1. **`ASSERT_EXTRUDER_MODE`** in the sliced start gcode — cancels on
   mismatch. Requires the slicer profile to emit it.
2. **`validate_gcode_extruder_mode`** — the plugin scans the first 256 KB at
   `PrintStarted` and cancels. Covers the touchscreen, **the web UI**, the
   REST API and print-restore alike.

Detection: `ASSERT_EXTRUDER_MODE` is authoritative; failing that,
`M104/M109 H0`, `MIX_HOPPER` or `PELLET_PREPRINT_CHECK` at line start imply
pellet. No signal at all → **the print proceeds** (no filament-side
heuristic, or every legacy pellet file would falsely cancel).

Mode mismatch always cancels — no "continue anyway", and not gated on the
compatibility-check preference.

## Slicer contract

One single-extruder machine definition per mode. Each start gcode must:

1. `ASSERT_EXTRUDER_MODE MODE=PELLET` (or `FILAMENT`) **first**, before heating.
2. **Emit no `T0`/`T1` at all** — there is only one tool, and a `T1` will
   fail. Existing IDEX-era files with explicit tool commands must be re-sliced.
3. Pellet profiles keep `M104 H0 S…` and MixHopper injection. In filament
   mode `H0` errors, which is a useful extra guard.
4. Never emit `M605`.
