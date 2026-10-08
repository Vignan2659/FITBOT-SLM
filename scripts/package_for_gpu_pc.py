"""Create FitBot_4B_Training_Kit.zip for the college GPU PC.

    .venv/bin/python scripts/package_for_gpu_pc.py   ->  FitBot_4B_Training_Kit.zip (project root)

Contents: notebook, setup guide, requirements, environment check, dataset v2 (train/validation/test + test_v1)
and its statistics. Unzip anywhere on the PC and follow COLLEGE_PC_GUIDE.md.
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "FitBot_4B_Training_Kit.zip"
KIT = "FitBot_4B_Training_Kit"
FILES = {
    ROOT / "training" / "FitBot_FineTuning_4B.ipynb": "FitBot_FineTuning_4B.ipynb",
    ROOT / "training" / "COLLEGE_PC_GUIDE.md": "COLLEGE_PC_GUIDE.md",
    ROOT / "training" / "requirements_4b.txt": "requirements_4b.txt",
    ROOT / "training" / "check_gpu_pc.py": "check_gpu_pc.py",
}
for name in ("training.jsonl", "validation.jsonl", "test.jsonl", "test_v1.jsonl", "dataset_stats.json", "README.md"):
    FILES[ROOT / "data" / "processed_v2" / name] = f"data/{name}"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for src, arc in FILES.items():
        z.write(src, f"{KIT}/{arc}")
print(f"{OUT.name}: {OUT.stat().st_size / 1e6:.1f} MB, {len(FILES)} files")
