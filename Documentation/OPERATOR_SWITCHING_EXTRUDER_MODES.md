# Operator guide: switching between pellet and filament

For the person standing at the machine. Engineering detail lives in
`HYBRID_IDEX_PENROSE_600.md`; this is the procedure only.

> A formatted, shareable version of this guide is published as an artifact:
> https://claude.ai/code/artifact/8d046b27-ade2-4ee0-84fa-0eed4220201a
> **This file is the source of truth** — update it here first.

---

## What the machine is

Your printer has two extruders fitted, but it only ever uses one at a time.
Switching takes about a minute and happens entirely from the touchscreen.

| | Pellet Extruder | Filament Extruder |
|---|---|---|
| Heaters | **two** — nozzle + barrel (H0) | **one** — nozzle only |
| Material | pellets, vacuum-fed from the hopper | filament, loaded from the Material screen |
| Bed levelling | **yes** — the only mode that can level | no — reuses the mesh from pellet mode |
| Prints with | the left carriage | the right carriage |

## Before you switch

- The printer is **not printing or paused**. The selector stays greyed out
  until the job is finished or cancelled.
- The **bed is clear**. The printer homes as part of the switch.
- Nothing else. You do not move anything by hand or change any files.

## Switching

1. **Open the Material & Nozzle screen.** The bay is named after the
   extruder currently fitted, so it also tells you which mode you are in.
2. **Tap the Extruder Type selector** at the top — it reads
   `Pellet Extruder` or `Filament Extruder`.
3. **Choose the other extruder, then confirm.** A dialog explains what will
   happen; nothing is sent to the printer until you tap Yes.
4. **Wait about a minute.** A progress message stays on screen.
   **Do not power the printer off during this step.**
5. **Home the printer** before starting a print. A confirmation dialog tells
   you the switch is done.

### What the printer is doing during that minute

Listed so the noise and movement are not a surprise — none of it needs your
attention.

| Stage | What you see |
|---|---|
| Homes | both carriages travel to their end positions |
| Parks | the extruder you are leaving moves to the far end and stays there |
| Cools | that extruder's heaters switch off — including the barrel, in pellet mode |
| Reconfigures | brief pause, no movement |
| Restarts | the printer reconnects and the screens update |

Only the motion controller restarts. The touchscreen stays on throughout.

## What looks different afterwards

| Screen | Pellet mode | Filament mode |
|---|---|---|
| Home | nozzle **and barrel** temperatures | nozzle temperature only |
| Control | barrel controls shown; toggle reads "Pellet Level Sensor" | no barrel controls; toggle reads "Filament Runout Sensor" |
| Material & Nozzle | one bay: Pellet Extruder | one bay: Filament Extruder |
| Web interface | pellet presets, profile ends "(Pellet)" | filament presets, profile ends "(Filament)" |

## Four things that catch people out

**Bed levelling only works in pellet mode.** Only the pellet nozzle can
touch off the bed sensor. Level in pellet mode — the result is saved and used
automatically in filament mode too. A filament job that asks to level will
skip it and use the saved result. That is normal.

**You do not have to re-level every time you switch.** The bed shape is
shared, and each extruder remembers its own height. Level when the bed
changes, not when the mode changes.

**Each extruder needs its first-layer height set once.** The two nozzles do
not sit at the same height, so each one keeps its own. On a new machine, or
if the first layer prints too high or digs in, do the paper test below. The
printer remembers it from then on, through every switch.

**But if you re-level, check both.** The two heights are independent, so
after re-levelling in pellet mode, check the filament first layer as well
and redo its paper test if it has moved.

**Your sliced file has to match the mode.** Slice with the machine profile
for the mode you are in. Start the wrong file and the printer cancels
immediately, naming the mode the file expects. It will not print with the
wrong extruder.

**To load filament, switch to filament mode first.** Only the fitted
extruder appears on the Material screen.

**The first time you use each mode, tune the heater.** The two extruders
heat very differently, so each keeps its own tuning. Run the heater tune once
per mode on a new machine — after that the printer remembers both, and
switching never loses either.

## If something looks wrong

| What you see | What it means |
|---|---|
| The selector is greyed out | Printing, paused, or not connected. Finish or cancel the job first. |
| "Printer is not idle after homing" | Something started while you were switching. Nothing was changed — check the printer and try again. |
| A print cancels the moment it starts | The file was sliced for the other mode. Switch modes, or re-slice. |
| Levelling skipped in filament mode | Expected — it uses the mesh saved from pellet mode. |
| First layer too high, or squashed | That extruder's height has not been set. Do the paper test below. |
| A message about the Z zero never being set | The filament extruder is new to this machine. Do the paper test below. |
| Temperatures look wrong after switching | Check you are reading the right row: filament mode has no barrel heater, so that row disappears. |

## Setting an extruder's first-layer height (the paper test)

Once per extruder, per machine. Takes two minutes.

1. Switch to the extruder you want to set, and make sure the bed is clear.
2. On the touchscreen open **Calibrate**, and run **Z Zero Calibrate**. The
   printer homes and brings the nozzle down to the bed at the centre.
3. Slide a sheet of ordinary paper under the nozzle.
4. Use the **Z − / Z +** buttons on the Control screen until the paper *just*
   drags — you can still move it, but you feel it.
   - Paper slides freely → nozzle too high → press **Z −**
   - Paper will not move → nozzle too low → press **Z +**
5. That is it. Every press is saved as you go. Home the printer and print.

The setting belongs to that extruder alone. Switching to the other one and
back does not disturb it.

> **While the printer is switching:** keep hands clear. The carriages move
> during homing and parking, and the extruder you are leaving may stay hot
> for several minutes after its heaters switch off.
