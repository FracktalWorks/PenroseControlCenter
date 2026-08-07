# Penrose 600 Hybrid IDEX — Pellet (T0) + Filament (T1)

Branch: `Hybrid-IDEX-Penrose-600`

## What this machine is

An IDEX Penrose 600 where the **left carriage (T0)** carries the usual pellet
auger extruder and the **right carriage (T1)** carries a Dragon TD-01 filament
extruder on a CAN-bus toolhead board.

Only one nozzle prints at a time. The second carriage exists so the operator
can switch between pellet printing and filament printing with `T0`/`T1`
instead of physically swapping the extruder head — it is *not* a dual-material
or duplication machine. `M605 S2` (COPY) and `M605 S3` (MIRROR) are blocked
with an error: two heads running different materials, flow rates and nozzle
sizes cannot print the same part in parallel.

**Heaters differ between the two sides.** T0 has two: its nozzle heater (PA1)
and the H0 pellet barrel heater (PA0). T1 is a regular filament hotend with a
single heater on the CAN toolhead — there is no H1, and `M104 H1` / `M109 H1`
return an error.

Compared to the two configurations this was built from:

| | Penrose 600 Dual | Penrose Single + filament head | **Penrose 600 Hybrid IDEX** |
|---|---|---|---|
| Carriages | 2 (both pellet) | 1 | 2 (pellet + filament) |
| Head choice | fixed | swap via UI dropdown | fixed per SKU |
| Barrel heaters | H0 + H1 | H0 (pellet head only) | H0 only |
| CAN toolhead | none | yes, when filament head selected | always |
| Paired IDEX modes | COPY/MIRROR | n/a | blocked |
| Revert path | — | pick the other head | pick the DUAL SKU |

To convert a machine back to dual pellet, select **Penrose 600 Dual** in
Settings → Printer Setup. The `[mcu E1]` block is commented out automatically
and its UUID is kept for when you switch back.

## Config files

```
firmware/printer.cfg                      v12  selector + [mcu] + [mcu E1]
firmware/PRINTER_PENROSE_600_HYBRID.cfg   v1   SKU: PRINTER_VARIABLES, kinematics, limits, bed mesh
firmware/BASE_PENROSE_HYBRID.cfg          v1   all hardware + IDEX macros
firmware/PELLET_RELAY_CONTROL_HYBRID.cfg  v1   left-only pellet feeder
firmware/CORE_GCODE_MACROS.cfg                 shared Marlin-compat macros
```

Only `printer.cfg`'s `# Version:` gates the in-app firmware update prompt — bump
it whenever any of the above changes, or machines in the field will never be
offered the update.

`variable_is_hybrid: 1` in `PRINTER_VARIABLES` is what the touchscreen app reads
to switch to hybrid behaviour (`config.IS_HYBRID` → `is_hybrid_printer()`).
`variable_is_dual_nozzle` stays `1`: this machine really does have two tools, and
that flag drives OctoPrint's extruder count, the tool1 UI rows and the dual
cooldown scripts.

## CAN bus bring-up (first boot, once per machine)

On this machine **both MCUs are CAN nodes** — the Manta M8P mainboard and the
TD-01 toolhead board, aliased `E1`. That differs from the other Penrose
variants, which reach the mainboard over USB serial.

1. **Bring up the `can0` interface** at 1 Mbit — `/etc/network/interfaces.d/can0`:

   ```
   allow-hotplug can0
   iface can0 can static
       bitrate 1000000
       up ip link set $IFACE txqueuelen 128
   ```

2. **Find both UUIDs:**

   ```
   ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0
   ```

   Two unclaimed UUIDs should appear. If nothing does, a board is not flashed
   with a CAN-capable Klipper build, `can0` is down, or the bus is missing
   termination at one end.

3. **Edit `/home/pi/printer.cfg`** — the shipped template has the mainboard on
   USB serial, because the DUAL and SINGLE variants share this file. For a
   hybrid machine, replace the `serial:`/`restart_method:` lines under `[mcu]`
   with the mainboard's UUID, and fill in the toolhead's:

   ```
   [mcu]
   canbus_uuid: <mainboard UUID>

   [mcu E1]
   canbus_uuid: <toolhead UUID>
   ```

   Enter these once. `PrinterConfigManager._sync_toolhead_mcu()` preserves the
   whole MCU block verbatim across every printer switch and firmware update —
   it only comments or uncomments the `[mcu E1]` lines and never touches
   `[mcu]` or rewrites a UUID. Selecting a non-hybrid SKU comments `[mcu E1]`
   out, because Klipper errors on an MCU that no config section references.

4. `FIRMWARE_RESTART`, then confirm Klipper reaches Ready and
   `canbus_query.py` reports no unclaimed UUIDs.

## Pin map

### T0 — Pellet head (left carriage), mainboard

| Function | Pin | Notes |
|---|---|---|
| Auger step / dir / enable | PG9 / PD7 / !PG11 | M6 slot, DM542T external driver |
| Nozzle heater / sensor | PA1 / PC5 | AC heater at `max_power: 0.5` |
| H0 barrel heater / sensor | PA0 / PB0 | max 480 °C |
| Part fans | PF7 / PF9 | `extruder_CF_0`, `extruder_CF_1` |
| Line vac solenoid | !PE9 | `pellet_vac_left`, PWM, active-LOW relay |
| 5/2 valve second solenoid | !PD15 | `pellet_vac_right`, **declared and held LOW** |
| Hopper level sensor | ^!PF4 | `pellet_sensor_left` |

`pellet_vac_right` has no hopper behind it on this machine, but the pin must
still be declared: a floating PD15 energises the second solenoid and shifts the
5/2 valve to the wrong position.

### T1 — Filament head (right carriage), CAN toolhead + M7

| Function | Pin | Notes |
|---|---|---|
| Extruder step / dir / enable | `E1: gpio24 / !gpio21 / !gpio28` | TMC2209 on the toolhead |
| TMC2209 UART | `E1: gpio25` | `run_current: 0.850`, `stealthchop_threshold: 0` |
| Hotend heater / sensor | `E1: gpio20` / `gpio26` | EPCOS 100K, max 310 °C |
| Part fan | `E1: gpio10` | `extruder1_CF` |
| Hotend cooling fan | `E1: gpio8` | `extruder1_AOF`, `heater: extruder1` |
| Side motor step / dir / enable | PD4 / PD3 / !PD6 | M7 slot on the mainboard |
| Side motor TMC5160 | cs PD5, SPI PG6/PG7/PG8 | `run_current: 1.00` |
| Filament runout switch | ^PC15 | M6-STOP, `switch_sensor_E1` |

The runout switch is on **M6-STOP (PC15)** — the input that carried the
right-hand hopper's capacitive level sensor on the dual pellet machine,
repurposed for the filament head. **PF3 (M2-STOP) is not available** for this:
it is the `dual_carriage` X endstop on this IDEX machine.

There is **no filament flow / motion sensor** on this machine.

The runout only pauses when T1 is the printing tool, so an empty filament spool
never interrupts a pellet print on T0:

```
pause_on_runout: False
runout_gcode:
    {% if printer.toolhead.homed_axes == 'xyz' and printer.toolhead.extruder == 'extruder1' %}
        RESPOND TYPE=echo MSG="Filament Runout T1"
        PAUSE
    {% endif %}
```

`pause_on_runout` must stay **False**: when it is True, Klipper's
`filament_switch_sensor` module pauses the print *before* rendering
`runout_gcode`, so the tool guard above would be powerless and a dry T1 spool
would park a running T0 pellet print. With False, the pause happens only when
the template explicitly issues `PAUSE` — and Klipper's `PAUSE` command sends
the same `action:paused` notification to OctoPrint that the built-in path
would, so nothing is lost. This matches the pattern used by every pellet
sensor in `PELLET_RELAY_CONTROL_*.cfg`.

### Side feed motor sync

`[extruder_stepper extruder_side1]` binds `extruder: extruder1` in the config,
so Klipper syncs the side feeder to the CAN drive motor at connect time —
the two are in lock-step from the moment Klipper starts. (Per the Klipper
config reference, `extruder:` is a required key on `[extruder_stepper]`; an
empty value means "not synchronized" and would leave the feeder idle until a
macro syncs it.) The `SYNC_E1_EXTRUDER` delayed_gcode, `FULL_CONTROL`, and
`homing_override` all re-assert the sync so a prior session's macros cannot
leave the two motors detached.

### Pins freed relative to Penrose 600 Dual

`PA3` and `PC4` (H1 barrel heater and sensor), `PA5` and `PA7` (T1 pellet nozzle
heater and sensor), `PF6` and `PF8` (T1 pellet part fans).

## G-code behaviour

| Command | Behaviour |
|---|---|
| `T0` / `T1` | Switch active tool with autopark and tool offsets. The only supported way to change printing head. |
| `M104 S… T0/T1` | Nozzle temperature for the given tool. |
| `M104 S… H0` | T0 pellet barrel heater. |
| `M104 S… H1` | **Error** — there is no barrel heater on the filament head. |
| `M109` | Same routing as `M104`, waits for temperature. |
| `M106 P0 S…` | T0 fans (`extruder_CF_0` + `extruder_CF_1`). |
| `M106 P1 S…` | T1 toolhead fan (`extruder1_CF`). |
| `M106 S…` | All fans. Empty fan-name variables are skipped. |
| `M605 S0` / `S1` | FULL_CONTROL with autopark off / on. |
| `M605 S2` / `S3` | **Error** — COPY/MIRROR are not supported on this machine. |
| `M701` / `LOAD_FILAMENT` | Heat T1, then push filament with the CAN motor and side feeder together. `S` temp, `L` length, `F` speed. |
| `M702` / `UNLOAD_FILAMENT` | Heat T1, retract, then turn the heater off. |
| `PELLET_PREPRINT_CHECK` | No-ops when T1 is the active tool. |
| `MIX_HOPPER` | No-ops when T1 is the active tool. |
| `SET_EXTRUDER_MODE MODE=PELLET/FILAMENT` | Persist the printing mode (variables.cfg). Applies immediately when idle + homed, otherwise at the next print start. |
| `_APPLY_EXTRUDER_MODE` | Activate the saved mode's tool (homes first if needed) and apply mode motion limits. Run automatically by OctoPrint's `beforePrintStarted` script. |
| `ASSERT_EXTRUDER_MODE MODE=PELLET/FILAMENT` | Slicer-profile guard — **cancels the print** with an error if the file's declared mode does not match the machine's mode. |
| `QUERY_EXTRUDER_MODE` | Report the saved mode and the active tool. |
| `G29` | Always probes with **T0** — the bed probe rides the pellet carriage; the TD-01 filament head has no probe. Pre-heats the nozzle to 150 °C **in pellet mode only** (in filament mode the pellet nozzle stays cold), and hands the carriage back to the mode's tool afterwards. |

Pellet auto-refill additionally requires T0 to be the active tool, so a
filament-only print can never trip a pellet outage pause or fire the line vac.

## Extruder mode (Pellet / Filament)

Both extruders are always present, so "mode" is a runtime state, not a config
swap: it decides **which tool a print uses when the sliced gcode contains no
explicit `T0`/`T1` commands** — the normal case, since both pellet and filament
jobs are sliced with single-extruder profiles.

- **Where**: Settings → Printer Setup → "Extruder Mode" dropdown (hybrid SKU
  only). Switching asks for confirmation, then sends `SET_EXTRUDER_MODE`.
  No firmware files are copied and no restart is needed.
- **Persistence**: `extruder_mode` in Klipper's `variables.cfg` — survives
  restarts and firmware config updates. Defaults to `pellet` when unset.
- **Application**: OctoPrint's `beforePrintStarted` script runs
  `_APPLY_EXTRUDER_MODE` → `PELLET_PREPRINT_CHECK` → `M514 S1`. The pellet
  check self-gates on the active tool, so it no-ops in filament mode.
- **Homing interaction**: `[homing_override]` forces T0 during every home
  (probe safety and legacy IDEX behaviour), then — after a **full** home only —
  re-activates T1 when the saved mode is `filament`. This is what keeps a job
  whose own start gcode calls `G28` printing on the filament head. The restore
  is motionless (T0 is at its −85 park, so autopark is skipped). Partial homes
  (`G28 X`) keep the legacy end-on-T0 behaviour.
- **Overrides**: explicit `T0`/`T1` in sliced gcode still wins — the mode only
  sets the starting tool.
- **Motion limits**: applying a mode also applies its motion tuning via
  `_EXTRUDER_MODE_LIMITS` — pellet keeps the gentler corners from the
  `[printer]` section (`SQUARE_CORNER_VELOCITY=4`) for melt-pressure
  stability; filament runs standard limits (`SQUARE_CORNER_VELOCITY=5`).
- **UI presentation**: in either mode the touchscreen presents the machine as
  a single-extruder printer — the Home screen shows only the mode's tool
  (plus the H0 barrel in pellet mode) and re-skins **live** when the mode
  changes; no firmware restart is needed. The Control and Filament screens
  deliberately keep both tools visible so the operator can prep the inactive
  head (preheat, load filament) before switching modes on the fly. A mode
  switched mid-print does not re-skin until it actually engages at the next
  job.

**Slicer contract for mode-based printing**: one single-extruder machine
definition per mode (in Fracktory 5 these are the
`penrose_600_idex_choosable_pellet` / `..._fdm` pair — the machine dropdown is
the slicer-side mode selector). Each profile's start gcode must:

1. Declare its mode — `ASSERT_EXTRUDER_MODE MODE=FILAMENT` (or `PELLET`) as
   the **first command**, before any heating. If the machine is in the other
   mode, the print cancels immediately with a clear error instead of printing
   with the wrong head.
2. Then either **explicitly select the matching tool** (`T1` in the filament
   profile, `T0` in the pellet profile — the Fracktory choosable profiles do
   this) or emit no tool command at all and let the mode's tool apply
   automatically (bare `M104`/`M109 S…` target the active tool; full `G28`
   restores the mode's tool). Both are supported; never select the *other*
   tool.
3. Pellet profiles keep their `M104 H0 S…` barrel line and `MIX_HOPPER`
   layer-change/interval injection.
4. Never emit `M605` (`S0/S1` runs `FULL_CONTROL`, which deliberately ends on
   T0 and would defeat filament mode).

`ASSERT_EXTRUDER_MODE` only exists on the Hybrid IDEX firmware — keep it out
of profiles that also target the dual-pellet or single machines.

**Input shaping:** no accelerometer is fitted, so `SHAPER_CALIBRATE` cannot be
run and the UI button stays disabled. The `[input_shaper]` section is present
if you want to set values by hand from a ringing tower test.

## Sensors and the UI

Three sensors exist; the Control screen exposes two toggles.

| Toggle | Drives | Preference key |
|---|---|---|
| "T0 Pellet Level Sensor" | `pellet_sensor_left` | `pellet_sensor_t0_enabled` |
| "T1 Filament Runout Sensor" | `switch_sensor_E1` | `extruder_runout_enabled` |

Lifecycle, from `MainController`:

| Event | Action |
|---|---|
| Startup, print started, print resumed | `apply_extruder_sensors()` — all sensors per preference |
| Print paused, cancelled, completed | `disable_extruder_sensors()` — all sensors off |
| Filament wizard open | T1 runout suspended; restored on Done/Cancel |

Sensors are disabled outside a print because manual loading and purging look
exactly like a runout, which would spuriously pause the next job.

Klipper reports the T1 event with `RESPOND TYPE=echo MSG="Filament Runout T1"`,
which the websocket client parses into a dialog.

## Other UI behaviour on this variant

- **H1 rows hidden** on the Home and Control screens (`HYBRID_HIDDEN_ELEMENTS`);
  tool1 nozzle temperature rows stay visible.
- **Nozzle sizes are per tool** — `nozzle_options_for_tool()`: T0 offers the
  pellet range (0.6–3.0 mm), T1 the filament range (0.25–1.0 mm).
- **Material button routing** — T0 opens the line vac load dialog, T1 opens the
  filament load/unload wizard.
- **T1's status label** shows its filament bay state (Loaded/Empty), not a
  hopper level; pellet sensor polling skips it.
- **Extruder Mode dropdown** in Printer Setup (see "Extruder mode" above). The
  selection mirrors Klipper's `variables.cfg` via the `EXTRUDER_MODE:` websocket
  messages, and is re-queried every time the screen opens.
- **Mode-skinned Home screen** — only the active mode's tool rows are shown
  (`MODE_HIDDEN_ELEMENTS` in `printer_ui_config.py`), re-applied live on
  `extruder_mode_changed`.
- **OctoPrint web UI temperature presets** — the hybrid SKU appends PLA/PETG/ABS
  *Filament* presets to the pellet presets in `config.yaml`.
- The plugin's software updater tracks the `Hybrid-IDEX-Penrose-600` branch by
  commit, not by release tag, so a release on the default branch cannot
  overwrite this variant.

## First power-on checklist

1. Settings → Printer Setup → **Penrose 600 Hybrid** → Set. After the reboot,
   check `/home/pi/printer.cfg`: the HYBRID include is active, `[mcu E1]` is
   uncommented with your UUID, `[mcu]` has the mainboard UUID, and the
   `SAVE_CONFIG` block survived.
2. `canbus_query.py` reports no unclaimed UUIDs; Klipper reaches Ready.
3. `QUERY_PELLET_SYSTEM` → left vac and sensor present, no right entries.
   Measure PD15 at the relay and confirm it is held LOW.
4. `DUMP_TMC STEPPER=extruder1` and `DUMP_TMC STEPPER=extruder_side1` both respond.
5. Heaters: `M104 T1 S60` ramps the CAN hotend, `M104 H0 S60` ramps the pellet
   barrel, `M104 H1 S60` returns a clean error.
6. `QUERY_FILAMENT_SENSOR SENSOR=switch_sensor_E1` reports correctly with
   filament present and absent.
7. `G28`, then `T1` and `T0` — autopark cycles without collision.
8. `M605 S2` → error message, no motion.
9. `M106 P1 S255` spins only the toolhead fan; `M106 P0 S255` only the T0 fans.
10. With T1 active, `G1 E10` turns both the CAN motor and the M7 side motor.
    With T0 active, the side motor stays still. Check the side motor direction
    matches the CAN motor — if it fights, invert `dir_pin: PD3`.
11. `M701` and `M702` load and unload cleanly.
12. `PID_CALIBRATE HEATER=extruder1`, then IDEX XY/Z tool-offset calibration.
13. Test print with a mid-print T0 ↔ T1 switch.
