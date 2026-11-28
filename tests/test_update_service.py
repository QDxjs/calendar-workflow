"""Release metadata, checksum and safe extraction checks for the updater."""

from __future__ import annotations

import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
import hashlib

from update_service import (
    ReleaseInfo,
    UpdateError,
    UpdateProgress,
    _extract_verified_archive,
    _download_archive,
    _download_with_windows,
    _read_url,
    _parse_checksum,
    parse_latest_release,
    _transport_error,
    UpdateProgress,
)


def release_payload(version: str = "0.6.9") -> dict:
    tag = f"v{version}"
    names = (
        f"CalendarWorkflow-{version}-windows-x64.zip",
        f"CalendarWorkflow-{version}-windows-x64.zip.sha256",
    )
    return {
        "draft": False,
        "prerelease": False,
        "tag_name": tag,
        "html_url": f"https://github.com/QDxjs/calendar-workflow/releases/tag/{tag}",
        "body": "更新说明",
        "assets": [
            {
                "name": name,
                "browser_download_url": f"https://github.com/QDxjs/calendar-workflow/releases/download/{tag}/{name}",
            }
            for name in names
        ],
    }


class UpdateServiceTests(unittest.TestCase):
    def test_certificate_verification_failure_has_actionable_message(self):
        error = _transport_error("TLS")
        self.assertIn("Windows 信任", str(error))
        self.assertIn("不会跳过证书验证", str(error))

    def test_windows_transport_reports_progress_and_final_url(self):
        process = Mock()
        process.stdout = io.StringIO(
            "PROGRESS|7|7\nCOMPLETE|7|7|https://api.github.com/test\n",
        )
        process.wait.return_value = 0
        process.poll.return_value = 0
        progress = []
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "response.bin"
            with patch("update_service.subprocess.Popen", return_value=process):
                result = _download_with_windows(
                    "https://api.github.com/test", destination,
                    maximum=100, timeout=10, accept="application/json",
                    progress=progress.append,
                )
        self.assertEqual(result, ("https://api.github.com/test", 7, 7))
        self.assertEqual(progress, [UpdateProgress(7, 7)])

    def test_windows_transport_maps_tls_validation_failures(self):
        process = Mock()
        process.stdout = io.StringIO("ERROR|TLS|\n")
        process.wait.return_value = 2
        process.poll.return_value = 2
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "response.bin"
            with patch("update_service.subprocess.Popen", return_value=process):
                with self.assertRaisesRegex(UpdateError, "Windows 信任"):
                    _download_with_windows(
                        "https://api.github.com/test", destination,
                        maximum=100, timeout=10, accept="application/json",
                    )

    def test_read_url_returns_verified_response_and_checks_content_length(self):
        content = b'{"draft":false}'

        def transfer(url, destination, **kwargs):
            destination.write_bytes(content)
            return url, len(content), len(content)

        with patch("update_service._download_with_windows", side_effect=transfer):
            self.assertEqual(
                _read_url("https://api.github.com/test", maximum=100), content,
            )

        def truncated_transfer(url, destination, **kwargs):
            destination.write_bytes(content)
            return url, len(content), len(content) + 1

        with patch("update_service._download_with_windows", side_effect=truncated_transfer):
            with self.assertRaisesRegex(UpdateError, "长度不匹配"):
                _read_url("https://api.github.com/test", maximum=100)

    def test_new_release_requires_exact_version_assets_and_returns_release(self):
        release = parse_latest_release(release_payload(), "0.6.8")
        self.assertIsNotNone(release)
        self.assertEqual(release.version, "0.6.9")
        self.assertEqual(release.archive_name, "CalendarWorkflow-0.6.9-windows-x64.zip")
        self.assertEqual(release.notes, "更新说明")

    def test_same_or_older_release_is_not_an_update(self):
        self.assertIsNone(parse_latest_release(release_payload("0.6.8"), "0.6.8"))
        self.assertIsNone(parse_latest_release(release_payload("0.6.7"), "0.6.8"))

    def test_rejects_prerelease_missing_assets_and_untrusted_urls(self):
        payload = release_payload()
        payload["prerelease"] = True
        with self.assertRaises(UpdateError):
            parse_latest_release(payload, "0.6.8")

        payload = release_payload()
        payload["assets"].pop()
        with self.assertRaises(UpdateError):
            parse_latest_release(payload, "0.6.8")

        payload = release_payload()
        payload["assets"][0]["browser_download_url"] = "https://example.com/update.zip"
        with self.assertRaises(UpdateError):
            parse_latest_release(payload, "0.6.8")

    def test_checksum_requires_exact_archive_name(self):
        digest = "a" * 64
        self.assertEqual(
            _parse_checksum(f"{digest}  CalendarWorkflow-0.6.9-windows-x64.zip\n".encode(),
                            "CalendarWorkflow-0.6.9-windows-x64.zip"),
            digest,
        )
        for content in (
            f"{digest}  another.zip".encode(),
            f"{digest[:-1]}  CalendarWorkflow-0.6.9-windows-x64.zip".encode(),
            f"{digest}  CalendarWorkflow-0.6.9-windows-x64.zip\n{digest}  second.zip".encode(),
        ):
            with self.subTest(content=content), self.assertRaises(UpdateError):
                _parse_checksum(content, "CalendarWorkflow-0.6.9-windows-x64.zip")

    def test_archive_download_checks_final_sha256_before_accepting(self):
        content = b"release archive bytes"
        def transfer(url, destination, **kwargs):
            destination.write_bytes(content)
            if kwargs["progress"] is not None:
                kwargs["progress"](UpdateProgress(len(content), len(content)))
            return "https://release-assets.githubusercontent.com/archive", len(content), len(content)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "archive.zip"
            with patch("update_service._download_with_windows", side_effect=transfer):
                _download_archive(
                    "https://github.com/QDxjs/calendar-workflow/releases/download/v0.6.9/archive.zip",
                    destination, hashlib.sha256(content).hexdigest(), None,
                )
            self.assertEqual(destination.read_bytes(), content)

            destination.unlink()
            with patch("update_service._download_with_windows", side_effect=transfer):
                with self.assertRaises(UpdateError):
                    _download_archive(
                        "https://github.com/QDxjs/calendar-workflow/releases/download/v0.6.9/archive.zip",
                        destination, "0" * 64, None,
                    )

    def test_extracts_only_expected_release_root_and_verifies_staged_package(self):
        release = parse_latest_release(release_payload(), "0.6.8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "update.zip"
            destination = root / "stage"
            destination.mkdir()
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("CalendarWorkflow/", "")
                package.writestr("CalendarWorkflow/CalendarWorkflow.exe", b"exe")
                package.writestr(
                    "CalendarWorkflow/_internal/PACKAGE_SHA256.json",
                    json.dumps({"version": release.version, "sha256": {"CalendarWorkflow.exe": "0" * 64}}),
                )
            with patch("update_service.subprocess.run") as verify:
                verify.return_value.returncode = 0
                _extract_verified_archive(archive, destination, release)
            verify.assert_called_once()
            self.assertEqual((destination / "CalendarWorkflow.exe").read_bytes(), b"exe")

    def test_rejects_traversal_duplicate_and_version_mismatch(self):
        release = parse_latest_release(release_payload(), "0.6.8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "update.zip"
            destination = root / "stage"
            destination.mkdir()
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("CalendarWorkflow/../../escape.txt", "no")
            with self.assertRaises(UpdateError):
                _extract_verified_archive(archive, destination, release)
            self.assertFalse((root.parent / "escape.txt").exists())

            archive = root / "duplicate.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("CalendarWorkflow/CalendarWorkflow.exe", b"exe")
                package.writestr("CalendarWorkflow/calendarworkflow.exe", b"duplicate")
            with self.assertRaises(UpdateError):
                _extract_verified_archive(archive, destination, release)

            archive = root / "version.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("CalendarWorkflow/CalendarWorkflow.exe", b"exe")
                package.writestr(
                    "CalendarWorkflow/_internal/PACKAGE_SHA256.json",
                    json.dumps({"version": "0.7.0", "sha256": {}}),
                )
            with self.assertRaises(UpdateError):
                _extract_verified_archive(archive, destination, release)


if __name__ == "__main__":
    unittest.main()
