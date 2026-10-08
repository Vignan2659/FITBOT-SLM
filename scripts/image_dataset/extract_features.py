"""Stage 1 of the exercise-image dataset audit: per-image features (no model training).

Source: free-exercise-db (Unlicense / public domain), cloned to data/raw/free-exercise-db-repo.
For every image: integrity check (PIL verify + full decode), resolution, file size, SHA-256, perceptual hashes
(pHash = DCT, dHash = gradient), brightness / contrast / sharpness (variance of the Laplacian) and a CLIP
image embedding (sentence-transformers clip-ViT-B-32) used only for near-duplicate confirmation and label checks.

Writes data/image_dataset/work/features.json and clip_image.npy (+ clip_text.npy for the exercise labels).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.fft import dctn
from scipy.ndimage import laplace

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "data" / "raw" / "free-exercise-db-repo"
WORK = ROOT / "data" / "image_dataset" / "work"


def phash(gray: Image.Image) -> int:
    a = np.asarray(gray.resize((32, 32), Image.LANCZOS), dtype=np.float64)
    d = dctn(a, norm="ortho")[:8, :8].flatten()
    med = np.median(d[1:])                      # ignore the DC term
    return int("".join("1" if v > med else "0" for v in d), 2)


def dhash(gray: Image.Image) -> int:
    a = np.asarray(gray.resize((9, 8), Image.LANCZOS), dtype=np.int16)
    return int("".join("1" if v else "0" for v in (a[:, 1:] > a[:, :-1]).flatten()), 2)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    meta = json.loads((REPO / "dist" / "exercises.json").read_text())
    rows, ok_imgs = [], []
    for ex in meta:
        for rel in ex.get("images") or []:
            p = REPO / "exercises" / rel
            r = {"source": f"exercises/{rel}", "exercise_id": ex["id"], "exercise": ex["name"], "frame": Path(rel).stem,
                 "category": ex.get("category"), "level": ex.get("level"), "equipment": ex.get("equipment"),
                 "primary_muscles": ex.get("primaryMuscles") or [], "exists": p.exists()}
            if not p.exists():
                r["error"] = "missing file"
                rows.append(r)
                continue
            raw = p.read_bytes()
            r["bytes"], r["sha256"] = len(raw), hashlib.sha256(raw).hexdigest()
            try:
                with Image.open(p) as im:
                    im.verify()
                with Image.open(p) as im:
                    im.load()
                    r["format"], r["mode"] = im.format, im.mode
                    r["width"], r["height"] = im.size
                    rgb = im.convert("RGB")
            except Exception as e:  # corrupted / truncated
                r["error"] = f"decode failed: {e}"
                rows.append(r)
                continue
            g = rgb.convert("L")
            r["phash"], r["dhash"] = f"{phash(g):016x}", f"{dhash(g):016x}"
            small = g.copy()
            small.thumbnail((512, 512))
            a = np.asarray(small, dtype=np.float64)
            r["brightness"], r["contrast"] = round(float(a.mean()), 2), round(float(a.std()), 2)
            r["sharpness"] = round(float(laplace(a).var()), 2)
            r["idx"] = len(ok_imgs)
            ok_imgs.append(rgb)
            rows.append(r)
    # exercises listed in the metadata without any image
    no_img = [{"exercise_id": e["id"], "exercise": e["name"]} for e in meta if not e.get("images")]
    print(f"{len(rows)} image records, {len(ok_imgs)} decoded, {len(no_img)} exercises without images")

    from sentence_transformers import SentenceTransformer
    clip = SentenceTransformer("clip-ViT-B-32", device="cpu")
    emb = clip.encode(ok_imgs, batch_size=32, normalize_embeddings=True, show_progress_bar=True, convert_to_numpy=True)
    np.save(WORK / "clip_image.npy", emb.astype(np.float32))
    labels = [f"a photo of a person doing the {e['name']} exercise" for e in meta]
    tem = clip.encode(labels, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
    np.save(WORK / "clip_text.npy", tem.astype(np.float32))
    probes = ["a photo of a person exercising", "a photo of a person lifting weights", "a photo of a person stretching",
              "gym equipment with no person", "a blank or empty image", "text, a logo or a diagram",
              "a cartoon or drawing", "a landscape photo", "food on a plate", "a screenshot of a website"]
    np.save(WORK / "clip_probes.npy", clip.encode(probes, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32))
    (WORK / "features.json").write_text(json.dumps({"images": rows, "exercises_without_images": no_img,
                                                    "exercise_ids": [e["id"] for e in meta], "probes": probes}, indent=1))
    print("features ->", WORK)


if __name__ == "__main__":
    main()
