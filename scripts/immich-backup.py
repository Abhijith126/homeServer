#!/usr/bin/env python3
"""Create an atomic Immich database archive before changing containers."""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def backup(stack, pre_update=False, destination=None):
    import os
    os.umask(0o077)
    def compose(*args):
        return subprocess.check_output(["docker", "compose", *args], cwd=stack, text=True)

    config = json.loads(compose("config", "--format", "json"))["services"]
    running = compose("ps", "--status", "running", "--quiet", "database").strip()
    if not running:
        volumes = config["database"].get("volumes", [])
        data = next((Path(v["source"]) for v in volumes
                     if v.get("type") == "bind" and v.get("target") == "/var/lib/postgresql/data"), None)
        existing = compose("ps", "--all", "--quiet", "database").strip()
        if pre_update and not existing and data is not None and (not data.exists() or not any(data.iterdir())):
            print("Immich: first deployment; no database to back up.")
            return
        raise RuntimeError("Immich database is not running; start/recover it before updating.")
    env = config["immich-server"]["environment"]
    destination = Path(destination) if destination is not None else Path(env["NFS_BACKUP"]) / "immich"
    destination.mkdir(parents=True, exist_ok=True)
    username = config["database"]["environment"]["POSTGRES_USER"]
    archive = destination / ("immich-db-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".sql.gz")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination, prefix=".immich-db-", delete=False) as output:
            temporary = Path(output.name)
            with subprocess.Popen(["docker", "compose", "exec", "-T", "database", "pg_dumpall",
                                   "--clean", "--if-exists", "--username=" + username],
                                  cwd=stack, stdout=subprocess.PIPE) as process:
                with gzip.GzipFile(fileobj=output, mode="wb") as compressed:
                    shutil.copyfileobj(process.stdout, compressed)
                if process.wait() != 0:
                    raise RuntimeError("Immich database dump failed; update cancelled.")
        # Read the complete stream to verify its gzip checksum and SQL content.
        with gzip.open(temporary, 'rb') as verification:
            prefix = verification.read(4096)
            if b'PostgreSQL' not in prefix or b'dump' not in prefix.lower():
                raise RuntimeError("Database export is not a PostgreSQL SQL dump")
            while verification.read(1024 * 1024):
                pass
        temporary.replace(archive)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Immich database backup: {archive}")
    print("Photo files are not included; keep a separate backup of the library.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stack", type=Path)
    parser.add_argument("--pre-update", action="store_true")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    try:
        backup(args.stack.resolve(), args.pre_update, args.destination)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Immich backup refused: {error}\n")
