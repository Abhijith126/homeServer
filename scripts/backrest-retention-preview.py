#!/usr/bin/env python3
"""Preview scoped 7/4/6 retention on Ryzen; never delete or prune."""

import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bootstrap_config", ROOT / "scripts/bootstrap-config.py"
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def commands(settings):
    counts = [
        settings.get("BACKREST_KEEP_" + key, default)
        for key, default in [("DAILY", "7"), ("WEEKLY", "4"), ("MONTHLY", "6")]
    ]
    if not all(str(count).isdecimal() and int(count) > 0 for count in counts):
        raise ValueError("Retention counts must be positive integers")
    result = []
    for node, plan in [("storage", "storage-data"), ("docker", "docker-appdata")]:
        result.append(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "backrest",
                "restic",
                "forget",
                "--dry-run",
                "--json",
                "--host",
                node,
                "--tag",
                f"created-by:{node},plan:{plan}",
                "--group-by",
                "host,tags,paths",
                "--keep-daily",
                str(counts[0]),
                "--keep-weekly",
                str(counts[1]),
                "--keep-monthly",
                str(counts[2]),
            ]
        )
    return result


if __name__ == "__main__":
    # Must run on the owner. The Compose directory selects the storage service;
    # no deletion flag is accepted by this script.
    for command in commands(config.read_env(ROOT / ".env")):
        subprocess.run(command, cwd=ROOT / "stacks/storage/backrest", check=True)
