# FitBot – Model Selection

## Current model (v2): `Qwen/Qwen3-4B-Instruct-2507` + QLoRA

FitBot v2 runs a **4.0 B-parameter** model, as the project brief asked for a 3.5-4 B model:

| Candidate | Size | Verdict |
|---|---|---|
| **Qwen3-4B-Instruct-2507** | 4.0 B | **Chosen.** Strong 4B instruction model, Apache-2.0, text-only, no "thinking" output, ChatML like v1, works with standard `transformers` + 4-bit QLoRA and fits a 12 GB GPU for training. |
| Qwen3.5-4B | 4 B | Newer, but multimodal with a new architecture needing the latest `transformers` and extra kernels; 4-bit QLoRA not recommended for it. |
| Phi-4-mini-instruct | 3.8 B | Good alternative (MIT); can be tried with `FITBOT_BASE_MODEL=microsoft/Phi-4-mini-instruct` and `target_modules="all-linear"`. |

Fine tuned with QLoRA (4-bit NF4 base, LoRA r = 16 on all attention + MLP projections, ~33 M trainable
parameters) on dataset v2, see [TRAINING_GUIDE.md](TRAINING_GUIDE.md). On the Mac it runs in float16 on the
Apple GPU (MPS), ~7.5 GB of weights, about 9-12 s per answer on an M5 with 16 GB.

The rest of this document describes the selection of the **v1 model** (SmolLM2-360M), kept for reference.


## Selected model: `HuggingFaceTB/SmolLM2-360M-Instruct` + LoRA fine tuning

| Property | Value |
|---|---|
| Parameters | 361.8 M (verified from the model's safetensors metadata on the HF Hub) |
| Architecture | Decoder only transformer (`llama` model type: RoPE, SiLU-gated MLP, grouped-query attention), 32 layers, hidden size 960, MLP size 2,560, 15 attention heads / 5 key-value heads, 49,152-token vocabulary, tied embeddings |
| Context length | 8,192 tokens (FitBot uses ≤ 1,024) |
| License | Apache-2.0 (permits modification and redistribution of the fine tuned weights) |
| Disk size | ≈ 724 MB in bf16; LoRA adapter ≈ 35 MB |
| Chat template | ChatML (`<|im_start|>system … <|im_end|>`) with system-prompt support |
| Gated | No – downloads without accepting extra terms |

The model is configurable through the `FITBOT_BASE_MODEL` environment variable and
the `BASE_MODEL` setting in the Colab notebook, so the pipeline can be rerun with a
different base (e.g. SmolLM2-135M for very weak hardware).

## Candidates investigated

Metadata was pulled from the Hugging Face Hub API on 2026-10-03.

| Model | Params | License | Gated | Notes |
|---|---:|---|---|---|
| distilgpt2 | 88 M | Apache-2.0 | no | Not instruction-tuned, no chat template, 1,024-token context; quality too low for conversation. |
| GPT-2 small | 137 M | MIT | no | Same issues as distilgpt2 (2019 pre-training, no instruction tuning). |
| SmolLM2-135M-Instruct | 135 M | Apache-2.0 | no | Very fast, but noticeably weaker reasoning; hallucinated a non-existent "chest extension" stretch in our zero shot test. Good fallback for low-end hardware. |
| **SmolLM2-360M-Instruct** | **362 M** | **Apache-2.0** | **no** | **Best quality/size trade-off among true "small" models; fast on a laptop; trains in minutes on a free Colab T4.** |
| Qwen2.5-0.5B-Instruct | 494 M | Apache-2.0 | no | Slightly stronger general knowledge, ~37 % more parameters, slower locally (see below). Strong alternative. |
| Qwen3-0.6B | 752 M | Apache-2.0 | no | Larger; "thinking" mode adds complexity for a short-answer assistant. |
| Gemma-3-270M-it | 268 M | Gemma terms | **manual gate** | Custom license + gated download complicate reproducibility for an academic project. |
| TinyLlama-1.1B-Chat | 1.1 B | Apache-2.0 | no | 3× larger; older (2023); heavier local inference. |
| SmolLM2-1.7B-Instruct | 1.7 B | Apache-2.0 | no | Better quality but no longer "small" for CPU inference; LoRA fits Colab, but local latency suffers. |
| Phi-3-mini / Phi-4-mini | 3.8 B | MIT | no | Strong, but ~10× the size; 4-bit quantisation would be needed on many laptops. |
| SmolLM3-3B | 3.1 B | Apache-2.0 | no | Same – excellent but beyond the SLM budget for local, CPU-friendly inference. |

## Local zero shot measurement (before fine tuning)

`scripts/compare_base_models.py` ran each candidate on this development machine
(Apple M5, PyTorch MPS, fp16, greedy decoding, 120 new tokens, FitBot system prompt).
Raw answers are saved in `evaluation/model_selection/base_model_comparison.json`.

| Model | Params | Avg latency / answer | Throughput |
|---|---:|---:|---:|
| SmolLM2-135M-Instruct | 134.5 M | 0.89 s | 103 tok/s |
| **SmolLM2-360M-Instruct** | **361.8 M** | **1.14 s** | **81 tok/s** |
| Qwen2.5-0.5B-Instruct | 494.0 M | 1.46 s | 63 tok/s |

Qualitative findings that motivated fine tuning:

* **All three base models answered "What is the capital of France?" with "Paris"**,
  ignoring the system prompt's instruction to stay in the fitness domain → the base
  models do not follow FitBot's scope.
* SmolLM2-135M invented a "Chest Extension" exercise; SmolLM2-360M listed "dumbbell
  rows" as a chest exercise → domain accuracy needs improvement and grounding.
* All models produced long, generic, list-heavy answers; FitBot needs concise
  coaching-style responses that use retrieved facts.

## Why SmolLM2-360M-Instruct

1. **Truly small** – 362 M parameters fits the SLM brief and runs on CPU or a laptop GPU.
2. **Fine tuning feasibility** – LoRA (r=16) on all attention + MLP projections trains 8.7 M parameters (2.3 % of
   parameters; the 916-record dataset trains in a few minutes on a Colab T4/L4/A100,
   and full fine tuning would also fit in 16 GB if desired.
3. **Local inference** – ~1 s per answer on Apple Silicon; still usable on CPU.
4. **Quality** – instruction-tuned with a chat template and system prompt support, so
   fine tuning only needs to *adapt* style, scope and grounding behaviour.
5. **Open license** – Apache-2.0, ungated; training data mixtures are published by
   Hugging Face (good for an academic write-up).
6. **Tokenizer / template** – ChatML lets us mask loss to assistant tokens only.

## Fine tuning approach: LoRA (PEFT)

| Setting | Value | Reason |
|---|---|---|
| Target modules | `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj` | Adapting both attention and MLP gives better domain adaptation than attention-only LoRA. |
| Rank `r` / `alpha` / dropout | 16 / 32 / 0.05 | Standard, stable configuration for small datasets. |
| Loss | Causal LM loss on **assistant tokens only** | The model learns to answer, not to reproduce prompts/context. |
| Precision | bf16 on Ampere+ GPUs, fp16 on T4, fp32 on CPU | Detected automatically in the notebook. |
| Export | LoRA adapter **and** merged full model | Adapter is small to download; merged model loads without PEFT. |

See [TRAINING_GUIDE.md](TRAINING_GUIDE.md) for the exact hyper-parameters and the
Colab procedure.
