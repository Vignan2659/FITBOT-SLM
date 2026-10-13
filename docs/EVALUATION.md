# FitBot – Evaluation

## v2 – Qwen3-4B (current model)

Evaluated by the training notebook on dataset v2 (`evaluation/training_run_4b/results.json`); generation metrics
on the 97 original v1 test questions (same questions as the 360M model) and 80 new v2 test questions.

| | Base Qwen3-4B | Fine tuned FitBot 4B | FitBot 360M (v1) |
|---|---:|---:|---:|
| Validation loss / perplexity | 2.552 / 12.84 | **0.474 / 1.61** | 0.894 / 2.45 |
| Test loss / perplexity | 2.550 / 12.81 | **0.482 / 1.62** | 0.897 / 2.45 |
| v1 test (97): ROUGE-L / token F1 | 0.228 / 0.332 | **0.604 / 0.665** | 0.488 / 0.537 |
| v2 new test (80): ROUGE-L / token F1 | 0.225 / 0.310 | **0.676 / 0.720** | – |
| Out of domain refusal rate (raw model) | 0.00 | **1.00** | – |
| Safety referral rate (all 177) | 0.92 | 0.92 | – |
| Number grounding (USDA / plans) | 0.94 | **0.96** | – |
| Avg answer length (words) | 126 | 52 | – |

Loss is measured on different datasets for v1 and v2 (v1: 916 records, v2: 5,470), so compare the loss columns
within a model; the 97 v1 test questions are identical for both.

**Full application test suites** (163 checked turns, `evaluation/run_test_suites.py`): **152/163 (93 %)** in
bfloat16 and **153/163 (94 %)** in float16, against 150/163 (92 %) for the 360M model. Details:
`evaluation/test_suite_summary_4b.md`, `evaluation/test_suite_summary_4b_fp16.md`.

The sections below are the original **v1 (SmolLM2-360M)** evaluation, kept for reference.


## 1. Methodology

### Train / validation / test split

* 916 cleaned records, split **by `group_id`** (all paraphrases of one question, all turns of one
  conversation, all questions about one food/exercise share a group) and stratified by category:
  726 train / 93 validation / 97 test.
* `build_dataset.py` asserts there is no shared group between train and test and reports how many test
  inputs also occur in training after normalisation (0).
* **Training** set: gradient updates. **Validation** set: loss every half epoch, best checkpoint selection
  and early stopping. **Test** set: used only for the final comparison below.

### Metrics

| Metric | How it is computed | Script |
|---|---|---|
| Training loss | Trainer log (answer tokens only) | notebook |
| Validation / test loss, perplexity | mean token cross-entropy on reference answers (teacher forcing), perplexity = e^loss | notebook, `evaluation/evaluate.py` |
| ROUGE-L, token F1 | overlap between generated answer and reference answer | both |
| Relevance | cosine similarity of all-MiniLM-L6-v2 embeddings (answer vs reference) | `evaluate.py` |
| Consistency | mean pairwise embedding similarity between answers to paraphrases of the same question | `evaluate.py` |
| Domain accuracy | 16 closed book fact probes (e.g. adult sleep ≥ 7 h, 150 min/week, protein RDA 0.8 g/kg), regex-checked; no retrieval context | `evaluate.py` + `fact_probes.json` |
| Safety | share of medical-safety prompts whose answer refers to a professional (raw model, guardrails off) | both |
| Out of domain handling | refusal rate on OOD prompts and false refusals on in domain prompts (raw model) | both |
| Number grounding | share of numbers in USDA / workout-plan answers that appear in the provided context | both |
| Latency | seconds per generated answer (greedy, ≤ 200 new tokens), mean and p95 | both |
| Application test suites | 140 questions + 20 multi turn conversations through the *full* pipeline with the real model: routing, cards, plans, follow-ups, guardrails, keyword relevance, USDA number grounding | `evaluation/run_test_suites.py` |
| Intent classifier | accuracy / macro-F1 / OOD precision-recall on held out data | `scripts/train_intent_classifier.py` |

## 2. Which training run these numbers come from

All results below are for the model **fine tuned on Google Colab (Tesla T4 GPU)** with
`training/FitBot_FineTuning.ipynb`: 3 epochs, 138 optimizer steps, 471 s of training, fp16, per-device batch 4 ×
gradient accumulation 4 (effective batch 16), gradient checkpointing. The ~33 MB LoRA adapter was downloaded and
merged into the base model locally by `scripts/install_model.py`; the backend serves that merged model
(`/health` reports `"trained_on": "Tesla T4"`).

Before the Colab run, the same notebook was also executed end to end on the development Mac's GPU (Apple MPS) to
verify it. That run reached almost identical numbers (test loss 0.896 vs 0.897, ROUGE-L 0.483 vs 0.488); its
outputs are kept in `models/_local_run/`.

Two Colab-specific issues were found and fixed in the notebook during the Colab run:
`torchao 0.10` preinstalled on Colab is rejected by PEFT 0.21 (the notebook now uninstalls it), and batch 8 ran out
of memory on the 15 GB T4 (GPUs under 20 GB now use batch 4 × 4 with gradient checkpointing, and the GPU cache is
released after the baseline evaluation).

## 3. Results

### 3.1 Training (Colab, Tesla T4)

| | Value |
|---|---|
| Trainable parameters (LoRA) | 8,683,520 (2.3 % of 370.5 M incl. adapter) |
| Training time | 471 s |
| Final training loss | 0.788 |
| Validation loss by evaluation (steps 23 → 138) | 1.375 → 1.114 → 0.985 → 0.917 → 0.898 → **0.894** |
| Base model validation loss | 1.713 |

![loss curves](../evaluation/charts/loss_curves.png)

Validation loss decreases at every evaluation and flattens in the third epoch with no upturn, so there is no
sign of over-fitting (early stopping did not trigger; the best checkpoint is the last one).

### 3.2 Base vs fine tuned on the held out test set (97 records)

Raw model only, **no guardrails, no structured cards**, same prompts (system prompt + retrieved context) for both.
Local inference on the Mac (MPS), greedy decoding. Numbers from `evaluation/evaluate.py` / `evaluation/results.json`.

| Metric | Base SmolLM2-360M | Fine tuned FitBot (Colab) | Change |
|---|---:|---:|---|
| Validation loss / perplexity | 1.713 / 5.55 | **0.896 / 2.45** | −48 % loss |
| Test loss / perplexity | 1.621 / 5.06 | **0.897 / 2.45** | −45 % loss |
| ROUGE-L F1 | 0.176 | **0.488** | ×2.8 |
| Token F1 | 0.247 | **0.537** | ×2.2 |
| Relevance (embedding similarity to reference) | 0.689 | **0.781** | +0.09 |
| Consistency (paraphrase answers, 48 pairs) | 0.700 | 0.715 | +0.015 |
| Domain fact accuracy (16 closed book probes) | 0.81 | 0.81 | same (different probes fail) |
| Out of domain refusal (n = 4) | 0.00 | 0.25 | small n |
| False refusals on in domain prompts | 0.00 | 0.054 | regression |
| Safety referral rate (n = 6) | 0.67 | 0.33 | regression, small n |
| Number grounding in USDA/plan answers | 0.92 | 0.91 | ≈ same |
| Latency mean per answer (MPS, measured in isolation) | 1.87 s | **0.97 s** | −48 % |
| Average answer length (words) | 99 | 46 | concise |

The latency row uses the earlier isolated measurement on the same machine; in the final `results.json` run the
base model's latency (2.74 s) was inflated because the test suites were running on the same GPU at the same time.
On the Colab T4 (batched generation) both models took ~1.5 s per answer.

![base vs fine tuned](../evaluation/charts/base_vs_finetuned.png)

**Interpretation.** Fine tuning strongly improved how closely and concisely the model answers in FitBot's style
and how well it uses the provided context (ROUGE-L ×2.8, perplexity halved, answers half as long). It did **not**
make the raw model reliable at refusing off topic questions or at always referring medical questions to a
professional, on very small test subsets (4 and 6 items) it was worse than the base model on the latter, and it
occasionally refuses in domain questions (5.4 %). Closed-book factual knowledge did not change (13/16 probes for
both; the fine tuned model e.g. wrongly calls dumbbell rows a chest exercise when asked without context). These
results justify the system design: **safety and scope are enforced by deterministic guardrails, and facts come
from retrieval**, while the SLM provides the conversational answer. Per-category ROUGE-L, all probe answers and
sample predictions are in [`evaluation/evaluation_report.md`](../evaluation/evaluation_report.md); the Colab
notebook's own results (`evaluation/training_run/results.json`) agree (test loss 0.897, ROUGE-L 0.488).

### 3.3 Full application test suites (Colab model, full pipeline)

`evaluation/run_test_suites.py`, 163 checked turns (140 single questions + 20 conversations with 43 turns).

| Suite | Items | Pass rate |
|---|---:|---:|
| Fitness questions | 50 | 76 % |
| Nutrition questions | 20 | 100 % |
| Exercise questions | 20 | 100 % |
| Sleep / recovery | 10 | 100 % |
| Safety | 10 | 100 % |
| Out of domain | 10 | 100 % |
| Follow up conversations | 20 (43 turns) | 98 % |
| **Total** | **163 turns** | **92 % (150/163)** |

0 false refusals over 141 in domain turns. 9 of the 13 failures are *intent-label* disagreements where the answer
itself passed all other checks (e.g. "Is swimming a good workout?" routed to `hydration` instead of `cardio`);
three are keyword-relevance misses and one fails both. The expectations were not relaxed after seeing the results.
(With the earlier TF-IDF-only intent classifier the same model scored 149/163; see 3.4.) Full answers: `evaluation/test_suite_results.json`;
failures: `evaluation/test_suite_summary.md`.

### 3.4 Intent classifier

Hybrid model: TF-IDF (word + char n-grams) concatenated with all-MiniLM-L6-v2 sentence embeddings (the encoder
already loaded for retrieval) -> logistic regression. Embedding weight and C were chosen on the validation split;
the earlier TF-IDF-only model is kept inside the saved file as an offline fallback.

| Split | TF-IDF only: accuracy / macro-F1 | **Hybrid: accuracy / macro-F1** | Hybrid OOD precision / recall |
|---|---:|---:|---:|
| Validation (213) | 0.831 / 0.662 | **0.906 / 0.781** | 0.958 / 0.958 |
| Test (217, FitBot + fitness-intent) | 0.830 / 0.732 | **0.876 / 0.744** | 0.957 / 0.917 (was 0.833 / 0.833) |
| Test, FitBot items only (97) | 0.763 | **0.835** | – |

In the full pipeline the switch fixed 4 turns and changed 3 others to a neighbouring intent (answers of similar
quality), net 149 -> 150/163. The classifier alone confuses neighbouring fitness intents; the domain-lexicon guardrail (whole-word short
stems, phrase-level food/exercise names, false-friend list) raises out of domain handling in the full pipeline to
10/10 in the OOD suite and 0 false refusals in the in domain suites.

### 3.5 Automated tests

| Suite | Result |
|---|---|
| Backend pytest (auth, hashing, logout revocation, conversations & privacy, chat pipeline, follow-ups, exercise/food search, planner, intent incl. offline fallback, slots, safety, rate limit, /api prefix) | 73 passed |
| Backend pytest `-m slm` (real Colab model: demo conversation, USDA number grounding) | 2 passed |
| Frontend Vitest (exercise card, food card, workout plan, message rendering) | 4 passed |
| Notebook executed end to end: locally (smoke + full MPS run, 31/31 cells) and on Colab T4 (all cells, after the two Colab fixes above) | passed |

### 3.6 Final acceptance test (browser, real model)

(Performed with the MPS-trained verification model; the Colab model passes the same flow in `pytest -m slm` and the follow up suite.)


Register → profile → dashboard → new chat → "What exercises can I do for chest?" (SLM answer + 6 chest cards with
images) → "I'm a beginner." (follow up, beginner-only cards) → "I only have dumbbells." (dumbbell chest workout:
4 exercises, sets × reps, rest, images) → "What should I eat after this workout?" (USDA food cards) → "How much
should I sleep?" ("7 or more hours") → "Give me a beginner 3-day gym workout" (3-day plan with day tabs) →
"What is the capital of France?" (scope message) → "I have chest pain when I exercise" (safety guardrail + disclaimer)
→ logout (protected route redirects to login) → login → previous conversation and its cards restored.
Two bugs found during this test were fixed and covered by regression tests (stale topic reused after a topic
change; explicit "gym" not overriding remembered equipment).
