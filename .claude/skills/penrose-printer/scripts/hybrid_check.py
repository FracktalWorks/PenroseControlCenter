#!/usr/bin/env python3
"""Health check for the Penrose 600 Hybrid config-swap model.

Reads the machine's live configuration over SSH and checks the invariants
that this design depends on. Every check here exists because breaking it
produces a specific, known failure - the reason is printed with the result
rather than left for someone to rediscover.

    python hybrid_check.py                 # all checks
    python hybrid_check.py --check mode    # one group
    python hybrid_check.py --json          # machine-readable

Read-only: opens files and greps. Never writes, never moves the machine.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conn import (  # noqa: E402
    add_connection_args, emit, rule, setting, ssh_client, ssh_read_file, ssh_run,
)

MODES = ("pellet", "filament")


class Findings:
    """Collects results so text and JSON renderings stay in step."""

    def __init__(self):
        self.items = []

    def add(self, group, ok, label, detail="", why=""):
        self.items.append({"group": group, "ok": ok, "label": label,
                           "detail": detail, "why": why})

    def failures(self):
        return [i for i in self.items if i["ok"] is False]

    def unknowns(self):
        return [i for i in self.items if i["ok"] is None]


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_mode(client, f: Findings) -> str | None:
    """Exactly one MODE_*.cfg include must be active."""
    cfg = ssh_read_file(client, setting("PENROSE_PRINTER_CFG"))
    if cfg is None:
        f.add("mode", False, "printer.cfg readable", "not found",
              "Nothing else can be checked without it.")
        return None

    active = [m.group(1).lower() for m in
              re.finditer(r"^\s*\[include MODE_(\w+)\.cfg\]", cfg, re.M)]
    present = re.findall(r"^\s*#?\s*\[include MODE_(\w+)\.cfg\]", cfg, re.M)

    if len(active) == 1:
        mode = active[0]
        f.add("mode", True, "exactly one extruder mode active", f"MODE_{mode.upper()}.cfg")
    elif not active:
        mode = None
        f.add("mode", False, "no extruder mode active",
              f"{len(present)} include line(s) present, all commented",
              "Klipper starts with no [stepper_x] and no [extruder] - it will not run at all.")
    else:
        mode = active[0]
        f.add("mode", False, "more than one mode active", ", ".join(active),
              "Duplicate [stepper_x]/[extruder] sections; the later include silently wins.")

    # The CAN toolhead is referenced by filament mode only.
    mcu_block = re.search(r"^\s*(#?)\s*\[mcu E1\]", cfg, re.M)
    if mcu_block:
        e1_active = mcu_block.group(1) != "#"
        if mode == "filament":
            f.add("mode", e1_active, "[mcu E1] uncommented for filament mode",
                  "active" if e1_active else "commented out",
                  "Filament mode drives the TD-01 over CAN; commented out, Klipper cannot find the extruder.")
        elif mode == "pellet":
            f.add("mode", not e1_active, "[mcu E1] commented out for pellet mode",
                  "commented" if not e1_active else "ACTIVE",
                  "Klipper errors on an MCU that no config section references.")
    else:
        f.add("mode", None, "[mcu E1] block present", "not found in printer.cfg")

    return mode


def check_calibration(client, f: Findings, mode: str | None) -> None:
    """SAVE_CONFIG contents and the per-mode calibration store."""
    cfg = ssh_read_file(client, setting("PENROSE_PRINTER_CFG"))
    if cfg is None:
        return

    marker = "#*# <---------------------- SAVE_CONFIG"
    if marker not in cfg:
        f.add("calibration", False, "SAVE_CONFIG block present", "missing",
              "Klipper refuses to start without [probe] z_offset, which lives here.")
        return
    tail = cfg[cfg.index(marker):]
    f.add("calibration", True, "SAVE_CONFIG block present")

    sections = re.findall(r"^#\*#\s*\[([^\]]+)\]", tail, re.M)
    f.add("calibration", "probe" in sections, "[probe] z_offset saved",
          ", ".join(sections) or "none",
          "Without it Klipper will not start: \"Option 'z_offset' in section 'probe' must be specified\".")

    # A plugin older than the fix welded the block header onto the first
    # section - '#*##*# [probe]' - which cost the machine its per-mode
    # calibration on the NEXT switch and left duplicate sections behind.
    welded = "#*##*#" in tail or "#*# #*#" in tail
    f.add("calibration", not welded, "SAVE_CONFIG block is well formed",
          "MANGLED - welded '#*##*#' seam found" if welded else "clean",
          "Caused by a compose bug in older plugin builds. Update the plugin and switch modes "
          "once: the parser now strips repeated prefixes and heals the block. Until then every "
          "switch silently drops the extruder PID.")

    dupes = sorted({x for x in sections if sections.count(x) > 1})
    f.add("calibration", not dupes, "no duplicated SAVE_CONFIG sections",
          ", ".join(dupes) if dupes else "none",
          "Two sections with the same name stop Klipper starting. Same cause and same fix as above.")

    has_mesh = any(s.startswith("bed_mesh") for s in sections)
    f.add("calibration", has_mesh, "bed mesh profile saved",
          "present" if has_mesh else "none",
          "The mesh is probed in pellet mode and SHARED with filament mode. Without it, level in pellet mode.")

    # Per-mode store written by the plugin on each switch
    state_dir = setting("PENROSE_MODE_STATE_DIR")
    code, out, _ = ssh_run(client, f"ls -1 {state_dir} 2>/dev/null")
    files = [x.strip() for x in out.splitlines() if x.strip()] if code == 0 else []
    if not files:
        f.add("calibration", None, "per-mode calibration store", f"{state_dir} empty or absent",
              "Populated on the first mode switch. Empty is normal before one has happened.")
    else:
        f.add("calibration", True, "per-mode calibration store", ", ".join(files))
        for m in MODES:
            want = f"saveconfig_{m}.cfg"
            if m == mode and want not in files:
                f.add("calibration", None, f"stored calibration for '{m}'", "not yet written",
                      "Written when you switch AWAY from this mode. Absent is normal until then.")


def check_heaters(client, f: Findings, mode: str | None) -> None:
    """Heater count and thermistor wiring must match the mode."""
    cfg_dir = "/home/pi"
    mode_file = f"{cfg_dir}/MODE_{mode.upper()}.cfg" if mode else None
    if not mode_file:
        return
    src = ssh_read_file(client, mode_file)
    if src is None:
        f.add("heaters", False, f"MODE_{mode.upper()}.cfg deployed", "not found on the machine",
              "printer.cfg includes it; Klipper will fail to start.")
        return
    f.add("heaters", True, f"MODE_{mode.upper()}.cfg deployed")

    has_h0 = bool(re.search(r"^\[heater_generic H0\]", src, re.M))
    if mode == "pellet":
        f.add("heaters", has_h0, "H0 barrel heater defined", "present" if has_h0 else "MISSING",
              "Pellet mode has TWO heaters: nozzle + H0 barrel.")
    else:
        f.add("heaters", not has_h0, "no H0 in filament mode",
              "correct" if not has_h0 else "H0 UNEXPECTEDLY PRESENT",
              "The filament head has no barrel heater.")

    # Thermistor: pellet heaters must not use a stock table
    sensors = re.findall(r"^sensor_type:\s*(.+)$", src, re.M)
    sensors = [s.split("#")[0].strip() for s in sensors]
    if mode == "pellet":
        stock = [s for s in sensors if "Semitec" in s or "EPCOS" in s]
        f.add("heaters", not stock, "pellet heaters use the custom thermistor",
              f"sensors: {', '.join(sensors)}",
              "A stock table UNDER-reads this sensor by ~61C at 250C and ~102C at 400C. "
              "Under-reading makes the PID drive the heater harder - overshoot on a 480C band heater.")
        core = ssh_read_file(client, f"{cfg_dir}/CORE_GCODE_MACROS.cfg") or ""
        defined = bool(re.search(r"^\[thermistor new_thermistor_t1\]", core, re.M))
        f.add("heaters", defined, "custom thermistor table defined",
              "in CORE_GCODE_MACROS.cfg" if defined else "NOT FOUND",
              "Heaters referencing an undefined sensor_type stop Klipper from starting.")
    else:
        f.add("heaters", None, "filament hotend sensor", f"{', '.join(sensors)}",
              "Should be stock EPCOS - same as every other Fracktal Works filament printer.")


def check_offsets(client, f: Findings, mode: str | None) -> None:
    """The filament head offset must exist and be applied."""
    var = ssh_read_file(client, setting("PENROSE_VARIABLES_CFG"))
    if var is None:
        f.add("offsets", None, "variables.cfg readable", "not found",
              "Holds tool_offset_x/y/z and babystep.")
        return
    vals = {}
    for key in ("tool_offset_x", "tool_offset_y", "tool_offset_z", "babystep_z"):
        m = re.search(rf"^{key}\s*=\s*(.+)$", var, re.M)
        if m:
            vals[key] = m.group(1).strip().strip("'\"")
    f.add("offsets", bool(vals), "head offsets stored", ", ".join(f"{k}={v}" for k, v in vals.items()) or "none")

    if mode == "filament":
        nonzero = any(abs(float(vals.get(k, 0) or 0)) > 1e-9
                      for k in ("tool_offset_x", "tool_offset_y", "tool_offset_z"))
        f.add("offsets", nonzero or None, "filament head offset is non-zero",
              "set" if nonzero else "all zero",
              "All-zero is only right if the two heads are mounted identically. Otherwise every "
              "filament print lands shifted. Set with SET_HEAD_OFFSET.")

    check_z_zero(client, f, mode, vals, var)


def check_z_zero(client, f: Findings, mode: str | None, vals: dict, var: str) -> None:
    """The per-head Z zero - the "filament prints too high" failure.

    Only the pellet nozzle triggers the bed probe, and the two nozzle tips do
    not hang the same distance below the gantry, so each head keeps its OWN
    [probe] z_offset in /home/pi/.penrose/saveconfig_<mode>.cfg. Shared
    across modes: the Z endstop (a gantry property) and the bed mesh (bed
    shape, pellet-probed).

    Two things go wrong here:
      - the head has never been zeroed and still carries the seeded default
      - z_offset is per mode but _APPLY_HEAD_OFFSET still adds tool_offset_z,
        so an IDEX-migrated machine is corrected twice
    """
    cfg = ssh_read_file(client, setting("PENROSE_PRINTER_CFG")) or ""
    m = re.search(r"^#\*#\s*z_offset\s*=\s*(-?[\d.]+)", cfg, re.M)
    probe_z = float(m.group(1)) if m else None
    tool_z = float(vals.get("tool_offset_z", 0) or 0)

    if probe_z is None:
        f.add("z-zero", None, "active mode Z zero", "no probe z_offset to read")
    else:
        f.add("z-zero", True, f"Z zero for the active ({mode or '?'}) head",
              f"probe z_offset {probe_z}")

    # Is the split actually per-mode on this machine, or an older plugin?
    state_dir = setting("PENROSE_MODE_STATE_DIR")
    code, out, _ = ssh_run(client, f"grep -l '\\[probe\\]' {state_dir}/*.cfg 2>/dev/null")
    stored = [x.strip().rsplit("/", 1)[-1] for x in out.splitlines() if x.strip()] if code == 0 else []
    per_mode_files = [x for x in stored if "shared" not in x]
    shared_files = [x for x in stored if "shared" in x]
    if stored:
        f.add("z-zero", not shared_files, "[probe] is stored per mode, not shared",
              ", ".join(stored),
              "z_offset in the SHARED file means both heads fight over one Z zero: tuning the "
              "filament first layer shifts pellet mode with it. Update the plugin - [probe] "
              "belongs in PER_MODE_SAVE_CONFIG_PREFIXES.")
        if mode:
            other = "filament" if mode == "pellet" else "pellet"
            have_other = any(other in x for x in per_mode_files)
            f.add("z-zero", have_other or None, f"'{other}' head has a stored Z zero",
                  "yes" if have_other else "not yet",
                  f"Written when you switch away from {other} mode. Until then that head falls "
                  "back to the seeded default and will print at the wrong height.")
    else:
        f.add("z-zero", None, "per-mode Z zero store", f"nothing in {state_dir}",
              "Populated on the first mode switch. Empty is normal before one has happened.")

    # Double correction: per-mode z_offset AND a head Z offset on top.
    base = ssh_read_file(client, "/home/pi/BASE_PENROSE_HYBRID.cfg") or ""
    # Look inside the macro DEFINITION, not at whatever follows the last
    # mention of the name. _APPLY_HEAD_OFFSET is also *called* from
    # homing_override and elsewhere, so splitting on the last occurrence
    # lands past the end of the file and finds nothing - which reported
    # "stored but not applied" on a machine that was applying it (.176,
    # BASE v6, filament Z corrected twice by 0.4mm).
    body = ""
    m = re.search(r"^\[gcode_macro _APPLY_HEAD_OFFSET\]\s*$", base, re.M)
    if m:
        rest = base[m.end():]
        nxt = re.search(r"^\[", rest, re.M)
        body = rest[:nxt.start()] if nxt else rest
    applies_tool_z = bool(re.search(r"SET_GCODE_OFFSET[^\n]*tool_offset_z", body))
    if abs(tool_z) > 1e-9:
        f.add("z-zero", not applies_tool_z, "no double Z correction",
              f"tool_offset_z = {tool_z}" + (" AND still applied" if applies_tool_z else " stored but not applied"),
              "With [probe] per mode, Z is entirely the active mode's z_offset. Applying "
              "tool_offset_z in _APPLY_HEAD_OFFSET as well corrects an IDEX-migrated machine "
              "twice. Update BASE_PENROSE_HYBRID.cfg (v7+).")

    # The touchscreen Z +/- buttons send M290.
    core = ssh_read_file(client, "/home/pi/CORE_GCODE_MACROS.cfg") or ""
    # Bound the macro by the next section header, not a fixed slice. A
    # 2500-char window silently truncated M290 once it grew (the debounce
    # line sits 3294 chars in on v5) and reported the debounce as MISSING
    # on a machine that had it.
    _m290_rest = core.split("[gcode_macro M290]")[-1]
    _m290_next = re.search(r"^\[", _m290_rest, re.M)
    m290 = _m290_rest[:_m290_next.start()] if _m290_next else _m290_rest
    debounced = "UPDATE_DELAYED_GCODE ID=_SAVE_Z_OFFSET" in m290
    pellet_only = "is_pellet" in m290
    f.add("z-zero", debounced, "M290 debounces its SAVE_CONFIG",
          "yes" if debounced else "NO - writes printer.cfg on every press",
          "Each press rewrote the whole of printer.cfg; 318 of them were recorded on .176. "
          "Update the firmware configs (CORE_GCODE_MACROS v4+).")
    if pellet_only and mode == "filament":
        f.add("z-zero", None, "Z +/- buttons work in filament mode", "disabled by an older M290 guard",
              "An intermediate build gated the probe fold to pellet mode, which stopped the "
              "contamination but left filament Z settable only via M851. With per-mode "
              "z_offset the fold is correct on either head.")



def check_carriage(client, f: Findings, mode: str | None) -> None:
    """The parked carriage must be homeable, not merely assumed."""
    if not mode:
        return
    src = ssh_read_file(client, f"/home/pi/MODE_{mode.upper()}.cfg")
    if src is None:
        return
    ms = re.search(r"\[manual_stepper parked_carriage\](.*?)(?=\n\[|\Z)", src, re.S)
    if not ms:
        f.add("carriage", False, "parked carriage declared", "no [manual_stepper parked_carriage]",
              "The idle carriage shares the X rail. Undeclared, its motor is never energised.")
        return
    body = ms.group(1)
    has_endstop = "endstop_pin" in body
    f.add("carriage", has_endstop, "parked carriage has its own endstop",
          "yes" if has_endstop else "NO - position is only assumed",
          "G28 homes the kinematic axes only; the parked carriage is invisible to it. "
          "Without an endstop, SET_POSITION merely DECLARES a position it never verified.")
    homer = bool(re.search(r"^\[gcode_macro _HOME_PARKED_CARRIAGE\]", src, re.M))
    f.add("carriage", homer, "_HOME_PARKED_CARRIAGE defined",
          "yes" if homer else "missing",
          "Run at boot and before every mode switch so both carriages are provably parked.")


def check_scripts(client, f: Findings, mode: str | None) -> None:
    """OctoPrint's generated gcode scripts must match the mode."""
    path = "/home/pi/.octoprint/scripts/gcode"
    for name in ("afterPrintDone", "beforePrintStarted"):
        body = ssh_read_file(client, f"{path}/{name}")
        if body is None:
            f.add("scripts", None, f"{name} present", "not found")
            continue
        if name == "afterPrintDone":
            has = "M104 H0 S0" in body
            if mode == "pellet":
                f.add("scripts", has, "cooldown switches off the H0 barrel",
                      "present" if has else "MISSING",
                      "Without it the barrel heater keeps running after every print.")
            else:
                f.add("scripts", not has, "cooldown omits H0 in filament mode",
                      "correct" if not has else "H0 line present",
                      "M104 H0 errors in filament mode - there is no barrel heater.")
        else:
            has_pellet_check = "PELLET_PREPRINT_CHECK" in body
            if mode == "pellet":
                f.add("scripts", has_pellet_check, "pre-print hopper check present")
            else:
                f.add("scripts", not has_pellet_check, "no pellet check in filament mode",
                      "correct" if not has_pellet_check else "present",
                      "PELLET_PREPRINT_CHECK does not exist in filament mode.")


def check_klipper(client, f: Findings, mode: str | None) -> None:
    """Is Klipper actually up, and does its log end clean?"""
    log = setting("PENROSE_KLIPPY_LOG")
    code, out, _ = ssh_run(client, f"test -f {log} && tail -n 400 {log}")
    if code != 0:
        f.add("klipper", None, "klippy.log readable", f"{log} not found",
              "Set PENROSE_KLIPPY_LOG if this install logs elsewhere.")
        return
    errors = [l for l in out.splitlines()
              if re.search(r"(Shutdown due to|Error |Unable to |must be specified|Timer too close|"
                           r"MCU .* shutdown|Lost communication|not heating at expected rate)", l)]
    f.add("klipper", not errors, "klippy.log tail is clean",
          f"{len(errors)} error line(s)" if errors else "no errors in last 400 lines",
          "Klipper's log is ground truth - read it before theorising.")
    for line in errors[-4:]:
        f.add("klipper", False, "log error", line.strip()[:150])


CHECKS = {
    "mode": None,  # always runs first; returns the mode
    "calibration": check_calibration,
    "heaters": check_heaters,
    "offsets": check_offsets,
    "carriage": check_carriage,
    "scripts": check_scripts,
    "klipper": check_klipper,
}


# ---------------------------------------------------------------------------

def render(payload):
    mode = payload["mode"]
    print("\n" + "=" * 66)
    print(f"  Penrose 600 Hybrid - configuration health")
    print(f"  active extruder mode: {(mode or 'NONE').upper()}")
    print("=" * 66)
    groups = {}
    for item in payload["findings"]:
        groups.setdefault(item["group"], []).append(item)
    for group, items in groups.items():
        rule(group.upper())
        for i in items:
            mark = "  ok  " if i["ok"] is True else (" FAIL " if i["ok"] is False else "  ??  ")
            print(f"  [{mark}] {i['label']}" + (f"  -  {i['detail']}" if i["detail"] else ""))
            if i["ok"] is not True and i["why"]:
                for line in _wrap(i["why"], 62):
                    print(f"           {line}")
    fails, unknown = payload["summary"]["failures"], payload["summary"]["unknowns"]
    print("\n" + "=" * 66)
    if fails:
        print(f"  {fails} FAILURE(S) - fix these before printing")
    elif unknown:
        print(f"  no failures, {unknown} item(s) could not be determined")
    else:
        print("  all checks passed")
    print("=" * 66 + "\n")


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Check the Penrose Hybrid config-swap invariants on a live machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--check", choices=["all"] + [k for k in CHECKS if k != "mode"],
                    default="all", help="run one group instead of all")
    add_connection_args(ap)
    args = ap.parse_args()

    f = Findings()
    client = ssh_client(args)
    try:
        mode = check_mode(client, f)
        for name, fn in CHECKS.items():
            if fn is None:
                continue
            if args.check in ("all", name):
                fn(client, f, mode)
    finally:
        client.close()

    payload = {
        "mode": mode,
        "findings": f.items,
        "summary": {"total": len(f.items), "failures": len(f.failures()),
                    "unknowns": len(f.unknowns())},
    }
    emit(payload, args.json, render)
    sys.exit(1 if f.failures() else 0)


if __name__ == "__main__":
    main()
