"""Prepare downloaded yoga photos for the web app.

    python3 scripts/yoga/process_photos.py <folder with <slug>-<n>.jpg originals>

Every photo is placed on the same 3:2 canvas so the frames of one pose line up when the app plays them as a short
motion (start position, then the pose). Landscape photos are scaled to the canvas; upright photos keep their full
height and the wall and floor are continued sideways from the photo's own edges. Writes
frontend/public/yoga/photos/<slug>-<n>.jpg (900 x 600, for pose pages) and
frontend/public/yoga/photos/thumb/<slug>-<n>.jpg (480 x 320, for cards). Needs Pillow.
Only files listed in data/yoga/photo_credits.json are processed, so every published photo has a credit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "public" / "yoga" / "photos"
W, H = 900, 600


def canvas(im: Image.Image) -> Image.Image:
    """Fit a photo on the shared 3:2 canvas without cutting off the person."""
    if im.width / im.height >= 1.3:                         # landscape: trim to 3:2 around the centre
        return ImageOps.fit(im, (W, H), Image.LANCZOS, centering=(0.5, 0.5))
    fg = im.resize((round(im.width * H / im.height), H), Image.LANCZOS)
    out = Image.new("RGB", (W, H))
    x0 = (W - fg.width) // 2
    # continue the wall and floor sideways from the photo's own edge columns, softened so no seam shows
    out.paste(fg.crop((0, 0, 12, H)).resize((x0, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)), (0, 0))
    right = W - x0 - fg.width
    out.paste(fg.crop((fg.width - 12, 0, fg.width, H)).resize((right, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)),
              (x0 + fg.width, 0))
    out.paste(fg, (x0, 0))
    return out


def main(src: Path) -> None:
    credits = json.loads((ROOT / "data" / "yoga" / "photo_credits.json").read_text(encoding="utf-8"))["photos"]
    for old in OUT.rglob("*.jpg"):
        old.unlink()
    (OUT / "thumb").mkdir(parents=True, exist_ok=True)
    total = 0
    for photos in credits.values():
        for ph in photos:
            im = canvas(ImageOps.exif_transpose(Image.open(src / ph["file"])).convert("RGB"))
            im.save(OUT / ph["file"], "JPEG", quality=80, optimize=True, progressive=True)
            im.resize((480, 320), Image.LANCZOS).save(OUT / "thumb" / ph["file"], "JPEG", quality=76, optimize=True,
                                                      progressive=True)
            total += 1
    size = sum(f.stat().st_size for f in OUT.rglob("*.jpg"))
    print(f"{total} photos written, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
