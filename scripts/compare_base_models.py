"""Quick zero-shot comparison of candidate base SLMs on this machine (Phase 4).

Measures parameter count, load memory (fp32 on CPU/MPS), generation latency and shows
answers to a few FitBot prompts. Results -> evaluation/model_selection/base_model_comparison.json
"""
import json, sys, time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ml.prompting import build_messages  # noqa: E402

MODELS = sys.argv[1:] or ["HuggingFaceTB/SmolLM2-135M-Instruct", "HuggingFaceTB/SmolLM2-360M-Instruct",
                          "Qwen/Qwen2.5-0.5B-Instruct"]
PROMPTS = ["What exercises can I do for chest?", "How much sleep do I need?",
           "What should I eat after a workout?", "What is the capital of France?"]
device = "mps" if torch.backends.mps.is_available() else "cpu"
out = []
for name in MODELS:
    tok = AutoTokenizer.from_pretrained(name)
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.float16 if device == "mps" else torch.float32).to(device).eval()
    load_s = time.time() - t0
    params = sum(p.numel() for p in model.parameters())
    res = {"model": name, "params_m": round(params / 1e6, 1), "load_seconds": round(load_s, 1), "device": device, "answers": []}
    lat, toks = [], []
    for q in PROMPTS:
        text = tok.apply_chat_template(build_messages(q), tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(device)
        t1 = time.time()
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=120, do_sample=False, pad_token_id=tok.eos_token_id)
        dt = time.time() - t1
        new = gen[0, enc["input_ids"].shape[1]:]
        lat.append(dt); toks.append(len(new))
        res["answers"].append({"q": q, "a": tok.decode(new, skip_special_tokens=True).strip()})
    res["avg_latency_s"] = round(sum(lat) / len(lat), 2)
    res["tokens_per_s"] = round(sum(toks) / sum(lat), 1)
    out.append(res)
    print(json.dumps({k: v for k, v in res.items() if k != "answers"}))
    del model
    if device == "mps":
        torch.mps.empty_cache()
(ROOT / "evaluation/model_selection/base_model_comparison.json").write_text(json.dumps(out, indent=2))
