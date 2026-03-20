# Linux Optimization Guide for Klipper — Preventing "Timer Too Close"

**Platform:** Raspberry Pi CM4 on BTT Manta M8P  
**OS:** Raspbian Buster (armhf)  
**Author:** Vijay Raghav Varada  
**Last Updated:** March 2026

---

## Overview

The "Timer too close" error occurs when the Klipper host (CM4) fails to send scheduled move commands to the MCU (STM32H723) in time. This is almost always caused by the host computer being momentarily overloaded — not by the MCU itself.

This guide provides step-by-step Linux-level optimizations to maximize scheduling headroom on the CM4, specifically tailored for:
- **Raspbian Buster** (legacy repos — no `cpufrequtils` package available)
- **BTT Manta M8P** with CM4 mounted directly on-board (no external USB cable)
- **Klipper + OctoPrint** running as a dedicated 3D printer controller

---

## Table of Contents

1. [CPU Governor → Performance](#1-cpu-governor--performance)
2. [ModemManager (Already Disabled)](#2-modemmanager-already-disabled)
3. [Bluetooth (Already Disabled)](#3-bluetooth-already-disabled)
4. [Reduce Swap Aggressiveness](#4-reduce-swap-aggressiveness)
5. [Set Klipper Process Priority](#5-set-klipper-process-priority)
6. [Disable Unnecessary Services](#6-disable-unnecessary-services)
7. [/boot/config.txt Optimizations](#7-bootconfigtxt-optimizations)
8. [Update /etc/rc.local for Boot Persistence](#8-update-etcrclocal-for-boot-persistence)
9. [Reboot & Verify](#9-reboot--verify)
10. [Post-Print Diagnostics](#10-post-print-diagnostics)

---

## 1. CPU Governor → Performance

By default, the CM4 uses the `ondemand` CPU governor which dynamically scales CPU frequency to save power. This introduces 5-10ms latency spikes when the CPU has to ramp up — unacceptable for real-time step scheduling.

### Apply Immediately

```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Verify

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# Expected output: performance
```

### Make Permanent

This is handled via `/etc/rc.local` — see [Step 9](#9-create-etcrclocal-for-boot-persistence).

> **Note:** On Raspbian Buster, the `cpufrequtils` package is no longer available from the default repos (404 error). Writing directly to sysfs via `rc.local` achieves the same result without any package dependency.

---

## 2. ModemManager (Already Disabled)

**This is explicitly warned about in the official Klipper FAQ.** ModemManager probes serial ports (including the one Klipper uses to talk to the MCU) and can cause "Lost communication with MCU" errors and timing disruptions.

> **Status on Penrose 600:** ModemManager is already **disabled by default** on this system. No action required.

### Verify

```bash
systemctl is-active ModemManager
# Expected output: inactive
```

### If It Were Active (reference only)

```bash
sudo systemctl stop ModemManager
sudo systemctl disable ModemManager
sudo systemctl mask ModemManager
```

---

## 3. Bluetooth (Already Disabled)

The CM4's Bluetooth shares the UART bus. Even if you're not using Bluetooth, the background services consume CPU cycles and generate interrupts.

> **Status on Penrose 600:** Bluetooth is already **disabled by default** on this system. No action required.

### Verify

```bash
systemctl is-active bluetooth
# Expected output: inactive
```

### If It Were Active (reference only)

```bash
sudo systemctl stop bluetooth
sudo systemctl disable bluetooth
sudo systemctl stop hciuart 2>/dev/null
sudo systemctl disable hciuart 2>/dev/null
# Also add to /boot/config.txt:
# dtoverlay=disable-bt
```

---

## 4. Reduce Swap Aggressiveness

The default `swappiness` value of `60` tells the kernel to aggressively move memory pages to swap (on the SD card / eMMC). This causes massive latency spikes (10-100ms+) when Klipper needs those pages back.

### Check Current Value

```bash
cat /proc/sys/vm/swappiness
# Default: 60 (too high for real-time applications)
```

### Apply Immediately

```bash
sudo sysctl vm.swappiness=10
```

### Make Permanent

```bash
echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.d/99-klipper.conf
```

### Verify

```bash
cat /proc/sys/vm/swappiness
# Expected output: 10
```

> **Why 10 and not 0?** A value of 0 doesn't completely disable swap — it just makes the kernel swap only under extreme memory pressure. Value 10 is the sweet spot for a dedicated printer with 1-4GB RAM where Klipper + OctoPrint typically use ~500MB.

---

## 5. Set Klipper Process Priority

Give Klipper's Python process higher scheduling priority than all other user-space processes.

### Create Systemd Override

```bash
sudo mkdir -p /etc/systemd/system/klipper.service.d

sudo tee /etc/systemd/system/klipper.service.d/priority.conf << 'EOF'
[Service]
Nice=-10
EOF
```

### Apply

```bash
sudo systemctl daemon-reload
sudo systemctl restart klipper
```

### Verify

```bash
ps -eo pid,ni,args | grep klippy.py
# Expected: <PID> -10 /home/pi/klippy-env/bin/python /home/pi/klipper_IDEX/klippy/klippy.py ...
```

> **Note:** The process shows as `python` in the `comm` column, so use `args` and grep for `klippy.py` instead.

> **Why Nice=-10 and not FIFO scheduling?** `CPUSchedulingPolicy=fifo` with `CPUSchedulingPriority=50` gives even higher priority, but on Buster with a CM4, FIFO scheduling can cause issues if Klipper hangs — it blocks other processes (including SSH) from recovering. `Nice=-10` gives Klipper priority over everything else without that risk.

---

## 6. Disable Unnecessary Services

Background services compete with Klipper for CPU time. On a dedicated printer, most are unnecessary.

### Safe to Disable

```bash
# Hotkey daemon (no keyboard attached to printer)
sudo systemctl disable --now triggerhappy

# Automatic apt updates (can cause CPU spikes during prints)
sudo systemctl disable --now apt-daily.timer
sudo systemctl disable --now apt-daily-upgrade.timer

# Man page indexing
sudo systemctl disable --now man-db.timer
```

### Optional — Only If You Access Printer by IP Address

```bash
# mDNS / Bonjour (provides .local hostname resolution)
# ONLY disable this if you access the printer by IP, NOT by hostname like "printer.local"
sudo systemctl disable --now avahi-daemon
```

### Audit Running Services

To see what's currently running:

```bash
systemctl list-units --type=service --state=running
```

---

## 7. /boot/config.txt Optimizations

Edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Add or modify these lines:

```ini
# === Klipper Optimizations ===

# Disable Bluetooth (frees UART, removes background interrupts)
dtoverlay=disable-bt

# Minimize GPU memory (printer doesn't need GPU rendering)
# Also reduces heat generation on the SoC
gpu_mem=16

# Disable audio (not needed on a printer, reduces heat)
dtparam=audio=off

# Raise soft thermal throttle threshold from 60°C to 70°C
# Default 60°C is too aggressive — CM4 is safe up to 80°C
# Hard throttle still kicks in at 85°C as a safety net
temp_soft_limit=70

# Overclock CM4 for more headroom (conservative)
# 1800MHz is safe with a heatsink. Use 1700 without one.
# DO NOT enable overclock until thermal throttling is resolved (vcgencmd get_throttled = 0x0)
arm_freq=1800
over_voltage=4
```

> **Note on heat reduction:** `gpu_mem=16` and `dtparam=audio=off` both reduce SoC heat generation by disabling unused hardware blocks. `temp_soft_limit=70` delays the point at which the firmware starts scaling down the CPU clock, giving more headroom before throttling kicks in.

### Overclock Safety Notes

| arm_freq | over_voltage | Requires Heatsink? | Notes |
|----------|-------------|-------------------|-------|
| 1500 | 0 (default) | No | Stock CM4 speed |
| 1700 | 2 | Recommended | Safe without heatsink in most enclosures |
| 1800 | 4 | **Yes** | Safe with heatsink or active cooling |
| 2000 | 6 | **Yes + fan** | Aggressive — test stability first |

> **Your setup (BTT M8P):** The M8P board typically has a heatsink area for the CM4. Verify your CM4 has a heatsink attached before using `arm_freq=1800`.

---

## 8. Update /etc/rc.local for Boot Persistence

The `/etc/rc.local` file already exists on this system and runs the touchscreen UI (fbcp + startx). The CPU governor line must be placed **before** `startx` — because `startx` is a blocking command and anything after it will never execute.

### Correct rc.local Contents

```bash
#!/bin/sh -e
#
# rc.local
#
# This script is executed at the end of each multiuser runlevel.
# Make sure that the script will "exit 0" on success or any other
# value on error.
#
# In order to enable or disable this script just change the execution
# bits.
#
# By default this script does nothing.

# Print the IP address
_IP=$(hostname -I) || true
if [ "$_IP" ]; then
  printf "My IP address is %s\n" "$_IP"
fi

sleep 7
fbcp &

con2fbmap 1 0

# === Klipper Optimizations ===
# Set CPU governor to performance (no frequency scaling)
echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null

startx -- -nocursor
exit 0
```

> **Critical:** The `echo performance` line MUST be placed **before** `startx -- -nocursor`. The `startx` command blocks and never returns, so any lines after it will not execute.

### How to Edit

```bash
sudo nano /etc/rc.local
```

Move the `echo performance | tee ...` line so it is between `con2fbmap 1 0` and `startx -- -nocursor`.

> **Important:** Do not overwrite this file — it contains critical startup commands for the touchscreen UI (`fbcp`, `con2fbmap`, `startx`).

### Verify rc.local is Enabled

```bash
sudo systemctl status rc-local
# Should show: active (exited) or enabled
```

If it's not enabled:

```bash
sudo systemctl enable rc-local
```

---

## 9. Reboot & Verify

```bash
sudo reboot
```

After reboot, run all verification checks:

```bash
echo "=== CPU Governor ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

echo "=== CPU Frequency ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq

echo "=== Swappiness ==="
cat /proc/sys/vm/swappiness

echo "=== ModemManager ==="
systemctl is-active ModemManager

echo "=== Bluetooth ==="
systemctl is-active bluetooth

echo "=== Klipper Priority ==="
ps -eo pid,ni,args | grep klippy.py
```

### Expected Output

```
=== CPU Governor ===
performance
=== CPU Frequency ===
1800000
=== Swappiness ===
10
=== ModemManager ===
inactive
=== Bluetooth ===
inactive
=== Klipper Priority ===
<PID> -10 /home/pi/klippy-env/bin/python /home/pi/klipper_IDEX/klippy/klippy.py /home/pi/printer.cfg -l /tmp/klippy.log
```

---

## 10. Post-Print Diagnostics

After completing a print, generate a load graph to visualize host performance:

```bash
~/klipper/scripts/graphstats.py /tmp/klippy.log -o /tmp/loadgraph.png
```

> **Note:** Your Klipper is installed at `~/klipper_IDEX/`, so the command may be:
> ```bash
> ~/klipper_IDEX/scripts/graphstats.py /tmp/klippy.log -o /tmp/loadgraph.png
> ```

Transfer the PNG to your PC and look for:
- **Bandwidth spikes** — indicates serial communication delays
- **Host buffer underruns** — host couldn't fill the MCU buffer fast enough
- **MCU load approaching 100%** — too many steppers at too high a rate

---

## Summary of All Changes

| # | Optimization | Status | Impact | Reversible? |
|---|---|---|---|---|
| 1 | CPU governor → performance | **Action required** | Eliminates 5-10ms frequency scaling latency | Yes (remove from rc.local) |
| 2 | ModemManager disabled | Already disabled | Prevents serial port probing/interference | Yes (`unmask` + `enable`) |
| 3 | Bluetooth disabled | Already disabled | Frees UART, removes background interrupts | Yes (remove overlay + `enable`) |
| 4 | Swappiness → 10 | **Action required** | Prevents disk I/O latency from memory pressure | Yes (remove sysctl conf) |
| 5 | Klipper Nice=-10 | **Action required** | Gives Klipper CPU priority over all user processes | Yes (delete override file) |
| 6 | Disable timers/services | **Action required** | Reduces CPU contention during prints | Yes (`enable` services) |
| 7 | Overclock 1800MHz | **Action required** | 20% more CPU headroom for step calculations | Yes (remove from config.txt) |
| 7 | gpu_mem=16 | **Action required** | Frees ~100MB RAM, reduces SoC heat | Yes (remove from config.txt) |
| 7 | temp_soft_limit=70 | **Action required** | Delays thermal throttling from 60°C to 70°C | Yes (remove from config.txt) |
| 7 | dtparam=audio=off | **Action required** | Reduces SoC heat generation | Yes (remove from config.txt) |

---

## Klipper Config Changes (Already Applied)

These firmware-level changes were also made to reduce MCU load:

| Setting | Before | After | File |
|---|---|---|---|
| `max_velocity` | 600 | 300 | `PRINTER_PENROSE_600.cfg` |
| `max_accel` | 2500 | 2000 | `PRINTER_PENROSE_600.cfg` |
| `gcode_arcs resolution` | 0.1 | 0.5 | `BASE_PENROSE.cfg` |
| `step_pulse_duration` (all 7 motors) | 0.000005 (5µs) | 0.000003 (3µs) | `BASE_PENROSE.cfg` |

### CM4 Temperature Monitoring (Add to Klipper Config)

Add the following to your Klipper configuration to display the CM4 SoC temperature alongside heater temps in the UI:

```ini
[temperature_sensor CM4]
sensor_type: temperature_host
min_temp: 0
max_temp: 100
```

This reads the CM4's SoC temperature directly from the Linux thermal zone. It will appear as a temperature sensor named "CM4" in OctoPrint / your UI. Use it to verify that thermals stay below 70°C during prints.

> **Where to add:** This can be added to `BASE_PENROSE.cfg` alongside other sensor definitions, or to `printer.cfg`.

---

## Troubleshooting

### "Timer too close" still occurs after all optimizations

1. **Check thermal throttling:**
   ```bash
   vcgencmd get_throttled
   ```
   - `0x0` = no throttling (good)
   - Any other value = throttling is occurring — improve cooling

2. **Check memory usage:**
   ```bash
   free -h
   ```
   If `Mem used` is close to total, consider disabling OctoPrint plugins.

3. **Check for kernel errors:**
   ```bash
   dmesg | grep -i "error\|throttl\|under.voltage"
   ```

4. **Check CPU temperature:**
   ```bash
   vcgencmd measure_temp
   ```
   Should be below 70°C during a print. Above 80°C causes throttling.

5. **Generate load graph:**
   ```bash
   ~/klipper_IDEX/scripts/graphstats.py /tmp/klippy.log -o /tmp/loadgraph.png
   ```

### Raspbian Buster Package Installation Errors (404)

The default Buster repos are EOL. To install packages, switch to the legacy mirror:

```bash
sudo sed -i 's|http://raspbian.raspberrypi.org/raspbian|http://legacy.raspbian.org/raspbian|g' /etc/apt/sources.list
sudo apt update
```

---

## How to Reverse All Changes

If you need to undo everything:

```bash
# Remove CPU governor line from rc.local (manually edit)
sudo nano /etc/rc.local
# Remove the 'echo performance | tee ...' line

# Restore default swappiness
sudo rm /etc/sysctl.d/99-klipper.conf
sudo sysctl vm.swappiness=60

# Remove Klipper priority override
sudo rm -rf /etc/systemd/system/klipper.service.d
sudo systemctl daemon-reload
sudo systemctl restart klipper

# Re-enable services
sudo systemctl enable --now triggerhappy
sudo systemctl enable --now apt-daily.timer
sudo systemctl enable --now apt-daily-upgrade.timer

# Remove /boot/config.txt additions (manually edit and remove the Klipper lines)
sudo nano /boot/config.txt

sudo reboot
```
