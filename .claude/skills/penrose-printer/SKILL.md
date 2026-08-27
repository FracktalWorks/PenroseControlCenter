---
name: penrose-printer
description: >
  Connect to a live Penrose 3D printer and debug it. Use for any printer
  problem or question that needs the real machine: Klipper errors and
  shutdowns, MCU/CAN/TMC faults, heater and thermistor behaviour, failed
  prints, homing and carriage issues, extruder-mode (pellet/filament)
  problems, OctoPrint state, and Raspberry Pi health. Also use to read
  printer.cfg, klippy.log, or temperatures from a machine.
---

# Penrose printer: live connection and debugging

Scripts live in `.claude/skills/penrose-printer/scripts/`. Run them from
the repo root; every one takes `--help`.

Connection settings come from `.env` (copy `.env.example`), from
environment variables, or from flags. Nothing is hard-coded.

## Safety contract

Read actions run freely. Anything that **moves the machine, changes its
state, or writes to it** requires an explicit `--i-understand` flag, and
you must confirm with the user first. That covers `--action gcode` with a
movement/heater command, `cancel`/`pause`/`resume`, `exec`, and
`restart`.

Never send `M112`, `FIRMWARE_RESTART`, heater commands, or motion to a
machine that might be printing. Check `printer_api.py --action status`
first.

## Routing table

| Situation | Command |
|---|---|
| **Start here for any fault** | `python .claude/skills/penrose-printer/scripts/klippy_log.py` |
| Is the config sane? (hybrid) | `python .claude/skills/penrose-printer/scripts/hybrid_check.py` |
| Explain one error message | `klippy_log.py --explain "<message>"` |
| Every error the tool knows | `klippy_log.py --list` |
| Printer state / job / temps | `printer_api.py --action status` |
| Which extruder mode is live | `printer_api.py --action mode` |
| Temperatures only | `printer_api.py --action temps` |
| Read a config off the machine | `printer_ssh.py --action config --file printer.cfg` |
| List configs + mode state store | `printer_ssh.py --action list` |
| Tail klippy / octoprint log | `printer_ssh.py --action logs --log klippy --lines 300` |
| Service state | `printer_ssh.py --action services` |
| Pi health + **undervoltage** | `printer_ssh.py --action system` |
| Back up configs before changes | `printer_ssh.py --action backup` |
| Send gcode (guarded) | `printer_api.py --action gcode --command "..." --i-understand` |

## Standard procedure

1. **Read the log first.** `klippy_log.py` is ground truth. Do not
   theorise from symptoms before you have looked.
2. **Rule out power.** `printer_ssh.py --action system` decodes the Pi's
   throttle flags. Undervoltage produces random MCU disconnects that look
   like config bugs and waste hours.
3. **Check the config invariants.** On a hybrid, `hybrid_check.py`
   verifies the whole config-swap model in one pass and explains why each
   check matters.
4. **One change at a time.** Back up first (`--action backup`), show the
   before/after, then verify before making the next change.
5. **Report as:** symptom → evidence (log lines, readings) → root cause →
   fix → how to verify. Quote the actual log line; do not paraphrase it.

## What is specific about this machine

The Penrose 600 Hybrid has two carriages on one X rail but Klipper is
configured as a **single-extruder printer**. Which head is active depends
on which file `printer.cfg` includes:

| | `MODE_PELLET.cfg` | `MODE_FILAMENT.cfg` |
|---|---|---|
| `[stepper_x]` | M1, endstop `PF0`, −85…600 | M2, endstop `PF3`, 0…640 |
| Parked carriage | M2, homes on `PF3` | M1, homes on `PF0` |
| `[extruder]` | pellet auger, `PA1` | TD-01 CAN, `E1: gpio20` |
| Heaters | **two** — nozzle + `H0` barrel | **one** — nozzle |
| `[mcu E1]` | must be **commented out** | must be **uncommented** |
| Bed levelling | works | not possible — reuses the saved mesh |

Failure modes that follow from this, and which `hybrid_check.py` tests:

- **No mode include active** → Klipper has no `[stepper_x]` and no
  `[extruder]`; it will not start.
- **`[mcu E1]` state wrong for the mode** → Klipper errors on an
  unreferenced MCU (pellet), or cannot find the extruder (filament).
- **Pellet heaters on a stock thermistor table** → under-reads by ~61 °C
  at 250 °C and ~102 °C at 400 °C. Under-reading makes the PID drive
  harder, so the real temperature overshoots. The custom table is
  `[thermistor new_thermistor_t1]` in `CORE_GCODE_MACROS.cfg`.
- **Head offset missing in filament mode** → every filament print lands
  shifted by the head mounting offset. `_APPLY_HEAD_OFFSET` applies it at
  boot and after every home; `SET_HEAD_OFFSET` sets it.
- **Cooldown script keeps the barrel hot** → `afterPrintDone` must
  contain `M104 H0 S0` in pellet mode and must *not* in filament mode
  (it errors there).
- **Per-mode calibration** lives in `/home/pi/.penrose/`. `[extruder]`
  PID is per mode; bed mesh, Z endstop and probe offset are shared.

Reference docs in this repo: `Documentation/HYBRID_IDEX_PENROSE_600.md`
(system reference), `Documentation/MIGRATION_PENROSE_600_HYBRID.md`
(commissioning), `Documentation/DESIGN_HYBRID_IDEX_CONFIG_SWAP.md` (why
it is built this way).

## Dependencies

```bash
pip install requests paramiko
```

`requests` is needed for the OctoPrint API, `paramiko` for SSH. Each
script says which one is missing rather than failing obscurely.
