"""Shared connection helpers for the Penrose printer tools.

Resolves connection settings once, in a documented precedence order, and
hands back ready-to-use HTTP / SSH clients. Every other script in this
folder imports from here so there is a single place that knows how to
reach a machine.

Precedence (first hit wins):
    1. an explicit CLI flag       --host / --api-key / ...
    2. a process environment var  PENROSE_HOST=...
    3. the repo's .env file       PENROSE_HOST=...
    4. a built-in default         (only where a sane one exists)

Nothing here mutates the printer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / ".env"

DEFAULTS = {
    "PENROSE_PORT": "5000",
    "PENROSE_SSH_USER": "pi",
    "PENROSE_SSH_PORT": "22",
    # Paths on the machine. Overridable because installs vary.
    "PENROSE_PRINTER_CFG": "/home/pi/printer.cfg",
    "PENROSE_VARIABLES_CFG": "/home/pi/.octoprint/data/klipper/variables.cfg",
    "PENROSE_KLIPPY_LOG": "/tmp/klippy.log",
    "PENROSE_OCTOPRINT_LOG": "/home/pi/.octoprint/logs/octoprint.log",
    "PENROSE_MODE_STATE_DIR": "/home/pi/.penrose",
}


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

_env_cache: Optional[Dict[str, str]] = None


def _load_env_file() -> Dict[str, str]:
    """Parse the repo .env file. Absent file is fine - returns {}."""
    global _env_cache
    if _env_cache is not None:
        return _env_cache
    values: Dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip("'\"")
    _env_cache = values
    return values


def setting(name: str, cli_value: Optional[str] = None) -> Optional[str]:
    """Resolve one setting through the documented precedence order."""
    if cli_value:
        return cli_value
    if os.environ.get(name):
        return os.environ[name]
    from_file = _load_env_file().get(name)
    if from_file:
        return from_file
    return DEFAULTS.get(name)


def require(name: str, cli_value: Optional[str] = None) -> str:
    """Resolve a setting, or exit with a message that says how to set it."""
    value = setting(name, cli_value)
    if not value:
        die(
            f"{name} is not set.\n"
            f"  Set it one of three ways:\n"
            f"    - pass the matching --flag\n"
            f"    - export {name}=...\n"
            f"    - add {name}=... to {ENV_FILE}\n"
            f"  Copy .env.example to .env to get started."
        )
    return value


def add_connection_args(parser: argparse.ArgumentParser) -> None:
    """Attach the standard connection flags to any script's parser."""
    g = parser.add_argument_group("connection")
    g.add_argument("--host", help="Printer IP or hostname (PENROSE_HOST)")
    g.add_argument("--port", help="OctoPrint port (PENROSE_PORT, default 5000)")
    g.add_argument("--api-key", help="OctoPrint API key (PENROSE_API_KEY)")
    g.add_argument("--ssh-user", help="SSH user (PENROSE_SSH_USER, default pi)")
    g.add_argument("--ssh-key", help="SSH private key path (PENROSE_SSH_KEY)")
    g.add_argument("--ssh-password", help="SSH password (PENROSE_SSH_PASSWORD)")
    g.add_argument("--json", action="store_true", help="Emit JSON instead of text")


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def die(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def emit(payload: Any, as_json: bool, text_renderer=None) -> None:
    """Print either JSON or a human rendering of the same payload."""
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    elif text_renderer:
        text_renderer(payload)
    else:
        print(json.dumps(payload, indent=2, default=str))


def rule(title: str) -> None:
    print(f"\n{title}\n{'-' * max(len(title), 8)}")


def status_line(ok: Optional[bool], label: str, detail: str = "") -> str:
    """ok True/False/None -> pass / FAIL / unknown."""
    mark = "  ok  " if ok is True else (" FAIL " if ok is False else "  ??  ")
    return f"[{mark}] {label}" + (f"  {detail}" if detail else "")


# ---------------------------------------------------------------------------
# HTTP (OctoPrint REST)
# ---------------------------------------------------------------------------

def http_session(args) -> "tuple[Any, str, dict]":
    """Return (requests_module, base_url, headers) for the OctoPrint API."""
    try:
        import requests  # noqa: F401
    except ImportError:
        die("the 'requests' package is required.  pip install requests")
    import requests

    host = require("PENROSE_HOST", getattr(args, "host", None))
    port = setting("PENROSE_PORT", getattr(args, "port", None))
    key = require("PENROSE_API_KEY", getattr(args, "api_key", None))
    base = f"http://{host}:{port}"
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    return requests, base, headers


def api_get(args, path: str, timeout: int = 15) -> Any:
    requests, base, headers = http_session(args)
    url = f"{base}{path}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        die(f"cannot reach OctoPrint at {base} ({e}).\n"
            f"  Check the printer is powered on and PENROSE_HOST is right.")
    if r.status_code == 403:
        die("OctoPrint rejected the API key (403). Check PENROSE_API_KEY.")
    if r.status_code == 404:
        return None
    if not r.ok:
        die(f"GET {path} failed: {r.status_code} {r.text[:200]}")
    if not r.text.strip():
        return None
    try:
        return r.json()
    except ValueError:
        return r.text


def api_post(args, path: str, payload: dict, timeout: int = 30) -> Any:
    requests, base, headers = http_session(args)
    url = f"{base}{path}"
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    except Exception as e:  # noqa: BLE001
        die(f"cannot reach OctoPrint at {base} ({e})")
    if r.status_code == 403:
        die("OctoPrint rejected the API key (403). Check PENROSE_API_KEY.")
    if not r.ok:
        die(f"POST {path} failed: {r.status_code} {r.text[:300]}")
    return r.json() if r.text.strip() else {"ok": True}


# ---------------------------------------------------------------------------
# SSH
# ---------------------------------------------------------------------------

def ssh_client(args):
    """Open an SSH connection to the printer. Caller must close it."""
    try:
        import paramiko  # noqa: F401
    except ImportError:
        die("the 'paramiko' package is required for SSH.  pip install paramiko")
    import paramiko

    host = require("PENROSE_SSH_HOST", getattr(args, "host", None)) \
        if setting("PENROSE_SSH_HOST") else require("PENROSE_HOST", getattr(args, "host", None))
    user = setting("PENROSE_SSH_USER", getattr(args, "ssh_user", None))
    port = int(setting("PENROSE_SSH_PORT") or 22)
    key = setting("PENROSE_SSH_KEY", getattr(args, "ssh_key", None))
    password = setting("PENROSE_SSH_PASSWORD", getattr(args, "ssh_password", None))

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: Dict[str, Any] = {"hostname": host, "username": user, "port": port, "timeout": 15}
    if key:
        kwargs["key_filename"] = os.path.expanduser(key)
    elif password:
        kwargs["password"] = password
    else:
        die("no SSH credential. Set PENROSE_SSH_KEY (preferred) or PENROSE_SSH_PASSWORD.")
    try:
        client.connect(**kwargs)
    except Exception as e:  # noqa: BLE001
        die(f"SSH to {user}@{host}:{port} failed ({e})")
    return client


def ssh_run(client, command: str, timeout: int = 30) -> "tuple[int, str, str]":
    """Run one command. Returns (exit_status, stdout, stderr)."""
    _in, out, err = client.exec_command(command, timeout=timeout)
    stdout = out.read().decode("utf-8", errors="replace")
    stderr = err.read().decode("utf-8", errors="replace")
    return out.channel.recv_exit_status(), stdout, stderr


def ssh_read_file(client, path: str, max_bytes: int = 400_000) -> Optional[str]:
    """Read a remote file, or None if it does not exist."""
    code, out, _ = ssh_run(client, f"test -f {path} && head -c {max_bytes} {path}")
    return out if code == 0 else None
