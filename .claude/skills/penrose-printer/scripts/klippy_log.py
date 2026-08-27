#!/usr/bin/env python3
"""Parse klippy.log and explain what the errors actually mean.

Klipper's log is ground truth - read it before theorising. This groups the
errors it finds and attaches the known cause for each, with the Penrose
specifics (config-swap model, pellet heaters, CAN toolhead) rather than
generic Klipper advice.

    python klippy_log.py                      # pull from the printer over SSH
    python klippy_log.py --file klippy.log    # parse a local copy
    python klippy_log.py --explain "Timer too close"

Read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conn import add_connection_args, die, emit, rule, setting, ssh_client, ssh_run  # noqa: E402

# Ordered: the first pattern that matches a line wins, so put the specific
# ones above the general ones.
KNOWN = [
    (r"Option '(\w+)' in section '(\w+)' must be specified",
     "Missing required config option",
     "Usually [probe] z_offset after a config change. It lives in the SAVE_CONFIG "
     "block at the bottom of printer.cfg, not in the included .cfg files. The plugin "
     "seeds it automatically on deploy - take the firmware update or re-select the SKU. "
     "Do NOT uncomment z_offset in the base cfg: a value there silently overrides the "
     "SAVE_CONFIG calibration and makes the wizard fail."),

    (r"Unknown config (?:object|section) '?\[?(\w+)",
     "Config references something that does not exist",
     "On the hybrid this usually means the MODE_*.cfg include is wrong: either none is "
     "active, or the active one does not match the hardware. Run hybrid_check.py --check mode."),

    (r"MCU '(\w+)' shutdown: Timer too close",
     "MCU scheduler missed its deadline",
     "Host or CAN timing, not a config parse problem. Work through "
     "Documentation/LINUX_OPTIMIZATION_KLIPPER.md (CPU governor, swap, service priority). "
     "Then check can0 bitrate is 1000000 with txqueuelen 128, and that the bus has 120 ohm "
     "termination at BOTH ends. dmesg | grep -i can shows bus-off storms."),

    (r"Lost communication with MCU '(\w+)'",
     "MCU stopped responding",
     "Rule out Pi undervoltage FIRST (printer_ssh.py --action system shows the power flags). "
     "For 'E1' specifically this is the CAN toolhead: check can0 is up, the UUID in "
     "printer.cfg matches, and the bus is terminated."),

    (r"Heater (\w+) not heating at expected rate",
     "verify_heater tripped",
     "On the 600x600 bed this can false-trigger near target; BASE_PENROSE_HYBRID.cfg relaxes "
     "the bed check. For a PELLET heater, suspect the thermistor table before the hardware: a "
     "stock table on the custom sensor under-reads badly, so Klipper sees a slow climb that is "
     "not real. Run hybrid_check.py --check heaters."),

    (r"(?:ADC out of range|Thermistor .* out of range)",
     "Temperature reading outside the sensor's valid band",
     "A disconnected or shorted thermistor, or the wrong sensor_type. Note that the pellet "
     "heaters ship with min_temp: -200, which SUPPRESSES this fault - if you see it, the "
     "reading is extreme. Check wiring first, then sensor_type."),

    (r"Move out of range",
     "Commanded position is outside the axis limits",
     "On the hybrid, X limits differ by mode: pellet is -85..600, filament is 0..640. A file "
     "sliced for the other mode, or a macro using the other mode's coordinates, produces this. "
     "Confirm the active mode with hybrid_check.py --check mode."),

    (r"Must home axis first|Must home (\w+) axis",
     "Move attempted before homing",
     "Expected after a mode switch - the machine comes back unhomed. Home before printing. "
     "If it happens mid-print, something cleared the homed state (an error, or FIRMWARE_RESTART)."),

    (r"Endstop (\w+) still triggered after retract",
     "Endstop did not release during homing",
     "The carriage is sitting on the switch, or the switch is stuck/miswired. On the hybrid, "
     "note the parked carriage has its OWN endstop (PF3 in pellet mode, PF0 in filament) used "
     "by _HOME_PARKED_CARRIAGE - a fault there points at that switch, not the printing axis."),

    (r"No trigger on (\w+) after full movement",
     "Homing move finished without hitting the endstop",
     "Switch not wired, wrong pin, or the axis did not move. For 'parked_carriage' check the "
     "endstop_pin in the active MODE_*.cfg matches the physical switch on that carriage."),

    (r"Unable to (?:open|read) (?:serial|CAN) port|Unable to connect",
     "Cannot reach the MCU at all",
     "Check the [mcu] serial/canbus_uuid in printer.cfg. On the hybrid, [mcu E1] must be "
     "UNCOMMENTED in filament mode and COMMENTED in pellet mode - Klipper errors on an MCU "
     "that no section references."),

    (r"TMC .* (?:communication|uart) error|Unable to read tmc",
     "Stepper driver not responding",
     "SPI/UART wiring or address. On the hybrid the filament drive TMC2209 is on the CAN "
     "toolhead (E1: gpio25) and the side feeder TMC5160 is on the mainboard M7."),

    (r"Shutdown due to (.+)",
     "Klipper shut down",
     "The real cause is the line ABOVE this one - this is the consequence. Read upward."),

    (r"Internal error on command:'?(\w+)",
     "Python traceback inside a command",
     "Usually a cascade after an earlier shutdown, or a macro bug. The traceback directly "
     "above this line is the actual diagnosis - capture the log before restarting."),
]

NOISE = re.compile(r"^(?:Stats |Starting Klippy|Args:|Git version|CPU:|Python:|"
                   r"video4linux|=+ Log rollover|mcu '\w+': Starting|Loaded MCU)")


def classify(line: str):
    for pattern, title, why in KNOWN:
        m = re.search(pattern, line)
        if m:
            return {"title": title, "why": why, "match": m.group(0)}
    return None


def fetch_log(args) -> list[str]:
    if args.file:
        p = Path(args.file)
        if not p.exists():
            die(f"{p} not found")
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    client = ssh_client(args)
    try:
        path = setting("PENROSE_KLIPPY_LOG")
        code, out, err = ssh_run(client, f"tail -n {int(args.lines)} {path}", timeout=45)
        if code != 0:
            die(f"could not read {path}: {err.strip() or 'not found'}")
        return out.splitlines()
    finally:
        client.close()


def analyse(lines: list[str]) -> dict:
    findings, counts = [], Counter()
    for idx, line in enumerate(lines):
        if NOISE.search(line):
            continue
        hit = classify(line)
        if hit:
            counts[hit["title"]] += 1
            if counts[hit["title"]] <= 3:  # keep the report readable
                findings.append({**hit, "line": line.strip()[:220],
                                 "context": [l.strip()[:160] for l in lines[max(0, idx - 3):idx]]})
    return {"scanned": len(lines), "findings": findings,
            "counts": dict(counts.most_common())}


def render(p):
    print(f"\nScanned {p['scanned']} log lines")
    if not p["findings"]:
        print("\n  No known error patterns found.")
        print("  If the machine is still misbehaving, widen the window with --lines 2000,")
        print("  or the failure may not reach klippy.log at all (check octoprint.log).")
        return
    rule("Error summary")
    for title, n in p["counts"].items():
        print(f"  {n:>4}x  {title}")
    for i, f in enumerate(p["findings"], 1):
        print(f"\n{'=' * 66}\n{i}. {f['title']}   (matched: {f['match']})\n{'=' * 66}")
        if f["context"]:
            print("  leading up to it:")
            for c in f["context"]:
                print(f"    | {c}")
        print(f"  >> {f['line']}")
        print("\n  What this means:")
        for line in _wrap(f["why"], 62):
            print(f"    {line}")


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line); line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Parse klippy.log and explain the errors, Penrose-specifically.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--file", help="parse a local log file instead of fetching over SSH")
    ap.add_argument("--lines", default=1500, help="lines to fetch (default 1500)")
    ap.add_argument("--explain", help="explain one error message without a log")
    ap.add_argument("--list", action="store_true", help="list every error this tool knows")
    add_connection_args(ap)
    args = ap.parse_args()

    if args.list:
        for _, title, why in KNOWN:
            print(f"\n{title}\n  " + "\n  ".join(_wrap(why, 68)))
        return
    if args.explain:
        hit = classify(args.explain)
        if not hit:
            print("Not a known pattern. Fetch the log around it:")
            print("  python klippy_log.py --lines 2000")
            sys.exit(1)
        print(f"\n{hit['title']}\n" + "-" * len(hit["title"]))
        print("\n".join("  " + l for l in _wrap(hit["why"], 68)))
        return

    emit(analyse(fetch_log(args)), args.json, render)


if __name__ == "__main__":
    main()
