"""Exercise real Git sync/state handling with a fake Docker CLI."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self.run_git(self.origin, "init", "--initial-branch=main")
        self.run_git(self.origin, "config", "user.name", "Test")
        self.run_git(self.origin, "config", "user.email", "test@example.invalid")
        shutil.copytree(REPO / "scripts", self.origin / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        for script in (self.origin / "scripts").glob("*.sh"):
            script.chmod(0o755)
        (self.origin / ".gitignore").write_text(".env\n.deploy-state/\n")
        for node, app in [("apps", "alpha"), ("apps", "beta"),
                          ("storage", "database"), ("infra", "caddy"),
                          ("infra", "portainer")]:
            stack = self.origin / "stacks" / node / app
            stack.mkdir(parents=True)
            (stack / "compose.yaml").write_text(
                f"name: {app}\nservices:\n  app:\n    image: example:1.0.0\n")
            secret = "UNRELATED" if node == "storage" else "SECRET"
            (stack / ".env.example").write_text(f"{secret}=CHANGEME\n")
        self.run_git(self.origin, "add", ".")
        self.run_git(self.origin, "commit", "-m", "Initial")
        self.checkout = self.root / "checkout"
        self.run_git(self.root, "clone", str(self.origin), str(self.checkout))
        (self.checkout / ".env").write_text("SECRET=configured\n")
        self.log = self.root / "docker.log"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        docker = bin_dir / "docker"
        docker.write_text("""#!/usr/bin/env bash
printf '%s: %s\\n' "$(basename "$PWD")" "$*" >>"$DOCKER_LOG"
if [[ "$1 $2 $3" == "compose config -q" && "$(basename "$PWD")" == "${FAIL_CONFIG:-}" ]]; then exit 1; fi
if [[ "$1 $2" == "compose up" && "$(basename "$PWD")" == "${FAIL_UP:-}" ]]; then exit 1; fi
exit 0
""")
        docker.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
                        DOCKER_LOG=str(self.log))
        self.env.pop("HOMELAB_SKIP_STACKS", None)

    @staticmethod
    def run_git(cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, check=True,
                              capture_output=True, text=True).stdout.strip()

    def deploy(self, node="apps", force=False):
        command = [str(self.checkout / "scripts/auto-deploy.sh"), node]
        if force:
            command.append("--force")
        return subprocess.run(command, cwd=self.checkout, env=self.env,
                              capture_output=True, text=True)

    def lines(self):
        return "".join(line for line in self.log.read_text().splitlines(keepends=True)
                       if ": ps " not in line and ": info " not in line) if self.log.exists() else ""

    def test_merge_deploy_idempotence_and_cleanup(self):
        result = self.deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("alpha: compose up -d --remove-orphans --wait", self.lines())
        self.assertEqual(self.lines().count("image prune --all --force"), 2)
        self.assertNotIn("--filter", self.lines())
        self.assertLess(self.lines().index("image prune"), self.lines().index("compose pull"))
        self.assertGreater(self.lines().rindex("image prune"), self.lines().rindex("compose up"))
        self.assertFalse((self.checkout / "stacks/storage/database/.env").exists())
        log = self.lines()
        self.assertEqual(self.deploy().returncode, 0)
        self.assertEqual(self.lines(), log + "checkout: image prune --all --force\n")
        compose = self.origin / "stacks/apps/alpha/compose.yaml"
        compose.write_text(compose.read_text().replace("1.0.0", "1.0.1"))
        self.run_git(self.origin, "add", ".")
        self.run_git(self.origin, "commit", "-m", "Image update")
        self.assertEqual(self.deploy().returncode, 0)
        expected = self.run_git(self.origin, "rev-parse", "HEAD")
        self.assertEqual((self.checkout / ".deploy-state/apps/revision").read_text().strip(), expected)
        self.assertNotEqual(log, self.lines())

    def test_failed_health_cleans_up_without_recording_success_and_retries(self):
        self.env["FAIL_UP"] = "beta"
        self.assertNotEqual(self.deploy().returncode, 0)
        self.assertEqual(self.lines().count("image prune --all --force"), 2)
        self.assertFalse((self.checkout / ".deploy-state/apps/success").exists())
        del self.env["FAIL_UP"]
        self.assertEqual(self.deploy().returncode, 0)
        self.assertIn("image prune", self.lines())

    def test_validation_failure_changes_no_containers(self):
        self.env["FAIL_CONFIG"] = "beta"
        self.assertNotEqual(self.deploy().returncode, 0)
        self.assertNotIn("compose up", self.lines())
        self.assertEqual(self.lines().count("image prune --all --force"), 2)

    def test_local_edits_are_preserved(self):
        path = self.checkout / "stacks/apps/alpha/compose.yaml"
        path.write_text("local edit\n")
        self.assertNotEqual(self.deploy().returncode, 0)
        self.assertEqual(path.read_text(), "local edit\n")
        self.assertEqual(self.lines(), "")

    def test_local_secret_changes_trigger_deployment(self):
        self.assertEqual(self.deploy().returncode, 0)
        log = self.lines()
        (self.checkout / ".env").write_text("SECRET=changed\n")
        self.assertEqual(self.deploy().returncode, 0)
        self.assertNotEqual(log, self.lines())

    def test_infra_build_reload_and_optional_portainer(self):
        result = self.deploy("infra")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("caddy: compose build --pull", self.lines())
        self.assertIn("caddy: compose exec -T caddy caddy reload", self.lines())
        self.assertNotIn("portainer: compose", self.lines())
        self.env["HOMELAB_SKIP_STACKS"] = ""
        self.assertEqual(self.deploy("infra", force=True).returncode, 0)
        self.assertIn("portainer: compose up", self.lines())


if __name__ == "__main__":
    unittest.main()
