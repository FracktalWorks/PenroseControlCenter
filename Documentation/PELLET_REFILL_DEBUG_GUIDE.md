# Pellet Auto-Refill System — Field Debug Guide (V7 — PWM + Polling)

> **No firmware changes required.** All commands run from the Klipper console (OctoPrint Terminal tab).

---

## Architecture Overview

The V7 pellet refill system uses a **hybrid PWM + polling** approach:

- **Hardware PWM pulsing** (`VALUE=0.5`, `cycle_time=2.0`) — the MCU toggles the relay at 0.5 Hz (1s ON / 1s OFF), independent of the gcode queue. This means pulsing timing is precise even during heavy printing.
- **Software polling** (`_PELLET_POLL_LEFT` / `_PELLET_POLL_RIGHT`) — a `delayed_gcode` timer fires every 2s to check the sensor and enforce a 30s safety timeout. If the sensor detects pellets, the poll stops the PWM. If 30s elapses without detection, the print pauses.

### VALUE Mapping

| Value | Relay State | Used By |
|-------|-------------|---------|
| `0` | OFF (valve closed) | All stop commands |
| `0.5` | PULSING (MCU-level 1s ON / 1s OFF) | Auto-refill during prints, manual refill macros |
| `1` | CONTINUOUS ON | `PELLET_VAC_LEFT_ON`, `PELLET_FORCE_REFILL`, quick tests |

---

## Quick Reference — Command Cheat Sheet

| Command | What it does |
|---------|-------------|
| `QUERY_PELLET_SYSTEM` | Full system status (sensors, valves, PWM state, printer state) |
| `PELLET_SYSTEM_TEST` | Quick valve click test (1s each side, continuous) |
| `TEST_PELLET_REFILL TOOL=0` | Full closed-loop refill test for left (T0) with PWM pulsing |
| `TEST_PELLET_REFILL TOOL=1` | Full closed-loop refill test for right (T1) with PWM pulsing |
| `TEST_PELLET_STOP TOOL=0` | Abort test, close valve, cancel polling, disable sensor |
| `PELLET_FORCE_REFILL TOOL=0 DURATION=10` | Force vac on continuously for exactly 10 seconds |
| `PELLET_VAC_ALL_OFF` | **Emergency stop** — close all valves, cancel all polling |
| `DEBUG_PINS` | Verify pin configuration |

---

## Step 1 — Read Sensor & Valve State

```
QUERY_PELLET_SYSTEM
```

**What to check:**

- Sensors show `Enabled` (they auto-enable 2s after boot)
- Hopper with pellets reads `Pellets: OK`
- Empty hopper reads `Pellets: LOW!`
- Vac relays show one of three states:
  - `OFF (valve closed)` — idle
  - `PULSING (PWM 1s on/1s off, auto-refill active)` — auto-refill in progress
  - `ON (continuous)` — manual override or force refill active

> If a sensor shows `NOT CONFIGURED!`, the sensor cfg is not included in `printer.cfg`.

---

## Step 2 — Valve Click Test

```
PELLET_SYSTEM_TEST
```

Cycles each solenoid ON (continuous, VALUE=1) for 1 second, then OFF. Listen for two distinct clicks (one per side).

| Observation | Meaning |
|-------------|---------|
| Click heard on both | Relays & wiring OK |
| No click on one side | Check relay wiring for that side |
| Click but no air | Solenoid OK, check pneumatic supply / tubing |

---

## Step 3 — Full Closed-Loop Refill Test

This is the main test. It runs the same logic that fires during a print, but with `FORCE=1` so it works without printing.

### Left (T0):
```
TEST_PELLET_REFILL TOOL=0
```

### Right (T1):
```
TEST_PELLET_REFILL TOOL=1
```

### Expected console output (success):

```
Pellet refill FORCED: T0 (Left) - starting PWM pulsed refill (1s on/1s off)
  ... relay clicks on and off at 1-second intervals ...
  ... pellets flow into hopper ...
Pellet T0 (Left): hopper FULL — stopping PWM refill (Xs elapsed)
```

The first message means PWM pulsing started (`VALUE=0.5`). The polling timer (`_PELLET_POLL_LEFT`) checks the sensor every 2 seconds. When pellets are detected, it stops the PWM and prints the second message. That's the full loop working end-to-end.

### If the hopper was already full:

```
Pellet refill skipped: T0 hopper already FULL (sensor detected)
```

→ Empty the hopper and retry, or use `PELLET_FORCE_REFILL TOOL=0 DURATION=10` to bypass the sensor check.

---

## Step 4 — Abort / Stop

At any point:

```
TEST_PELLET_STOP TOOL=0
```

This closes the valve (VALUE=0), cancels the `_PELLET_POLL_LEFT` polling timer, resets elapsed tracking, and disables the sensor (returns to pre-test state). Use `TEST_PELLET_STOP` (no TOOL param) to stop both sides.

---

## Step 5 — Verify Post-Test State

```
QUERY_PELLET_SYSTEM
```

Confirm valves show `OFF (valve closed)` and sensors are in their expected state.

---

## Debugging Specific Failures

### Sensor doesn't read LOW when hopper is empty

| Check | How |
|-------|-----|
| Sensor wired correctly | `QUERY_PELLET_SYSTEM` — does it show `OK` when empty? If so, pin inversion is wrong |
| Sensor powered | Check 24V to sensor, LED on sensor board |
| Sensitivity | Capacitive sensors have a trim pot — adjust until it triggers at pellet level |

### Vac turns on but no pellets flow

| Check | How |
|-------|-----|
| Air supply connected | Verify compressor is on, pressure at line vac |
| Tube not blocked | Disconnect tube at hopper end, check airflow |
| Bulk hopper empty | Visually check upstream supply |
| Wrong vac | Have someone watch both vacs — only one should activate (`PELLET_FORCE_REFILL TOOL=0 DURATION=5`) |

### Vac never shuts off automatically

| Check | How |
|-------|-----|
| Pellets not reaching sensor | Fill level may be below sensor — check physical sensor position |
| Sensor not triggering | Watch sensor LED as pellets fill — should change state |
| insert_gcode not firing | **Known Klipper limitation:** `insert_gcode` only fires when printer is NOT printing. The PWM + polling mechanism compensates — `_PELLET_POLL_LEFT`/`_PELLET_POLL_RIGHT` checks sensor status every 2s regardless of print state |
| Polling timer not running | Check console for `starting PWM pulsed refill` messages — the poll timer starts alongside the PWM |
| event_delay too high | Default is 0.5s — should be fine, but if sensor bounces, it may re-trigger |
| debounce_delay | Set to 1.0s — sensor must be stable for 1s before state updates, prevents oscillation |

### Relay clicks but doesn't pulse (stays continuously on or off)

| Check | How |
|-------|-----|
| PWM not enabled | Verify `pwm: True` in the `[output_pin]` section for the relay |
| cycle_time wrong | Should be `cycle_time: 2.0` (produces 0.5 Hz → 1s ON / 1s OFF at VALUE=0.5) |
| VALUE not 0.5 | Check that auto-refill macros use `VALUE=0.5`, not `VALUE=1` |
| Relay can't switch at 0.5 Hz | Some relays have minimum switching time — test with `PELLET_SYSTEM_TEST` to confirm relay responds |

### Timeout fires even though hopper filled

The polling timer checks the sensor every 2 seconds and tracks elapsed time. If 30s elapses (15 poll cycles) without the sensor detecting pellets, the print pauses.

If it pauses despite a full hopper, the sensor isn't detecting the pellets. Run:

```
QUERY_PELLET_SYSTEM
```

If the sensor still reads `LOW!` even with a visibly full hopper, the sensor sensitivity needs adjusting (trim pot) or the sensor is too far from the pellets.

---

## Testing the Timeout Safety

To verify the 30s timeout and pause behavior works:

```
TEST_PELLET_REFILL TOOL=0 TIMEOUT_TEST=1
```

**Do NOT connect pellet supply.** After ~30 seconds, you should see:

```
Pellet Outage T0 - 30s PWM refill failed, print paused
```

> Note: This will issue a `PAUSE` command. If not printing, the pause is harmless.

---

## Mutual Exclusion Check

Only one vac should run at a time. To verify:

1. `PELLET_VAC_LEFT_ON` — left vac turns on (VALUE=1, continuous)
2. `PELLET_VAC_RIGHT_ON` — left vac turns **off**, right turns **on** (VALUE=1, continuous)
3. `PELLET_VAC_ALL_OFF` — both off, all polling cancelled

If both run simultaneously, the pneumatic system can't deliver adequate suction.

---

## Pin & PWM Reference

| Component | Tool 0 (Left) | Tool 1 (Right) |
|-----------|---------------|----------------|
| Vac relay pin | PE9 | PD15 |
| Sensor pin | PF4 (^!) | PC15 (^!) |
| Relay logic | Active-LOW (inverted in config) | Active-LOW (inverted in config) |
| Sensor logic | LOW = empty, HIGH = full | LOW = empty, HIGH = full |
| PWM cycle_time | 2.0s | 2.0s |
| PWM at VALUE=0.5 | 1s ON / 1s OFF | 1s ON / 1s OFF |
| Poll timer | `_PELLET_POLL_LEFT` (2s interval) | `_PELLET_POLL_RIGHT` (2s interval) |
| Safety timeout | 30s (tracked via `left_elapsed`) | 30s (tracked via `right_elapsed`) |
