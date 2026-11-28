"""Exercise the portable updater's directory swap and rollback on Windows."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid


POWERSHELL = shutil.which("powershell.exe")
INSTALLER = Path(__file__).resolve().parents[1] / "tools" / "apply_update.ps1"


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
class UpdateInstallerTests(unittest.TestCase):
    def _prepare(self, root: Path, *, valid_executable: bool) -> tuple[Path, Path]:
        install = root / "CalendarWorkflow"
        stage = root / f".CalendarWorkflow.update-{uuid.uuid4().hex}"
        (install / "calendar_runs").mkdir(parents=True)
        stage.mkdir()
        (install / "CalendarWorkflow.exe").write_bytes(b"old executable")
        (install / "old-file.txt").write_text("old package", encoding="utf-8")
        (install / "calendar_runs" / "keep.txt").write_text("user data", encoding="utf-8")
        (stage / "CalendarWorkflow.exe").write_bytes(
            b"invalid executable" if not valid_executable else Path(os.environ["WINDIR"], "System32", "whoami.exe").read_bytes()
        )
        (stage / "new-file.txt").write_text("new package", encoding="utf-8")
        return install, stage

    def _run_installer(self, install: Path, stage: Path, *, restart: bool) -> subprocess.CompletedProcess[str]:
        arguments = [
            POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(INSTALLER), "-InstallDirectory", str(install), "-StageDirectory", str(stage),
            "-ProcessId", "2147483647", "-CleanupScriptPath", "", "-NoUI",
        ]
        if not restart:
            arguments.append("-NoRestart")
        return subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=45, check=False)

    def test_installs_new_files_and_moves_user_data_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install, stage = self._prepare(root, valid_executable=True)
            result = self._run_installer(install, stage, restart=False)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertFalse((install / "old-file.txt").exists())
            self.assertEqual((install / "new-file.txt").read_text(encoding="utf-8"), "new package")
            self.assertEqual((install / "calendar_runs" / "keep.txt").read_text(encoding="utf-8"), "user data")
            self.assertFalse(stage.exists())
            self.assertEqual(list(root.glob(".CalendarWorkflow.backup-*")), [])

    def test_failed_restart_rolls_back_old_files_and_user_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install, stage = self._prepare(root, valid_executable=False)
            result = self._run_installer(install, stage, restart=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((install / "CalendarWorkflow.exe").read_bytes(), b"old executable")
            self.assertEqual((install / "old-file.txt").read_text(encoding="utf-8"), "old package")
            self.assertEqual((install / "calendar_runs" / "keep.txt").read_text(encoding="utf-8"), "user data")
            self.assertFalse((install / "new-file.txt").exists())
            self.assertEqual(list(root.glob(".CalendarWorkflow.backup-*")), [])


if __name__ == "__main__":
    unittest.main()
