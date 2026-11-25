"""PNG rasterization and integrity validation for calendar SVG pages."""

from __future__ import annotations

import struct
import subprocess
import zlib
from pathlib import Path

PNG_SCALE = 1
RENDER_TIMEOUT_SECONDS = 120


def svg_to_png(
    svg_path: Path,
    png_path: Path,
    *,
    renderer_path: Path,
    width: int,
    height: int,
    scale: int = PNG_SCALE,
    timeout_seconds: int = RENDER_TIMEOUT_SECONDS,
) -> None:
    """Rasterize an SVG, then reject missing, corrupt, or incorrectly sized output."""
    if not renderer_path.exists():
        raise FileNotFoundError(f"找不到 PNG 渲染器：{renderer_path}")
    try:
        subprocess.run(
            [str(renderer_path), "--zoom", str(scale), str(svg_path), str(png_path)],
            check=True, capture_output=True, text=True, timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"PNG 导出超时（超过 {timeout_seconds} 秒）：{svg_path.name}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"PNG 导出失败：{detail or f'exit code {exc.returncode}'}") from exc
    validate_png(png_path, width=width, height=height, scale=scale)


def validate_png(
    png_path: Path,
    *,
    width: int,
    height: int,
    scale: int = PNG_SCALE,
) -> None:
    """Validate dimensions and chunk integrity of an existing PNG."""
    try:
        png_data = png_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"PNG 渲染器未生成输出文件：{png_path.name}") from exc
    signature = b"\x89PNG\r\n\x1a\n"
    if not png_data.startswith(signature):
        raise RuntimeError(f"PNG 渲染器输出文件无效：{png_path.name}")

    offset = len(signature)
    actual_size: tuple[int, int] | None = None
    saw_image_data = False
    saw_end = False
    while offset < len(png_data):
        if offset + 12 > len(png_data):
            raise RuntimeError(f"PNG 分块被截断：{png_path.name}")
        chunk_length = struct.unpack_from(">I", png_data, offset)[0]
        chunk_type_start = offset + 4
        chunk_data_start = offset + 8
        chunk_end = chunk_data_start + chunk_length
        crc_end = chunk_end + 4
        if crc_end > len(png_data):
            raise RuntimeError(f"PNG 分块长度超出文件边界：{png_path.name}")
        chunk_type = png_data[chunk_type_start:chunk_data_start]
        expected_crc = struct.unpack_from(">I", png_data, chunk_end)[0]
        actual_crc = zlib.crc32(png_data[chunk_type_start:chunk_end]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise RuntimeError(
                f"PNG 分块校验失败：{png_path.name} ({chunk_type.decode('ascii', 'replace')})"
            )
        if offset == len(signature):
            if chunk_type != b"IHDR" or chunk_length != 13:
                raise RuntimeError(f"PNG 缺少有效的 IHDR 头：{png_path.name}")
            actual_size = struct.unpack_from(">II", png_data, chunk_data_start)
        elif chunk_type == b"IHDR":
            raise RuntimeError(f"PNG 包含重复 IHDR 头：{png_path.name}")
        if chunk_type == b"IDAT":
            saw_image_data = True
        if chunk_type == b"IEND":
            if chunk_length != 0 or not saw_image_data or crc_end != len(png_data):
                raise RuntimeError(f"PNG 结束块无效或文件含尾随数据：{png_path.name}")
            saw_end = True
            break
        offset = crc_end

    if not saw_end:
        raise RuntimeError(f"PNG 缺少完整的 IEND 结束块：{png_path.name}")
    expected_size = (width * scale, height * scale)
    if actual_size != expected_size:
        raise RuntimeError(
            f"PNG 尺寸错误：{png_path.name} 为 {actual_size[0]} × {actual_size[1]}，"
            f"预期 {expected_size[0]} × {expected_size[1]}。"
        )
