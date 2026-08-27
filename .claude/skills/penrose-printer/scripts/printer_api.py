#!/usr/bin/env python3
"""Talk to a Penrose printer over the OctoPrint REST API.

Read actions are safe to run any time. Actions that move the machine or
change its state are gated behind --i-understand, so nothing here can
surprise a running print by accident.

    python printer_api.py --action status
    python printer_api.py --action temps
    python printer_api.py --action mode
    python printer_api.py --action gcode --command "QUERY_EXTRUDER_MODE" --i-understand

Connection comes from .env / env vars / flags - see _conn.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conn import (  # noqa: E402
    add_connection_args, api_get, api_post, die, emit, rule, setting, status_line,
)

READ_ACTIONS = ("status", "connection", "temps", "job", "mode", "version", "profile", "files")
WRITE_ACTIONS = ("gcode", "cancel", "pause", "resume")

# Commands that move the machine or change persistent state. Sending these
# is a physical action, so they need --i-understand even in --action gcode.
MOVEMENT_PREFIXES = (
    "G0", "G1", "G28", "G29", "G30", "M84", "M18", "T0", "T1",
    "MANUAL_STEPPER", "PREPARE_EXTRUDER_MODE_SWITCH", "SET_EXTRUDER_MODE",
    "BED_MESH_CALIBRATE", "PROBE", "HOME", "FORCE_MOVE", "SET_HEAD_OFFSET",
    "M104", "M109", "M140", "M190", "PID_CALIBRATE", "SAVE_CONFIG",
    "FIRMWARE_RESTART", "RESTART", "M112",
)


def is_movement(command: str) -> bool:
    head = command.strip().upper()
    return any(head.startswith(p) for p in MOVEMENT_PREFIXES)


# ---------------------------------------------------------------------------

def act_status(args):
    state = api_get(args, "/api/printer?exclude=history") or {}
    conn = api_get(args, "/api/connection") or {}
    job = api_get(args, "/api/job") or {}
    return {
        "state": (state.get("state") or {}).get("text", "unknown"),
        "flags": (state.get("state") or {}).get("flags", {}),
        "connection": (conn.get("current") or {}),
        "job_state": job.get("state"),
        "job_file": ((job.get("job") or {}).get("file") or {}).get("name"),
        "progress": round((job.get("progress") or {}).get("completion") or 0, 1),
        "temperatures": state.get("temperature", {}),
    }


def act_temps(args):
    state = api_get(args, "/api/printer?exclude=history,sd") or {}
    return {"temperatures": state.get("temperature", {})}


def act_job(args):
    return api_get(args, "/api/job") or {}


def act_connection(args):
    return api_get(args, "/api/connection") or {}


def act_version(args):
    return api_get(args, "/api/version") or {}


def act_profile(args):
    prof = api_get(args, "/api/printerprofiles") or {}
    return prof.get("profiles", prof)


def act_files(args):
    data = api_get(args, "/api/files?recursive=false") or {}
    return [
        {"name": f.get("name"), "size": f.get("size"), "date": f.get("date")}
        for f in data.get("files", []) if f.get("type") == "machinecode"
    ][:40]


def act_mode(args):
    """Report the hybrid extruder mode as the machine currently sees it.

    Uses temperature keys as the tell: pellet mode exposes an H0 barrel
    heater, filament mode does not. That is the same signal the
    touchscreen and OctoPrint web UI key off, so it reflects what Klipper
    actually loaded rather than what a config file says it should be.
    """
    state = api_get(args, "/api/printer?exclude=history,sd") or {}
    temps = state.get("temperature", {}) or {}
    keys = sorted(temps.keys())
    has_h0 = "H0" in temps
    has_tool1 = "tool1" in temps
    if has_tool1:
        inferred = "IDEX / dual (tool1 present - not the config-swap model)"
    elif has_h0:
        inferred = "pellet"
    else:
        inferred = "filament"
    return {
        "inferred_mode": inferred,
        "heater_keys": keys,
        "has_H0_barrel": has_h0,
        "has_tool1": has_tool1,
        "note": "Cross-check against the active MODE_*.cfg include with hybrid_check.py",
    }


def act_gcode(args):
    if not args.command:
        die("--action gcode needs --command \"<gcode>\"")
    if is_movement(args.command) and not args.i_understand:
        die(
            f"'{args.command}' can move the machine or change persistent state.\n"
            f"  Re-run with --i-understand once you have confirmed:\n"
            f"    - the printer is not mid-print\n"
            f"    - the bed is clear and nobody is reaching into the machine"
        )
    api_post(args, "/api/printer/command", {"commands": args.command.split("\n")})
    return {"sent": args.command, "note": "OctoPrint accepted the command; check --action temps or the log for the result"}


def act_cancel(args):
    if not args.i_understand:
        die("cancelling a print is destructive. Re-run with --i-understand")
    api_post(args, "/api/job", {"command": "cancel"})
    return {"cancelled": True}


def act_pause(args):
    if not args.i_understand:
        die("pausing affects a running print. Re-run with --i-understand")
    api_post(args, "/api/job", {"command": "pause", "action": "pause"})
    return {"paused": True}


def act_resume(args):
    if not args.i_understand:
        die("resuming affects a running print. Re-run with --i-understand")
    api_post(args, "/api/job", {"command": "pause", "action": "resume"})
    return {"resumed": True}


ACTIONS = {
    "status": act_status, "temps": act_temps, "job": act_job,
    "connection": act_connection, "version": act_version, "profile": act_profile,
    "files": act_files, "mode": act_mode, "gcode": act_gcode,
    "cancel": act_cancel, "pause": act_pause, "resume": act_resume,
}


# ---------------------------------------------------------------------------

def render_status(p):
    rule("Printer")
    print(f"  state      : {p['state']}")
    conn = p.get("connection") or {}
    print(f"  connected  : {conn.get('state', '?')}  port={conn.get('port', '?')}")
    if p.get("job_file"):
        print(f"  job        : {p['job_file']}  ({p['progress']}%)  {p.get('job_state')}")
    else:
        print("  job        : none")
    render_temps(p)


def render_temps(p):
    temps = p.get("temperatures") or {}
    if not temps:
        print("  (no temperature data - is Klipper connected?)")
        return
    rule("Temperatures")
    label = {"tool0": "nozzle", "tool1": "tool1", "H0": "H0 barrel",
             "H1": "H1 barrel", "bed": "bed", "chamber": "chamber"}
    for key in sorted(temps):
        t = temps[key] or {}
        if not isinstance(t, dict):
            continue
        actual, target = t.get("actual"), t.get("target")
        print(f"  {label.get(key, key):<10} {actual:>7.1f} C  ->  {target:>6.1f} C"
              if isinstance(actual, (int, float)) and isinstance(target, (int, float))
              else f"  {label.get(key, key):<10} {actual} -> {target}")


def render_mode(p):
    rule("Extruder mode (inferred from live heaters)")
    print(f"  mode        : {p['inferred_mode']}")
    print(f"  heaters     : {', '.join(p['heater_keys']) or 'none'}")
    print(status_line(p["has_H0_barrel"], "H0 barrel heater present",
                      "(expected in pellet mode only)"))
    print(f"\n  {p['note']}")


RENDER = {"status": render_status, "temps": render_temps, "mode": render_mode}


def main():
    ap = argparse.ArgumentParser(
        description="Query and control a Penrose printer via OctoPrint.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--action", required=True, choices=sorted(ACTIONS),
                    help="read: " + ", ".join(READ_ACTIONS) + " | write: " + ", ".join(WRITE_ACTIONS))
    ap.add_argument("--command", help="gcode to send (with --action gcode)")
    ap.add_argument("--i-understand", action="store_true",
                    help="confirm a physical / destructive action")
    add_connection_args(ap)
    args = ap.parse_args()

    result = ACTIONS[args.action](args)
    emit(result, args.json, RENDER.get(args.action))


if __name__ == "__main__":
    main()
