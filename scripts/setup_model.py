"""Download the FitBot LoRA adapter and merge it into Qwen3-4B-Instruct-2507 -> models/fitbot-qwen3-4b/merged.

    .venv/bin/python scripts/setup_model.py                      # download the adapter from the GitHub release
    .venv/bin/python scripts/setup_model.py --adapter ~/Downloads/fitbot-qwen3-4b-adapter.zip   # local zip
    .venv/bin/python scripts/setup_model.py --adapter https://.../fitbot-qwen3-4b-adapter.zip    # other URL

What it does (skips steps that are already done):
  1. Gets the adapter (~120 MB zip) into models/fitbot-qwen3-4b/adapter/
  2. Downloads the base model Qwen/Qwen3-4B-Instruct-2507 (~8 GB, Hugging Face cache, once)
  3. Merges the LoRA weights into it and saves models/fitbot-qwen3-4b/merged/ (~7.5 GB, bfloat16)
Needs ~16 GB RAM and ~20 GB free disk. Runs on CPU, so any Mac (or Linux/Windows machine) can do it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# FITBOT_SETUP_DIR / FITBOT_SETUP_BASE exist for testing the script with a tiny model
RUN_DIR = Path(os.environ.get("FITBOT_SETUP_DIR", ROOT / "models" / "fitbot-qwen3-4b"))
ADAPTER_DIR = RUN_DIR / "adapter"
MERGED_DIR = RUN_DIR / "merged"
BASE_MODEL = os.environ.get("FITBOT_SETUP_BASE", "Qwen/Qwen3-4B-Instruct-2507")
# Asset attached to the GitHub release (see README "Publishing a release"). Override with FITBOT_ADAPTER_URL.
DEFAULT_ADAPTER_URL = os.environ.get(
    "FITBOT_ADAPTER_URL",
    "https://github.com/Vignan2659/FITBOT-SLM/releases/download/v1.0.0/fitbot-qwen3-4b-adapter.zip")


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        total, done = int(r.headers.get("Content-Length", 0)), 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:6.0f} / {total / 1e6:.0f} MB", end="", flush=True)
    print()


def install_adapter(source: str) -> None:
    """Extract a release zip (adapter/ + fitbot_model_card.json) into models/fitbot-qwen3-4b/."""
    with tempfile.TemporaryDirectory() as tmp:
        if source.startswith(("http://", "https://")):
            zp = Path(tmp) / "adapter.zip"
            download(source, zp)
        else:
            zp = Path(source).expanduser()
            if not zp.exists():
                sys.exit(f"File not found: {zp}")
        with zipfile.ZipFile(zp) as z:
            z.extractall(tmp)
        found = next(Path(tmp).rglob("adapter_config.json"), None)
        if not found:
            sys.exit("The zip has no adapter_config.json - is it the FitBot adapter release asset?")
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        if ADAPTER_DIR.exists():
            shutil.rmtree(ADAPTER_DIR)
        shutil.copytree(found.parent, ADAPTER_DIR)
        card = found.parent.parent / "fitbot_model_card.json"
        if card.exists():
            shutil.copy2(card, RUN_DIR / "fitbot_model_card.json")
    print(f"Adapter installed in {ADAPTER_DIR}")


def merge() -> None:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print(f"Loading base model {BASE_MODEL} (first run downloads ~8 GB) ...")
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, low_cpu_mem_usage=True)
    print("Merging the FitBot LoRA adapter ...")
    model = PeftModel.from_pretrained(base, ADAPTER_DIR).merge_and_unload()
    model.config.use_cache = True
    tmp = MERGED_DIR.with_name("merged.partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    model.save_pretrained(tmp, safe_serialization=True)
    AutoTokenizer.from_pretrained(ADAPTER_DIR).save_pretrained(tmp)
    for card in (ADAPTER_DIR / "fitbot_model_card.json", RUN_DIR / "fitbot_model_card.json"):
        if card.exists():
            shutil.copy2(card, tmp / "fitbot_model_card.json")
            break
    tmp.rename(MERGED_DIR)
    print(f"Merged model saved to {MERGED_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", default=None, help="adapter zip: local path or URL (default: GitHub release)")
    ap.add_argument("--force", action="store_true", help="re-download the adapter and rebuild merged/")
    args = ap.parse_args()
    if (MERGED_DIR / "config.json").exists() and not args.force:
        print(f"Model already installed: {MERGED_DIR}")
        return
    if args.force or args.adapter or not (ADAPTER_DIR / "adapter_config.json").exists():
        install_adapter(args.adapter or DEFAULT_ADAPTER_URL)
    if args.force and MERGED_DIR.exists():
        shutil.rmtree(MERGED_DIR)
    merge()


if __name__ == "__main__":
    main()
