# PenroseControlCenter

OctoPrint plugin providing the touchscreen UI for Fracktal Works **Penrose**
pellet 3D printers, plus the Klipper firmware configs those machines run.

## Layout

| Path | What it is |
|---|---|
| `octoprint_PenroseControlCenter/` | the plugin (PyQt5 touchscreen UI + OctoPrint integration) |
| `octoprint_PenroseControlCenter/firmware/` | **the Klipper configs shipped to machines** |
| `octoprint_PenroseControlCenter/utils/printer_config_manager.py` | deploys firmware configs, rewrites `printer.cfg`, regenerates OctoPrint configs |
| `octoprint_PenroseControlCenter/ui/` | one folder per screen (`.ui` + controller `.py`) |
| `Documentation/` | system references and commissioning guides |
| `.claude/skills/penrose-printer/` | tools to connect to and debug a live machine |

## Branch model — read this before pushing

Machine variants ship on **their own branches**, and the plugin's software
updater in `__init__.py` is pinned to the branch it lives on:

```python
type="github_commit", branch="Hybrid-IDEX-Penrose-600", ...
```

Merging a variant branch into `production` **carries that pin with it**,
which would make every production machine auto-update onto the variant
branch. Never merge a variant into `production` without first reverting the
updater pin, and confirm with the user before any such merge.

`production` is the main branch and uses release-gated updates for the
general fleet.

## Firmware configs

Machines pull config updates through the in-app prompt, which is gated
**solely** on `firmware/printer.cfg`'s `# Version:` line. Change any config
file and bump that, or machines in the field will never be offered it.

Note the blast radius: `CORE_GCODE_MACROS.cfg` and the `BASE_PENROSE_*.cfg`
files are shared across SKUs, so a change there reaches every machine on the
branch — not just the variant being worked on.

Deployment rewrites `printer.cfg` from the template and preserves only the
`[mcu]` block and the `SAVE_CONFIG` tail. **Anything hand-added to a
deployed `printer.cfg` is destroyed on the next update.**

## The Penrose 600 Hybrid

Two carriages on one X rail — pellet auger left, TD-01 CAN filament head
right — but Klipper is configured as a **single-extruder printer**. The
active head is whichever `MODE_*.cfg` `printer.cfg` includes; switching
rewrites that include and restarts Klipper.

Start with `Documentation/HYBRID_IDEX_PENROSE_600.md`. Design rationale is
in `Documentation/DESIGN_HYBRID_IDEX_CONFIG_SWAP.md`; commissioning steps in
`Documentation/MIGRATION_PENROSE_600_HYBRID.md`.

## Working on a live machine

Use the `penrose-printer` skill — it holds the routing table and the
machine's failure modes. Copy `.env.example` to `.env` first.

Read actions are free. Anything that **moves the machine, heats it, or
writes to it** requires `--i-understand` and the user's explicit go-ahead.
Check `printer_api.py --action status` before any motion or heater command.

klippy.log is ground truth — `klippy_log.py` before theorising, and quote
the real line rather than paraphrasing it.

## Conventions

- Firmware `.cfg` comments explain **why**, especially where a value is
  load-bearing (pin conflicts, held-low outputs, heaters that error by
  design). Preserve that when editing.
- UI element visibility is data-driven in `utils/printer_ui_config.py`, not
  scattered through screen classes.
- Python is 2/3-era OctoPrint style with broad `try/except` around hardware
  calls; match the surrounding code rather than modernising it.
