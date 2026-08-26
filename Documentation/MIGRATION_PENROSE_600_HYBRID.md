# Commissioning a Penrose 600 Hybrid (config-swap model)

Procedure to move a machine onto the `Hybrid-IDEX-Penrose-600` software and
validate **both extruder modes**.

Target state: two carriages on one X rail, but Klipper configured as a
**single-extruder printer** in whichever mode is selected — pellet auger
(left) or TD-01 filament head (right) — switched from the touchscreen.

Companion reference: `HYBRID_IDEX_PENROSE_600.md` (pin map, macros, per-mode
calibration). Design rationale: `DESIGN_HYBRID_IDEX_CONFIG_SWAP.md`.

> **This is a first deployment of a reworked motion configuration.** Work
> through §5 with the emergency stop in reach. The carriage clearance at
> full travel (§5.2) is the one geometry figure that has never been
> measured — the old config enforced it dynamically and this one cannot.

---

## 0. Prerequisites

- [ ] TD-01 CAN toolhead on the right carriage; side feed motor on **M7**.
- [ ] Filament runout switch on **M6-STOP (PC15)**. Not PF3 — that is the
      right carriage's X endstop.
- [ ] 5/2 valve: left solenoid PE9, right solenoid PD15 (both held LOW by
      firmware in every mode).
- [ ] Manta M8P and TD-01 both flashed as CAN nodes on `can0` @ 1 Mbit,
      both UUIDs known.
- [ ] **Record the machine's existing `tool_offset_x/y/z`** from
      `~/.octoprint/data/klipper/variables.cfg`. These carry over and are
      what keeps filament prints positioned correctly.

## 1. Back up

```bash
mkdir -p ~/config_backup_$(date +%Y%m%d)
cp ~/printer.cfg ~/*.cfg ~/config_backup_$(date +%Y%m%d)/ 2>/dev/null
cp ~/.octoprint/data/klipper/variables.cfg ~/config_backup_$(date +%Y%m%d)/
cp ~/.octoprint/config.yaml ~/.octoprint/printerProfiles/_default.profile ~/config_backup_$(date +%Y%m%d)/
```

`variables.cfg` holds the head offsets and babystep — the migration
preserves it, but back it up anyway.

## 2. Install the plugin

```bash
~/oprint/bin/pip install --force-reinstall \
  https://github.com/FracktalWorks/PenroseControlCenter/archive/Hybrid-IDEX-Penrose-600.zip
sudo service octoprint restart
```

## 3. Select the SKU

Touchscreen: **Settings → Printer Setup → "Penrose 600 Hybrid" → Set** →
confirm → reboot. This copies the firmware files and regenerates the
OctoPrint configs.

The machine comes up in **pellet mode** by default. Verify:

```bash
grep -n "include MODE_" ~/printer.cfg     # exactly ONE uncommented
grep -A1 "mcu E1" ~/printer.cfg           # commented out in pellet mode
tail -20 ~/printer.cfg                    # SAVE_CONFIG block intact
cat ~/.octoprint/scripts/gcode/afterPrintDone
```

`afterPrintDone` must contain `M104 H0 S0` in pellet mode.

## 4. First Klipper checks — no motion

| Command | Expect |
|---|---|
| `STATUS` | Ready |
| `QUERY_EXTRUDER_MODE` | `EXTRUDER_MODE:PELLET` + "Heaters: nozzle + H0 barrel" |
| `QUERY_HEAD_OFFSET` | your recorded `tool_offset_*` values |
| `M104 S60` then `M104 S0` | nozzle heats |
| `M104 H0 S60` then `M104 H0 S0` | **barrel heats** — the second heater |
| `M105` at room temperature | pellet nozzle and H0 both read ambient ±3 °C — see §4.1 |
| `QUERY_PELLET_SYSTEM` | left vac + sensor, no right entries |
| `M605 S1` | unknown command (correct — IDEX macros are gone) |

Measure PD15 stays LOW.

### 4.1 Pellet thermistor  ⚠ verify before any PID tuning

The pellet nozzle and H0 barrel use a **custom NTC table**
(`[thermistor new_thermistor_t1]` in `BASE_PENROSE_HYBRID.cfg`), not a
Klipper built-in. The filament hotend keeps stock EPCOS, like every other
Fracktal Works filament printer.

This matters because the stock `ATC Semitec 104GT-2` table under-reads this
sensor badly, and under-reading makes the PID drive the heater *harder*:

| True temp | Reported as Semitec | Error |
|---|---|---|
| 250 °C | 189 °C | **−61 °C** |
| 400 °C | 298 °C | **−102 °C** |

- [ ] Cold machine: `M105` — pellet nozzle and H0 both read ambient within
      a few degrees. A reading of ~15–20 °C low at room temperature is the
      signature of a stock table still being applied somewhere.
- [ ] Heat H0 to 200 °C and check against an independent probe (IR or
      thermocouple) on the barrel. Should agree within a few degrees.
- [ ] Only then run `PID_CALIBRATE` (§6). Tuning against a wrong curve
      bakes the error into the PID constants.

**Known limits of this table:**

- Calibrated **50–250 °C only**. Above 250 °C the Steinhart-Hart curve is
  extrapolated — it stays monotonic and sane out to 480 °C, but its
  accuracy there is unverified. If you routinely run PEEK/PPS above 300 °C,
  recalibrate with points spanning the real working range.
- With the default 4700 Ω pullup, ADC resolution falls below one count per
  °C past **~350 °C** (roughly 6 °C per count at 480 °C). `max_temp: 480`
  is therefore optimistic; a lower pullup would be needed to resolve the
  top of that range properly.

## 5. Motion — the new part. Take this slowly.

### 5.1 Parked carriage holds — quick confirmation

X and Y are **ball screw driven**, so a parked carriage cannot drift: the
screw and the stepper's detent torque hold it mechanically even with the
driver unpowered. This is what makes the brief unpowered window during
`FIRMWARE_RESTART` safe, and the `[manual_stepper]` in each mode file is
belt-and-braces rather than the sole guard.

Worth one confirmation anyway, since it underpins every mode switch:

- [ ] Home (`G28`). Both carriages go to their endstops.
- [ ] Mark the right carriage's position against the rail.
- [ ] `FIRMWARE_RESTART` — it must not move.
- [ ] Push it gently by hand once Klipper is up — it should resist.

### 5.2 Carriage clearance  ⚠ measurement required

The old `safe_distance: 60` no longer exists; `position_max` is the only
guard.

- [ ] With the right carriage parked at 640, jog the pellet carriage to
      **X=600** slowly and **measure the gap between carriage bodies**.
- [ ] If they touch or come within a few mm, edit `MODE_PELLET.cfg`:
      `position_max: 580`, redeploy, re-test.

### 5.3 Basic motion

- [ ] `G28` homes X toward −85, Y, Z. Ends parked left.
- [ ] Jog X/Y/Z over the bed; no binding, no contact with the parked carriage.
- [ ] `M106 S255` spins the two pellet fans; `M107` stops them.

## 6. Calibrate pellet mode

| Step | How |
|---|---|
| Nozzle PID | `PID_CALIBRATE HEATER=extruder TARGET=220` → `SAVE_CONFIG` |
| Bed mesh | `G29` — probes with the pellet nozzle, saves `p1` |
| Z probe offset | Calibrate → Z Probe Offset wizard |
| Nozzle size | Filament screen → edit the bay |

## 7. First mode switch

**Material/Nozzle screen → Extruder Type → Filament Extruder → confirm.**

Expected: homes, parks, heaters off, ~1 minute of reconfiguration, Klipper
restarts, dialog confirms.

Then verify:

```bash
grep -n "include MODE_" ~/printer.cfg     # MODE_FILAMENT now active
grep -A1 "mcu E1" ~/printer.cfg           # now UNCOMMENTED
ls /home/pi/.penrose/                     # saveconfig_pellet + _shared
cat ~/.octoprint/scripts/gcode/afterPrintDone   # H0 line GONE
```

| Command | Expect |
|---|---|
| `QUERY_EXTRUDER_MODE` | `EXTRUDER_MODE:FILAMENT` + "Heaters: nozzle only" |
| `M104 H0 S60` | clean error — no barrel heater |
| `QUERY_HEAD_OFFSET` | stored values, and live gcode offset **non-zero** |
| `DUMP_TMC STEPPER=extruder` | CAN toolhead TMC2209 responds |

- [ ] `G28` — homes X toward **640** now. Left carriage stays parked.
- [ ] `G1 E20 F300` (hot) — CAN motor **and** M7 side motor turn together.
- [ ] Home screen shows nozzle only, no H0 rows. Control screen has no H0
      column. Toggle reads "Filament Runout Sensor".

### 7.1 Head offset  ⚠ verify before printing anything real

- [ ] After `G28`, `QUERY_HEAD_OFFSET` shows the live gcode offset applied
      (non-zero X/Y/Z). If it is zero, `_APPLY_HEAD_OFFSET` did not run.
- [ ] Print a **single-wall 50 mm square** and measure its position against
      the bed origin. It must land where the pellet head would print it.
- [ ] If displaced, correct with `SET_HEAD_OFFSET X=… Y=… Z=…` and reprint.

## 8. Calibrate filament mode

Its PID is *not* inherited — the split is deliberate.

| Step | How |
|---|---|
| Hotend PID | `PID_CALIBRATE HEATER=extruder TARGET=220` → `SAVE_CONFIG` |
| Load filament | Filament screen → bay → wizard |
| Rotation distance | Mark, `G1 E100 F300`, measure. 4.7158 = TD-01 stock |
| Bed mesh | **Not possible** — pellet mode's `p1` is used automatically |

## 9. Round-trip the calibration  ⚠ the destructive-failure test

This is what proves per-mode storage works.

- [ ] Note filament PID: `grep -A4 "\[extruder\]" ~/printer.cfg | tail -5`
- [ ] Switch to **pellet**. Note its PID — must be the pellet value, **not**
      the filament one.
- [ ] Confirm `[bed_mesh p1]` still present.
- [ ] Switch back to **filament**. PID must be the filament value again.
- [ ] Repeat once more each way.

**If PID values swap or vanish, stop** — the SAVE_CONFIG split is
misbehaving and every switch is destroying calibration.

## 10. Print validation

**Pellet mode**

- [ ] Home screen shows nozzle **+ H0 barrel** rows.
- [ ] Print a small pellet job (`ASSERT_EXTRUDER_MODE MODE=PELLET`, no `T`).
- [ ] Hopper auto-refill and `MIX_HOPPER` work.
- [ ] Cancel → cooldown turns off **both** nozzle and H0.
- [ ] Start a **filament-profile** file → cancels with the mode-mismatch error.
- [ ] Same file from the **OctoPrint web UI** → cancels identically.

**Filament mode**

- [ ] Print a small filament job. Correct position (§7.1) and first layer.
- [ ] Runout mid-print → pauses, dialog, reload, resume.
- [ ] Start a **pellet-profile** file → cancels.
- [ ] Web UI shows **one** tool, filament presets, profile named "(Filament)".

## 11. Slicer profiles

Both Fracktory definitions become plain single-extruder machines:

- **Remove `T0`/`T1` entirely** — there is no second tool, and a `T1` will
  fail. **Existing IDEX-era files must be re-sliced.**
- Keep `ASSERT_EXTRUDER_MODE MODE=…` as the first command.
- Pellet keeps `M104 H0 S…` and MixHopper; it errors in filament mode, which
  is a useful guard.
- Never emit `M605`.

## 12. Rollback

Configs: Settings → Printer Setup → "Penrose 600 Dual" → Set. MCU block and
SAVE_CONFIG are preserved.

Plugin:

```bash
~/oprint/bin/pip install --force-reinstall \
  https://github.com/FracktalWorks/PenroseControlCenter/archive/production.zip
sudo service octoprint restart
```

Full restore: copy the §1 backup back over `/home/pi/` and `~/.octoprint/`,
reboot.

## 13. Troubleshooting

**"Option 'z_offset' in section 'probe' must be specified"** — the plugin
seeds it automatically; take the firmware update or re-select the SKU.

**"Unknown sensor" on print start** — a mode/sensor mismatch. Check
`QUERY_EXTRUDER_MODE` matches the active `MODE_*.cfg` include.

**Filament print offset from pellet print** — head offset. §7.1.

**"MCU 'mcu' shutdown: Timer too close"** — host/CAN timing, not this
change. See `LINUX_OPTIMIZATION_KLIPPER.md`; check `can0` bitrate and 120 Ω
termination at both ends.

**Klipper won't start after a switch** — check exactly one `MODE_*.cfg` is
uncommented, and that `[mcu E1]` is uncommented **only** in filament mode
(Klipper errors on an MCU nothing references).
