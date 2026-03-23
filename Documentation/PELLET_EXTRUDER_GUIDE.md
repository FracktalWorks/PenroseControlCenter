# Penrose Pellet Extruder System - Technical Guide

> **Version:** 1.0  
> **Last Updated:** February 2026  
> **Author:** Vijay Raghav Varada  
> **Purpose:** Reference documentation for AI agents and developers working on the Penrose pellet 3D printing system

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Auger Screw Specifications](#auger-screw-specifications)
3. [Heating System](#heating-system)
4. [Pellet Feeding System](#pellet-feeding-system)
5. [Extrusion Theory - Pumping Action](#extrusion-theory---pumping-action)
6. [Temperature Guidelines](#temperature-guidelines)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Firmware Configuration](#firmware-configuration)

---

## System Overview

The Penrose 600 is a **Cartesian IDEX (Independent Dual Extruder) pellet 3D printer** featuring:

| Specification | Value |
|---------------|-------|
| **Build Volume** | 600 × 600 × 625 mm |
| **Kinematics** | Cartesian with dual X carriages |
| **Extruders** | 2 × Pellet auger extruders |
| **Feed System** | Pneumatic line-vac with capacitive sensors |
| **Control System** | Klipper firmware via OctoPrint |
| **Nozzle Diameter** | 0.4mm (configurable) |
| **Materials** | PLA, PETG, ABS, PA, PC, PEEK (with appropriate temps) |

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PENROSE 600 SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   [BULK HOPPER] ──► [LINE VAC] ──► [EXTRUDER HOPPER]                   │
│        │                │                  │                            │
│        │           Pneumatic          Capacitive                        │
│        │           Solenoid           Level Sensor                      │
│        │           Valves             (auto-refill)                     │
│        │                                   │                            │
│        └───────────────────────────────────┘                            │
│                                                                         │
│   [EXTRUDER HOPPER] ──► [AUGER SCREW] ──► [HEATED BARREL] ──► [NOZZLE] │
│                              │                  │               │       │
│                         12mm dia            H0/H1           Extruder    │
│                         180mm len           Heater          Heater      │
│                                                                         │
│   Tool 0 (Left/Primary):  PD14 (relay), PF4 (sensor)                   │
│   Tool 1 (Right/Secondary): PE9 (relay), PC15 (sensor)                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Auger Screw Specifications

### Physical Dimensions

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Total Length** | 180 mm | |
| **Diameter** | 12 mm | Outer diameter |
| **Pitch** | 10 mm | ~18 flights total |
| **Compression Ratio** | 2:1 | (4mm ÷ 2mm flight depth) |

### Zone Breakdown

```
                            180mm Total Length
├────────────────────────────────────────────────────────────────────────┤

│◄───── Feed Zone ─────►│◄─── Compression ───►│◄────── Metering ───────►│
│         30%           │         30%         │          40%            │
│        ~54mm          │        ~54mm        │         ~72mm           │
│                       │                     │                         │
│     4mm flight        │    4mm → 2mm        │      2mm flight         │
│       depth           │   (tapered core)    │        depth            │
│                       │                     │                         │
│   ~5.4 flights        │   ~5.4 flights      │    ~7.2 flights         │
│                       │                     │                         │
        ↓                       ↓                        ↓
    [UNHEATED]           [HEATER 1: H0/H1]      [HEATER 2: Nozzle]
    Feed throat          Barrel heater          Final melt zone
```

### Zone Functions

| Zone | Length | Flight Depth | Function |
|------|--------|--------------|----------|
| **Feed** | 54mm (30%) | 4mm | Receive pellets, convey solid material, maximum volumetric intake |
| **Compression** | 54mm (30%) | 4mm → 2mm | Compress pellets, begin melting from barrel wall inward, build pressure |
| **Metering** | 72mm (40%) | 2mm | Homogenize melt, consistent output, final pressure regulation |

### Key Calculated Parameters

```
Channel Volume Comparison:
- Feed zone channel:       ~V₁ = π × 12mm × 4mm × 10mm ≈ 1508 mm³/flight
- Metering zone channel:   ~V₂ = π × 12mm × 2mm × 10mm ≈ 754 mm³/flight

Compression Ratio: V₁/V₂ = 2:1

Suitable for: PLA, PETG, ABS, ASA, PA (most common thermoplastics)
May need adjustment for: HDPE, PP (may need 3:1), soft TPU (may need 1.5:1)
```

---

## Heating System

### Heater Configuration

The system uses **dual-zone heating** per extruder:

| Zone | Klipper Name | Pin (T0) | Pin (T1) | Location |
|------|--------------|----------|----------|----------|
| **Barrel** | H0 / H1 | PA1 | PA5 | Compression zone (54-108mm) |
| **Nozzle** | extruder / extruder1 | PA0 | PA3 | Metering zone + nozzle (108-180mm) |

### Thermal Profile Diagram

```
    TEMPERATURE ALONG EXTRUDER LENGTH
    
    °C
    │
400 │                                              ┌── PEEK/PPS
    │                                         ┌────┘
350 │                                    ┌────┘
    │                               ┌────┘
300 │                          ┌────┘
    │                     ┌────┘               ← High-temp materials
250 │                ┌────┘
    │           ┌────┘
200 │      ┌────┘                              ← Standard materials (PLA/PETG)
    │ ┌────┘
150 │─┘
    │
100 │
    │
 50 │════════════
    │   COLD
  0 └──────────────────────────────────────────────►
    FEED      COMPRESSION         METERING       NOZZLE
    0mm          54mm               108mm         180mm
    
    ═══ Unheated (ambient/cooled)
    ─── Barrel heater (H0/H1)
    ─── Nozzle heater
```

### Heater Specifications

```
[heater_generic H0]                    [extruder]
├── max_power: 0.5 (50%)               ├── max_power: 0.5 (50%)
├── sensor_type: ATC Semitec 104GT-2   ├── sensor_type: ATC Semitec 104GT-2
├── control: PID                       ├── control: PID
├── max_temp: 480°C                    ├── max_temp: 480°C
└── min_temp: -200°C                   └── min_extrude_temp: 130°C
```

### Temperature Delta Rule

> **Critical Principle:** Barrel temperature should be **25-40°C BELOW** nozzle temperature to maintain solid bed for optimal pumping efficiency.

```
Barrel (H0/H1) = Nozzle - ΔT

Where ΔT = 25-40°C for most materials

Example for PLA:
- Nozzle: 180°C
- Barrel: 140-155°C
- Delta: 25-40°C
```

---

## Pellet Feeding System

### Overview

Automated pellet feeding uses:
1. **Bulk hopper** - Large reservoir of pellets
2. **Line-vac system** - Pneumatic venturi for pellet transport
3. **Capacitive sensors** - Detect pellet level in extruder hopper
4. **Solenoid valves** - Control air flow to line-vac

### Hardware Configuration

| Component | Tool 0 (Left) | Tool 1 (Right) |
|-----------|---------------|----------------|
| **Relay Pin** | PD14 | PE9 |
| **Sensor Pin** | PF4 | PC15 |
| **Relay Logic** | Active-LOW (0=ON) | Active-LOW (0=ON) |
| **Sensor Logic** | Inverted (^!) | Inverted (^!) |

### Control Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTO-REFILL CONTROL LOOP                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐                                                  │
│   │ Sensor LOW   │ ──► Hopper empty                                │
│   │ (no pellets) │     │                                           │
│   └──────────────┘     ▼                                           │
│                   ┌──────────────────────┐                          │
│                   │ Check conditions:    │                          │
│                   │ - Is printing?       │                          │
│                   │ - Is this tool active?│                         │
│                   │ - Not paused?        │                          │
│                   └──────────┬───────────┘                          │
│                              │ YES                                  │
│                              ▼                                      │
│                   ┌──────────────────────┐                          │
│                   │ Turn ON vac relay    │                          │
│                   │ (VALUE=0)            │                          │
│                   │ Start 60s timeout    │                          │
│                   └──────────┬───────────┘                          │
│                              │                                      │
│                              ▼                                      │
│   ┌──────────────┐    ┌──────────────────────┐                      │
│   │ Sensor HIGH  │◄───│ Pellets flow into    │                      │
│   │ (pellets OK) │    │ hopper via line-vac  │                      │
│   └──────┬───────┘    └──────────────────────┘                      │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────────────┐                                          │
│   │ Turn OFF vac relay   │                                          │
│   │ (VALUE=1)            │                                          │
│   │ Cancel timeout       │                                          │
│   └──────────────────────┘                                          │
│                                                                     │
│   TIMEOUT (60s): If hopper doesn't fill → PAUSE print, alert user  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### G-code Commands

| Command | Description |
|---------|-------------|
| `QUERY_PELLET_SYSTEM` | Show status of all sensors and valves |
| `PELLET_SYSTEM_TEST` | Cycle both valves for testing |
| `PELLET_VAC_LEFT_ON` / `OFF` | Manual control of T0 valve |
| `PELLET_VAC_RIGHT_ON` / `OFF` | Manual control of T1 valve |
| `PELLET_VAC_ALL_OFF` | Emergency stop - close all valves |
| `PELLET_FORCE_REFILL TOOL=0 DURATION=10` | Force refill for X seconds |
| `SET_PELLET_SENSOR S=1 TOOL=0` | Enable/disable sensor |

---

## Extrusion Theory - Pumping Action

### The Two Flow Mechanisms

**Total Output = Drag Flow - Pressure Backflow**

#### 1. Drag Flow (Forward)

Material adheres to barrel wall and is pushed forward by rotating screw flights:

```
    BARREL WALL (stationary - material sticks here)
    ════════════════════════════════════════════════
         →→→→→→→→→→→→→→→→→→→→→→→→→→→→→→
              DRAG carries material forward
    
    ╔═══╗     ╔═══╗     ╔═══╗     ╔═══╗
    ║   ║     ║   ║     ║   ║     ║   ║    ROTATION →
    ╚═══╝     ╚═══╝     ╚═══╝     ╚═══╝
                SCREW FLIGHTS
    ════════════════════════════════════════════════
```

#### 2. Pressure Flow (Backward - Backflow)

Nozzle resistance creates pressure that pushes melt backwards:

```
    NOZZLE ◄─────────────── PRESSURE GRADIENT ───────────────► FEED
    HIGH                                                        LOW
    
    Melt can flow backwards through channels (bad for efficiency)
    Solid material CANNOT flow backwards (good - acts as seal!)
```

### The Solid Bed Concept

**Critical:** The solid bed acts as a dynamic seal preventing backflow:

```
    CROSS-SECTION OF SCREW CHANNEL
    
    ════════════════════════════════  BARREL (heated)
    │░░░░░░░░░░░░│██████████████████│
    │░░ MELT ░░░░│████ SOLID BED ███│
    │░░ POOL ░░░░│██████████████████│
    │░░░░░░░░░░░░│██████████████████│
    ════════════════════════════════
    
    MELT POOL: Can flow backwards (reduces efficiency)
    SOLID BED: Blocks backflow (maintains pumping efficiency)
```

### Pumping Efficiency Comparison

| Condition | Drag Flow | Backflow | Net Output | Efficiency |
|-----------|-----------|----------|------------|------------|
| **100% Solid** | 100% | ~0% | ~100% | ~95-98% |
| **50% Solid Bed** | 100% | ~20% | ~80% | ~75-85% |
| **All Melt** | 100% | ~40-50% | ~50-60% | ~50-60% |

### Optimal Solid Bed Profile

```
    SOLID BED WIDTH ALONG SCREW LENGTH
    
    100% ██████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ██████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
     50% ██████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ██████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
      0% ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         └──────────────────────────────────────────────────────────────►
         FEED          COMPRESSION              METERING           NOZZLE
         
         GOAL: Solid bed shrinks progressively and disappears at end of metering
```

---

## Temperature Guidelines

### Material Temperature Profiles

| Material | Feed Zone | Barrel (H0/H1) | Nozzle | ΔT | Tg |
|----------|-----------|----------------|--------|----|----|
| **PLA** | <50°C | 140-160°C | 175-200°C | 30-40°C | 55-60°C |
| **PETG** | <70°C | 200-220°C | 240-260°C | 35-40°C | 80°C |
| **ABS** | <90°C | 200-220°C | 240-260°C | 35-40°C | 105°C |
| **ASA** | <90°C | 210-230°C | 250-270°C | 35-40°C | 100°C |
| **TPU** | <60°C | 180-200°C | 215-235°C | 30-35°C | -40°C |
| **PA6/66** | <80°C | 230-250°C | 265-290°C | 35-45°C | 50-75°C |
| **PC** | <120°C | 255-275°C | 290-310°C | 30-40°C | 147°C |
| **PEEK** | <150°C | 340-370°C | 400-430°C | 50-60°C | 143°C |

### Temperature Rules

```
╔══════════════════════════════════════════════════════════════════════╗
║                    TEMPERATURE CONFIGURATION RULES                   ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  RULE 1: Feed Zone Temperature                                       ║
║  ─────────────────────────────                                       ║
║  Keep BELOW glass transition (Tg) to prevent bridging                ║
║  Ideal: Tg - 10°C to 20°C                                            ║
║                                                                      ║
║  RULE 2: Barrel (H0/H1) Temperature                                  ║
║  ─────────────────────────────────                                   ║
║  Set 25-40°C BELOW nozzle temperature                                ║
║  This maintains solid bed through compression zone                   ║
║  Too hot = backflow, too cold = jamming                              ║
║                                                                      ║
║  RULE 3: Temperature Gradient                                        ║
║  ────────────────────────────                                        ║
║  Always INCREASE toward nozzle: Feed < Barrel < Nozzle               ║
║  Never: Hot → Cold → Hot (creates freeze-off)                        ║
║                                                                      ║
║  RULE 4: Speed Compensation                                          ║
║  ─────────────────────────                                           ║
║  Higher speeds = reduce ΔT (material has less time to melt)          ║
║  Lower speeds = can increase ΔT (more residence time)                ║
║                                                                      ║
║  RULE 5: Thermal Equilibrium                                         ║
║  ──────────────────────────                                          ║
║  Wait 5+ minutes after temperature changes before testing            ║
║  Metal mass takes time to stabilize                                  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Example: PLA Configuration

```
PLA at Moderate Speed:

M104 T0 S180        ; Nozzle to 180°C
M104 H0 S145        ; Barrel to 145°C (ΔT = 35°C)

; Wait for temps
M109 T0 S180        ; Wait for nozzle
M109 H0 S145        ; Wait for barrel

; Test extrusion
G91
G1 E50 F60          ; Extrude 50mm at 1mm/s
G90
```

---

## Troubleshooting Guide

### Quick Diagnostic Commands

```gcode
; 1. Full system status
QUERY_PELLET_SYSTEM

; 2. Check all temperatures
M105

; 3. Current position
M114

; 4. Test pellet valves
PELLET_SYSTEM_TEST

; 5. Force refill hopper
PELLET_FORCE_REFILL TOOL=0 DURATION=10
```

### Problem Matrix

| Symptom | Likely Zone | Probable Cause | Solution |
|---------|-------------|----------------|----------|
| **No output, motor stalls** | Feed/Compression | Barrel too cold, solid plug | ↑ Barrel temp 15-20°C |
| **No output, motor easy** | Compression/Metering | Barrel too hot, backflow | ↓ Barrel temp 10-15°C |
| **Unmelted particles** | Metering | Insufficient heat | ↑ Both temps 10-15°C |
| **Pulsing/surging** | Compression | Unstable melt transition | Adjust ΔT, check pellet feed |
| **Intermittent feeding** | Feed | Bridging in hopper | Cool feed zone, check pellet size |
| **Low output at high speed** | All | Insufficient heat transfer | ↑ Both temps, or ↓ speed |
| **Stringing/oozing** | Nozzle | Too hot, low viscosity | ↓ Nozzle temp 5-10°C |
| **Poor layer adhesion** | Metering/Nozzle | Underextrusion or temp | Check flow, ↑ nozzle temp |
| **Hopper runs empty** | Feed system | Sensor or valve failure | Run QUERY_PELLET_SYSTEM |

### Feed Zone Problems

| Issue | Symptom | Diagnosis | Fix |
|-------|---------|-----------|-----|
| **Pellet bridging** | Clicking, intermittent feed | Pellets stuck at throat | Cool feed zone, add vibration |
| **Heat creep** | Soft pellets jam | Feed zone too hot | Add cooling, thermal break |
| **Starve feeding** | Low output, pulsing | Insufficient pellet supply | Check hopper level, vacuum system |

### Compression Zone Problems

| Issue | Symptom | Diagnosis | Fix |
|-------|---------|-----------|-----|
| **Solid plug** | Motor stalls, high torque | Barrel too cold | ↑ H0/H1 by 15-20°C |
| **Premature melt** | Low output, easy motor | Barrel too hot | ↓ H0/H1 by 10-15°C |
| **Uneven melting** | Surging, inconsistent output | Temp instability | Check PID tuning, wait for equilibrium |

### Metering Zone Problems

| Issue | Symptom | Diagnosis | Fix |
|-------|---------|-----------|-----|
| **Incomplete melting** | Particles in output | Nozzle too cold | ↑ Nozzle 10-15°C |
| **Thermal degradation** | Discoloration, smell | Nozzle too hot | ↓ Nozzle 10-15°C |
| **High pressure drop** | Low flow rate | Nozzle clog or too small | Clean/replace nozzle |

### Pellet Feed System Problems

| Issue | Symptom | Diagnosis | Fix |
|-------|---------|-----------|-----|
| **Valve won't open** | No pellet flow | Relay/wiring issue | Check pin, run DEBUG_PINS |
| **Sensor always LOW** | Constant refill attempts | Sensor misconfigured | Check ^! inversion |
| **Sensor always HIGH** | Never refills | Pellets stuck on sensor | Clean sensor face |
| **60s timeout** | Print pauses | Bulk supply empty | Refill bulk hopper |
| **Air leak** | Weak vacuum | Tube disconnected | Check all connections |

---

## Firmware Configuration

### Key Configuration Files

| File | Purpose |
|------|---------|
| `PRINTER_PENROSE_600_DUAL.cfg` | Dual nozzle IDEX printer settings, build volume, kinematics |
| `PRINTER_PENROSE_600_SINGLE.cfg` | Single nozzle printer settings, build volume, kinematics |
| `BASE_PENROSE_DUAL.cfg` | IDEX hardware configuration, steppers, heaters, dual carriage |
| `BASE_PENROSE_SINGLE.cfg` | Single nozzle hardware configuration |
| `PELLET_RELAY_CONTROL_DUAL.cfg` | Line-vac solenoids, control macros (both LEFT and RIGHT) |
| `PELLET_RELAY_CONTROL_SINGLE.cfg` | Line-vac solenoid, control macros (LEFT only) |
| `T0_PELLET_LEVEL_SENSOR.cfg` | Left hopper level sensor |
| `T1_PELLET_LEVEL_SENSOR.cfg` | Right hopper level sensor (dual nozzle only) |
| `CORE_GCODE_MACROS.cfg` | Common G-code macros |

### Extruder Configuration

```ini
[extruder]
step_pin: PG9
dir_pin: PD7
enable_pin: !PG11
microsteps: 2                    # Low microsteps for torque
rotation_distance: 14.0          # Calibrated for pellet auger
step_pulse_duration: 0.000005    # 5µs for DM542 driver
nozzle_diameter: 0.4
filament_diameter: 1.75          # Legacy setting, not used for pellets
heater_pin: PA0
max_power: 0.5                   # AC heater limited to 50%
sensor_pin: PB0
sensor_type: ATC Semitec 104GT-2
control: pid
min_extrude_temp: 130
max_extrude_only_distance: 5000.0
max_extrude_cross_section: 8.0   # Allows high-volume pellet extrusion
min_temp: -200
max_temp: 480

[heater_generic H0]
gcode_id: H0
heater_pin: PA1
max_power: 0.5
sensor_pin: PC5
sensor_type: ATC Semitec 104GT-2
control: pid
min_temp: -200
max_temp: 480
```

### Pellet Valve Configuration

```ini
[output_pin pellet_vac_left]
pin: PD14
value: 1           # Start OFF (valve closed) - Active LOW
shutdown_value: 1  # On shutdown, close valve (safety)

[output_pin pellet_vac_right]
pin: PE9
value: 1
shutdown_value: 1
```

### Pellet Sensor Configuration

```ini
[filament_switch_sensor pellet_sensor_left]
switch_pin: ^!PF4              # Internal pullup, inverted for active-LOW
pause_on_runout: False         # Don't pause - we handle via macros
event_delay: 0.5
runout_gcode:
    _PELLET_CHECK_AND_REFILL TOOL=0
insert_gcode:
    _PELLET_STOP_REFILL TOOL=0
```

---

## Appendix: Quick Reference Card

```
╔══════════════════════════════════════════════════════════════════════╗
║               PENROSE PELLET EXTRUDER QUICK REFERENCE                ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  AUGER: 12mm Ø × 180mm, 10mm pitch, 2:1 compression                  ║
║  ZONES: Feed 30% (4mm) → Compression 30% (4→2mm) → Metering 40% (2mm)║
║                                                                      ║
║  HEATERS:                                                            ║
║    Barrel (H0/H1): Compression zone | Nozzle: Metering zone          ║
║                                                                      ║
║  TEMPERATURE RULE:                                                   ║
║    Barrel = Nozzle - 25°C to 40°C                                    ║
║                                                                      ║
║  PLA QUICK SETUP:                                                    ║
║    Barrel: 140-160°C | Nozzle: 175-200°C | Feed: <50°C               ║
║                                                                      ║
║  DIAGNOSTIC COMMANDS:                                                ║
║    QUERY_PELLET_SYSTEM    - Full status                              ║
║    PELLET_SYSTEM_TEST     - Test valves                              ║
║    M105                   - All temperatures                         ║
║                                                                      ║
║  PINS:                                                               ║
║    T0: Relay PD14, Sensor PF4    T1: Relay PE9, Sensor PC15          ║
║                                                                      ║
║  TROUBLESHOOTING:                                                    ║
║    No output + high torque = Barrel too COLD                         ║
║    No output + easy motor = Barrel too HOT                           ║
║    Surging = Temperature instability or feed issue                   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial comprehensive documentation |

---

*This document is intended for AI agents and developers working on the Penrose pellet 3D printing system. For questions or updates, refer to the firmware configuration files in the `firmware/` directory.*
