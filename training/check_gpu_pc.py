"""Quick environment check for the college GPU PC (run before opening the notebook).

    python check_gpu_pc.py
Prints PASS / WARN / FAIL for: Python, PyTorch + CUDA, GPU + VRAM, RAM, free disk, required packages,
bitsandbytes 4-bit on the GPU, and access to Hugging Face.
"""
import importlib.util
import platform
import shutil
import sys
import urllib.request

ok = True


def report(status, msg):
    global ok
    ok &= status != "FAIL"
    print(f"[{status}] {msg}")


report("PASS" if sys.version_info >= (3, 10) else "FAIL", f"Python {sys.version.split()[0]} ({platform.system()} {platform.release()})")
try:
    import torch
    report("PASS", f"PyTorch {torch.__version__} (CUDA build {torch.version.cuda})")
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        mem = p.total_memory / 1024**3
        report("PASS" if mem >= 11 else "WARN", f"GPU {p.name} with {mem:.1f} GB VRAM, bf16={torch.cuda.is_bf16_supported()}")
    else:
        report("FAIL", "PyTorch cannot see a CUDA GPU - install the CUDA build of PyTorch and a current NVIDIA driver")
except ImportError:
    report("FAIL", "PyTorch not installed")

try:
    import psutil
    ram = psutil.virtual_memory().total / 1024**3
    report("PASS" if ram >= 24 else "WARN", f"RAM {ram:.0f} GB (merging the full model needs ~10 GB free)")
except ImportError:
    report("WARN", "psutil not installed - RAM not checked")
free = shutil.disk_usage(".").free / 1024**3
report("PASS" if free >= 30 else "WARN", f"Free disk here: {free:.0f} GB (need ~25 GB: model download 8 GB + merged model 8 GB + checkpoints)")

for mod, pip in [("transformers", "transformers"), ("peft", "peft"), ("accelerate", "accelerate"), ("datasets", "datasets"),
                 ("bitsandbytes", "bitsandbytes"), ("rouge_score", "rouge-score"), ("matplotlib", "matplotlib"),
                 ("jupyter", "jupyter")]:
    if importlib.util.find_spec(mod) is None:
        report("FAIL", f"missing package: pip install {pip}")
    elif mod == "transformers":
        import transformers
        from packaging.version import Version
        v = transformers.__version__
        report("PASS" if Version(v) >= Version("4.51.0") else "FAIL", f"transformers {v} (Qwen3 needs >= 4.51)")
    else:
        report("PASS", f"{mod} installed")

try:
    import bitsandbytes as bnb
    import torch
    if torch.cuda.is_available():
        lin = bnb.nn.Linear4bit(64, 64, compute_dtype=torch.bfloat16, quant_type="nf4").cuda()
        y = lin(torch.randn(2, 64, device="cuda", dtype=torch.bfloat16))
        report("PASS", f"bitsandbytes {bnb.__version__}: 4-bit layer runs on the GPU {tuple(y.shape)}")
except Exception as e:  # noqa: BLE001
    report("FAIL", f"bitsandbytes 4-bit test failed: {e}")

try:
    urllib.request.urlopen("https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507", timeout=15)
    report("PASS", "Hugging Face reachable (model can be downloaded)")
except Exception as e:  # noqa: BLE001
    report("WARN", f"Hugging Face not reachable ({e}) - copy the model folder in by USB instead (see guide)")

print("\nREADY - open FitBot_FineTuning_4B.ipynb" if ok else "\nFix the FAIL items above first (see COLLEGE_PC_GUIDE.md)")
