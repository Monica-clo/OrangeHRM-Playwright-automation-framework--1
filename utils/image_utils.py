"""Creates a small PNG profile picture (no extra dependency) if the test image is missing."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data)) + tag + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def ensure_png(path: Path, size: int = 200) -> Path:
    """Return `path`, generating a 200x200 gradient PNG (< 1MB, as OrangeHRM requires) if absent."""
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # PNG filter type: none
        for x in range(size):
            raw += bytes((255, 120 + (x * 100) // size, 30 + (y * 150) // size))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def image_size(path: Path) -> tuple[int, int]:
    """Return (width, height) of a PNG, GIF or JPEG file without extra dependencies."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":
        index = 2
        while index < len(data):
            marker, length = data[index + 1], struct.unpack(">H", data[index + 2:index + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return width, height
            index += 2 + length
    raise ValueError(f"Unsupported or corrupt image file: {path}")


ALLOWED_PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")
MAX_PHOTO_SIZE_BYTES = 1024 * 1024   # OrangeHRM: "Accepts jpg, .png, .gif up to 1MB"


def validate_profile_photo(photo: Path) -> None:
    """Fail early with a clear message if OrangeHRM would reject the photo."""
    if not photo.is_file():
        raise FileNotFoundError(f"Profile photo not found: {photo}")
    if photo.suffix.lower() not in ALLOWED_PHOTO_EXTENSIONS:
        raise ValueError(f"'{photo.name}' must be one of {ALLOWED_PHOTO_EXTENSIONS}")
    size = photo.stat().st_size
    if size > MAX_PHOTO_SIZE_BYTES:
        raise ValueError(f"'{photo.name}' is {size / 1024:.0f} KB - OrangeHRM accepts up to 1 MB")
