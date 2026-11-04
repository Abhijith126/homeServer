"""Backup layout, identity and fail-closed configuration regression tests."""

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "backrest_config", ROOT / "scripts/backrest-config.py"
)
configuration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configuration)
HASH = base64.b64encode(("$2b$12$" + "a" * 53).encode()).decode()


class MigrationTests(unittest.TestCase):
    def manifest(self, node, stack):
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.example",
                "config",
                "--format",
                "json",
            ],
            cwd=ROOT / "stacks" / node / stack,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_two_targets_and_two_backrest_instances(self):
        targets = {
            p.name
            for p in (ROOT / "stacks").iterdir()
            if p.is_dir() and not p.name.startswith("_")
        }
        self.assertEqual(targets, {"storage", "docker"})
        for node in targets:
            manifest = self.manifest(node, "backrest")
            self.assertEqual(set(manifest["services"]), {"backrest"})
            service = manifest["services"]["backrest"]
            self.assertEqual(service["hostname"], node)
            self.assertIn(
                "ghcr.io/garethgeorge/backrest:v1.14.1@sha256:", service["image"]
            )
            self.assertEqual(manifest["name"], "backrest")
            self.assertFalse((ROOT / "stacks" / node / "restic").exists())
            self.assertNotIn("0.0.0.0", [p["host_ip"] for p in service["ports"]])
            self.assertFalse(service.get("privileged", False))
            for mount in service["volumes"]:
                self.assertNotIn("docker.sock", mount["source"])
                if mount["target"].startswith("/sources/"):
                    self.assertTrue(mount["read_only"])
        self.assertFalse((ROOT / "scripts/restic-scheduler.sh").exists())

    def test_named_volumes_reference_existing_production_identity(self):
        manifest = self.manifest("docker", "backrest")
        sources = {
            v["source"]
            for v in manifest["services"]["backrest"]["volumes"]
            if v["type"] == "volume"
        }
        self.assertEqual(sources, {"caddy-data", "caddy-config", "unbound-state"})
        for key, name in [
            ("caddy-data", "caddy_caddy-data"),
            ("caddy-config", "caddy_caddy-config"),
            ("unbound-state", "pihole-unbound_unbound-state"),
        ]:
            self.assertTrue(manifest["volumes"][key]["external"])
            self.assertEqual(manifest["volumes"][key]["name"], name)

    def test_home_assistant_route_is_independent_and_backup_admin_is_not_proxied(self):
        route = (ROOT / "stacks/docker/caddy/Caddyfile").read_text()
        self.assertIn("reverse_proxy {$HA_HOST}:8123", route)
        self.assertNotIn("9898", route)

    def test_config_covers_sources_and_has_no_automatic_deletion(self):
        for node in configuration.NODES:
            desired = configuration.desired(ROOT, node)
            repo, plan = desired["repo"], desired["plan"]
            self.assertEqual(desired["instance"], node)
            self.assertFalse(repo["autoInitialize"])
            self.assertFalse(repo["autoUnlock"])
            self.assertEqual(repo["forgetPolicy"]["schedule"], {"disabled": True})
            self.assertEqual(repo["prunePolicy"]["schedule"], {"disabled": True})
            self.assertEqual(plan["retention"], {"policyKeepAll": True})
            self.assertEqual(plan["schedule"], {"disabled": True})
            self.assertIn("/sources/appdata", plan["paths"])
            self.assertIn("/sources/checkout", plan["paths"])
            if node == "storage":
                self.assertIn("/sources/immich-exports", plan["paths"])
                self.assertIn("/sources/appdata/immich/postgres", plan["excludes"])
                self.assertEqual(plan["hooks"][0]["onError"], "ON_ERROR_FATAL")
            else:
                self.assertNotIn("/sources/nas", plan["paths"])
                self.assertIn("/sources/volumes", plan["paths"])
                self.assertEqual(repo["checkPolicy"]["schedule"], {"disabled": True})

    def test_reconcile_preserves_auth_and_pairing_and_refuses_wrong_repo(self):
        desired = configuration.desired(ROOT, "docker")
        existing = {
            "version": 6,
            "instance": "docker",
            "auth": {"users": [{"name": "private"}]},
            "sync": {
                "knownHosts": [{"instanceId": "storage", "keyId": "do-not-change"}]
            },
        }
        result = configuration.reconcile(existing, desired, "a" * 64, {})
        self.assertEqual(result["sync"], existing["sync"])
        self.assertEqual(result["auth"], existing["auth"])
        self.assertEqual(result["repos"][0]["guid"], "a" * 64)
        with self.assertRaisesRegex(ValueError, "GUID differs"):
            configuration.reconcile(result, desired, "b" * 64, {})
        with self.assertRaisesRegex(ValueError, "identity"):
            configuration.reconcile(
                existing, configuration.desired(ROOT, "storage"), "a" * 64, {}
            )

    def test_config_requires_authentication_and_never_inlines_repo_password(self):
        desired = configuration.desired(ROOT, "storage")
        with self.assertRaises(ValueError):
            configuration.reconcile({}, desired, "a" * 64, {})
        result = configuration.reconcile(
            {}, desired, "a" * 64, {"BACKREST_AUTH_BCRYPT": HASH}
        )
        self.assertFalse(result["auth"]["disabled"])
        self.assertEqual(result["repos"][0]["password"], "")
        self.assertEqual(
            result["repos"][0]["env"], ["RESTIC_PASSWORD=${RESTIC_PASSWORD}"]
        )

    def test_running_legacy_scheduler_blocks_config_import(self):
        for name in ("restic", "restic-media", "restic-check", "backrest"):
            with patch.object(
                configuration.subprocess, "check_output", return_value=name + "\n"
            ) as command:
                with self.assertRaisesRegex(ValueError, "Stop Backrest"):
                    configuration.install(ROOT, "storage")
                self.assertEqual(command.call_count, 1)

    def test_native_schedules_are_configurable_but_client_maintenance_stays_disabled(
        self,
    ):
        with patch.object(
            configuration,
            "settings",
            return_value={
                "BACKREST_ENABLE_SCHEDULES": "true",
                "BACKREST_STORAGE_CRON": "30 1 * * *",
                "BACKREST_DOCKER_CRON": "30 4 * * *",
                "BACKREST_CHECK_CRON": "0 12 * * 0",
            },
        ):
            self.assertEqual(
                configuration.desired(ROOT, "storage")["plan"]["schedule"]["cron"],
                "30 1 * * *",
            )
            client = configuration.desired(ROOT, "docker")
            self.assertEqual(client["plan"]["schedule"]["clock"], "CLOCK_LOCAL")
            self.assertTrue(client["repo"]["checkPolicy"]["schedule"]["disabled"])

    def test_retention_preview_is_always_dry_run_and_instance_plan_scoped(self):
        spec = importlib.util.spec_from_file_location(
            "preview", ROOT / "scripts/backrest-retention-preview.py"
        )
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        for command, host in zip(preview.commands({}), ("storage", "docker")):
            self.assertIn("--dry-run", command)
            self.assertNotIn("--prune", command)
            self.assertEqual(command[command.index("--host") + 1], host)
            tag = command[command.index("--tag") + 1]
            self.assertIn("created-by:" + host, tag)
            self.assertIn(",plan:", tag)
        with self.assertRaises(ValueError):
            preview.commands({"BACKREST_KEEP_DAILY": "-1"})

    def test_unsafe_bind_addresses_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "stacks/storage/backrest"
            target.mkdir(parents=True)
            (target / ".env.example").write_text(
                (ROOT / "stacks/storage/backrest/.env.example").read_text()
            )
            for address in ("0.0.0.0", "8.8.8.8", "224.0.0.1"):
                (root / ".env").write_text("BACKREST_BIND_IP=" + address + "\n")
                with self.assertRaisesRegex(ValueError, "trusted LAN"):
                    configuration.desired(root, "storage")

    def test_existing_repo_under_another_id_is_not_duplicated(self):
        with self.assertRaisesRegex(ValueError, "another ID"):
            configuration.reconcile(
                {"repos": [{"id": "previous", "guid": "a" * 64}]},
                configuration.desired(ROOT, "storage"),
                "a" * 64,
                {"BACKREST_AUTH_BCRYPT": HASH},
            )

    def test_cron_rejects_invalid_ranges_before_deployment(self):
        for expression in (
            "0 24 * * *",
            "0 2 * * 7",
            "*/0 * * * *",
            "0 2 32 * *",
            "0 2 * * MON",
        ):
            with self.assertRaises(ValueError):
                configuration.cron(expression)
        self.assertEqual(configuration.cron("*/15 1-4 * * 0,6")["clock"], "CLOCK_LOCAL")
