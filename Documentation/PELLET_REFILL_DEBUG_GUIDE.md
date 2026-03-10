# Pellet Auto-Refill System — Field Debug Guide

> **No firmware changes required.** All commands run from the Klipper console (OctoPrint Terminal tab).

---

## Quick Reference — Command Cheat Sheet

| Command | What it does |
|---------|-------------|
| `QUERY_PELLET_SYSTEM` | Full system status (sensors, valves, printer state) |
| `PELLET_SYSTEM_TEST` | Quick valve click test (1s each side) |
| `TEST_PELLET_REFILL TOOL=0` | Full closed-loop refill test for left (T0) |
| `TEST_PELLET_REFILL TOOL=1` | Full closed-loop refill test for right (T1) |
| `TEST_PELLET_STOP TOOL=0` | Abort test, close valve, disable sensor |
| `PELLET_FORCE_REFILL TOOL=0 DURATION=10` | Force vac on for exactly 10 seconds |
| `PELLET_VAC_ALL_OFF` | **Emergency stop** — close all valves immediately |
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
- Both vac relays show `OFF` when idle

> If a sensor shows `NOT CONFIGURED!`, the sensor cfg is not included in `printer.cfg`.

---

## Step 2 — Valve Click Test

```
PELLET_SYSTEM_TEST
```

Cycles each solenoid ON for 1 second, then OFF. Listen for two distinct clicks (one per side).

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
Pellet refill FORCED: T0 (Left) - vac ON, timeout 120s
  ... pellets flow into hopper ...
Pellet refill stopped: T0 (Left) - vac OFF, timeout cancelled
```

The first message means the vac started. The second message means the **sensor detected pellets and triggered automatic shutoff**. That's the full loop working end-to-end.

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

This closes the valve, cancels the timeout, and disables the sensor (returns to pre-test state). Use `TEST_PELLET_STOP` (no TOOL param) to stop both sides.

---

## Step 5 — Verify Post-Test State

```
QUERY_PELLET_SYSTEM
```

Confirm valves are OFF and sensors are in their expected state.

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
| insert_gcode not firing | Sensor must be **enabled** — `QUERY_PELLET_SYSTEM` should show `Enabled` |
| event_delay too high | Default is 0.5s — should be fine, but if sensor bounces, it may re-trigger |

### Timeout fires (120s) even though hopper filled

The sensor isn't detecting the pellets. Run:

```
QUERY_PELLET_SYSTEM
```

If the sensor still reads `LOW!` even with a visibly full hopper, the sensor sensitivity needs adjusting (trim pot) or the sensor is too far from the pellets.

---

## Testing the Timeout Safety

To verify the 120-second timeout and pause behavior works:

```
TEST_PELLET_REFILL TOOL=0 TIMEOUT_TEST=1
```

**Do NOT connect pellet supply.** After 120 seconds, you should see:

```
Pellet Outage T0 - Supply exhausted, print paused
```

> Note: This will issue a `PAUSE` command. If not printing, the pause is harmless.

---

## Mutual Exclusion Check

Only one vac should run at a time. To verify:

1. `PELLET_VAC_LEFT_ON` — left vac turns on
2. `PELLET_VAC_RIGHT_ON` — left vac turns **off**, right turns **on**
3. `PELLET_VAC_ALL_OFF` — both off

If both run simultaneously, the pneumatic system can't deliver adequate suction.

---

## Pin Reference

| Component | Tool 0 (Left) | Tool 1 (Right) |
|-----------|---------------|----------------|
| Vac relay pin | PE9 | PD15 |
| Sensor pin | PF4 (^!) | PC15 (^!) |
| Relay logic | Active-LOW (VALUE=1 = ON) | Active-LOW (VALUE=1 = ON) |
| Sensor logic | LOW = empty, HIGH = full | LOW = empty, HIGH = full |
