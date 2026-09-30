"""Test bootstrap configuration without installing packages or changing the host."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bootstrap_config", REPO / "scripts/bootstrap-config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copy(REPO / ".env.example", self.root / ".env.example")
        for source in (REPO / "stacks").glob("*/*/.env.example"):
            target = self.root / source.relative_to(REPO)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, target)
        (self.root / "scripts").mkdir()
        shutil.copy(REPO / "scripts/gen-env.sh", self.root / "scripts/gen-env.sh")
        self.answers = {}
        self.optional = {}
        self.extra_skip = ""
        self.output = io.StringIO()

    def configure(self, node):
        def ask(label, default="", validate=lambda value: bool(value)):
            value = self.answers.get(label, default)
            self.assertTrue(validate(value), f"Invalid test answer for {label}: {value}")
            return value

        def yes(label, default=False):
            return self.optional.get(label, default)

        def password(label):
            return "" if label.startswith("Optional Tailscale") else "shared-backup-password"

        with patch.object(config, "ask", side_effect=ask), patch.object(config, "yes", side_effect=yes), \
                patch.object(config.getpass, "getpass", side_effect=password), \
                patch("builtins.input", return_value=self.extra_skip), contextlib.redirect_stdout(self.output):
            config.configure(node, self.root)
        return json.loads((self.root / ".bootstrap/vars.json").read_text())

    def generate(self, data):
        return subprocess.run(["bash", str(self.root / "scripts/gen-env.sh"),
                               "--node", data["bootstrap_node"],
                               "--skip", " ".join(data["bootstrap_skip"])],
                              capture_output=True, text=True)

    def test_apps_generate_credentials_and_preserve_them_on_rerun(self):
        data = self.configure("apps")
        env = config.read_env(self.root / ".env")
        key = env["HOMARR_SECRET_ENCRYPTION_KEY"]
        self.assertRegex(key, r"^[a-f0-9]{64}$")
        self.assertEqual(env["RESTIC_PASSWORD"], "shared-backup-password")
        self.assertEqual(self.generate(data).returncode, 0)
        self.configure("apps")
        self.assertEqual(config.read_env(self.root / ".env")["HOMARR_SECRET_ENCRYPTION_KEY"], key)
        self.assertNotIn("shared-backup-password", self.output.getvalue())
        self.assertEqual(os.stat(self.root / ".env").st_mode & 0o777, 0o600)

    def test_storage_skips_unconfigured_vpn_and_uses_custom_directories(self):
        self.answers.update({"Media export directory on storage": "/srv/media",
                             "Backup export directory on storage": "/srv/backups"})
        data = self.configure("storage")
        self.assertIn("qbittorrent", data["bootstrap_skip"])
        env = config.read_env(self.root / ".env")
        self.assertEqual(env["IMMICH_LIBRARY"], "/srv/media/Gallery")
        self.assertEqual(env["RESTIC_REPO_PATH"], "/srv/backups/restic")
        result = self.generate(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "stacks/storage/qbittorrent/.env").exists())

    def test_infra_internal_tls_and_custom_addresses(self):
        self.answers.update({"Storage node LAN IPv4": "10.10.0.10",
                             "Apps node LAN IPv4": "10.10.0.11",
                             "Infra node LAN IPv4": "10.10.0.12",
                             "LAN CIDR": "10.10.0.0/24"})
        data = self.configure("infra")
        self.assertIn("diun", data["bootstrap_skip"])
        self.assertIn("beszel-agent", data["bootstrap_skip"])
        env = config.read_env(self.root / ".env")
        self.assertEqual(env["CADDY_GLOBAL_OPTIONS"], "local_certs")
        self.assertEqual(env["PIHOLE_HOST_IP"], "10.10.0.12")
        self.assertEqual(data["nfs_mounts"][0]["src"], "10.10.0.10:/mnt/nas")
        result = self.generate(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(config.read_env(self.root / "stacks/infra/caddy/.env")["APPS_HOST"], "10.10.0.11")

    def test_literal_secrets_survive_environment_roundtrip(self):
        secret = "already$safe #don't-change"
        config.write_env(self.root / ".env", {"RESTIC_PASSWORD": secret})
        data = self.configure("apps")
        self.assertEqual(config.read_env(self.root / ".env")["RESTIC_PASSWORD"], secret)
        self.assertEqual(self.generate(data).returncode, 0)
        self.assertEqual(config.read_env(self.root / "stacks/apps/restic/.env")["RESTIC_PASSWORD"], secret)

    def test_wireguard_credentials_reach_generated_stack(self):
        self.optional["Enable qBittorrent with your VPN account"] = True
        self.answers.update({"VPN protocol: openvpn or wireguard": "wireguard",
                             "WireGuard interface address": "10.20.0.2/32"})
        data = self.configure("storage")
        result = self.generate(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        env = config.read_env(self.root / "stacks/storage/qbittorrent/.env")
        self.assertEqual(env["VPN_TYPE"], "wireguard")
        self.assertEqual(env["OPENVPN_PASSWORD"], "")
        self.assertEqual(env["WIREGUARD_PRIVATE_KEY"], "shared-backup-password")
        self.assertEqual(env["WIREGUARD_ADDRESSES"], "10.20.0.2/32")

    def test_existing_standalone_credentials_are_reused(self):
        config.write_env(self.root / "stacks/apps/homarr/.env", {"HOMARR_SECRET_ENCRYPTION_KEY": "a" * 64})
        config.write_env(self.root / "stacks/apps/restic/.env", {"RESTIC_PASSWORD": "existing-backup-password"})
        self.configure("apps")
        env = config.read_env(self.root / ".env")
        self.assertEqual(env["HOMARR_SECRET_ENCRYPTION_KEY"], "a" * 64)
        self.assertEqual(env["RESTIC_PASSWORD"], "existing-backup-password")

    def test_existing_application_data_needs_current_key(self):
        data = self.root / "existing-data"
        (data / "homarr").mkdir(parents=True)
        self.answers["Local application data directory"] = str(data)
        self.configure("apps")
        self.assertEqual(config.read_env(self.root / ".env")["HOMARR_SECRET_ENCRYPTION_KEY"], "shared-backup-password")

    def test_duplicate_addresses_are_rejected_before_writing_environment(self):
        self.answers["Apps node LAN IPv4"] = "192.168.1.120"
        with self.assertRaisesRegex(ValueError, "different LAN"):
            self.configure("apps")
        self.assertFalse((self.root / ".env").exists())


if __name__ == "__main__":
    unittest.main()
