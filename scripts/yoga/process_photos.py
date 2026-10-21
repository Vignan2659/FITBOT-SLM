"""Resize downloaded yoga photos for the web app.

    python3 scripts/yoga/process_photos.py <folder with <slug>-<n>.jpg originals>

Writes frontend/public/yoga/photos/<slug>-<n>.jpg (longest side 800 px, for pose pages) and
frontend/public/yoga/photos/thumb/<slug>-<n>.jpg (longest side 420 px, for cards). Needs Pillow.
Only files listed in data/yoga/photo_credits.json are processed, so every published photo has a credit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "public" / "yoga" / "photos"


def save(im: Image.Image, path: Path, size: int, quality: int) -> None:
    im = im.copy()
    im.thumbnail((size, size), Image.LANCZOS)
    im.save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def main(src: Path) -> None:
    credits = json.loads((ROOT / "data" / "yoga" / "photo_credits.json").read_text(encoding="utf-8"))["photos"]
    (OUT / "thumb").mkdir(parents=True, exist_ok=True)
    total = 0
    for slug, photos in credits.items():
        for ph in photos:
            im = ImageOps.exif_transpose(Image.open(src / ph["file"])).convert("RGB")
            save(im, OUT / ph["file"], 800, 80)
            save(im, OUT / "thumb" / ph["file"], 420, 76)
            total += 1
    size = sum(f.stat().st_size for f in OUT.rglob("*.jpg"))
    print(f"{total} photos written, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
