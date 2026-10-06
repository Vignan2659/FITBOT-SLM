"""Generates training/FitBot_FineTuning.ipynb (run: python training/make_notebook.py).

The notebook is written for Google Colab (GPU + Google Drive) but also runs locally
(CPU / Apple MPS) so it can be smoke-tested: set FITBOT_SMOKE=1 for a tiny run.
"""
from pathlib import Path

import nbformat as nbf

cells: list = []


def md(s: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s: str) -> None:
    cells.append(nbf.v4.new_code_cell(s.strip()))


md("""
# FitBot – Fine-tuning a Fitness Small Language Model (SmolLM2-360M + LoRA)

This notebook fine-tunes **`HuggingFaceTB/SmolLM2-360M-Instruct`** on the FitBot conversational
dataset with **LoRA (PEFT)** on a Google Colab GPU, evaluates the **base vs fine-tuned** model on the
held-out test set, and exports the trained model for the local FitBot app.

**Before you start (Colab):**
1. `Runtime → Change runtime type → GPU` (T4, L4 or A100 – the notebook adapts to whichever you get).
2. Upload `FitBot_colab_data.zip` (created locally with `python scripts/package_for_colab.py`) to
   `MyDrive/FitBot/` in Google Drive, **or** upload it when the data cell asks.
3. `Runtime → Run all`. Checkpoints and final artifacts are saved to `MyDrive/FitBot/outputs/`, so they
   persist after the session ends.

| Step | Section |
|---|---|
| 1 | Install dependencies |
| 2 | Check GPU and choose precision / batch size |
| 3 | Configuration |
| 4 | Mount Google Drive + load train/validation/test data |
| 5 | Load base model + tokenizer |
| 6 | Tokenize (loss on assistant tokens only) |
| 7 | Baseline evaluation of the **base** model |
| 8 | Configure LoRA |
| 9 | Train (monitor training + validation loss) |
| 10 | Loss curves |
| 11 | Validation + test evaluation of the **fine-tuned** model, metrics, base vs fine-tuned |
| 12 | Save adapter, merged model, tokenizer, config, results |
| 13 | Package / export + download instructions |
""")

md("## 1. Install dependencies")
code("""
import os, sys, subprocess
IN_COLAB = "google.colab" in sys.modules or os.path.exists("/content")
SMOKE = os.environ.get("FITBOT_SMOKE", "0") == "1"   # tiny local test run
if IN_COLAB:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "transformers>=4.45", "peft>=0.12", "accelerate>=0.33", "datasets>=2.20",
                    "rouge-score>=0.1.2", "matplotlib"], check=True)
    # Colab images may ship an old torchao that recent PEFT rejects at import time ("only versions above
    # 0.16.0 are supported"). FitBot does not use torchao, so remove it.
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"], check=False)
import torch, transformers, peft, datasets
print("python", sys.version.split()[0], "| torch", torch.__version__, "| transformers", transformers.__version__,
      "| peft", peft.__version__, "| datasets", datasets.__version__)
print("Running in Colab:", IN_COLAB, "| smoke test:", SMOKE)
""")

md("""
## 2. Check GPU availability

The notebook never assumes a specific GPU. It detects the device and picks precision and batch size:

* **Ampere or newer** (A100, L4, …, compute capability ≥ 8.0) → `bf16`
* **Older GPUs** (T4, V100, P100) → `fp16` mixed precision
* **No GPU** → `fp32` on CPU/MPS (only suitable for the smoke test)
""")
code("""
if torch.cuda.is_available():
    DEVICE = "cuda"
    props = torch.cuda.get_device_properties(0)
    GPU_NAME, GPU_MEM_GB = props.name, props.total_memory / 1024**3
    major, _ = torch.cuda.get_device_capability(0)
    USE_BF16, USE_FP16 = major >= 8, major < 8
elif torch.backends.mps.is_available():
    DEVICE, GPU_NAME, GPU_MEM_GB, USE_BF16, USE_FP16 = "mps", "Apple MPS", 0.0, False, False
else:
    DEVICE, GPU_NAME, GPU_MEM_GB, USE_BF16, USE_FP16 = "cpu", "none", 0.0, False, False

# per-device batch size from available memory; gradient accumulation keeps the effective batch at 16
if GPU_MEM_GB >= 35:   PER_DEVICE_BS = 16
elif GPU_MEM_GB >= 20: PER_DEVICE_BS = 8
else:                  PER_DEVICE_BS = 4      # T4 (15 GB) and smaller: 1,024-token rows x 49k vocab logits are large
if DEVICE == "mps":   # Apple GPUs share system RAM: small micro-batches + gradient checkpointing
    PER_DEVICE_BS = 2
EFFECTIVE_BS = 16
GRAD_ACCUM = max(1, EFFECTIVE_BS // PER_DEVICE_BS)
USE_GRAD_CKPT = DEVICE == "mps" or (DEVICE == "cuda" and GPU_MEM_GB < 20)
print(f"device={DEVICE} gpu={GPU_NAME} mem={GPU_MEM_GB:.1f}GB bf16={USE_BF16} fp16={USE_FP16} "
      f"batch={PER_DEVICE_BS} x accum {GRAD_ACCUM}")
if DEVICE != "cuda" and not SMOKE:
    print("WARNING: no CUDA GPU detected. In Colab choose Runtime > Change runtime type > GPU.")
""")

md("## 3. Configuration")
code("""
import json, time, random
import numpy as np

CONFIG = {
    "base_model": os.environ.get("FITBOT_BASE_MODEL", "HuggingFaceTB/SmolLM2-360M-Instruct"),
    "max_seq_length": 1024,          # longest FitBot example is ~910 tokens
    "num_train_epochs": 3,
    "learning_rate": 2e-4,
    "lr_scheduler_type": "cosine",
    "warmup_ratio": 0.05,
    "weight_decay": 0.0,
    "per_device_train_batch_size": PER_DEVICE_BS,
    "gradient_accumulation_steps": GRAD_ACCUM,
    "lora_r": 16, "lora_alpha": 32, "lora_dropout": 0.05,
    "lora_target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "early_stopping_patience": 2,
    "seed": 42,
    "gen_max_new_tokens": 200,
    "gen_repetition_penalty": 1.1,
    "precision": "bf16" if USE_BF16 else ("fp16" if USE_FP16 else "fp32"),
    "device": DEVICE, "gpu_name": GPU_NAME,
}
if SMOKE:
    CONFIG.update({"num_train_epochs": 1, "max_steps": 3, "gen_max_new_tokens": 24})
# Optional cap on how many test examples get *generation* metrics (loss/perplexity always use the full
# sets). Default = all. Only useful for slow local (non-CUDA) runs.
GEN_EVAL_LIMIT = int(os.environ.get("FITBOT_GEN_EVAL_LIMIT", "0")) or None
RUN_NAME = "fitbot-smollm2-360m-lora"

random.seed(CONFIG["seed"]); np.random.seed(CONFIG["seed"]); torch.manual_seed(CONFIG["seed"])
print(json.dumps(CONFIG, indent=2))
""")

md("""
## 4. Mount Google Drive and load the dataset

Expected files (from `FitBot_colab_data.zip`): `training.jsonl`, `validation.jsonl`, `test.jsonl`,
`dataset_stats.json`. Every record carries a ready-made `messages` list (system prompt with retrieved
context → history → user → assistant) produced by the same prompt builder the FitBot backend uses,
so training and inference prompts are identical.
""")
code("""
import zipfile, glob, shutil
from pathlib import Path

if IN_COLAB:
    from google.colab import drive
    drive.mount("/content/drive")
    WORK = Path("/content/drive/MyDrive/FitBot")
else:
    WORK = Path(os.environ.get("FITBOT_WORK", Path.cwd().parent / "models" / "_notebook_run"))
WORK.mkdir(parents=True, exist_ok=True)
DATA_DIR = WORK / "data"
OUT_DIR = WORK / "outputs" / RUN_NAME
OUT_DIR.mkdir(parents=True, exist_ok=True)

def find_data():
    if (DATA_DIR / "training.jsonl").exists():
        return DATA_DIR
    zips = list(WORK.glob("FitBot_colab_data*.zip")) + list(Path("/content").glob("FitBot_colab_data*.zip"))
    if zips:
        with zipfile.ZipFile(zips[0]) as z:
            z.extractall(DATA_DIR)
        return DATA_DIR
    local = Path.cwd().parent / "data" / "processed"          # running inside the FitBot repo
    if (local / "training.jsonl").exists():
        return local
    if IN_COLAB:
        from google.colab import files
        print("Upload FitBot_colab_data.zip")
        up = files.upload()
        for name in up:
            with zipfile.ZipFile(name) as z:
                z.extractall(DATA_DIR)
        return DATA_DIR
    raise FileNotFoundError("Dataset not found - see the instructions at the top of the notebook.")

DATA_DIR = find_data()
def read_jsonl(p):
    with open(p) as fh:
        return [json.loads(l) for l in fh if l.strip()]

raw = {s: read_jsonl(DATA_DIR / f"{s}.jsonl") for s in ("training", "validation", "test")}
if SMOKE:
    raw = {"training": raw["training"][:24], "validation": raw["validation"][:8], "test": raw["test"][:8]}
for k, v in raw.items():
    print(f"{k:11s} {len(v):4d} records")
assert not ({r["group_id"] for r in raw["training"]} & {r["group_id"] for r in raw["test"]}), "test leakage!"
print("No group overlap between training and test.")
print(json.dumps(raw["training"][0]["messages"], indent=1)[:1200])
""")

md("## 5. Load the base model and tokenizer")
code("""
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained(CONFIG["base_model"])
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
dtype = torch.bfloat16 if USE_BF16 else (torch.float16 if USE_FP16 else torch.float32)
# fp16 training keeps master weights in fp32 (AMP); bf16 models can be loaded directly in bf16
load_dtype = torch.bfloat16 if USE_BF16 else torch.float32
model = AutoModelForCausalLM.from_pretrained(CONFIG["base_model"], dtype=load_dtype).to(DEVICE)
model.config.use_cache = False
n_params = sum(p.numel() for p in model.parameters())
print(f"Loaded {CONFIG['base_model']} with {n_params/1e6:.1f}M parameters on {DEVICE}")
""")

md("""
## 6. Tokenize – loss only on FitBot's answer

The prompt (system + retrieved context + history + user turn) is masked with `-100`, so the model is
trained to produce the assistant answer, not to copy the prompt.
""")
code("""
from datasets import Dataset

END = "<|im_end|>"
def encode(rec):
    prompt = tokenizer.apply_chat_template(rec["messages"][:-1], tokenize=False, add_generation_prompt=True)
    answer = rec["messages"][-1]["content"] + END + "\\n"
    p_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    a_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
    max_len = CONFIG["max_seq_length"]
    if len(p_ids) + len(a_ids) > max_len:                 # keep the answer, trim the oldest prompt tokens
        p_ids = p_ids[-(max_len - len(a_ids)):]
    ids = p_ids + a_ids
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": [-100] * len(p_ids) + a_ids}

tok = {s: Dataset.from_list([encode(r) for r in recs]) for s, recs in raw.items()}
lens = [len(x) for x in tok["training"]["input_ids"]]
print({s: len(d) for s, d in tok.items()}, "| max tokens", max(lens), "| mean", int(np.mean(lens)))
print("Example answer tokens:", tokenizer.decode([t for t in tok["training"][0]["labels"] if t != -100])[:300])
""")

code("""
from dataclasses import dataclass

@dataclass
class Collator:
    pad_id: int
    multiple: int = 64      # few distinct tensor shapes: friendlier to GPU kernels and MPS memory caching
    def __call__(self, batch):
        m = max(len(b["input_ids"]) for b in batch)
        m = ((m + self.multiple - 1) // self.multiple) * self.multiple
        pad = lambda seq, v: seq + [v] * (m - len(seq))
        return {
            "input_ids": torch.tensor([pad(b["input_ids"], self.pad_id) for b in batch]),
            "attention_mask": torch.tensor([pad(b["attention_mask"], 0) for b in batch]),
            "labels": torch.tensor([pad(b["labels"], -100) for b in batch]),
        }
collator = Collator(tokenizer.pad_token_id)
""")

md("""
## 7. Baseline: evaluate the **base** model before fine-tuning

* **Loss / perplexity** on validation and test answers (same masking as training).
* **Generation metrics** on the test set: ROUGE-L and token-F1 against the reference answer,
  out-of-domain refusal rate, safety-referral rate, number grounding (are numbers in the answer present in
  the provided USDA/plan context?), and latency.
""")
code("""
import math, re
from rouge_score import rouge_scorer

@torch.no_grad()
def eval_loss(m, ds, bs=8):
    m.eval(); total, count = 0.0, 0
    for i in range(0, len(ds), bs):
        batch = collator([ds[j] for j in range(i, min(i + bs, len(ds)))])
        batch = {k: v.to(DEVICE) for k, v in batch.items()}
        with torch.autocast(device_type="cuda", dtype=dtype, enabled=DEVICE == "cuda" and dtype != torch.float32):
            logits = m(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits.float()
        shift_logits, shift_labels = logits[:, :-1], batch["labels"][:, 1:]
        loss = torch.nn.functional.cross_entropy(shift_logits.reshape(-1, shift_logits.size(-1)),
                                                 shift_labels.reshape(-1), ignore_index=-100, reduction="sum")
        total += loss.item(); count += (shift_labels != -100).sum().item()
    avg = total / max(count, 1)
    return {"loss": round(avg, 4), "perplexity": round(math.exp(avg), 3), "tokens": count}

REFUSAL = re.compile(r"focused on fitness|only help with|outside what i can help|can't help with that", re.I)
REFERRAL = re.compile(r"doctor|healthcare|health professional|physiotherapist|dietitian|pharmacist|emergency|mental health|obstetric|surgeon", re.I)
NUM = re.compile(r"\\d+(?:\\.\\d+)?")
scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)

def token_f1(pred, ref):
    p, r = re.findall(r"\\w+", pred.lower()), re.findall(r"\\w+", ref.lower())
    if not p or not r: return 0.0
    common = sum(min(p.count(w), r.count(w)) for w in set(p))
    if common == 0: return 0.0
    prec, rec = common / len(p), common / len(r)
    return 2 * prec * rec / (prec + rec)

@torch.no_grad()
def generate(m, records, bs=8):
    m.eval(); tokenizer.padding_side = "left"; outs, times = [], []
    for i in range(0, len(records), bs):
        chunk = records[i:i + bs]
        prompts = [tokenizer.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True) for r in chunk]
        enc = tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(DEVICE)
        t0 = time.time()
        gen = m.generate(**enc, max_new_tokens=CONFIG["gen_max_new_tokens"], do_sample=False,
                         repetition_penalty=CONFIG["gen_repetition_penalty"], pad_token_id=tokenizer.pad_token_id)
        dt = (time.time() - t0) / len(chunk)
        for row in gen[:, enc["input_ids"].shape[1]:]:
            outs.append(tokenizer.decode(row, skip_special_tokens=True).strip()); times.append(dt)
        if DEVICE == "mps":
            torch.mps.empty_cache()
    tokenizer.padding_side = "right"
    return outs, times

def generation_metrics(records, preds, times):
    rl = [scorer.score(r["response"], p)["rougeL"].fmeasure for r, p in zip(records, preds)]
    f1 = [token_f1(p, r["response"]) for r, p in zip(records, preds)]
    ood = [(r, p) for r, p in zip(records, preds) if r["intent"] == "out_of_domain"]
    ind = [(r, p) for r, p in zip(records, preds) if r["intent"] != "out_of_domain"]
    safety = [(r, p) for r, p in zip(records, preds) if r["intent"] == "medical_safety"]
    grounded = [(r, p) for r, p in zip(records, preds) if r["source"] in ("usda", "planner") and r["context"]]
    def grounded_frac(r, p):
        nums = NUM.findall(p)
        ctx = " ".join(r["context"])
        return 1.0 if not nums else sum(n in ctx for n in nums) / len(nums)
    mean = lambda xs: round(float(np.mean(xs)), 4) if xs else None
    return {
        "n": len(records),
        "rougeL_f": mean(rl), "token_f1": mean(f1),
        "ood_refusal_rate": mean([1.0 if REFUSAL.search(p) else 0.0 for _, p in ood]),
        "in_domain_false_refusal_rate": mean([1.0 if REFUSAL.search(p) else 0.0 for _, p in ind]),
        "safety_referral_rate": mean([1.0 if REFERRAL.search(p) else 0.0 for _, p in safety]),
        "number_grounding_rate": mean([grounded_frac(r, p) for r, p in grounded]),
        "avg_latency_s": mean(times),
        "avg_answer_words": mean([len(p.split()) for p in preds]),
    }

base_results = {"validation": eval_loss(model, tok["validation"]), "test": eval_loss(model, tok["test"])}
GEN_SET = raw["test"][:GEN_EVAL_LIMIT] if GEN_EVAL_LIMIT else raw["test"]
base_preds, base_times = generate(model, GEN_SET)
base_results["test_generation"] = generation_metrics(GEN_SET, base_preds, base_times)
print(json.dumps(base_results, indent=2))
import gc
gc.collect()
if DEVICE == "cuda":
    torch.cuda.empty_cache()   # release generation caches before training
""")

md("## 8. Configure LoRA (PEFT)")
code("""
from peft import LoraConfig, get_peft_model, TaskType

lora_cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=CONFIG["lora_r"], lora_alpha=CONFIG["lora_alpha"],
                      lora_dropout=CONFIG["lora_dropout"], target_modules=CONFIG["lora_target_modules"], bias="none")
if USE_GRAD_CKPT:
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
CONFIG["trainable_params"] = trainable
""")

md("""
## 9. Train

Validation loss is computed at the end of every epoch (every few steps in smoke mode). The best checkpoint
(lowest validation loss) is restored at the end, and early stopping prevents over-fitting. Checkpoints go to
Google Drive so an interrupted Colab session can resume.
""")
code("""
from transformers import TrainingArguments, Trainer, EarlyStoppingCallback

steps_per_epoch = math.ceil(len(tok["training"]) / (PER_DEVICE_BS * GRAD_ACCUM))
eval_every = max(1, steps_per_epoch // 2)
total_steps = CONFIG.get("max_steps") or steps_per_epoch * CONFIG["num_train_epochs"]
warmup_steps = int(CONFIG["warmup_ratio"] * total_steps)   # integer works on transformers 4.x and 5.x
args = TrainingArguments(
    output_dir=str(OUT_DIR / "checkpoints"),
    num_train_epochs=CONFIG["num_train_epochs"],
    max_steps=CONFIG.get("max_steps", -1),
    per_device_train_batch_size=PER_DEVICE_BS,
    per_device_eval_batch_size=PER_DEVICE_BS,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=CONFIG["learning_rate"],
    lr_scheduler_type=CONFIG["lr_scheduler_type"],
    warmup_steps=warmup_steps,
    weight_decay=CONFIG["weight_decay"],
    logging_steps=1 if SMOKE else 5,
    eval_strategy="steps", eval_steps=1 if SMOKE else eval_every,
    save_strategy="steps", save_steps=1 if SMOKE else eval_every, save_total_limit=2,
    load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
    bf16=USE_BF16, fp16=USE_FP16,
    report_to="none", seed=CONFIG["seed"], remove_unused_columns=False,
    dataloader_pin_memory=DEVICE == "cuda",
    torch_empty_cache_steps=4 if DEVICE == "mps" else None,
)
trainer = Trainer(model=model, args=args, train_dataset=tok["training"], eval_dataset=tok["validation"],
                  data_collator=collator,
                  callbacks=[EarlyStoppingCallback(early_stopping_patience=CONFIG["early_stopping_patience"])])
t0 = time.time()
resume = any((OUT_DIR / "checkpoints").glob("checkpoint-*")) and not SMOKE
train_out = trainer.train(resume_from_checkpoint=True if resume else None)
TRAIN_SECONDS = round(time.time() - t0, 1)
print(train_out)
print(f"Training time: {TRAIN_SECONDS}s | best checkpoint: {trainer.state.best_model_checkpoint}")
""")

md("## 10. Training and validation loss curves")
code("""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

hist = trainer.state.log_history
train_pts = [(h["step"], h["loss"]) for h in hist if "loss" in h and "eval_loss" not in h]
eval_pts = [(h["step"], h["eval_loss"]) for h in hist if "eval_loss" in h]
fig, ax = plt.subplots(figsize=(8, 4.5))
if train_pts: ax.plot(*zip(*train_pts), label="training loss", color="#2a6fdb", linewidth=1.8)
if eval_pts:  ax.plot(*zip(*eval_pts), label="validation loss", color="#e8590c", marker="o", linewidth=1.8)
ax.axhline(base_results["validation"]["loss"], color="#868e96", linestyle="--", linewidth=1, label="base model validation loss")
ax.set_xlabel("optimizer step"); ax.set_ylabel("cross-entropy loss (answer tokens)")
ax.set_title("FitBot fine-tuning: SmolLM2-360M-Instruct + LoRA")
ax.spines[["top", "right"]].set_visible(False); ax.grid(alpha=0.25); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(OUT_DIR / "loss_curves.png", dpi=150)
(OUT_DIR / "log_history.json").write_text(json.dumps(hist, indent=1))
plt.close(fig)
print("saved", OUT_DIR / "loss_curves.png")
""")
code("""
from IPython.display import Image, display
display(Image(filename=str(OUT_DIR / "loss_curves.png")))
""")

md("## 11. Evaluate the fine-tuned model (validation + held-out test) and compare with the base model")
code("""
model.config.use_cache = True
if USE_GRAD_CKPT:
    model.base_model.model.gradient_checkpointing_disable()
ft_results = {"validation": eval_loss(model, tok["validation"]), "test": eval_loss(model, tok["test"])}
ft_preds, ft_times = generate(model, GEN_SET)
ft_results["test_generation"] = generation_metrics(GEN_SET, ft_preds, ft_times)

def per_category(records, preds):
    out = {}
    for r, p in zip(records, preds):
        out.setdefault(r["category"], []).append(scorer.score(r["response"], p)["rougeL"].fmeasure)
    return {k: round(float(np.mean(v)), 4) for k, v in sorted(out.items())}

results = {
    "run_name": RUN_NAME, "base_model": CONFIG["base_model"], "config": CONFIG,
    "train_seconds": TRAIN_SECONDS, "train_runtime_metrics": train_out.metrics,
    "best_checkpoint": trainer.state.best_model_checkpoint,
    "final_train_loss": next((h["loss"] for h in reversed(hist) if "loss" in h and "eval_loss" not in h), None),
    "best_validation_loss": trainer.state.best_metric,
    "base": base_results, "fine_tuned": ft_results,
    "rougeL_by_category": {"base": per_category(GEN_SET, base_preds), "fine_tuned": per_category(GEN_SET, ft_preds)},
    "generation_eval_examples": len(GEN_SET),
    "dataset_sizes": {k: len(v) for k, v in raw.items()},
    "smoke_test": SMOKE,
}
rows = [("validation loss", "validation", "loss"), ("validation perplexity", "validation", "perplexity"),
        ("test loss", "test", "loss"), ("test perplexity", "test", "perplexity")]
print(f"{'metric':32s}{'base':>12s}{'fine-tuned':>14s}")
for label, split, key in rows:
    print(f"{label:32s}{base_results[split][key]:>12}{ft_results[split][key]:>14}")
for key in ft_results["test_generation"]:
    print(f"{('test ' + key):32s}{str(base_results['test_generation'][key]):>12}{str(ft_results['test_generation'][key]):>14}")
""")
code("""
samples = []
for r, b, f in list(zip(GEN_SET, base_preds, ft_preds))[:40]:
    samples.append({"category": r["category"], "intent": r["intent"], "question": r["input"],
                    "reference": r["response"], "base": b, "fine_tuned": f})
(OUT_DIR / "test_predictions.json").write_text(json.dumps(
    [{"question": r["input"], "category": r["category"], "intent": r["intent"], "reference": r["response"],
      "base": b, "fine_tuned": f} for r, b, f in zip(GEN_SET, base_preds, ft_preds)], indent=1))
for s in samples[:6]:
    print("Q:", s["question"]); print("  BASE:", s["base"][:220]); print("  FITBOT:", s["fine_tuned"][:220]); print()
""")

md("""
## 12. Save the fine-tuned model, tokenizer, training configuration and evaluation results

* `adapter/` – LoRA adapter only (~30 MB) + tokenizer.
* `merged/` – base weights with the adapter merged in (stand-alone; loads without PEFT). **This is what
  the FitBot backend loads.**
""")
code("""
ADAPTER_DIR, MERGED_DIR = OUT_DIR / "adapter", OUT_DIR / "merged"
model.save_pretrained(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)

merged = model.merge_and_unload()
merged = merged.to(torch.float16 if DEVICE == "cuda" else torch.float32)
merged.config.use_cache = True
merged.save_pretrained(MERGED_DIR, safe_serialization=True)
tokenizer.save_pretrained(MERGED_DIR)

(OUT_DIR / "training_config.json").write_text(json.dumps(CONFIG, indent=2))
(OUT_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str))
(MERGED_DIR / "fitbot_model_card.json").write_text(json.dumps({
    "name": "FitBot SLM", "base_model": CONFIG["base_model"], "method": "LoRA (PEFT), merged",
    "dataset_sizes": results["dataset_sizes"], "best_validation_loss": results["best_validation_loss"],
    "test_loss": ft_results["test"]["loss"], "test_perplexity": ft_results["test"]["perplexity"],
    "trained_on": GPU_NAME, "smoke_test": SMOKE,
    "license": "Apache-2.0 (base model) - fine-tuned weights released with the FitBot project",
}, indent=2))
print("Saved to", OUT_DIR)

# quick reload check of the merged model
reloaded = AutoModelForCausalLM.from_pretrained(MERGED_DIR).to(DEVICE)
msgs = raw["test"][0]["messages"][:-1]
enc = tokenizer(tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True), return_tensors="pt").to(DEVICE)
out = reloaded.generate(**enc, max_new_tokens=60, do_sample=False, pad_token_id=tokenizer.pad_token_id)
print("Reload test ->", tokenizer.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True))
del reloaded
""")

md("## 13. Package and export")
code("""
PKG = WORK / f"{RUN_NAME}.zip"                      # full package: merged model + adapter (~0.75 GB)
LITE = WORK / f"{RUN_NAME}-adapter.zip"             # small package: LoRA adapter + results (~35 MB)
extras = ("training_config.json", "results.json", "log_history.json", "loss_curves.png", "test_predictions.json")
with zipfile.ZipFile(PKG, "w", zipfile.ZIP_DEFLATED) as z:
    for p in MERGED_DIR.rglob("*"):
        z.write(p, Path(RUN_NAME) / "merged" / p.relative_to(MERGED_DIR))
    for p in ADAPTER_DIR.rglob("*"):
        z.write(p, Path(RUN_NAME) / "adapter" / p.relative_to(ADAPTER_DIR))
    for name in extras:
        z.write(OUT_DIR / name, Path(RUN_NAME) / name)
with zipfile.ZipFile(LITE, "w", zipfile.ZIP_DEFLATED) as z:
    for p in ADAPTER_DIR.rglob("*"):
        z.write(p, Path(RUN_NAME) / "adapter" / p.relative_to(ADAPTER_DIR))
    z.write(MERGED_DIR / "fitbot_model_card.json", Path(RUN_NAME) / "fitbot_model_card.json")
    for name in extras:
        z.write(OUT_DIR / name, Path(RUN_NAME) / name)
print(f"Full package:    {PKG} ({PKG.stat().st_size/1e6:.0f} MB)")
print(f"Adapter package: {LITE} ({LITE.stat().st_size/1e6:.0f} MB)")
if IN_COLAB and not SMOKE:
    try:
        from google.colab import files
        files.download(str(LITE))      # small and reliable; install_model.py merges it locally
    except Exception as e:
        print("Automatic download unavailable - download from Google Drive instead:", e)
""")

md("""
## How to use the trained model in the local FitBot project

1. Download **`fitbot-smollm2-360m-lora-adapter.zip`** (~35 MB, downloaded automatically above) – or the full
   **`fitbot-smollm2-360m-lora.zip`** (~0.75 GB, merged model included) from `MyDrive/FitBot/` in Google Drive.
2. On your computer, inside the FitBot project folder run:

   ```bash
   .venv/bin/python scripts/install_model.py ~/Downloads/fitbot-smollm2-360m-lora-adapter.zip
   ```

   This extracts to `models/fitbot-smollm2-360m-lora/`, merges the LoRA adapter into the base model locally
   when only the adapter was downloaded (identical weights to Colab's `merged/`), and copies `results.json`,
   `log_history.json` and `loss_curves.png` into `evaluation/training_run/`.
3. Make sure `backend/.env` contains `FITBOT_MODEL_PATH=models/fitbot-smollm2-360m-lora/merged`
   (this is the default).
4. Re-run the local evaluation: `.venv/bin/python evaluation/evaluate.py` and start the backend.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {
    "accelerator": "GPU",
    "colab": {"provenance": [], "gpuType": "T4", "name": "FitBot_FineTuning.ipynb"},
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
out = Path(__file__).with_name("FitBot_FineTuning.ipynb")
nbf.write(nb, out)
print("wrote", out)
