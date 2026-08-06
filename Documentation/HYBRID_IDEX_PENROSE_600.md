# Penrose 600 Hybrid IDEX — Pellet (T0) + Filament (T1)

Branch: `Hybrid-IDEX-Penrose-600`

## What this machine is

An IDEX Penrose 600 where the **left carriage (T0)** carries the usual pellet
auger extruder and the **right carriage (T1)** carries a Dragon TD-01-style
filament extruder on a CAN-bus toolhead board.

Only one nozzle prints at a time. The second carriage exists so the operator
can switch between pellet printing and filament printing with `T0`/`T1`
instead of physically swapping the extruder head — it is *not* a dual-material
or duplication machine. `M605 S2` (COPY) and `M605 S3` (MIRROR) are blocked
with an error: two heads running different materials, flow rates and nozzle
sizes cannot print the same part in parallel.

Compared to the two configurations this was built from:

| | Penrose 600 Dual | Hybrid-Penrose-600 (single) | **Penrose 600 Hybrid IDEX** |
|---|---|---|---|
| Carriages | 2 (both pellet) | 1 | 2 (pellet + filament) |
| Head choice | fixed | swap via UI dropdown | fixed per SKU |
| Barrel heaters | H0 + H1 | H0 (pellet head only) | H0 only |
| CAN toolhead | none | yes, when filament head selected | always |
| Paired IDEX modes | COPY/MIRROR | n/a | blocked |
| Revert path | — | pick the other head | pick the DUAL SKU |

To convert a machine back to dual pellet, select **Penrose 600 Dual** in
Settings → Printer Setup. The CAN toolhead MCU block is commented out
automatically and the UUID is kept for when you switch back.

## Config files

```
firmware/printer.cfg                      v12  selector + [mcu] + [mcu toolhead0]
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

The T1 filament extruder lives on a TD-01 CAN toolhead board. The Manta M8P
mainboard runs in USB-to-CAN bridge mode, so the host talks USB serial to the
M8P and the M8P bridges to the toolhead over CAN.

1. **Bring up the `can0` interface** at 1 Mbit — `/etc/network/interfaces.d/can0`:

   ```
   allow-hotplug can0
   iface can0 can static
       bitrate 1000000
       up ip link set $IFACE txqueuelen 128
   ```

2. **Find the toolhead's UUID:**

   ```
   ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0
   ```

   An unclaimed board reports one UUID. If nothing appears, the toolhead is not
   flashed with a CAN-capable Klipper build, `can0` is down, or termination is
   missing at one end of the bus.

3. **Paste the UUID into `/home/pi/printer.cfg`**, in the MCU Config block:

   ```
   [mcu toolhead0]
   canbus_uuid: <the UUID from step 2>
   ```

   Enter it once. `PrinterConfigManager._sync_toolhead_mcu()` preserves this
   block verbatim across every printer switch and firmware update — it only
   comments or uncomments the lines, never rewrites the UUID. Selecting a
   non-hybrid SKU comments the block out, because Klipper errors on an MCU that
   no config section references.

4. `FIRMWARE_RESTART`, then confirm Klipper reaches Ready and
   `canbus_query.py` now reports zero unclaimed UUIDs.

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
| Extruder step / dir / enable | `toolhead0: gpio24 / !gpio21 / !gpio28` | TMC2209 on the toolhead |
| TMC2209 UART | `toolhead0: gpio25` | `run_current: 0.850` |
| Hotend heater / sensor | `toolhead0: gpio20` / `gpio26` | EPCOS 100K, max 310 °C |
| Part fan | `toolhead0: gpio10` | `extruder_CF` |
| Hotend cooling fan | `toolhead0: gpio8` | `heater: extruder1` |
| Toolhead LED | `toolhead0: gpio2` | green, on at startup |
| ADXL345 | `toolhead0: gpio13/14/15/12` | cs / sclk / mosi / miso |
| Side motor step / dir / enable | PD4 / PD3 / !PD6 | M7 slot on the mainboard |
| Side motor TMC5160 | cs PD5, SPI PG6/PG7/PG8 | `run_current: 1.00` |
| **Filament runout switch** | **^PF5 — `PLACEHOLDER(PINS-TBD)`** | **must be confirmed** |
| **Filament flow sensor** | **^PC15 — `PLACEHOLDER(PINS-TBD)`** | **must be confirmed** |

The side motor is assigned `extruder: extruder1`, so it stays in lock-step with
the CAN drive motor. `SYNC_EXTRUDER_MOTION ... MOTION_QUEUE=extruder1` is
repeated in `STARTUP`, `FULL_CONTROL` and `homing_override` as a safeguard
against a prior session leaving it detached.

### Placeholder pins — read before first power-on

Both T1 sensor pins are placeholders pending the real wiring. Until they are
confirmed:

- Both sensors ship with `pause_on_runout: False`, so a floating input cannot
  pause a print. Their `runout_gcode` still emits the `RESPOND` message the UI
  listens for.
- Every placeholder is tagged `PLACEHOLDER(PINS-TBD)`. Find them all with
  `grep -rn "PLACEHOLDER(PINS-TBD)" octoprint_PenroseControlCenter/firmware/`.
- **PF3 is not available.** It is the `dual_carriage` X endstop on this IDEX
  machine. The single-nozzle hybrid branch used PF3 for the runout switch;
  copying that pin here breaks T1 homing.
- PC15 (M6-STOP) is genuinely free — it was the right hopper's level sensor on
  the dual pellet machine.

Once the real pins are known, update both `switch_pin` values, flip both
`pause_on_runout` to `True`, remove the markers and bump `printer.cfg`.

### Pins freed relative to Penrose 600 Dual

`PA3` and `PC4` (H1 barrel heater and sensor), `PA5` and `PA7` (T1 pellet nozzle
heater and sensor), `PF6` and `PF8` (T1 pellet part fans), `PC15` (right hopper
level sensor).

## G-code behaviour

| Command | Behaviour |
|---|---|
| `T0` / `T1` | Switch active tool with autopark and tool offsets. The only supported way to change printing head. |
| `M104 S… T0/T1` | Nozzle temperature for the given tool. |
| `M104 S… H0` | T0 pellet barrel heater. |
| `M104 S… H1` | **Error** — there is no barrel heater on the filament head. |
| `M109` | Same routing as `M104`, waits for temperature. |
| `M106 P0 S…` | T0 fans (`extruder_CF_0` + `extruder_CF_1`). |
| `M106 P1 S…` | T1 toolhead fan (`extruder_CF`). |
| `M106 S…` | All fans. Empty fan-name variables are skipped. |
| `M605 S0` / `S1` | FULL_CONTROL with autopark off / on. |
| `M605 S2` / `S3` | **Error** — COPY/MIRROR are not supported on this machine. |
| `PELLET_PREPRINT_CHECK` | No-ops when T1 is the active tool. |
| `MIX_HOPPER` | No-ops when T1 is the active tool. |
| `SHAPER_CALIBRATE` | Run with T1 active — the ADXL345 is on that carriage. The UI does this automatically. |

Pellet auto-refill additionally requires T0 to be the active tool, so a
filament-only print can never trip a pellet outage pause or fire the line vac.

## Sensors and the UI

Four sensors exist; the Control screen exposes them as two toggles.

| Toggle | Drives | Preference key |
|---|---|---|
| "T0 Pellet Level Sensor" | `pellet_sensor_left` | `pellet_sensor_t0_enabled` |
| "T1 Filament Sensors" | `extruder_runout` **and** `extruder_flow` | `extruder_runout_enabled`, `extruder_flow_enabled` |

Lifecycle, from `MainController`:

| Event | Action |
|---|---|
| Startup, print started, print resumed | `apply_extruder_sensors()` — all sensors per preference |
| Print paused, cancelled, completed | `disable_extruder_sensors()` — all sensors off |
| Filament wizard open | T1 sensors suspended; restored on Done/Cancel |

Sensors are disabled outside a print because manual loading and purging look
exactly like a runout or a flow stall, which would spuriously pause the next job.

Klipper reports T1 events with `RESPOND` messages the websocket client parses:
`Filament Runout T1` and `Filament Flow Stall T1` each raise a dialog.

## Other UI behaviour on this variant

- **H1 rows hidden** on the Home and Control screens (`HYBRID_HIDDEN_ELEMENTS`);
  tool1 nozzle temperature rows stay visible.
- **Nozzle sizes are per tool** — `nozzle_options_for_tool()`: T0 offers the
  pellet range (0.6–3.0 mm), T1 the filament range (0.25–1.0 mm).
- **Material button routing** — T0 opens the line vac load dialog, T1 opens the
  filament load/unload wizard.
- **T1's status label** shows its filament bay state (Loaded/Empty), not a
  hopper level; pellet sensor polling skips it.
- **Input shaper calibration is enabled**, and only on this variant — it is the
  only Penrose with an accelerometer.
- The plugin's software updater tracks the `Hybrid-IDEX-Penrose-600` branch by
  commit, not by release tag, so a release on the default branch cannot
  overwrite this variant.

## First power-on checklist

1. Settings → Printer Setup → **Penrose 600 Hybrid** → Set. After the reboot,
   check `/home/pi/printer.cfg`: the HYBRID include is active, `[mcu toolhead0]`
   is uncommented with your UUID, and the `SAVE_CONFIG` block survived.
2. `canbus_query.py` reports no unclaimed UUIDs; Klipper reaches Ready.
3. `QUERY_PELLET_SYSTEM` → left vac and sensor present, no right entries.
   Measure PD15 at the relay and confirm it is held LOW.
4. `DUMP_TMC STEPPER=extruder1` and `DUMP_TMC STEPPER=extruder_side` both respond.
5. `ACCELEROMETER_QUERY CHIP="adxl345 toolhead0"` returns live values.
6. Heaters: `M104 T1 S60` ramps the CAN hotend, `M104 H0 S60` ramps the pellet
   barrel, `M104 H1 S60` returns a clean error.
7. `G28`, then `T1` and `T0` — autopark cycles without collision.
8. `M605 S2` → error message, no motion.
9. `M106 P1 S255` spins only the toolhead fan; `M106 P0 S255` only the T0 fans.
10. With T1 active, `G1 E10` turns both the CAN motor and the M7 side motor.
    With T0 active, the side motor stays still.
11. Confirm the real filament sensor pins, update the config, set
    `pause_on_runout: True`, bump `printer.cfg`, commit.
12. `PID_CALIBRATE HEATER=extruder1`, `SHAPER_CALIBRATE` (T1 active), IDEX XY/Z
    tool-offset calibration.
13. Test print with a mid-print T0 ↔ T1 switch.
