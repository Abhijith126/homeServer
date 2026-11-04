#!/usr/bin/env python3
"""Forced SSH command: produce a verified Immich export, never accept arguments."""

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    if len(sys.argv) != 1:
        sys.exit("No arguments accepted by the forced export command")
    settings = load("bootstrap-config").read_env(ROOT / ".env")
    destination = Path(settings.get("IMMICH_EXPORT_DIR", "/mnt/hdd2/immich"))
    if not destination.is_absolute():
        sys.exit("IMMICH_EXPORT_DIR must be absolute")
    # No SSH_ORIGINAL_COMMAND evaluation. The caller can only request this export.
    load("immich-backup").backup(
        ROOT / "stacks/storage/immich", destination=destination
    )
