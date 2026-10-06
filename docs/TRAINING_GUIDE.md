# FitBot – Training Guide (Google Colab GPU)

The FitBot SLM is fine-tuned on a **Google Colab GPU**. The local machine is only used for
dataset preparation, the backend/frontend, testing and local inference.

```
Local project ──(FitBot_colab_data.zip)──► Google Drive ──► Colab GPU: FitBot_FineTuning.ipynb
      ▲                                                            │ LoRA fine-tuning + evaluation
      └──── scripts/install_model.py ◄── fitbot-smollm2-360m-lora-adapter.zip (~35 MB browser download; full merged zip on Drive)
```

## 1. Prepare the data locally

```bash
.venv/bin/python scripts/build_exercise_db.py      # free-exercise-db -> data/exercises (verifies image URLs)
.venv/bin/python scripts/build_food_db.py          # USDA SR Legacy  -> data/nutrition
.venv/bin/python scripts/build_dataset.py          # -> data/processed/{training,validation,test}.jsonl
.venv/bin/python scripts/package_for_colab.py      # -> FitBot_colab_data.zip (≈245 KB)
```

`build_dataset.py` prints the cleaning statistics and verifies there is **no group-level or
text-level overlap** between the training and test splits.

## 2. Run the notebook in Colab

1. Open <https://colab.research.google.com> → *File → Upload notebook* →
   `training/FitBot_FineTuning.ipynb`.
2. *Runtime → Change runtime type → **GPU*** (T4 is enough; L4/A100 are faster).
3. In Google Drive create the folder `MyDrive/FitBot/` and upload `FitBot_colab_data.zip` into it
   (or skip this – the data cell will show an upload button).
4. *Runtime → Run all*. Approve the Google Drive permission prompt.

The notebook never assumes a particular GPU. Cell 2 reads the device name, memory and compute
capability, then picks:

| Detected | Precision | Per-device batch × grad. accumulation |
|---|---|---|
| A100 / H100 (≥ 35 GB) | bf16 | 16 × 1 |
| L4 / A10 (20-35 GB) | bf16 | 8 × 2 |
| T4 / V100 and other GPUs < 20 GB | fp16 (AMP) | 4 × 4 + gradient checkpointing |
| No GPU | fp32 (smoke test only) | 4 × 4 |

## 3. What the notebook does

| # | Step | Details |
|---|---|---|
| 1 | Install | `transformers`, `peft`, `accelerate`, `datasets`, `rouge-score`, `matplotlib` |
| 2 | GPU check | device, memory, precision and batch size (table above) |
| 3 | Config | all hyper-parameters in one `CONFIG` dict (saved to `training_config.json`) |
| 4 | Data | mounts Drive, loads the three splits, asserts no train/test group overlap |
| 5 | Model | `HuggingFaceTB/SmolLM2-360M-Instruct` + tokenizer |
| 6 | Tokenize | ChatML via the tokenizer's chat template; **labels = -100 on the prompt**, loss on the answer only |
| 7 | Baseline | base model validation/test loss + perplexity and generation metrics on the test set |
| 8 | LoRA | r = 16, α = 32, dropout 0.05 on q/k/v/o/gate/up/down projections → 8.7 M trainable params (2.3 %) |
| 9 | Train | cosine LR 2e-4, 5 % warm-up, 3 epochs, eval + checkpoint every half epoch, best-by-validation-loss restored, early stopping (patience 2), checkpoints on Drive (resumable) |
| 10 | Curves | training vs validation loss chart (`loss_curves.png`) |
| 11 | Evaluation | fine-tuned validation/test loss + perplexity; ROUGE-L, token-F1, OOD refusal, safety referral, number grounding, latency; base vs fine-tuned table; per-category ROUGE-L |
| 12 | Save | `adapter/` (LoRA + tokenizer), `merged/` (stand-alone fp16 model + tokenizer), `training_config.json`, `results.json`, `log_history.json`, `test_predictions.json`, reload test |
| 13 | Package | full `MyDrive/FitBot/fitbot-smollm2-360m-lora.zip` (merged + adapter) and small `…-adapter.zip` (auto-downloaded; merged locally by the installer) |

Measured on a Colab Tesla T4: ~3 min baseline evaluation, 471 s (≈8 min) training, ~3 min fine-tuned evaluation,
plus saving/packaging – about 15–20 minutes end to end.

## 4. Install the trained model locally

```bash
.venv/bin/python scripts/install_model.py ~/Downloads/fitbot-smollm2-360m-lora-adapter.zip
```

This extracts to `models/fitbot-smollm2-360m-lora/` and copies the Colab results and charts to
`evaluation/training_run/`. The backend loads `models/fitbot-smollm2-360m-lora/merged` (configurable with
`FITBOT_MODEL_PATH` in `backend/.env`). Then re-run the local evaluation:

```bash
.venv/bin/python evaluation/evaluate.py
.venv/bin/python evaluation/run_test_suites.py
```

## 5. Running the notebook locally (optional)

The same notebook runs on a local machine (CUDA, Apple MPS or CPU). It was verified end-to-end
this way:

```bash
cd training
FITBOT_SMOKE=1 ../.venv/bin/jupyter nbconvert --to notebook --execute FitBot_FineTuning.ipynb --output /tmp/smoke.ipynb
```

`FITBOT_SMOKE=1` trains for 3 steps on a tiny subset (pipeline check only). Without it the full
training runs; on Apple MPS set `FITBOT_GEN_EVAL_LIMIT=24` to cap the *generation* metrics
(PyTorch MPS caches a graph for every new sequence shape during `generate()`, which makes long
batched generation slow and memory-hungry; CUDA GPUs are not affected). `FITBOT_WORK=<dir>`
controls where outputs are written.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `No CUDA GPU detected` warning | Runtime → Change runtime type → GPU, then *Run all* again |
| Session disconnected mid-training | Re-run all cells – training resumes from the last checkpoint in Drive |
| `Dataset not found` | Upload `FitBot_colab_data.zip` to `MyDrive/FitBot/` or use the upload button |
| CUDA out of memory | Restart runtime; the notebook will choose a smaller batch automatically on small GPUs. Otherwise set `PER_DEVICE_BS = 4` in cell 2 |
| `ImportError: Found an incompatible version of torchao` | Fixed in the notebook (setup cell uninstalls Colab's old `torchao`, which FitBot does not use). With an older copy of the notebook run `!pip uninstall -y torchao` and re-run from the LoRA cell |
| CUDA OOM right after a failed cell | A failed cell's traceback keeps GPU tensors alive: *Runtime → Restart session and run all* (data and checkpoints are on Drive) |
| `TrainingArguments` errors | The notebook supports transformers 4.45+ and 5.x; if Colab ships an older version, the first cell upgrades it |
