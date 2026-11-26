"""Rebuild the original calendar/book icon using the bundled SVG renderer."""

from pathlib import Path
import struct
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def main() -> None:
    assets = ROOT / "assets"
    images = []
    with tempfile.TemporaryDirectory(prefix="calendar-icon-") as scratch:
        for size in SIZES:
            png = Path(scratch) / f"{size}.png"
            subprocess.run([
                str(ROOT / "tools/resvg/resvg.exe"), "--width", str(size), "--height", str(size),
                str(assets / "calendar.svg"), str(png),
            ], check=True, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            images.append(png.read_bytes())
    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, image in zip(SIZES, images):
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(image), offset))
        offset += len(image)
    (assets / "calendar.ico").write_bytes(bytes(directory) + b"".join(images))
    (assets / "calendar.png").write_bytes(images[-1])
    print("Rebuilt calendar.svg as a nine-size Windows ICO and 256px PNG.")


if __name__ == "__main__":
    main()
