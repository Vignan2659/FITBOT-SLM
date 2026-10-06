"""Zip the processed dataset for upload to Google Drive / Colab.

Usage: python scripts/package_for_colab.py   ->  FitBot_colab_data.zip (project root)
Upload the zip to MyDrive/FitBot/ (or upload it when the notebook asks).
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed"
OUT = ROOT / "FitBot_colab_data.zip"
FILES = ["training.jsonl", "validation.jsonl", "test.jsonl", "dataset_stats.json"]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name in FILES:
        z.write(SRC / name, name)
print(f"Wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB) containing {FILES}")
print("Next: upload it to Google Drive at MyDrive/FitBot/ and open training/FitBot_FineTuning.ipynb in Colab.")
