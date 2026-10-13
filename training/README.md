# FitBot training

| File | Purpose |
|---|---|
| `FitBot_FineTuning_4B.ipynb` | QLoRA fine tuning of Qwen3-4B-Instruct-2507 on dataset v2, base vs fine tuned evaluation, export (NVIDIA GPU) |
| `make_notebook_4b.py` | Source of the notebook (edit this, then run it to regenerate the notebook) |
| `requirements_4b.txt` | Packages for training (install the CUDA build of PyTorch first) |
| `runs/FitBot_FineTuning_4B_full_run.ipynb` | The executed notebook of the released model, with all outputs |

Full guide, settings and troubleshooting: [`docs/TRAINING_GUIDE.md`](../docs/TRAINING_GUIDE.md).
Training needs an NVIDIA GPU (12 GB or more). Running the trained model works on a Mac (see the main README).
