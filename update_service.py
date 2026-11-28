"""Check, download and stage verified Windows portable releases."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Callable
from urllib.parse import urlparse
import zipfile


REPOSITORY = "QDxjs/calendar-workflow"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ARCHIVE_PREFIX = "CalendarWorkflow-"
MAX_RELEASE_METADATA = 1024 * 1024
MAX_CHECKSUM_SIZE = 1024
MAX_ARCHIVE_SIZE = 1024 * 1024 * 1024
MAX_EXPANDED_SIZE = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 50000
CHUNK_SIZE = 1024 * 1024
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
}


class UpdateError(RuntimeError):
    """An update could not be checked, downloaded or validated."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    release_url: str
    notes: str
    archive_url: str
    checksum_url: str
    archive_name: str


@dataclass(frozen=True)
class UpdateProgress:
    received: int
    total: int | None


def _transport_error(code: str, detail: str = "") -> UpdateError:
    if code == "TLS":
        return UpdateError(
            "GitHub HTTPS 证书链验证失败。请检查系统日期、HTTPS 代理配置，以及代理证书是否受 Windows 信任；"
            "程序不会跳过证书验证。"
        )
    if code.startswith("HTTP:"):
        status = code.partition(":")[2]
        if status == "404":
            return UpdateError("GitHub Release 或附件不存在。")
        if status == "403":
            return UpdateError("GitHub 暂时限制了请求，请稍后重试。")
        return UpdateError(f"GitHub 请求失败（HTTP {status}）。")
    if code == "TIMEOUT":
        return UpdateError("连接 GitHub 超时，请检查网络后重试。")
    if code == "SIZE":
        return UpdateError("GitHub 返回的数据超过允许大小。")
    if code == "NETWORK":
        return UpdateError("无法连接 GitHub，请检查网络或代理配置。")
    return UpdateError(f"Windows HTTPS 请求失败：{detail or code}")


def _validate_transfer_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in allowed_hosts
            or parsed.port not in (None, 443) or parsed.username is not None or parsed.password is not None):
        raise UpdateError("下载请求使用了不受支持的 HTTPS 地址。")


def _download_with_windows(
    url: str,
    destination: Path,
    *,
    maximum: int,
    timeout: int,
    accept: str,
    progress: Callable[[UpdateProgress], None] | None = None,
) -> tuple[str, int, int | None]:
    script = Path(__file__).resolve().parent / "tools" / "update_transport.ps1"
    if not script.is_file():
        raise UpdateError("找不到 Windows HTTPS 传输组件。")
    if destination.exists():
        raise UpdateError("更新临时文件已存在，拒绝覆盖。")
    command = [
        "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(script),
        "-Uri", url, "-DestinationPath", str(destination.resolve()),
        "-MaximumBytes", str(maximum), "-TimeoutSeconds", str(timeout), "-Accept", accept,
    ]
    if progress is not None:
        command.append("-ReportProgress")

    process = None
    completed = None
    received = 0
    total: int | None = None
    output_lines: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=destination.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.stdout is None:
            raise UpdateError("无法读取 Windows HTTPS 传输状态。")
        for line in process.stdout:
            line = line.rstrip("\r\n")
            fields = line.split("|", 3)
            if fields[0] == "PROGRESS" and len(fields) == 3:
                try:
                    received = int(fields[1])
                    total_value = int(fields[2])
                    total = total_value if total_value >= 0 else None
                except ValueError as exc:
                    raise UpdateError("Windows HTTPS 传输返回了无效进度。") from exc
                if progress is not None:
                    progress(UpdateProgress(received, total))
            elif fields[0] == "COMPLETE" and len(fields) == 4:
                try:
                    received = int(fields[1])
                    total_value = int(fields[2])
                    total = total_value if total_value >= 0 else None
                except ValueError as exc:
                    raise UpdateError("Windows HTTPS 传输返回了无效长度。") from exc
                completed = fields[3]
            elif line:
                output_lines.append(line[:1000])
        return_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise UpdateError("Windows HTTPS 请求超时。") from exc
    except OSError as exc:
        raise UpdateError(f"无法启动 Windows HTTPS 传输组件：{exc}") from exc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if process is not None and process.stdout is not None:
            process.stdout.close()

    if return_code != 0:
        error_line = next((line for line in reversed(output_lines) if line.startswith("ERROR|")), "")
        _, _, error = error_line.partition("|")
        code, _, detail = error.partition("|")
        raise _transport_error(code, detail)
    if completed is None:
        raise UpdateError("Windows HTTPS 传输未返回完成状态。")
    if received > maximum or (total is not None and total > maximum):
        raise _transport_error("SIZE")
    return completed, received, total


def _check_final_url(final_url: str, initial_url: str, allowed_hosts: set[str]) -> None:
    _validate_transfer_url(initial_url, {"api.github.com", "github.com"})
    _validate_transfer_url(final_url, allowed_hosts)


def _version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value) is None:
        raise UpdateError("版本号格式无效。")
    return tuple(int(part) for part in value.split("."))


def _github_download_url(value: object, filename: str, tag_name: str) -> str:
    if not isinstance(value, str):
        raise UpdateError("GitHub Release 缺少有效的下载地址。")
    parsed = urlparse(value)
    expected_path = f"/{REPOSITORY}/releases/download/{tag_name}/{filename}"
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.port not in (None, 443)
            or parsed.username is not None or parsed.password is not None or parsed.path != expected_path
            or parsed.query or parsed.fragment):
        raise UpdateError("GitHub Release 的下载地址与附件名称不匹配。")
    return value


def parse_latest_release(payload: object, current_version: str) -> ReleaseInfo | None:
    current = _version_tuple(current_version)
    if not isinstance(payload, dict) or payload.get("draft") is not False or payload.get("prerelease") is not False:
        raise UpdateError("GitHub 返回的正式发行信息无效。")
    tag_name = payload.get("tag_name")
    match = re.fullmatch(r"v([0-9]+\.[0-9]+\.[0-9]+)", tag_name) if isinstance(tag_name, str) else None
    if match is None:
        raise UpdateError("GitHub 最新正式发行的版本标签格式无效。")
    version = match.group(1)
    if _version_tuple(version) <= current:
        return None

    archive_name = f"{ARCHIVE_PREFIX}{version}-windows-x64.zip"
    checksum_name = f"{archive_name}.sha256"
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("GitHub Release 没有可用的便携版附件。")
    asset_urls: dict[str, str] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        if name in (archive_name, checksum_name):
            asset_urls[name] = _github_download_url(asset.get("browser_download_url"), name, tag_name)
    if archive_name not in asset_urls or checksum_name not in asset_urls:
        raise UpdateError("此 GitHub Release 缺少便携 ZIP 或 SHA-256 校验文件。")

    release_url = payload.get("html_url")
    parsed_release_url = urlparse(release_url) if isinstance(release_url, str) else None
    if (parsed_release_url is None or parsed_release_url.scheme != "https"
            or parsed_release_url.hostname != "github.com"
            or parsed_release_url.path != f"/{REPOSITORY}/releases/tag/{tag_name}"):
        raise UpdateError("GitHub Release 页面地址无效。")
    notes = payload.get("body")
    if not isinstance(notes, str):
        notes = ""
    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        release_url=release_url,
        notes=notes[:4000],
        archive_url=asset_urls[archive_name],
        checksum_url=asset_urls[checksum_name],
        archive_name=archive_name,
    )


def _read_url(url: str, *, maximum: int, timeout: int = 20) -> bytes:
    _validate_transfer_url(url, {"api.github.com", "github.com"})
    with tempfile.TemporaryDirectory(prefix="calendar-update-response-") as temporary:
        destination = Path(temporary) / "response.bin"
        final_url, received, total = _download_with_windows(
            url, destination, maximum=maximum, timeout=timeout,
            accept="application/vnd.github+json, application/octet-stream, text/plain",
        )
        _check_final_url(final_url, url, {"api.github.com", "github.com", *ALLOWED_DOWNLOAD_HOSTS})
        if (received > maximum or (total is not None and received != total)
                or not destination.is_file() or destination.stat().st_size != received):
            raise UpdateError("GitHub 返回的数据超过允许大小或长度不匹配。")
        return destination.read_bytes()


def check_for_update(current_version: str) -> ReleaseInfo | None:
    payload_bytes = _read_url(API_URL, maximum=MAX_RELEASE_METADATA)
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("GitHub 返回的发行信息无法解析。") from exc
    return parse_latest_release(payload, current_version)


def _parse_checksum(payload: bytes, archive_name: str) -> str:
    try:
        text = payload.decode("utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise UpdateError("SHA-256 校验文件不是有效文本。") from exc
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", text)
    if match is None or match.group(2) != archive_name:
        raise UpdateError("SHA-256 校验文件格式或文件名不匹配。")
    return match.group(1).lower()


def _download_archive(
    url: str,
    destination: Path,
    expected_digest: str,
    progress: Callable[[UpdateProgress], None] | None,
) -> None:
    digest = hashlib.sha256()
    _validate_transfer_url(url, {"github.com"})
    final_url, received, total = _download_with_windows(
        url, destination, maximum=MAX_ARCHIVE_SIZE, timeout=30,
        accept="application/octet-stream", progress=progress,
    )
    _check_final_url(final_url, url, ALLOWED_DOWNLOAD_HOSTS)
    if (not destination.is_file() or destination.stat().st_size != received
            or (total is not None and received != total)):
        raise UpdateError("更新包下载未完成。")
    with destination.open("rb") as source:
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
    if digest.hexdigest() != expected_digest:
        raise UpdateError("更新包 SHA-256 不匹配，已拒绝安装。")


def _safe_archive_path(name: str, version: str) -> tuple[str, ...]:
    if "\\" in name or "\0" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise UpdateError("更新 ZIP 中包含不安全的文件路径。")
    raw_parts = name.rstrip("/").split("/")
    allowed_roots = {"CalendarWorkflow", f"CalendarWorkflow-{version}"}
    if (not raw_parts or raw_parts[0] not in allowed_roots
            or any(part in ("", ".", "..") or ":" in part for part in raw_parts)):
        raise UpdateError("更新 ZIP 的目录结构无效。")
    parsed = PurePosixPath(*raw_parts)
    if parsed.is_absolute() or parsed.parts != tuple(raw_parts):
        raise UpdateError("更新 ZIP 中包含不安全的文件路径。")
    return tuple(raw_parts[1:])


def _extract_verified_archive(archive_path: Path, destination: Path, release: ReleaseInfo) -> None:
    seen: set[str] = set()
    expanded_size = 0
    try:
        with zipfile.ZipFile(archive_path) as package:
            entries = package.infolist()
            if not entries or len(entries) > MAX_ARCHIVE_ENTRIES:
                raise UpdateError("更新 ZIP 的文件数量无效。")
            for entry in entries:
                relative = _safe_archive_path(entry.filename, release.version)
                if not relative:
                    if not entry.is_dir():
                        raise UpdateError("更新 ZIP 的顶层目录无效。")
                    continue
                key = "/".join(relative).casefold()
                if key in seen:
                    raise UpdateError("更新 ZIP 中包含重复路径。")
                seen.add(key)
                mode = (entry.external_attr >> 16) & 0o170000
                expected_mode = 0o040000 if entry.is_dir() else 0o100000
                if mode not in (0, expected_mode):
                    raise UpdateError("更新 ZIP 中包含链接或特殊文件。")
                if entry.flag_bits & 0x1:
                    raise UpdateError("更新 ZIP 中包含加密文件，无法安全校验。")
                if not entry.is_dir():
                    expanded_size += entry.file_size
                    if expanded_size > MAX_EXPANDED_SIZE:
                        raise UpdateError("更新 ZIP 解压后超过允许大小。")

            destination_resolved = destination.resolve()
            for entry in entries:
                relative = _safe_archive_path(entry.filename, release.version)
                if not relative:
                    continue
                target = destination.joinpath(*relative)
                if not target.resolve().is_relative_to(destination_resolved):
                    raise UpdateError("更新 ZIP 中包含越界文件路径。")
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, CHUNK_SIZE)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"更新 ZIP 无法安全解压：{exc}") from exc

    inventory_path = destination / "_internal" / "PACKAGE_SHA256.json"
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("更新包缺少有效的文件完整性清单。") from exc
    if not isinstance(inventory, dict) or inventory.get("version") != release.version:
        raise UpdateError("更新包内部版本与 GitHub Release 标签不一致。")
    executable = destination / "CalendarWorkflow.exe"
    if not executable.is_file():
        raise UpdateError("更新包缺少桌面程序。")
    try:
        result = subprocess.run(
            [str(executable), "--verify-package"],
            cwd=destination,
            check=False,
            capture_output=True,
            timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"无法验证下载后的便携程序：{exc}") from exc
    if result.returncode != 0:
        raise UpdateError("更新包内部文件校验失败，已拒绝安装。")


def download_and_stage_update(
    release: ReleaseInfo,
    install_directory: Path,
    progress: Callable[[UpdateProgress], None] | None = None,
) -> Path:
    install_directory = install_directory.resolve()
    if not install_directory.is_dir() or install_directory.is_symlink():
        raise UpdateError("无法确定当前便携版安装目录。")
    parent = install_directory.parent
    stage_directory: Path | None = None
    archive_path: Path | None = None
    keep_stage = False
    try:
        stage_directory = Path(tempfile.mkdtemp(
            prefix=f".{install_directory.name}.update-", dir=parent,
        ))
        archive_fd, archive_name = tempfile.mkstemp(prefix="calendar-update-", suffix=".zip")
        os.close(archive_fd)
        archive_path = Path(archive_name)
        archive_path.unlink()
        checksum = _parse_checksum(
            _read_url(release.checksum_url, maximum=MAX_CHECKSUM_SIZE),
            release.archive_name,
        )
        _download_archive(release.archive_url, archive_path, checksum, progress)
        _extract_verified_archive(archive_path, stage_directory, release)
        keep_stage = True
        return stage_directory
    except OSError as exc:
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"无法在当前程序目录准备更新：{exc}") from exc
    finally:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
        if stage_directory is not None and not keep_stage:
            shutil.rmtree(stage_directory, ignore_errors=True)


def launch_update_installer(
    stage_directory: Path,
    install_directory: Path,
    helper_script: Path,
    process_id: int,
) -> None:
    if os.name != "nt":
        raise UpdateError("自动安装仅支持 Windows 便携版。")
    if not helper_script.is_file():
        raise UpdateError("找不到升级安装组件。")
    fd, script_name = tempfile.mkstemp(prefix="calendar-update-", suffix=".ps1")
    os.close(fd)
    script_copy = Path(script_name)
    try:
        shutil.copyfile(helper_script, script_copy)
        arguments = [
            "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(script_copy),
            "-InstallDirectory", str(install_directory.resolve()),
            "-StageDirectory", str(stage_directory.resolve()),
            "-ProcessId", str(process_id),
            "-CleanupScriptPath", str(script_copy),
        ]
        subprocess.Popen(
            arguments,
            cwd=install_directory.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    except OSError as exc:
        script_copy.unlink(missing_ok=True)
        raise UpdateError(f"无法启动升级安装程序：{exc}") from exc


def remove_staged_update(stage_directory: Path, install_directory: Path) -> None:
    install_directory = install_directory.resolve()
    stage_directory = stage_directory.resolve()
    expected_prefix = f".{install_directory.name}.update-"
    if (stage_directory.parent != install_directory.parent
            or not stage_directory.name.startswith(expected_prefix)
            or stage_directory.is_symlink()):
        raise UpdateError("拒绝清理不属于本次升级的目录。")
    shutil.rmtree(stage_directory)
