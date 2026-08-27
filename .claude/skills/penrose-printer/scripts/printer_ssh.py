#!/usr/bin/env python3
"""SSH into a Penrose printer to read logs, configs and service state.

    python printer_ssh.py --action logs --lines 200
    python printer_ssh.py --action config --file printer.cfg
    python printer_ssh.py --action services
    python printer_ssh.py --action system
    python printer_ssh.py --action backup
    python printer_ssh.py --action exec --command "uptime" --i-understand

Read actions are safe. --action exec and --action restart change the
machine, so they need --i-understand.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conn import (  # noqa: E402
    add_connection_args, die, emit, rule, setting, ssh_client, ssh_read_file, ssh_run,
)

# Config files worth reading, resolved to their on-machine paths.
KNOWN_CONFIGS = {
    "printer.cfg": None,           # filled from PENROSE_PRINTER_CFG
    "variables.cfg": None,         # filled from PENROSE_VARIABLES_CFG
    "MODE_PELLET.cfg": "/home/pi/MODE_PELLET.cfg",
    "MODE_FILAMENT.cfg": "/home/pi/MODE_FILAMENT.cfg",
    "BASE_PENROSE_HYBRID.cfg": "/home/pi/BASE_PENROSE_HYBRID.cfg",
    "CORE_GCODE_MACROS.cfg": "/home/pi/CORE_GCODE_MACROS.cfg",
    "PRINTER_PENROSE_600_HYBRID.cfg": "/home/pi/PRINTER_PENROSE_600_HYBRID.cfg",
}

SERVICES = ("klipper", "octoprint", "moonraker")


def act_logs(client, args):
    which = args.log
    path = {"klippy": setting("PENROSE_KLIPPY_LOG"),
            "octoprint": setting("PENROSE_OCTOPRINT_LOG")}[which]
    code, out, err = ssh_run(client, f"tail -n {int(args.lines)} {shlex.quote(path)}")
    if code != 0:
        die(f"could not read {path}: {err.strip() or 'not found'}")
    return {"log": which, "path": path, "lines": out.splitlines()}


def act_config(client, args):
    name = args.file
    path = KNOWN_CONFIGS.get(name, name if name.startswith("/") else f"/home/pi/{name}")
    if name == "printer.cfg":
        path = setting("PENROSE_PRINTER_CFG")
    elif name == "variables.cfg":
        path = setting("PENROSE_VARIABLES_CFG")
    body = ssh_read_file(client, path)
    if body is None:
        die(f"{path} not found on the machine")
    return {"path": path, "content": body}


def act_list(client, args):
    code, out, _ = ssh_run(client, "ls -la /home/pi/*.cfg 2>/dev/null")
    code2, out2, _ = ssh_run(client, f"ls -la {setting('PENROSE_MODE_STATE_DIR')} 2>/dev/null")
    return {"configs": out.splitlines(), "mode_state": out2.splitlines() if code2 == 0 else []}


def act_services(client, args):
    result = {}
    for svc in SERVICES:
        code, out, _ = ssh_run(client, f"systemctl is-active {svc} 2>/dev/null")
        state = out.strip() or "not-found"
        code2, out2, _ = ssh_run(
            client, f"systemctl show {svc} -p ActiveEnterTimestamp --value 2>/dev/null")
        result[svc] = {"state": state, "since": out2.strip() or "-"}
    return {"services": result}


def act_system(client, args):
    cmds = {
        "uptime": "uptime",
        "load": "cat /proc/loadavg",
        "memory": "free -h | head -2",
        "disk": "df -h / | tail -1",
        "temperature": "vcgencmd measure_temp 2>/dev/null || cat /sys/class/thermal/thermal_zone0/temp",
        "throttled": "vcgencmd get_throttled 2>/dev/null",
        "can0": "ip -details link show can0 2>/dev/null | head -4",
    }
    out = {}
    for label, cmd in cmds.items():
        code, stdout, _ = ssh_run(client, cmd)
        out[label] = stdout.strip() if code == 0 else "unavailable"
    # Decode the throttled bitmask - undervoltage is the usual hidden cause
    raw = out.get("throttled", "")
    if "=" in raw:
        try:
            bits = int(raw.split("=")[1], 16)
            out["power_flags"] = {
                "undervoltage_now": bool(bits & 0x1),
                "throttled_now": bool(bits & 0x4),
                "undervoltage_since_boot": bool(bits & 0x10000),
                "throttled_since_boot": bool(bits & 0x40000),
            }
        except (ValueError, IndexError):
            pass
    return {"system": out}


def act_backup(client, args):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"/home/pi/config_backup_{stamp}"
    code, out, err = ssh_run(
        client,
        f"mkdir -p {dest} && cp /home/pi/*.cfg {dest}/ 2>/dev/null; "
        f"cp {shlex.quote(setting('PENROSE_VARIABLES_CFG'))} {dest}/ 2>/dev/null; "
        f"ls -1 {dest}")
    return {"backup_dir": dest, "files": out.splitlines()}


def act_exec(client, args):
    if not args.command:
        die("--action exec needs --command")
    if not args.i_understand:
        die("running an arbitrary command on the printer needs --i-understand")
    code, out, err = ssh_run(client, args.command, timeout=60)
    return {"command": args.command, "exit": code, "stdout": out, "stderr": err}


def act_restart(client, args):
    if not args.i_understand:
        die("restarting a service interrupts the machine. Re-run with --i-understand")
    svc = args.service
    if svc not in SERVICES:
        die(f"--service must be one of {', '.join(SERVICES)}")
    code, out, err = ssh_run(client, f"sudo systemctl restart {svc}", timeout=60)
    return {"restarted": svc, "exit": code, "stderr": err.strip()}


ACTIONS = {"logs": act_logs, "config": act_config, "list": act_list,
           "services": act_services, "system": act_system, "backup": act_backup,
           "exec": act_exec, "restart": act_restart}


def render_default(p):
    if "lines" in p:
        rule(f"{p['log']} ({p['path']})")
        for line in p["lines"]:
            print("  " + line)
        return
    if "content" in p:
        rule(p["path"])
        print(p["content"])
        return
    if "services" in p:
        rule("Services")
        for name, info in p["services"].items():
            print(f"  {name:<12} {info['state']:<12} since {info['since']}")
        return
    if "system" in p:
        s = p["system"]
        rule("Raspberry Pi")
        for k in ("uptime", "load", "memory", "disk", "temperature", "can0"):
            if s.get(k) and s[k] != "unavailable":
                print(f"  {k:<12} {s[k].splitlines()[0] if s[k] else ''}")
        flags = s.get("power_flags")
        if flags:
            rule("Power")
            bad = any(flags.values())
            for k, v in flags.items():
                print(f"  {'!!' if v else '  '} {k}: {v}")
            if bad:
                print("\n  Undervoltage causes random MCU disconnects and shutdowns.")
                print("  Rule it out before chasing config problems.")
        return
    print(p)


def main():
    ap = argparse.ArgumentParser(
        description="Read logs, configs and system state from a Penrose printer over SSH.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--action", required=True, choices=sorted(ACTIONS))
    ap.add_argument("--log", choices=["klippy", "octoprint"], default="klippy")
    ap.add_argument("--lines", default=200, help="log lines to tail (default 200)")
    ap.add_argument("--file", default="printer.cfg",
                    help="config to read: " + ", ".join(KNOWN_CONFIGS) + ", or an absolute path")
    ap.add_argument("--command", help="command for --action exec")
    ap.add_argument("--service", choices=SERVICES, help="service for --action restart")
    ap.add_argument("--i-understand", action="store_true", help="confirm a state-changing action")
    add_connection_args(ap)
    args = ap.parse_args()

    client = ssh_client(args)
    try:
        result = ACTIONS[args.action](client, args)
    finally:
        client.close()
    emit(result, args.json, render_default)


if __name__ == "__main__":
    main()
