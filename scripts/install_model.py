"""Install a model package exported by the Colab notebook into the local project.

Usage: python scripts/install_model.py ~/Downloads/fitbot-smollm2-360m-lora.zip

Extracts to models/<run_name>/ and copies training results/charts to evaluation/training_run/.
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def merge_adapter(adapter_dir: Path, out_dir: Path) -> None:
    """Merge a LoRA adapter (small download) into its base model locally -> same weights as Colab's merged/."""
    import torch
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer
    print(f"Merging LoRA adapter {adapter_dir} into its base model ...")
    model = AutoPeftModelForCausalLM.from_pretrained(adapter_dir, dtype=torch.float32)
    merged = model.merge_and_unload().to(torch.float16)
    merged.config.use_cache = True
    merged.save_pretrained(out_dir, safe_serialization=True)
    AutoTokenizer.from_pretrained(adapter_dir).save_pretrained(out_dir)
    card = adapter_dir.parent / "fitbot_model_card.json"
    if card.exists():
        shutil.copy2(card, out_dir / "fitbot_model_card.json")
    print(f"Merged model written to {out_dir}")


def main(zip_path: str) -> None:
    zp = Path(zip_path).expanduser()
    if not zp.exists():
        sys.exit(f"File not found: {zp}")
    with zipfile.ZipFile(zp) as z:
        top = {n.split("/")[0] for n in z.namelist()}
        if len(top) != 1:
            sys.exit(f"Unexpected package layout: {top}")
        run = top.pop()
        dest = ROOT / "models" / run
        if dest.exists():
            shutil.rmtree(dest)
        z.extractall(ROOT / "models")
    merged = dest / "merged"
    if not (merged / "config.json").exists():
        if not (dest / "adapter" / "adapter_config.json").exists():
            sys.exit("Package has neither merged/ nor adapter/ - was the notebook run to the end?")
        merge_adapter(dest / "adapter", merged)
    colab_dir = ROOT / "evaluation" / "training_run"
    colab_dir.mkdir(parents=True, exist_ok=True)
    for name in ("results.json", "log_history.json", "loss_curves.png", "training_config.json", "test_predictions.json"):
        if (dest / name).exists():
            shutil.copy2(dest / name, colab_dir / name)
    res = json.loads((dest / "results.json").read_text()) if (dest / "results.json").exists() else {}
    print(f"Installed model to {merged.relative_to(ROOT)}")
    if res:
        print(f"  trained on: {res.get('config', {}).get('gpu_name')} | smoke test: {res.get('smoke_test')}")
        print(f"  test loss: base {res['base']['test']['loss']} -> fine-tuned {res['fine_tuned']['test']['loss']}")
    print(f"Set FITBOT_MODEL_PATH=models/{run}/merged in backend/.env (default) and restart the backend.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
