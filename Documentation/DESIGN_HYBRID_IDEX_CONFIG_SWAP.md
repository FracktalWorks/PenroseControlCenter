# Design: per-mode Klipper configs for the Penrose 600 Hybrid IDEX

Status: **proposal, not implemented.** Written for a go/no-go decision.

Target: replace the runtime `SET_EXTRUDER_MODE` switch with a **config swap**,
so Klipper itself sees a single-extruder printer in each mode — the same
pattern the `Hybrid-Penrose-600` (swappable-head) branch already ships.

---

## 0. The constraint this design must work around

**Only T0 can trigger the bed probe.** Confirmed on hardware.

A filament-mode config makes T1 the printing toolhead and demotes T0 to a
parked, non-printing carriage. **It therefore cannot probe the bed at all.**

This is not a flaw introduced by the swap — today's `G29` already forces T0
for exactly the same reason. But it does mean the design has to answer
"how does a filament-mode machine get a bed mesh?", and the answer shapes
several decisions below:

> **Bed levelling is performed in pellet mode. The resulting mesh is carried
> across the swap and re-used in filament mode.** Each mode keeps its own Z
> zero reference, because the two nozzles sit at different heights.

Section 4 is the mechanism that makes this work, and it is the single most
important part of this design. If it is skipped, switching modes silently
destroys the other mode's calibration.

---

## 1. What actually improves

Worth stating plainly, because the swap is a large change:

| Gain | Why it matters |
|---|---|
| **Klipper reports one extruder** | The OctoPrint profile can honestly be `extruder.count = 1`. Today it must stay 2, because OctoPrint maps tool0/tool1 onto `M104 T0/T1` — a 1-extruder profile would heat the *pellet* nozzle in filament mode. The swap removes that hazard at the root. |
| **Native Z zero per mode** | Today the mesh is T0-probed and T1 relies on `tool_offset_z` applied as a gcode offset. Each mode config can instead calibrate its own `[stepper_z] position_endstop` for its own nozzle — no gcode offset in the print path. Likely a better first layer. |
| **No `dual_carriage` in the print path** | No autopark, no tool-offset juggling, no `_IDEX_SWITCH_TOOL`, no COPY/MIRROR blocking. Substantially less firmware surface. |
| **Slicer profiles get simpler** | Truly single-extruder, no `T0`/`T1` at all. `M104 S…` unambiguous. A stray tool command can no longer select the wrong head. |
| **Per-mode PID and heater config** | See §4 — today both heads would fight over one `[extruder]` PID block. |

## 2. What it costs

| Cost | Detail |
|---|---|
| **Klipper restart per switch** | Loses the restart-free runtime switch. Switch becomes: park → write config → `FIRMWARE_RESTART` → re-home. Tens of seconds, not instant. |
| **Bed levelling still needs pellet mode** | The probe constraint is unchanged (§0). |
| **UI mode system reworked** | `SET_EXTRUDER_MODE` and the `variables.cfg` mode variable are replaced by a config-file selection. The touchscreen skinning can stay as-is (it reads a flag), but its source of truth changes. |
| **Parked carriage must be handled** | §3. This is the main new safety-critical mechanism. |
| **Per-mode SAVE_CONFIG infrastructure** | §4. New code in `printer_config_manager`. |

---

## 3. File layout

Mirrors the `Hybrid-Penrose-600` pattern (`EXTRUDER_PELLET.cfg` /
`EXTRUDER_FILAMENT.cfg` toggled by an include), extended to also swap the
X carriage.

```
printer.cfg                          selector + [mcu] + [mcu E1]   (preserved)
PRINTER_PENROSE_600_HYBRID.cfg       SKU: kinematics, limits, bed mesh, PRINTER_VARIABLES
BASE_PENROSE_HYBRID.cfg              SHARED hardware: Y, Y1, Z, bed, probe, chamber,
                                     runout switch, common macros
MODE_PELLET.cfg          <-- one of these two is included -->
MODE_FILAMENT.cfg
CORE_GCODE_MACROS.cfg                unchanged (fleet-wide)
PELLET_RELAY_CONTROL_HYBRID.cfg      included by MODE_PELLET.cfg only
```

`printer.cfg` gains a second selector block, exactly like the sibling branch:

```ini
########################################
# Select Extruder Mode - uncomment ONE
[include MODE_PELLET.cfg]
#[include MODE_FILAMENT.cfg]
########################################
```

### `MODE_PELLET.cfg`

| Section | Pins |
|---|---|
| `[stepper_x]` | M1 — step `PE6`, dir `PE5`, en `!PC14`, endstop `^PF0`, `position_endstop: -85`, min `-85`, max `600` |
| `[extruder]` | M6 auger — `PG9`/`PD7`/`!PG11`, heater `PA1` (`max_power: 0.5`), sensor `PC5` |
| `[heater_generic H0]` | barrel — `PA0`/`PB0`, max 480 °C |
| `[fan_generic extruder_CF_0/1]` | `PF7` / `PF9` |
| `[manual_stepper parked_carriage]` | **M2 pins** — holds the T1 carriage (§3.1) |
| `[include PELLET_RELAY_CONTROL_HYBRID.cfg]` | vac, hopper sensor, refill |

### `MODE_FILAMENT.cfg`

| Section | Pins |
|---|---|
| `[stepper_x]` | **M2** — step `PE2`, dir `!PE1`, en `!PE4`, endstop `^PF3`, `position_endstop: 640`, min `0`, max `640` |
| `[extruder]` | TD-01 CAN — `E1: gpio24/21/28`, heater `E1: gpio20`, sensor `E1: gpio26`, `rotation_distance: 4.7158` |
| `[tmc2209 extruder]` | `E1: gpio25`, `run_current: 0.850` |
| `[extruder_stepper extruder_side1]` | M7 `PD4`/`PD3`/`!PD6`, `extruder: extruder` (note: now binds to `extruder`, not `extruder1`) |
| `[tmc5160 extruder_stepper extruder_side1]` | cs `PD5`, SPI `PG6/7/8` |
| `[fan_generic extruder1_CF]`, `[heater_fan extruder1_AOF]` | `E1: gpio10`, `E1: gpio8` |
| `[manual_stepper parked_carriage]` | **M1 pins** — holds the T0 carriage (§3.1) |
| `[output_pin pellet_vac_right]` | **`!PD15`, `value: 0`** — must still be declared and held LOW even with no pellet system active, or a floating PD15 shifts the 5/2 valve (see pin map). Same for `pellet_vac_left` (`!PE9`). |

**No `[dual_carriage]` section in either file.** That is the point of the design.

### 3.1 The parked carriage

Both carriages are always physically on the same X rail. The mode that is
not printing must still **hold its carriage at its far endstop**, or it is
free to drift into the printing carriage's path.

`[manual_stepper]` is the right tool: it energises the motor and holds
position, but is not part of the kinematic X axis.

```ini
[manual_stepper parked_carriage]
step_pin: PE2               # M2 in pellet mode / PE6 (M1) in filament mode
dir_pin: !PE1
enable_pin: !PE4
microsteps: 8
rotation_distance: 20
velocity: 40
accel: 200
```

Then hold it at boot:

```ini
[delayed_gcode HOLD_PARKED_CARRIAGE]
initial_duration: 2
gcode:
    MANUAL_STEPPER STEPPER=parked_carriage ENABLE=1
    MANUAL_STEPPER STEPPER=parked_carriage SET_POSITION=0
```

**The carriage is not homed in this mode** — `manual_stepper` has no
endstop here. Its position is whatever it was physically left at, which is
why the switch sequence (§5) *must* park it before swapping.

> **Open risk:** between Klipper shutdown and restart the motor is briefly
> unpowered. A belt-driven carriage should not move under its own weight on
> a horizontal rail, but this wants confirming on the machine before the
> design is trusted. If it does drift, the fallback is to give the parked
> carriage its endstop pin and home it once at startup.

---

## 4. Per-mode `SAVE_CONFIG` — the critical piece

Klipper writes calibration into the `#*#` block at the bottom of
`printer.cfg`. `PrinterConfigManager` currently **preserves that block
wholesale** across config changes.

That breaks the moment both modes define a section called `[extruder]`,
because the two heads need *different* values for the *same* keys:

| SAVE_CONFIG key | Pellet mode | Filament mode | Conflict? |
|---|---|---|---|
| `[extruder] pid_Kp/Ki/Kd` | auger + AC band heater | TD-01 hotend | **Yes — total** |
| `[stepper_z] position_endstop` | Z zero for pellet nozzle | Z zero for TD-01 nozzle | **Yes** |
| `[probe] z_offset` | calibrated | unused (cannot probe) | Yes |
| `[bed_mesh p1]` | probed with T0 | **shared — this is the mesh we carry across** | No, deliberate |

A single shared block means every mode switch silently corrupts the other
mode's PID and Z zero. **This is the part that must not be skipped.**

### Proposed mechanism

Split the preserved block by origin, in `printer_config_manager`:

```
/home/pi/.penrose/saveconfig_pellet.cfg      per-mode: [extruder], [stepper_z], [probe]
/home/pi/.penrose/saveconfig_filament.cfg    per-mode
/home/pi/.penrose/saveconfig_shared.cfg      shared:   [bed_mesh p1]
```

Implemented: `PER_MODE_SAVE_CONFIG_PREFIXES` includes `'probe'`, so each
mode stores its own `[probe] z_offset` (pellet = bed-probed, filament =
seeded/manual `M851`). `[stepper_z]` remains shared.

On every mode switch:

1. Read the live `#*#` block out of `printer.cfg`.
2. Split it by section name: `[bed_mesh *]` → shared file; everything else →
   the **outgoing** mode's file.
3. Write the new `printer.cfg` with the new include.
4. Re-assemble the `#*#` block from `shared` + the **incoming** mode's file
   and append it.
5. `FIRMWARE_RESTART`.

The existing `_seed_probe_z_offset()` guard still applies to whichever block
is assembled, so a mode that has never been calibrated still boots.

> Note: the `Hybrid-Penrose-600` branch appears to have this same latent
> problem (both its heads define `[extruder]` and share one SAVE_CONFIG
> block). Worth checking whether PID is silently carried between heads
> there — if so, this mechanism should be back-ported.

---

## 5. Switch sequence

Ordered, because step 1 is what keeps the carriages apart:

```
1. Refuse if printing/paused (as today).
2. G28                                  full home - both carriages to their endstops
3. Park the OUTGOING carriage at its endstop and leave it there
4. Turn off the outgoing head's heaters (nozzle + H0 if leaving pellet)
5. M400                                 drain the queue
6. SAVE_CONFIG NO_RESTART=1             flush live calibration to disk
7. Plugin: split + store SAVE_CONFIG (§4), rewrite printer.cfg include,
   comment/uncomment [mcu E1] for the target mode
8. FIRMWARE_RESTART
9. On reconnect: HOLD_PARKED_CARRIAGE energises the parked motor;
   prompt the operator to re-home
```

Steps 2–6 are a new `PREPARE_EXTRUDER_MODE_SWITCH` macro; step 7 is plugin
code; step 8–9 are existing machinery.

`[mcu E1]` handling: in **pellet** mode the CAN toolhead is referenced by
nothing, and Klipper errors on an unreferenced MCU — so `[mcu E1]` must be
**commented out** in pellet mode and uncommented in filament mode. The
existing `_sync_toolhead_mcu()` already does exactly this shape of edit for
SKU changes; it needs a mode argument.

---

## 6. Plugin / UI changes

| Area | Change |
|---|---|
| Source of truth | `variables.cfg:extruder_mode` → **which `MODE_*.cfg` is included** in `printer.cfg`. Read it the way `get_current_printer_selection()` reads the SKU. |
| `SET_EXTRUDER_MODE` | Replaced by a plugin-side operation (file rewrite + restart). Keep the macro name as a thin wrapper that errors with "use the Material/Nozzle screen". |
| Material/Nozzle selector | Unchanged UI. Handler calls the new config-swap path instead of sending gcode; needs a progress dialog (restart takes ~20–30 s). |
| Screen skinning | **Unchanged.** `MODE_HIDDEN_ELEMENTS` keys off a mode string; that string now comes from the active include. |
| `config.IS_HYBRID` | Keep. Add `variable_extruder_mode: 'pellet'/'filament'` to each `MODE_*.cfg`'s `PRINTER_VARIABLES` so the existing Klipper-variable reader picks it up with no new parsing. |
| OctoPrint profile | **Now genuinely `extruder.count = 1`** in both modes. Remove the "must stay 2" guard and its comment. |
| Temperature presets | Unchanged mechanism (already per-mode). |
| Wrong-file guard | **Keep `ASSERT_EXTRUDER_MODE` and `validate_gcode_extruder_mode`.** Both still apply, and matter more: with one `[extruder]` there is no `T1` to catch a wrong file mechanically. |

---

## 7. Slicer impact

Both Fracktory machine definitions become plain single-extruder profiles:

- **Remove** the explicit `T0` / `T1` from start gcode — there is only one tool.
- **Keep** `ASSERT_EXTRUDER_MODE MODE=PELLET|FILAMENT` as the first command.
- Pellet profile keeps `M104 H0 S…` and MixHopper injection; `H0` does not
  exist in filament mode and errors there, which is a useful extra guard.
- Existing sliced files with explicit `T1` **will fail** in filament mode
  (no second tool). Migration note required.

---

## 8. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Parked carriage drifts while unpowered during restart | **High** — carriage collision | Test on machine (§3.1). Fallback: give it an endstop and home at boot. |
| Per-mode SAVE_CONFIG not implemented / buggy | **High** — silently destroys PID + Z zero | §4 is mandatory. Round-trip test: calibrate both modes, switch 3× each way, assert both sets survive byte-identical. |
| Operator switches mode with a tall part on the bed | Medium | Switch already homes first; keep the "clear the bed" confirmation. |
| Filament mode cannot level | Medium | Documented workflow: level in pellet mode. Mesh carried via shared SAVE_CONFIG. |
| Field machines mid-migration | Medium | Bump `printer.cfg` version; migration doc must cover re-calibrating PID/Z per mode once. |

## 9. Effort

Rough, for planning only:

| Work | Size |
|---|---|
| `MODE_PELLET.cfg` / `MODE_FILAMENT.cfg` split out of `BASE_PENROSE_HYBRID.cfg` | M |
| Per-mode SAVE_CONFIG split/restore in `printer_config_manager` | **L** (highest-risk code) |
| `PREPARE_EXTRUDER_MODE_SWITCH` macro + parked-carriage hold | M |
| Plugin mode-switch path (file rewrite, restart, progress UI) | M |
| Rip out `dual_carriage`, autopark, `_IDEX_SWITCH_TOOL`, `M605`, tool offsets | M (mostly deletion) |
| OctoPrint profile to 1 extruder | S |
| Docs + slicer profile updates | M |
| On-machine commissioning of both modes | **L** |

## 10. Recommendation

The design is sound and the simplification is real — particularly the honest
one-extruder OctoPrint profile and the native per-mode Z zero, which is the
most likely route to a better first layer in filament mode.

Two things should be settled **before** writing any of it:

1. **Confirm the parked carriage does not move** while its motor is
   unpowered through a `FIRMWARE_RESTART` (§3.1). Cheap to test, and it
   gates whether `manual_stepper` is sufficient or the carriage needs its
   endstop back.
2. **Accept that filament mode will never bed level.** If that is not
   acceptable long-term, the cheaper fix is to bring the T1 nozzle into the
   probe circuit — which would also make today's runtime-switch design work
   correctly, without any of this rework.
