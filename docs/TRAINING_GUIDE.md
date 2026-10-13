# FitBot – Training Guide (Qwen3-4B + QLoRA)

You only need this guide to **re-train** the model. To *use* FitBot, the README's Quick start downloads the
ready-made adapter.

**Model:** `Qwen/Qwen3-4B-Instruct-2507`: 4.0 B parameters, Apache-2.0, text-only, answers directly (no
"thinking" output), ChatML chat format.
**Method:** QLoRA. The base model is loaded in 4-bit NF4 with bitsandbytes and LoRA adapters are trained in bf16
(r = 16, alpha = 32, dropout 0.05, all attention and MLP projections, about 33 M trainable parameters).
**Data:** FitBot dataset v2 (`data/processed_v2/`): 5,470 conversations (4,382 train / 527 validation / 561 test).
Each record has a ready-made `messages` field built by the app's own prompt builder, and the loss is on
assistant tokens only.

> QLoRA (bitsandbytes 4-bit) needs an **NVIDIA GPU with CUDA**, so training cannot run on a Mac.
> Use a Linux/WSL2 PC with an NVIDIA GPU (≥ 12 GB VRAM) or a cloud GPU such as Google Colab (L4/A100).

## Hyper-parameters (as used for the released model)

| Setting | Value |
|---|---|
| Epochs | 2 (early stopping, patience 3 evaluations; best checkpoint kept) |
| Learning rate / schedule | 1e-4, cosine, 3 % warm-up |
| Effective batch | 16 (micro-batch 2 × gradient accumulation 8) |
| Max sequence length | 1,280 tokens |
| Optimizer | `paged_adamw_8bit`, gradient checkpointing |
| Evaluation | every half epoch on the validation set |

The released run took **76 min** of training on an RTX 4070 (12 GB), peak GPU memory 9.8 GB. Validation loss per
half epoch was 0.613 → **0.551** (best, end of epoch 1) → 0.600 → 0.592, so the epoch-1 checkpoint was kept.

## Steps

```bash
# on the GPU machine, in the project folder
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   # CUDA build - see pytorch.org
pip install -r training/requirements_4b.txt
nvidia-smi                                                            # the GPU must be listed
jupyter notebook training/FitBot_FineTuning_4B.ipynb
```

1. **Smoke test:** Section 0 has `FITBOT_SMOKE = "1"`. *Run All*. It downloads the model (~8 GB), loads it in
   4-bit, trains 4 steps, evaluates a few questions and saves a small adapter. It must finish without errors.
2. **Full run:** set Section 0 to `os.environ.setdefault("FITBOT_SMOKE", "0")`, restart the kernel and *Run All*.
   If it stops, run all again: training resumes from the last checkpoint in `outputs/fitbot-qwen3-4b-qlora/checkpoints/`.
3. **CUDA out of memory:** in Section 0 uncomment `FITBOT_BATCH = "1"` and `FITBOT_MAX_LEN = "1024"`, restart and
   *Run All* (the effective batch stays 16).

Time on an RTX 4070: model download 5-15 min, baseline evaluation 10-20 min, training 40-100 min, fine-tuned
evaluation 10-20 min, merge 5-15 min.

The notebook is generated from `training/make_notebook_4b.py` (edit that file, then run it to regenerate).
`training/runs/FitBot_FineTuning_4B_full_run.ipynb` is the executed notebook of the released run, with all outputs.

## Outputs

`outputs/fitbot-qwen3-4b-qlora/` contains `adapter/` (LoRA adapter + tokenizer), `merged/` (optional full
16-bit model), `results.json`, `base_results.json`, `log_history.json`, `loss_curves.png`,
`test_predictions.json` and `training_config.json`.

## Using a new run in the app

1. Zip the adapter the same way as the release asset (an `adapter/` folder plus `fitbot_model_card.json`).
2. `.venv/bin/python scripts/setup_model.py --adapter path/to/your-adapter.zip --force`
3. Copy the result files to `evaluation/training_run_4b/` and re-run `evaluation/run_test_suites.py`.

## Rebuilding the dataset

```bash
.venv/bin/python scripts/build_exercise_catalog_v2.py    # 871 cleaned exercises
.venv/bin/python scripts/build_dataset_v2.py             # data/processed_v2/*.jsonl
```

The previous model (SmolLM2-360M + LoRA, trained on Google Colab on dataset v1) is documented in
[MODEL_SELECTION.md](MODEL_SELECTION.md) and [EVALUATION.md](EVALUATION.md); its results are in
`evaluation/training_run_360m/`, and its notebook is in the git history.
