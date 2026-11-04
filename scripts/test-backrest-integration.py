"""Disposable local integration: auth, pairing, backup, history sync and restore."""

import base64
import gzip
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

R = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cfg", R / "scripts/backrest-config.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
D = ["docker", "--host=unix:///var/run/docker.sock"]
I = next(
    line.split("image:", 1)[1].strip()
    for line in (R / "stacks/storage/backrest/compose.yaml").read_text().splitlines()
    if "image:" in line
)
root = Path(tempfile.mkdtemp(prefix="backrest-functional-", dir="/tmp"))
ident = uuid.uuid4().hex[:8]
net = "backrest-test-" + ident
names = {n: "backrest-test-" + n + "-" + ident for n in ("storage", "docker")}
created = []
# Read only committed templates, never the caller's private root .env.
fixture_config = root / "configuration"
for node in ("storage", "docker"):
    target = fixture_config / "stacks" / node / "backrest"
    target.mkdir(parents=True)
    shutil.copyfile(
        R / "stacks" / node / "backrest/.env.example", target / ".env.example"
    )


class TestCommandError(RuntimeError):
    def __init__(self, result):
        # Never echo arguments: authenticated API commands carry test JWTs.
        super().__init__(
            f"Isolated Docker test command failed with exit {result.returncode}"
        )
        self.output = result.stdout


def run(*a, **kw):
    result = subprocess.run(D + list(a), capture_output=True, text=True, **kw)
    if result.returncode:
        raise TestCommandError(result)
    return result.stdout


for folder in (
    "repo",
    "appdata",
    "checkout",
    "volumes",
    "nas/Gallery",
    "nas/Files",
    "nas/Drive",
    "exports",
    "hooks",
    "restored",
):
    (root / folder).mkdir(parents=True, exist_ok=True)
(root / "appdata/config.txt").write_text("recover-this-config")
(root / "hooks/fail").touch()
(root / "hooks/immich-export.sh").write_text(
    '#!/bin/sh\nset -e\n[ ! -f /fixture/fail ]\nprintf -- "-- PostgreSQL database cluster dump\\nSELECT 1;\\n" | gzip > /fixture/exports/current.sql.gz\n'
)
# Fixture-only mount lets a test hook simulate the validated host-side exporter.
(root / "hooks/exports").mkdir()


def restic(*args):
    return run(
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "XDG_CACHE_HOME=/tmp/cache",
        "-v",
        f"{root}/repo:/repo",
        "-v",
        f"{root}/appdata:/sources/appdata:ro",
        "-v",
        f"{root}/restored:/restore",
        "-e",
        "RESTIC_PASSWORD=test-only",
        "--entrypoint",
        "restic",
        I,
        "-r",
        "/repo",
        *args,
    )


def start(node):
    s = root / node
    name = names[node]
    (s / "state").mkdir(exist_ok=True)
    run(
        "run",
        "-d",
        "--name",
        name,
        "--network",
        net,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "XDG_CACHE_HOME=/tmp/cache",
        "-v",
        f"{s}/config:/config",
        "-v",
        f"{s}/state:/state",
        "-v",
        f"{root}/repo:/repo",
        "-v",
        f"{root}/appdata:/sources/appdata:ro",
        "-v",
        f"{root}/checkout:/sources/checkout:ro",
        "-v",
        f"{root}/volumes:/sources/volumes:ro",
        "-v",
        f"{root}/nas:/sources/nas:ro",
        "-v",
        f"{root}/hooks/exports:/sources/immich-exports:ro",
        "-v",
        f"{root}/hooks:/fixture",
        "-v",
        f"{root}/hooks/immich-export.sh:/hooks/immich-export.sh:ro",
        "-e",
        "BACKREST_DATA=/state",
        "-e",
        "BACKREST_CONFIG=/config/config.json",
        "-e",
        "BACKREST_RESTIC_COMMAND=/bin/restic",
        "-e",
        "RESTIC_PASSWORD=test-only",
        "-e",
        "TZ=Europe/Amsterdam",
        I,
    )
    created.append(name)
    for attempt in range(40):
        try:
            run("exec", name, "curl", "-fsS", "http://127.0.0.1:9898/")
            return
        except TestCommandError:
            time.sleep(0.25)
    raise RuntimeError("Backrest did not become ready: " + node)


def api(node, path, data, token=None):
    args = [
        "exec",
        names[node],
        "curl",
        "--fail-with-body",
        "-sS",
        "-X",
        "POST",
        "-H",
        "Content-Type: application/json",
    ]
    if token:
        args += ["-H", "Authorization: Bearer " + token]
    return json.loads(
        run(*args, "-d", json.dumps(data), "http://127.0.0.1:9898/" + path) or "{}"
    )


def stop(node):
    run("rm", "-f", names[node])
    created.remove(names[node])


def snapshots():
    return json.loads(restic("snapshots", "--json")) or []


def await_snapshot(node):
    for attempt in range(100):
        matches = [
            s
            for s in snapshots()
            if "plan:" + ("storage-data" if node == "storage" else "docker-appdata")
            in s.get("tags", [])
        ]
        if matches:
            return matches[-1]
        time.sleep(0.25)
    raise RuntimeError("Backup did not produce snapshot: " + node)


try:
    run("pull", I)
    restic("init")
    guid = json.loads(restic("cat", "config"))["id"]
    for host in ("apps", "infra", "storage", "docker"):
        restic("backup", "--host", host, "--tag", "homelab", "/sources/appdata")
    historical = {s["id"] for s in snapshots()}
    run("network", "create", "--internal", net)
    for node in names:
        (root / node / "config").mkdir(parents=True)
        seed = m.reconcile(
            {},
            m.desired(fixture_config, node),
            guid,
            {
                "BACKREST_AUTH_BCRYPT": base64.b64encode(
                    ("$2b$12$" + "a" * 53).encode()
                ).decode()
            },
        )
        (root / node / "config/config.json").write_text(json.dumps(seed))
        start(node)
        hashed = api(
            node, "v1.Authentication/HashPassword", {"value": "disposable-password"}
        )["value"]
        stop(node)
        cfg = json.loads((root / node / "config/config.json").read_text())
        cfg["auth"]["users"][0]["passwordBcrypt"] = hashed
        (root / node / "config/config.json").write_text(json.dumps(cfg))
        start(node)
    tokens = {
        n: api(
            n,
            "v1.Authentication/Login",
            {"username": "admin", "password": "disposable-password"},
        )["token"]
        for n in names
    }
    pair = api(
        "storage",
        "v1.Backrest/GeneratePairingToken",
        {
            "label": "disposable",
            "ttlSeconds": "900",
            "maxUses": 1,
            "permissions": [{"type": "PERMISSION_READ_OPERATIONS", "scopes": ["*"]}],
        },
        tokens["storage"],
    )["token"]
    keysecret, instance = pair.rsplit("#", 1)
    key, secret = keysecret.split(":", 1)
    stop("docker")
    p = root / "docker/config/config.json"
    cfg = json.loads(p.read_text())
    cfg["sync"]["knownHosts"] = [
        {
            "instanceId": instance,
            "keyId": key,
            "instanceUrl": "http://" + names["storage"] + ":9898",
            "initialPairingSecret": secret,
            "permissions": [{"type": "PERMISSION_READ_OPERATIONS", "scopes": ["*"]}],
        }
    ]
    p.write_text(json.dumps(cfg))
    start("docker")
    tokens["docker"] = api(
        "docker",
        "v1.Authentication/Login",
        {"username": "admin", "password": "disposable-password"},
    )["token"]
    api("docker", "v1.Backrest/Backup", {"value": "docker-appdata"}, tokens["docker"])
    docker_snapshot = await_snapshot("docker")
    assert docker_snapshot["hostname"] == "docker"
    for attempt in range(80):
        ops = api(
            "storage",
            "v1.Backrest/GetOperations",
            {"selector": {"instanceId": "docker"}, "lastN": "30"},
            tokens["storage"],
        )
        if docker_snapshot["id"] in json.dumps(ops):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Completed client operation was not synchronized")
    print(
        "PASS official single-use pairing + authenticated API + Lenovo operation history on Ryzen"
    )
    try:
        api(
            "storage",
            "v1.Backrest/Backup",
            {"value": "storage-data"},
            tokens["storage"],
        )
    except TestCommandError as error:
        assert "hook" in error.output.lower(), "Expected a pre-snapshot hook failure"
    else:
        raise RuntimeError("Failed hook unexpectedly succeeded")
    assert not [
        s for s in snapshots() if "plan:storage-data" in s.get("tags", [])
    ], "Failed export hook allowed a backup"
    (root / "hooks/fail").unlink()
    api("storage", "v1.Backrest/Backup", {"value": "storage-data"}, tokens["storage"])
    storage_snapshot = await_snapshot("storage")
    assert gzip.decompress(
        (root / "hooks/exports/current.sql.gz").read_bytes()
    ).startswith(b"-- PostgreSQL")
    assert historical <= {s["id"] for s in snapshots()}, "Historical snapshots changed"
    print(
        "PASS fatal pre-backup export hook; successful Storage backup; historical snapshots preserved"
    )
    restic("restore", docker_snapshot["id"], "--target", "/restore/new", "--verify")
    assert (
        root / "restored/new/sources/appdata/config.txt"
    ).read_text() == "recover-this-config"
    old = next(s for s in snapshots() if s["hostname"] == "apps")
    restic("restore", old["id"], "--target", "/restore/old-apps", "--verify")
    assert (
        root / "restored/old-apps/sources/appdata/config.txt"
    ).read_text() == "recover-this-config"
    restic("check")
    print(
        "PASS new and historical staging restores with byte comparison; repository integrity check"
    )
    print("Fixture directory (no production data):", root)
finally:
    for name in created:
        subprocess.run(D + ["rm", "-f", name], capture_output=True)
    subprocess.run(D + ["network", "rm", net], capture_output=True)
