"""Stage 2: deduplicate, clean, organise and split the exercise-image dataset (data only, no model training).

    .venv/bin/python scripts/image_dataset/extract_features.py   # stage 1 (features, hashes, CLIP embeddings)
    .venv/bin/python scripts/image_dataset/build_dataset.py      # stage 2 (this file)

Duplicate detection
  * exact      : identical SHA-256 file hash
  * similar    : different exercises whose photos differ in <= 3 % of pixels (e.g. the same standing start pose);
                 both are kept, but they are forced into the same split
  * near       : same aspect ratio, CLIP cosine >= 0.90 (prefilter) and <= 1 % of pixels differ by > 30 grey levels
                 at 96x64 (threshold calibrated by visual review: every pair under it was the same photo re-encoded /
                 re-used; above it pairs were genuinely different frames)
  Duplicates are grouped with union-find; one representative per group is kept, the rest go to duplicates/.
Rejection
  * corrupted / undecodable / missing files (automatic)
  * irrelevant: close-ups that do not show the exercise (found by viewing all 1,746 images; listed in IRRELEVANT)
  * very low quality: sharpness/brightness/resolution limits below (none of the source images fell under them;
    small but usable images are kept with a warning)
Splitting
  Whole exercises (both frames) are assigned to one split, and exercises linked by a duplicate group are merged
  into one unit first, so no duplicate or near-duplicate can appear in two splits. 80/10/10 by image count,
  stratified by exercise category, fixed seed.
Nothing is deleted: rejected and duplicate images are copied to rejected/ and duplicates/.
"""
from __future__ import annotations

import collections
import csv
import json
import random
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "data" / "raw" / "free-exercise-db-repo"
OUT = ROOT / "data" / "image_dataset"
WORK = OUT / "work"
SEED = 42
NEAR_FRAC, NEAR_COS, SIMILAR_FRAC = 0.01, 0.90, 0.03
MIN_SIDE, WARN_SIDE, MIN_SHARP, MIN_BRIGHT, MAX_BRIGHT = 128, 400, 30, 12, 245

IRRELEVANT = {  # source path -> reason (visual review)
    "exercises/Bicycling/0.jpg": "close-up of a helmet buckle; exercise not shown",
    "exercises/Bicycling/1.jpg": "close-up of a bicycle seat; exercise not shown",
    "exercises/Skating/0.jpg": "close-up of a helmet; exercise not shown",
}


def norm_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("&", "and")).strip("_")
    return re.sub(r"_+", "_", s)


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def main() -> None:
    F = json.loads((WORK / "features.json").read_text())
    rows = F["images"]
    E = np.load(WORK / "clip_image.npy")
    n = len(rows)

    # ---------------- quality
    for r in rows:
        r["normalized_exercise"] = norm_name(r["exercise"])
        r["filename"] = f"{r['normalized_exercise']}_{r['frame']}.jpg"
        notes = []
        if "error" in r:
            status = "rejected_corrupt"
            notes.append(r["error"])
        elif r["source"] in IRRELEVANT:
            status = "rejected_irrelevant"
            notes.append(IRRELEVANT[r["source"]])
        elif min(r["width"], r["height"]) < MIN_SIDE or r["sharpness"] < MIN_SHARP or not MIN_BRIGHT <= r["brightness"] <= MAX_BRIGHT:
            status = "rejected_low_quality"
            notes.append(f"{r['width']}x{r['height']} sharpness {r['sharpness']} brightness {r['brightness']}")
        elif min(r["width"], r["height"]) < WARN_SIDE:
            status = "ok_low_resolution"
            notes.append(f"small image {r['width']}x{r['height']} (kept)")
        else:
            status = "ok"
        r["quality_status"], r["notes"] = status, "; ".join(notes)

    # ---------------- duplicates
    valid = [i for i, r in enumerate(rows) if "idx" in r]
    dsu, method = DSU(n), {}
    by_sha = collections.defaultdict(list)
    for i in valid:
        by_sha[rows[i]["sha256"]].append(i)
    for g in by_sha.values():
        for j in g[1:]:
            dsu.union(g[0], j)
            method[(g[0], j)] = "exact"
    idx2row = {rows[i]["idx"]: i for i in valid}
    S = E @ E.T
    small = {}

    def px(i):
        if i not in small:
            with Image.open(REPO / rows[i]["source"]) as im:
                small[i] = np.asarray(im.convert("L").resize((96, 64), Image.BILINEAR), dtype=np.float32)
        return small[i]

    near_pairs, similar = 0, []
    for a in range(len(E)):
        for b in range(a + 1, len(E)):
            if S[a, b] < NEAR_COS:
                continue
            i, j = idx2row[a], idx2row[b]
            ri, rj = rows[i], rows[j]
            ar_i, ar_j = ri["width"] / ri["height"], rj["width"] / rj["height"]
            if abs(ar_i - ar_j) / ar_i > 0.03 or dsu.find(i) == dsu.find(j):
                continue
            frac = (np.abs(px(i) - px(j)) > 30).mean()
            if frac <= NEAR_FRAC:
                dsu.union(i, j)
                near_pairs += 1
            elif frac <= SIMILAR_FRAC and ri["exercise_id"] != rj["exercise_id"]:
                similar.append((i, j))
    groups = collections.defaultdict(list)
    for i in valid:
        groups[dsu.find(i)].append(i)
    gid = 0
    for members in sorted(groups.values(), key=lambda g: rows[g[0]]["source"]):
        if len(members) == 1:
            r = rows[members[0]]
            r["duplicate_status"], r["duplicate_group"] = "unique", ""
            continue
        gid += 1
        exact = len({rows[m]["sha256"] for m in members}) == 1
        # representative: a usable image, preferring the exercise whose name sorts first (deterministic)
        cand = [m for m in members if rows[m]["quality_status"].startswith("ok")] or members
        rep = min(cand, key=lambda m: (rows[m]["exercise_id"], rows[m]["frame"]))
        names = sorted({rows[m]["exercise_id"] for m in members})
        for m in members:
            r = rows[m]
            r["duplicate_group"] = f"dup_{gid:03d}"
            kind = "exact" if exact else "near"
            r["duplicate_status"] = f"{kind}_kept" if m == rep else f"{kind}_duplicate"
            if len(names) > 1:
                r["notes"] = "; ".join(x for x in (r["notes"], f"same photo used by: {', '.join(names)}") if x)
    sdsu = DSU(n)
    for i, j in similar:
        sdsu.union(i, j)
    sg = collections.defaultdict(list)
    for i, j in similar:
        sg[sdsu.find(i)] += [i, j]
    for k, members in enumerate(sorted(sg.values(), key=lambda g: rows[min(g)]["source"]), 1):
        for m in set(members):
            r = rows[m]
            if r.get("duplicate_status") == "unique":
                r["duplicate_status"], r["duplicate_group"] = "similar_kept", f"sim_{k:03d}"
                others = sorted({rows[x]["exercise_id"] for x in members} - {r["exercise_id"]})
                r["notes"] = "; ".join(x for x in (r["notes"], f"near-identical pose to: {', '.join(others)} (same split)") if x)
    for r in rows:
        r.setdefault("duplicate_status", "n/a")
        r.setdefault("duplicate_group", "")
        r["final_status"] = ("clean" if r["quality_status"].startswith("ok") and not r["duplicate_status"].endswith("_duplicate")
                             else "duplicate" if r["quality_status"].startswith("ok") else "rejected")

    # ---------------- split units: exercises merged through duplicate groups
    ex_ids = sorted({r["exercise_id"] for r in rows})
    eid = {e: k for k, e in enumerate(ex_ids)}
    udsu = DSU(len(ex_ids))
    for g in groups.values():
        for m in g[1:]:
            udsu.union(eid[rows[g[0]]["exercise_id"]], eid[rows[m]["exercise_id"]])
    for i, j in similar:
        udsu.union(eid[rows[i]["exercise_id"]], eid[rows[j]["exercise_id"]])
    units = collections.defaultdict(list)
    for e in ex_ids:
        units[udsu.find(eid[e])].append(e)
    clean_count = collections.Counter(r["exercise_id"] for r in rows if r["final_status"] == "clean")
    cat_of = {r["exercise_id"]: r["category"] for r in rows}
    rng = random.Random(SEED)
    by_cat = collections.defaultdict(list)
    for u in units.values():
        size = sum(clean_count[e] for e in u)
        if size:
            by_cat[cat_of[u[0]]].append((u, size))
    split_of = {}
    for cat in sorted(by_cat):
        us = by_cat[cat]
        rng.shuffle(us)
        us.sort(key=lambda x: -x[1])               # large merged units first, then greedy fill toward 80/10/10
        total = sum(s for _, s in us)
        target = {"train": .8 * total, "validation": .1 * total, "test": .1 * total}
        have = dict.fromkeys(target, 0)
        for u, s in us:
            sp = max(target, key=lambda k: (target[k] - have[k]) / target[k])
            have[sp] += s
            for e in u:
                split_of[e] = sp
    for r in rows:
        r["split"] = split_of.get(r["exercise_id"], "") if r["final_status"] == "clean" else ""

    # leakage checks
    for g in list(groups.values()) + [[i, j] for i, j in similar]:
        sp = {split_of.get(rows[m]["exercise_id"]) for m in g}
        assert len(sp - {None}) <= 1, ("duplicate/similar group crosses splits", g)
    for e in ex_ids:
        assert len({r["split"] for r in rows if r["exercise_id"] == e and r["split"]}) <= 1

    # ---------------- copy files (originals untouched; nothing deleted)
    for sub in ("clean", "duplicates", "rejected"):
        d = OUT / sub
        if d.exists():
            shutil.rmtree(d)           # only this script's own generated output
    for r in rows:
        if r["final_status"] == "clean":
            rel = Path("clean") / r["split"] / r["normalized_exercise"] / r["filename"]
        elif r["final_status"] == "duplicate":
            rel = Path("duplicates") / r["duplicate_group"] / r["filename"]
        else:
            rel = Path("rejected") / r["quality_status"].replace("rejected_", "") / r["filename"]
        r["dataset_path"] = str(rel)
        if (REPO / r["source"]).exists():
            (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / r["source"], OUT / rel)

    # ---------------- manifest (CSV + JSON)
    cols = ["filename", "exercise", "normalized_exercise", "exercise_id", "frame", "category", "level", "equipment",
            "primary_muscles", "resolution", "width", "height", "bytes", "quality_status", "sharpness", "brightness",
            "duplicate_status", "duplicate_group", "final_status", "split", "dataset_path", "source", "sha256",
            "phash", "notes"]
    out_rows = []
    for r in rows:
        o = {c: r.get(c, "") for c in cols}
        o["resolution"] = f"{r.get('width', '')}x{r.get('height', '')}"
        o["primary_muscles"] = ", ".join(r.get("primary_muscles") or [])
        out_rows.append(o)
    with open(OUT / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)
    (OUT / "manifest.json").write_text(json.dumps(out_rows, indent=1))
    ex_meta = json.loads((REPO / "dist" / "exercises.json").read_text())
    exercises = []
    for e in ex_meta:
        ims = [r for r in rows if r["exercise_id"] == e["id"] and r["final_status"] == "clean"]
        if ims:
            exercises.append({"exercise": e["name"], "normalized_exercise": norm_name(e["name"]), "exercise_id": e["id"],
                              "split": ims[0]["split"], "images": [r["dataset_path"] for r in ims],
                              "category": e.get("category"), "level": e.get("level"), "equipment": e.get("equipment"),
                              "primary_muscles": e.get("primaryMuscles"), "secondary_muscles": e.get("secondaryMuscles"),
                              "instructions": e.get("instructions")})
    (OUT / "exercises.json").write_text(json.dumps(exercises, indent=1))
    write_report(rows, exercises, F, near_pairs)
    print(f"similar cross-exercise pairs kept together: {len(similar)}")


def write_report(rows, exercises, F, near_pairs) -> None:
    C = collections.Counter
    st = C(r["final_status"] for r in rows)
    q = C(r["quality_status"] for r in rows)
    d = C(r["duplicate_status"] for r in rows)
    sp = C(r["split"] for r in rows if r["split"])
    spx = C(e["split"] for e in exercises)
    per_ex = C(r["exercise_id"] for r in rows if r["final_status"] == "clean")
    hist = C(per_ex.values())
    groups = collections.defaultdict(list)
    for r in rows:
        if r["duplicate_group"]:
            groups[r["duplicate_group"]].append(r)
    cats = collections.defaultdict(C)
    for r in rows:
        if r["split"]:
            cats[r["category"]][r["split"]] += 1
    L = ["# Exercise image dataset – cleaning report", "",
         "Source: [free-exercise-db](https://github.com/yuhonas/free-exercise-db) (Unlicense / public domain), "
         f"commit cloned to `data/raw/free-exercise-db-repo`. Data collection and cleaning only – **no model was trained**.", "",
         "## Totals", "", "| | Count |", "|---|---:|",
         f"| Exercises in source metadata | {len(F['exercise_ids'])} |",
         f"| Exercises with no image in source | {len(F['exercises_without_images'])} ({', '.join(x['exercise'] for x in F['exercises_without_images'])}) |",
         f"| Images in source | {len(rows)} |",
         f"| **Clean images (final dataset)** | **{st['clean']}** |",
         f"| **Unique exercises in final dataset** | **{len(exercises)}** |",
         f"| Duplicate images moved to `duplicates/` | {st['duplicate']} |",
         f"| Rejected images moved to `rejected/` | {st['rejected']} |", "",
         "## Duplicates", "", "| Type | Groups | Images kept | Images set aside |", "|---|---:|---:|---:|"]
    for kind in ("exact", "near", "similar"):
        g = {r["duplicate_group"] for r in rows if r["duplicate_status"].startswith(kind)}
        L.append(f"| {kind.capitalize()} | {len(g)} | {d[kind + '_kept']} | {d.get(kind + '_duplicate', 0)} |")
    L += ["", "Exact = identical file hash (SHA-256). Near = same photo re-saved / re-used (≤ 1 % of pixels differ after "
          "downscaling, CLIP similarity ≥ 0.90), calibrated by viewing the candidate pairs. Perceptual hashes (pHash, "
          "dHash) are stored in the manifest; on their own they flagged many *different* photos taken in the same "
          "studio, so they were not used as the deciding test. Similar = different exercises whose start photos are almost "
          "identical (<= 3 % of pixels differ); both are kept but always placed in the same split. The two frames of one "
          "exercise (start / end position) are never treated as duplicates and always share a split.", "",
          "| Group | Kept image | Duplicates set aside |", "|---|---|---|"]
    for g, ms in sorted(groups.items()):
        if g.startswith("sim_"):
            L.append(f"| {g} (similar, all kept) | {', '.join(m['source'].split('/', 1)[1] for m in ms)} | - |")
            continue
        kept = [m["source"].split("/", 1)[1] for m in ms if m["duplicate_status"].endswith("_kept")]
        dup = [m["source"].split("/", 1)[1] for m in ms if m["duplicate_status"].endswith("_duplicate")]
        L.append(f"| {g} | {', '.join(kept)} | {', '.join(dup)} |")
    L += ["", "## Quality check", "", "| Status | Images |", "|---|---:|"]
    for k, v in sorted(q.items()):
        L.append(f"| {k} | {v} |")
    L += ["", "Every image was decoded fully (no corrupted files) and every image was viewed. Rejected as irrelevant:", ""]
    for r in rows:
        if r["quality_status"] == "rejected_irrelevant":
            L.append(f"* `{r['source']}` – {r['notes'].split(';')[0]}")
    L += ["", "Images that appear under more than one exercise name (start-position photos shared between stretches, "
          "etc.) are kept once and noted in the manifest's `notes` column; they are not mislabelled, the source reuses "
          "the same photo for related movements.", "",
          "## Splits (no exercise and no duplicate group appears in more than one split)", "",
          "| Split | Images | Exercises |", "|---|---:|---:|"]
    tot = sum(sp.values())
    for s in ("train", "validation", "test"):
        L.append(f"| {s} | {sp[s]} ({sp[s] / tot:.1%}) | {spx[s]} |")
    L += ["", "| Category | Train | Validation | Test |", "|---|---:|---:|---:|"]
    for c in sorted(cats):
        L.append(f"| {c} | {cats[c]['train']} | {cats[c]['validation']} | {cats[c]['test']} |")
    L += ["", "## Images per exercise (clean set)", "", "| Images per exercise | Exercises |", "|---:|---:|"]
    for k in sorted(hist):
        L.append(f"| {k} | {hist[k]} |")
    L += ["", "Full per-exercise list with split and image paths: `exercises.json`; per-image details: `manifest.csv` / "
          "`manifest.json` (filename, exercise, resolution, quality status, duplicate status, duplicate group, split).", "",
          "## Folder layout", "", "```", "data/image_dataset/",
          "  clean/{train,validation,test}/<normalized_exercise>/<normalized_exercise>_<frame>.jpg",
          "  duplicates/<duplicate_group>/...        (set aside, not deleted)",
          "  rejected/<reason>/...                    (set aside, not deleted)",
          "  manifest.csv  manifest.json  exercises.json  REPORT.md", "```", "",
          "Rebuild: `.venv/bin/python scripts/image_dataset/extract_features.py && .venv/bin/python scripts/image_dataset/build_dataset.py`"]
    (OUT / "REPORT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:25]))


if __name__ == "__main__":
    main()
