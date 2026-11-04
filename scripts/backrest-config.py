#!/usr/bin/env python3
"""Render private desired settings, then explicitly install while Backrest is stopped.

The root .env owns these managed repo/plan fields. UI auth and pairing survive
reconciliation. No repository is ever initialized and no retention is enabled.
"""

import argparse
import base64
from datetime import datetime, timezone
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bootstrap_config", ROOT / "scripts/bootstrap-config.py"
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
NODES = ("storage", "docker")


def settings(root, node):
    values = config.read_env(root / "stacks" / node / "backrest/.env.example")
    values.update(config.read_env(root / ".env"))
    address = ipaddress.ip_address(values["BACKREST_BIND_IP"])
    if (
        address.version != 4
        or not address.is_private
        or address.is_unspecified
        or address.is_multicast
    ):
        raise ValueError("BACKREST_BIND_IP must be a trusted LAN or loopback address")
    port = values.get("BACKREST_PORT", "9898")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("BACKREST_PORT must be a valid TCP port")
    ZoneInfo(values.get("TZ", "Europe/Amsterdam"))
    return values


def cron(value):
    fields = value.split()
    if len(fields) != 5:
        raise ValueError("Schedules must be five-field numeric cron expressions")
    for field, minimum, maximum in zip(fields, (0, 0, 1, 1, 0), (59, 23, 31, 12, 6)):
        for part in field.split(","):
            base, slash, step = part.partition("/")
            if slash and (not step.isdecimal() or not 1 <= int(step) <= maximum + 1):
                raise ValueError("Invalid cron step")
            if base == "*":
                continue
            bounds = base.split("-")
            if len(bounds) not in (1, 2) or not all(
                bound.isdecimal() for bound in bounds
            ):
                raise ValueError("Schedules must use numeric cron fields")
            numbers = [int(bound) for bound in bounds]
            if not all(
                minimum <= number <= maximum for number in numbers
            ) or numbers != sorted(numbers):
                raise ValueError("Cron field out of range")
    return {"cron": value, "clock": "CLOCK_LOCAL"}


def desired(root, node):
    env = settings(root, node)
    enabled = env.get("BACKREST_ENABLE_SCHEDULES", "false")
    if enabled not in ("true", "false"):
        raise ValueError("BACKREST_ENABLE_SCHEDULES must be true or false")
    schedule = cron(env["BACKREST_" + node.upper() + "_CRON"])
    check_schedule = cron(env["BACKREST_CHECK_CRON"])
    if enabled == "false":
        schedule = {"disabled": True}
        check_schedule = {"disabled": True}
    plan = {
        "id": "storage-data" if node == "storage" else "docker-appdata",
        "repo": "homelab",
        "paths": ["/sources/appdata", "/sources/checkout"],
        "excludes": [
            "/sources/appdata/backrest/data",
            "/sources/appdata/backrest/cache",
            "/sources/appdata/backrest/tmp",
            "/sources/appdata/backrest/restores",
            "/sources/appdata/backrest/ssh",
            "/sources/checkout/.git",
            "/sources/checkout/.bootstrap",
            "/sources/checkout/.deploy-state",
            "/sources/checkout/.backrest",
            "**/node_modules",
            "**/__pycache__",
            "**/.venv",
            "**/dist",
            "**/.cache",
            "**/*.partial",
            "**/.immich-db-*",
        ],
        "schedule": schedule,
        "retention": {"policyKeepAll": True},
        "backup_flags": ["--host " + node, "--tag homelab"],
    }
    if node == "storage":
        plan["paths"] += [
            "/sources/nas/Gallery",
            "/sources/nas/Files",
            "/sources/nas/Drive",
            "/sources/immich-exports",
        ]
        plan["excludes"] += ["/sources/appdata/immich/postgres"]
        plan["backup_flags"] += ["--tag media"]
        plan["hooks"] = [
            {
                "conditions": ["CONDITION_SNAPSHOT_START"],
                "onError": "ON_ERROR_FATAL",
                "actionCommand": {"command": "/bin/sh /hooks/immich-export.sh"},
            }
        ]
    else:
        plan["paths"] += ["/sources/volumes"]
    repo = {
        "id": "homelab",
        "uri": "/repo",
        "password": "",
        "env": ["RESTIC_PASSWORD=${RESTIC_PASSWORD}"],
        "flags": ["--retry-lock 30m"],
        "autoInitialize": False,
        "autoUnlock": False,
        "shared": False,
        "prunePolicy": {"schedule": {"disabled": True}},
        "forgetPolicy": {
            "schedule": {"disabled": True},
            "retention": {"policyKeepAll": True},
        },
        "checkPolicy": {
            "schedule": check_schedule if node == "storage" else {"disabled": True},
            "structureOnly": True,
        },
    }
    return {"instance": node, "repo": repo, "plan": plan}


def atomic_json(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(data, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def render(root, check=False):
    if not (root / ".env").is_file():
        raise ValueError("Configure the root .env first")
    for node in NODES:
        value = desired(root, node)
        path = root / ".backrest" / (node + ".json")
        if check:
            if not path.is_file() or json.loads(path.read_text()) != value:
                raise ValueError(
                    f"Backrest desired settings for {node} are stale; run make config"
                )
        else:
            atomic_json(path, value)
    print(
        "Backrest desired settings "
        + (
            "verified"
            if check
            else "rendered; install explicitly with sudo make backrest-config NODE=..."
        )
    )


def reconcile(existing, wanted, guid, env):
    if existing.get("instance", wanted["instance"]) != wanted["instance"]:
        raise ValueError("Refusing to change an existing Backrest instance identity")
    if existing.get("version", 6) != 6:
        raise ValueError(
            "Expected Backrest config schema 6; review migrations before editing"
        )
    result = json.loads(json.dumps(existing))
    result.update(
        version=6, instance=wanted["instance"], modno=existing.get("modno", 0) + 1
    )
    auth = result.get("auth")
    if not auth or auth.get("disabled") or not auth.get("users"):
        encoded = env.get("BACKREST_AUTH_BCRYPT", "")
        try:
            hashed = base64.b64decode(encoded, validate=True).decode("ascii")
        except (ValueError, UnicodeError) as error:
            raise ValueError(
                "Configure BACKREST_AUTH_BCRYPT: base64 of a bcrypt hash"
            ) from error
        if not re.fullmatch(r"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}", hashed):
            raise ValueError("Configure BACKREST_AUTH_BCRYPT: base64 of a bcrypt hash")
        result["auth"] = {
            "disabled": False,
            "users": [{"name": "admin", "passwordBcrypt": encoded}],
        }
    repo = dict(wanted["repo"], guid=guid)
    repos = result.setdefault("repos", [])
    if any(r.get("guid") == guid and r["id"] != repo["id"] for r in repos):
        raise ValueError(
            "Repository GUID already imported under another ID; review before adding homelab"
        )
    previous = next((r for r in repos if r["id"] == repo["id"]), None)
    if previous and previous.get("guid") != guid:
        raise ValueError(
            "Existing homelab repository GUID differs; refusing to replace it"
        )
    if previous and previous.get("originInstanceId"):
        raise ValueError(
            "This setup uses local repo configs; resolve shared-repo ownership first"
        )
    repos[:] = [r for r in repos if r["id"] != repo["id"]] + [repo]
    plans = result.setdefault("plans", [])
    plans[:] = [p for p in plans if p["id"] != wanted["plan"]["id"]] + [wanted["plan"]]
    return result


def verify(root, node):
    env = settings(root, node)
    path = Path(env["DOCKER_DATA"]) / "backrest/config/config.json"
    try:
        installed = json.loads(path.read_text())
    except PermissionError:
        # The production container runs as root to read all source data. Its
        # atomically saved config is root-private; capture it without printing.
        raw = subprocess.check_output(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "cat",
                "backrest",
                "/config/config.json",
            ],
            cwd=root / "stacks" / node / "backrest",
            text=True,
        )
        installed = json.loads(raw)
    auth = installed.get("auth", {})
    if (
        installed.get("instance") != node
        or auth.get("disabled")
        or not auth.get("users")
    ):
        raise ValueError(
            "Backrest must have the correct instance identity and authentication enabled"
        )
    repo = next((r for r in installed.get("repos", []) if r["id"] == "homelab"), {})
    if (
        repo.get("autoInitialize")
        or repo.get("autoUnlock")
        or not re.fullmatch("[0-9a-f]{64}", repo.get("guid", ""))
    ):
        raise ValueError(
            "Import the existing repository with auto-initialize/unlock disabled first"
        )
    if repo.get("uri") != "/repo":
        raise ValueError("Expected the existing repository mount /repo")
    print(
        f"Backrest {node} identity, authentication and existing-repository configuration verified"
    )


def install(root, node):
    if node not in NODES:
        raise ValueError("Select storage or docker")
    running = subprocess.check_output(
        ["docker", "ps", "--format", "{{.Names}}"], text=True
    ).splitlines()
    if set(running) & {"backrest", "restic", "restic-media", "restic-check"}:
        raise ValueError(
            "Stop Backrest and legacy Restic jobs manually before installing config; see docs/migration.md"
        )
    env = settings(root, node)
    if not config.usable(env.get("RESTIC_PASSWORD", "")):
        raise ValueError("Preserve the existing RESTIC_PASSWORD in the root .env")
    state = Path(env["DOCKER_DATA"]) / "backrest"
    if not state.is_absolute():
        raise ValueError("DOCKER_DATA must be absolute")
    path = state / "config/config.json"
    existing = json.loads(path.read_text()) if path.exists() else {}
    # Read-only import of an existing repository; never run init or create a repo.
    raw = subprocess.check_output(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "restic",
            "backrest",
            "cat",
            "config",
        ],
        cwd=root / "stacks" / node / "backrest",
        text=True,
    )
    guid = json.loads(raw).get("id", "")
    if not re.fullmatch("[0-9a-f]{64}", guid):
        raise ValueError("Cannot verify the existing repository GUID")
    result = reconcile(existing, desired(root, node), guid, env)
    for folder in ("config", "data", "cache", "tmp", "restores", "ssh"):
        (state / folder).mkdir(mode=0o700, parents=True, exist_ok=True)
    if existing:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        atomic_json(state / "config" / ("config.before-" + stamp + ".json"), existing)
    atomic_json(path, result)
    print(
        f"Imported existing repository and reconciled {node} plan; auth and pairing preserved. Backrest remains stopped."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("render", "check", "install", "verify"))
    parser.add_argument("node", nargs="?", choices=NODES)
    args = parser.parse_args()
    try:
        if args.action == "verify":
            verify(ROOT, args.node)
        elif args.action == "install":
            install(ROOT, args.node)
        else:
            render(ROOT, check=args.action == "check")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Backrest configuration refused: {error}\n")
