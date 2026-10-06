# FitBot training (Google Colab)

| File | Purpose |
|---|---|
| `FitBot_FineTuning.ipynb` | The Colab notebook: GPU detection → LoRA fine-tuning of SmolLM2-360M-Instruct → base vs fine-tuned evaluation → export |
| `make_notebook.py` | Source of the notebook (edit this, then `python training/make_notebook.py` to regenerate) |
| `requirements.txt` | Packages the notebook installs |

## Quick start

1. Locally: `.venv/bin/python scripts/package_for_colab.py` → creates `FitBot_colab_data.zip`.
2. Upload the zip to Google Drive at **`MyDrive/FitBot/`**.
3. Open `FitBot_FineTuning.ipynb` in Colab, choose **Runtime → Change runtime type → GPU**, then **Runtime → Run all**.
4. When it finishes, download **`fitbot-smollm2-360m-lora-adapter.zip`** (automatic, ≈35 MB) - the full merged package is also saved in `MyDrive/FitBot/`.
5. Locally: `.venv/bin/python scripts/install_model.py ~/Downloads/fitbot-smollm2-360m-lora-adapter.zip` and restart the backend.

Full step-by-step instructions, hyper-parameters and troubleshooting: [`docs/TRAINING_GUIDE.md`](../docs/TRAINING_GUIDE.md).
