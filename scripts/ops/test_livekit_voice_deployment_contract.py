"""Offline safety tests for the LiveKit Cloud voice deployment helper.

A fake lk command exercises local preflight and temporary build-context behavior.
No LiveKit account, database, credentials, image build, or network is used.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCRIPT = SOURCE_ROOT / "scripts" / "ops" / "deploy-livekit-cloud-free-voice.sh"


FAKE_LK = r"""#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$FAKE_LK_LOG"

if [[ "$1" == "agent" && "$2" == "create" ]]; then
  secret_file=""
  previous=""
  for item in "$@"; do
    if [[ "$previous" == "--secrets-file" ]]; then
      secret_file="$item"
      break
    fi
    previous="$item"
  done
  [[ "$secret_file" == "$FAKE_SECRET_EXPECTED" ]]
  [[ "$secret_file" != "$PWD/"* ]]
  [[ ! -e "$PWD/voice.env" ]]
  [[ ! -e "$PWD/.env" ]]
  printf '[project]\nsubdomain = "synthetic"\n[agent]\nid = "CA_SYNTHETIC"\n' > livekit.toml
  exit 0
fi

if [[ "$1" == "agent" && "$2" == "deploy" ]]; then
  [[ -f "$PWD/livekit.toml" ]]
  secret_file=""
  previous=""
  for item in "$@"; do
    if [[ "$previous" == "--secrets-file" ]]; then
      secret_file="$item"
      break
    fi
    previous="$item"
  done
  [[ "$secret_file" == "$FAKE_SECRET_EXPECTED" ]]
  [[ "$secret_file" != "$PWD/"* ]]
  [[ ! -e "$PWD/voice.env" ]]
  exit 0
fi

if [[ "$1" == "--config" && "$3" == "agent" && "$4" == "status" ]]; then
  [[ -f "$2" ]]
  exit 0
fi

echo "Unexpected synthetic lk invocation" >&2
exit 98
"""


class LiveKitVoiceDeploymentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="aqlyra-livekit-test-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.script_dir = self.repo / "scripts" / "ops"
        self.backend = self.repo / "backend"
        self.script_dir.mkdir(parents=True)
        (self.backend / "app").mkdir(parents=True)
        for filename in (
            "Dockerfile.voice",
            "requirements.txt",
            "requirements-voice.txt",
            ".dockerignore",
        ):
            (self.backend / filename).write_text("# synthetic\n", encoding="utf-8")
        (self.backend / "app" / "worker.py").write_text("# synthetic\n", encoding="utf-8")
        shutil.copy2(SOURCE_SCRIPT, self.script_dir / SOURCE_SCRIPT.name)

        self.home = self.root / "home"
        self.home.mkdir()
        self.state_dir = self.home / ".config" / "aqlyra"
        self.secrets_dir = self.root / "private"
        self.secrets_dir.mkdir()
        self.secret_file = self.secrets_dir / "voice.env"
        self.secret_file.write_text(
            "APP_ENV=production\n"
            "DATABASE_URL=postgresql://synthetic:synthetic-password-123456@db.invalid/app\n"
            "GROQ_API_KEY=synthetic-not-a-real-key\n"
            "SECRET_KEY=synthetic-not-a-real-secret-value-123456789\n",
            encoding="utf-8",
        )
        self.secret_file.chmod(0o600)

        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        fake_lk = self.fake_bin / "lk"
        fake_lk.write_text(FAKE_LK, encoding="utf-8")
        fake_lk.chmod(0o700)
        self.log_file = self.root / "lk.log"

        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": str(self.fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            "AQLYRA_VOICE_SECRETS_FILE": str(self.secret_file),
            "FAKE_SECRET_EXPECTED": str(self.secret_file),
            "FAKE_LK_LOG": str(self.log_file),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self.script_dir / SOURCE_SCRIPT.name), action],
            cwd=self.repo,
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_create_uploads_private_secrets_by_path_not_build_context(self) -> None:
        result = self.run_script("create")
        self.assertEqual(result.returncode, 0, result.stderr)
        state_file = self.state_dir / "livekit-voice.toml"
        self.assertTrue(state_file.is_file())
        self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o600)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("agent create", log)
        self.assertIn("--secrets-file", log)
        self.assertIn("agent status", log)
        self.assertNotIn("synthetic-not-a-real-key", log)
        self.assertNotIn("synthetic-not-a-real-secret", log)

    def test_deploy_reuses_saved_agent_config_without_uploading_secret_file(self) -> None:
        self.state_dir.mkdir(parents=True)
        state_file = self.state_dir / "livekit-voice.toml"
        state_file.write_text('[project]\nsubdomain = "synthetic"\n[agent]\nid = "CA_SYNTHETIC"\n')
        state_file.chmod(0o600)

        result = self.run_script("deploy")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("agent deploy", log)
        self.assertIn("--secrets-file", log)
        self.assertIn("agent status", log)

    def test_symlinked_secret_file_is_rejected_before_cloud_cli(self) -> None:
        link = self.secrets_dir / "linked.env"
        link.symlink_to(self.secret_file)
        self.env["AQLYRA_VOICE_SECRETS_FILE"] = str(link)
        result = self.run_script("create")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a symlink", result.stderr)
        self.assertFalse(self.log_file.exists())

    def test_group_or_world_readable_secret_file_is_rejected(self) -> None:
        self.secret_file.chmod(0o644)
        result = self.run_script("create")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("chmod 600", result.stderr)
        self.assertFalse(self.log_file.exists())

    def test_secret_file_inside_repository_is_rejected(self) -> None:
        repo_secret = self.repo / ".voice.env"
        repo_secret.write_text("SECRET_KEY=synthetic\n", encoding="utf-8")
        repo_secret.chmod(0o600)
        self.env["AQLYRA_VOICE_SECRETS_FILE"] = str(repo_secret)
        result = self.run_script("create")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the Git repository", result.stderr)
        self.assertFalse(self.log_file.exists())

    def test_symlinked_state_directory_and_state_file_are_rejected(self) -> None:
        outside = self.root / "outside-state"
        outside.mkdir()
        (self.home / ".config").mkdir()
        self.state_dir.symlink_to(outside, target_is_directory=True)
        result = self.run_script("status")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlinked LiveKit state path", result.stderr)

        self.state_dir.unlink()
        self.state_dir.mkdir()
        target = self.root / "other-config.toml"
        target.write_text("[agent]\nid = 'CA_OTHER'\n", encoding="utf-8")
        (self.state_dir / "livekit-voice.toml").symlink_to(target)
        result = self.run_script("status")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlinked LiveKit state path", result.stderr)

    def test_invalid_action_never_invokes_cli(self) -> None:
        result = self.run_script("delete")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.log_file.exists())


if __name__ == "__main__":
    unittest.main()

    def test_create_uses_unique_atomic_state_tempfile_and_cleans_it(self) -> None:
        result = self.run_script("create")
        self.assertEqual(result.returncode, 0, result.stderr)
        state_file = self.state_dir / "livekit-voice.toml"
        self.assertTrue(state_file.is_file())
        leftovers = list(self.state_dir.glob("livekit-voice.toml.tmp.*"))
        self.assertEqual(leftovers, [])
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("agent create", log)
