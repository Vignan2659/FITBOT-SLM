# FitBot 4B – fine-tuning on the college GPU PC

**Model:** `Qwen/Qwen3-4B-Instruct-2507` – 4.0 B parameters, Apache-2.0, no sign-up gate, text-only, answers
directly (no "thinking" output), same ChatML chat format as the current FitBot model.
**Method:** QLoRA – the base model is loaded in 4-bit (NF4) and small LoRA adapters (r = 16, all attention + MLP
layers, ~33 M trainable parameters) are trained in bf16.
**Data:** FitBot dataset v2 – 5,470 conversations (4,382 train / 527 validation / 561 test).

**PC:** Intel i7-14700K · 32 GB RAM · NVIDIA RTX 4070 (12 GB) · Windows.

## Why this model

| Candidate | Size | Verdict |
|---|---|---|
| **Qwen3-4B-Instruct-2507** | 4.0 B | **Chosen.** Strong 4B instruction model, Apache-2.0, text-only, no thinking mode, works with standard `transformers` + 4-bit QLoRA, fits 12 GB comfortably. |
| Qwen3.5-4B | 4 B | Newer, but multimodal with a new architecture that needs the latest `transformers` and extra GPU kernels (hard on Windows), and Unsloth advises against 4-bit QLoRA for it. Riskier for a first run. |
| Phi-4-mini-instruct | 3.8 B | Good alternative (MIT). To try it, set `FITBOT_BASE_MODEL=microsoft/Phi-4-mini-instruct` (the LoRA module names differ – use `target_modules="all-linear"`). |
| Qwen3.8 family | 27 B and larger | No small model; does not fit a 12 GB GPU. |

## Time estimate (RTX 4070, QLoRA)

The training data is **1.39 M tokens per epoch** (measured with the Qwen tokenizer; mean 317 tokens/example).

| Step | Time |
|---|---|
| Setup + package installs | 15-30 min (first time) |
| Model download (~8 GB) | 5-15 min, depends on the network |
| Smoke test (Section 0 = "1") | 3-5 min after the download |
| Baseline evaluation | 10-20 min |
| **Training, 2 epochs (~550 optimizer steps)** | **~40-100 min** |
| Fine-tuned evaluation | 10-20 min |
| Merge + save full model (optional) | 5-15 min |
| **Total for the full run** | **about 1.5-3 hours** |

These are estimates. The real speed shows in the progress bar after the first ~10 steps. If a session ends,
re-run the notebook: training resumes from the last checkpoint.

## 1. Setup (Windows)

1. **NVIDIA driver:** open a terminal and run `nvidia-smi`. It should list the RTX 4070. If not, install the
   current Game Ready / Studio driver from nvidia.com.
2. **Python 3.11 or 3.12** from python.org (tick "Add python.exe to PATH").
3. Copy the kit folder `FitBot_4B_Training_Kit` somewhere with ≥ 30 GB free (e.g. `D:\FitBot4B`), then in a
   terminal (PowerShell) inside that folder:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   # PyTorch with CUDA - pick the command for "Windows / Pip / CUDA" on https://pytorch.org/get-started/locally/
   # e.g.:
   pip install torch --index-url https://download.pytorch.org/whl/cu128
   pip install -r requirements_4b.txt
   python check_gpu_pc.py
   ```

   All lines should say PASS (WARN is OK to read and decide). If PyTorch "cannot see a CUDA GPU", you installed
   the CPU build - reinstall with the `--index-url` line above.

   *Linux / WSL2:* the same steps with `source .venv/bin/activate` work; in WSL2 install the NVIDIA driver on
   Windows only (not inside WSL).

4. **Optional – model download in advance / blocked network:** on any machine with internet run
   `huggingface-cli download Qwen/Qwen3-4B-Instruct-2507 --local-dir Qwen3-4B-Instruct-2507` and copy that
   folder into the kit. Then before starting Jupyter set
   `$env:FITBOT_BASE_MODEL = "Qwen3-4B-Instruct-2507"` (PowerShell).

## 2. Run

```powershell
.venv\Scripts\activate
jupyter notebook FitBot_FineTuning_4B.ipynb
```

1. **Smoke test:** leave Section 0 as `os.environ.setdefault("FITBOT_SMOKE", "1")` and *Run → Run All Cells*.
   It downloads the model, loads it in 4-bit, trains 4 steps, evaluates a few questions and saves an adapter.
   If this finishes without errors, the full run will work.
2. **Full run:** change Section 0 to `"0"`, then *Kernel → Restart & Run All*. Keep the PC awake (disable sleep).
3. Watch: the training progress bar (time remaining) and the validation loss printed every half epoch - it should
   go down and stay below the base model's value shown in the loss-curve plot.

**If you see "CUDA out of memory":** close other GPU programs, then in Section 0 uncomment the two lines
`FITBOT_BATCH = "1"` and `FITBOT_MAX_LEN = "1024"` and choose *Kernel → Restart & Run All* (training resumes; the
effective batch stays 16).

## 3. What to bring home

`fitbot-qwen3-4b-qlora-adapter.zip` (~130 MB) in the kit folder - the trained LoRA adapter, tokenizer, model card,
`results.json` (all metrics), `base_results.json`, `log_history.json`, `loss_curves.png`, `test_predictions.json`.
The merged 16-bit model is in `outputs/fitbot-qwen3-4b-qlora/merged/` (~8 GB) - copy it too if you have space;
otherwise it can be re-created at home from the base model + adapter.

## 4. After training (at home)

* Results for the report: `results.json` → base vs fine-tuned loss/perplexity, generation metrics on the 97
  original v1 test questions (directly comparable with the 360M model's ROUGE-L 0.488 / token-F1 0.537) and on
  new v2 test questions, plus per-category ROUGE-L.
* Using the 4B model in the FitBot app is a separate step (load the merged model or base + adapter, then re-run
  `evaluation/run_test_suites.py`). Keep the current 360M model as the fallback and switch only if the 4B model
  scores better. Note that a 4B model runs slower on a laptop than the 360M model.
