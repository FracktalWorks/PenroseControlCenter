# Migrating a Penrose 600 to the Hybrid IDEX configuration

Step-by-step procedure to move a machine onto the `Hybrid-IDEX-Penrose-600`
software and validate that **both extruder modes** work end to end.

Target state: IDEX with a **pellet auger on T0 (left)** and a **TD-01 CAN
filament head on T1 (right)**, an operator-selectable Extruder Mode
(Pellet / Filament) in the touchscreen UI, and OctoPrint configured to match.

Companion reference: `HYBRID_IDEX_PENROSE_600.md` (pin map, CAN bring-up,
G-code behaviour, sensor lifecycle). This document is the migration recipe;
that one is the system reference.

---

## 0. Prerequisites (hardware, done before software migration)

- [ ] Right pellet extruder removed; TD-01 CAN toolhead fitted on the right
      carriage (drive motor, hotend, part fan, always-on fan).
- [ ] Side feed motor wired to mainboard **M7** (TMC5160).
- [ ] Filament runout switch wired to **M6-STOP (PC15)** on the M8P.
      (Do **not** use M2-STOP/PF3 — that is the T1 X endstop.)
- [ ] 5/2 valve: left solenoid on PE9; right solenoid line on PD15 present
      (firmware holds it LOW permanently).
- [ ] Manta M8P flashed as a **CAN node** (USB-to-CAN bridge mode), TD-01
      flashed with Klipper CAN firmware, both on `can0` @ 1 Mbit.
- [ ] Both CAN UUIDs known. On this machine:
      `[mcu]` = mainboard, `[mcu E1]` = TD-01 toolhead. Verify with:

      ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0

      Two UUIDs must appear (a claimed UUID stops being listed once Klipper
      connects — run this with Klipper stopped if you want to see both).

## 1. Back up the current machine state

SSH to the machine (`pi@<printer-ip>`):

```bash
mkdir -p ~/config_backup_$(date +%Y%m%d)
cp ~/printer.cfg ~/*.cfg ~/variables.cfg ~/config_backup_$(date +%Y%m%d)/ 2>/dev/null
cp ~/.octoprint/config.yaml ~/.octoprint/printerProfiles/_default.profile ~/config_backup_$(date +%Y%m%d)/
```

`variables.cfg` carries your tool offsets, babystep and (after this migration)
the extruder mode — it is preserved by the migration, but back it up anyway.

## 2. Install the plugin from the hybrid branch

```bash
~/oprint/bin/pip install --force-reinstall \
  https://github.com/FracktalWorks/PenroseControlCenter/archive/Hybrid-IDEX-Penrose-600.zip
sudo service octoprint restart
```

From this point the plugin's software updater tracks the
`Hybrid-IDEX-Penrose-600` branch **by commit**, so future updates arrive
through the normal UI update flow.

## 3. One-time printer.cfg CAN edit (only if migrating from USB serial)

If the deployed `/home/pi/printer.cfg` still connects the mainboard over USB
serial, edit its MCU block once:

```
[mcu]
canbus_uuid: <mainboard-uuid>        # replaces serial:/restart_method:

[mcu E1]
canbus_uuid: <toolhead-uuid>
```

The config manager **preserves this block verbatim** across every SKU change
and firmware update afterwards — the UUIDs never need to be entered again.
(When the Hybrid SKU is selected, the manager auto-uncomments `[mcu E1]`;
when a non-hybrid SKU is selected it re-comments it.)

## 4. Select the Hybrid SKU

On the touchscreen: **Settings → Printer Setup → Printer Type: "Penrose 600
Hybrid" → Set** → confirm → the machine reboots.

This copies all firmware `.cfg` files, activates
`[include PRINTER_PENROSE_600_HYBRID.cfg]`, uncomments `[mcu E1]`, and
regenerates the OctoPrint configs (printer profile with 2 extruders,
600×600×625 volume, filament temperature presets, gcode scripts).

After the reboot verify on the machine:

```bash
grep -A2 "PRINTER_PENROSE_600_HYBRID" ~/printer.cfg   # include active
grep -A1 "mcu E1" ~/printer.cfg                        # UUID present, uncommented
tail -20 ~/printer.cfg                                 # SAVE_CONFIG block intact
cat ~/.octoprint/scripts/gcode/beforePrintStarted      # has _APPLY_EXTRUDER_MODE
```

`beforePrintStarted` must read:

```
_APPLY_EXTRUDER_MODE  ; Activate pellet/filament mode tool
PELLET_PREPRINT_CHECK  ; Refill T0 hopper if empty (skipped in filament mode)
M514 S1  ; Open door/chamber on print start
```

## 5. First Klipper checks (no motion yet)

In the OctoPrint terminal:

| Command | Expect |
|---|---|
| `STATUS` | Klipper reports Ready |
| `QUERY_EXTRUDER_MODE` | `EXTRUDER_MODE:PELLET` (default) + active tool |
| `QUERY_PELLET_SYSTEM` | Left vac OFF, left sensor state; T1 listed as filament |
| `QUERY_FILAMENT_SENSOR SENSOR=switch_sensor_E1` | matches whether filament sits in the M6-STOP switch |
| `IDEX_STATUS` | carriage_0 PRIMARY, carriage_1 INACTIVE |
| `DUMP_TMC STEPPER=extruder1` | registers read (CAN toolhead TMC2209 alive) |
| `DUMP_TMC STEPPER=extruder_stepper extruder_side1` | registers read (M7 TMC5160 alive) |
| `M104 T1 S60` then `M104 T1 S0` | T1 temp rises on the toolhead sensor |
| `M104 H1 S60` | clean error ("no barrel heater on the T1 filament head") |
| `M605 S2` | clean error (COPY not supported), **no motion** |

Also measure PD15 stays LOW (right solenoid never energises).

## 6. Motion + tool switching

1. `G28` — full home. The head ends parked with **T0 active** (pellet is the
   default mode).
2. `T1` → T0 parks left, T1 activates. `T0` → back. Watch for clean parking
   at both ends.
3. `M106 P1 S255` → only the toolhead fan spins. `M106 P0 S255` → only the
   two T0 fans. `M107` → all off.
4. Side motor lock-step: with T1 active and hotend at temperature,
   `G1 E20 F300` — the CAN motor **and** the M7 side motor must both turn,
   the same direction as filament feed. If the side motor fights the CAN
   motor, invert `dir_pin: PD3` in `BASE_PENROSE_HYBRID.cfg`
   (`[extruder_stepper extruder_side1]`) and `FIRMWARE_RESTART`.
   With **T0 active**, `G1 E5` must move only the pellet auger — the side
   motor stays still.

## 7. Calibration

| Step | How | Notes |
|---|---|---|
| T1 hotend PID | `PID_CALIBRATE HEATER=extruder1 TARGET=220` then `SAVE_CONFIG` | Shipped PID values are placeholders from the pellet config |
| Bed mesh | `G29` | Now always probes with T0 — the probe rides the pellet carriage |
| XY tool offset | Calibrate → IDEX calibration / camera wizard | Stored in `variables.cfg` (`tool_offset_x/y`) |
| Z tool offset | Calibrate → Tool Offset Z (manual) | The probe-differential Z wizard is **not usable** — T1 has no probe. Use the manual paper method, save with `M218 T1 Z<offset>` |
| T1 rotation distance sanity | Mark filament, `G1 E100 F300`, measure | 4.7158 matches the Dragon TD-01; adjust only if gears differ |
| Nozzle sizes in UI | Filament screen → edit each bay | Feeds the pre-print compatibility check (T0 pellet sizes, T1 filament sizes) |

## 8. Extruder mode — how to operate

**Settings → Printer Setup → Extruder Mode** (dropdown, hybrid only):

- **Pellet Extruder (T0)** / **Filament Extruder (T1)** — pick one, confirm.
- The mode is stored in Klipper's `variables.cfg` (`extruder_mode`) and
  survives restarts and firmware updates.
- If the machine is **idle and homed**, the carriages switch immediately.
  Idle but unhomed: applied at the next print start. Printing: saved and
  applied to the *next* job.
- Every print then starts on the mode's tool automatically
  (`beforePrintStarted` → `_APPLY_EXTRUDER_MODE`), and a `G28` inside the
  job's start gcode keeps that tool (full homes re-activate T1 in filament
  mode after the mandatory T0 homing state).

The touchscreen presents the machine as a **single-extruder printer in the
active mode**: the Home screen shows only the mode's tool (plus H0 in pellet
mode) and re-skins live on mode change — no restart needed. Control and
Filament screens keep both tools so the inactive head can be prepped
(preheated, loaded) ahead of an on-the-fly mode switch.

**Slicer contract** (single-extruder profiles, one per mode):

- **First start-gcode line**: `ASSERT_EXTRUDER_MODE MODE=PELLET` in the pellet
  profile, `ASSERT_EXTRUDER_MODE MODE=FILAMENT` in the filament profile. This
  is the protection that a sliced file can never print with the wrong head:
  on a mismatch the print cancels immediately with an on-screen error telling
  the operator to switch the mode and reprint.
- Then home with `G28`; set temperatures with `M104`/`M109 S…` (no `T`
  needed — bare `S` targets the active = mode tool). Pellet profiles keep
  their `M104 H0 S…` barrel line and `MIX_HOPPER` layer-change line.
- Do **not** emit `M605` or `T0`/`T1` in mode-based profiles — `M605` resets
  to T0 and would defeat filament mode. (Explicit `T0`/`T1` is allowed when
  you *intend* to pick the tool from the slicer instead of the UI mode; omit
  the `ASSERT_EXTRUDER_MODE` line in such profiles.)
- No wipe tower / ooze shield — only one tool prints per job.
- Motion tuning per mode is applied by the firmware
  (`_EXTRUDER_MODE_LIMITS`): pellet keeps gentle corners (SCV 4), filament
  runs standard (SCV 5) — no slicer-side changes needed.

## 9. Workflow validation — Pellet mode

Set mode = **Pellet Extruder (T0)**, then verify:

- [ ] Home screen shows only T0 + H0 + bed rows (T1 rows hidden).
- [ ] Start a **filament-profile** file (with `ASSERT_EXTRUDER_MODE
      MODE=FILAMENT`) → print cancels immediately with the mode-mismatch
      error. This is the wrong-file protection working.
- [ ] Print a small pellet job (single-extruder pellet profile with
      `ASSERT_EXTRUDER_MODE MODE=PELLET`). It prints with T0; T1 stays
      parked right the whole time.
- [ ] `beforePrintStarted` ran the hopper check: console shows
      "Pre-print pellet check…" and refills if the hopper is empty.
- [ ] Auto-refill mid-print: empty the hopper sensor → vac pulses (2s/0.5s)
      until full; 60 s without fill → "Pellet Outage T0", print pauses,
      UI shows the outage dialog.
- [ ] `MIX_HOPPER` at layer change pulses the vac (only in this mode).
- [ ] Pull the T1 filament out of the runout switch mid-print → **nothing
      happens** (console may log the event; no pause).
- [ ] Pause → T0 parks, barrel/nozzle temps saved; Resume → temps restored,
      T0 re-activated, print continues.
- [ ] Cancel/Done → cooldown script homes, `M104 T0 S0`, `M104 T1 S0`,
      bed off, motors off; pellet + filament sensors disarmed.

## 10. Workflow validation — Filament mode

Set mode = **Filament Extruder (T1)**, then verify:

- [ ] Mode switch while idle+homed physically swaps carriages (T0 parks
      left, T1 comes in). `QUERY_EXTRUDER_MODE` → `EXTRUDER_MODE:FILAMENT`.
- [ ] Home screen re-skins **live** (no restart): T0 and H0 rows disappear,
      T1 rows appear.
- [ ] Start a **pellet-profile** file → cancels with the mode-mismatch error.
- [ ] Load filament: Filament screen → T1 bay → wizard (heats, feeds the
      2500 mm PTFE path in 150 mm steps, purge loop). Runout sensor is
      suspended during the wizard and restored after.
- [ ] Print a small filament job (single-extruder filament profile, bare
      `M104/M109 S…`). The job's own `G28` notwithstanding, it prints with
      **T1**; the pellet system stays silent (no vac, no barrel heat).
- [ ] Pellet hopper empty during the filament print → console logs
      "skipped: T1 (Filament) is the active tool", **no pause, no vac**.
- [ ] Filament runout mid-print → "Filament Runout T1", print pauses, UI
      dialog appears. Reload via wizard, Resume → continues on T1.
- [ ] `M106 S…` from the job drives the toolhead fan (P1); bare `M106`
      drives all fans (legacy behaviour, harmless to the parked T0).
- [ ] Bed mesh from this mode (`G29` or wizard) switches to T0 to probe —
      watch it park T1 first, then probe with the pellet carriage.
- [ ] Cancel/Done → same cooldown as pellet mode; machine may sit with T1
      selected afterwards (the next job re-applies whatever mode is set).

## 11. Mode-switch edge cases (worth one pass)

- [ ] Switch mode while a print is running → UI confirms, tools do **not**
      swap mid-print, and the Home screen keeps the running mode's skin;
      the new mode (and skin) engage at the next job.
- [ ] Switch mode while unhomed → no motion; next print start homes and
      lands on the requested tool.
- [ ] Reboot after setting filament mode → `QUERY_EXTRUDER_MODE` still
      reports FILAMENT (persisted in `variables.cfg`); the Printer Setup
      dropdown shows it after the screen opens.

## 12. Rollback

- **Configs**: Settings → Printer Setup → "Penrose 600 Dual" → Set. The MCU
  block (both UUIDs) and the SAVE_CONFIG tail are preserved; `[mcu E1]` is
  re-commented automatically. (A dual-pellet machine also needs its right
  pellet hardware back, of course.)
- **Plugin**: `~/oprint/bin/pip install --force-reinstall
  https://github.com/FracktalWorks/PenroseControlCenter/archive/production.zip`
  then `sudo service octoprint restart`.
- **Full restore**: copy the step-1 backup over `/home/pi/` and
  `~/.octoprint/`, reboot.
