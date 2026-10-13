# FitBot – A Fitness-Domain Small Language Model: Project Report

> **Update (v2, October 2026):** FitBot now runs a fine-tuned **Qwen3-4B-Instruct-2507** (QLoRA, dataset v2 with
> 5,470 conversations and all 871 exercises) instead of SmolLM2-360M. v2 results: test perplexity 1.62, ROUGE-L 0.604
> on the v1 test questions (360M: 0.488), 93-94 % of the full application checks. See the [README](README.md),
> [docs/EVALUATION.md](docs/EVALUATION.md) and [docs/TRAINING_GUIDE.md](docs/TRAINING_GUIDE.md). This report
> describes the v1 system; the app architecture, data sources and safety layer are unchanged.


## 1. Problem statement

General-purpose chatbots answer fitness questions inconsistently: they drift out of scope, invent
nutrient values, give unsafe advice (crash diets, training through pain) and require cloud APIs.
Small language models (SLMs) can run locally and cheaply, but out of the box they lack domain
focus — in our zero-shot test, every base candidate answered *"What is the capital of France?"*
despite a fitness-only system prompt, and one listed dumbbell rows as a chest exercise.

**Goal:** build a locally runnable, domain-specific SLM assistant for fitness and wellness that
gives grounded, safe, conversational answers, shows real exercise images and real nutrition data,
and keeps per-user chat history.

## 2. Objectives

1. Research and justify public datasets and a suitable open SLM.
2. Build a clean, leakage-free conversational dataset (train/validation/test).
3. Fine-tune the SLM on a Google Colab GPU with LoRA and evaluate base vs fine-tuned.
4. Ground factual content with structured retrieval (exercises with images, USDA nutrition, workout planner).
5. Support follow-ups and optional profile personalisation.
6. Enforce safety and out-of-domain behaviour.
7. Deliver a full-stack app (FastAPI + SQLite + auth, React UI) with automated tests and documentation.

## 3. System overview

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short: React frontend → FastAPI → chat pipeline
(safety screen → intent + slots → dialogue state → structured + semantic retrieval → fine-tuned
SLM → output safety) → structured JSON (answer, exercise cards, food cards, workout plan, sources).

## 4. Data

Full details: [docs/DATASET_RESEARCH.md](docs/DATASET_RESEARCH.md).

| Purpose | Source | License | Size used |
|---|---|---|---|
| Conversational fine-tuning | FitBot Curated Conversational Dataset (built here) | MIT (project) | 916 records |
| Exercises + images | free-exercise-db | Unlicense | 58 curated / 876 catalog, 116 verified image URLs |
| Nutrition | USDA FoodData Central SR Legacy | CC0 1.0 | 111 foods (7,793 available) |
| Intent / OOD classifier | harshmakwana/fitness-intent + FitBot labels | MIT | 1,200 + FitBot inputs |
| Retrieval passages | written for the project, aligned with HHS PAG, DGA 2020-2025, CDC, NASEM, ISSN, ACSM | – | 76 passages |

Seven Hugging Face fitness datasets were evaluated; none combined a clear license, conversational
format and consistent, safe content (several had no license, one stripped all punctuation, one
contained contradictory workout prescriptions), so the conversational set was built in this
project and grounded in the licensed structured sources.

**Preprocessing** (`scripts/build_dataset.py`): hand-written seeds with paraphrases, multi-turn
conversations, profile-personalised examples, safety and out-of-domain examples, plus examples
generated from structured data (exercise how-to, muscle-group lists, USDA nutrient facts, food
lists, planner outputs, follow-up chains). Cleaning removes empty, too short/long, unsafe-pattern,
duplicate and contradictory records (11 duplicates removed). 69 % of records (632) carry retrieved
context so the model learns to use it; 52 records carry conversation history and 27 a user profile.

## 5. Model

Details: [docs/MODEL_SELECTION.md](docs/MODEL_SELECTION.md). **SmolLM2-360M-Instruct** (361.8 M
parameters, Apache-2.0, Llama-style decoder, ChatML template) was chosen over distilgpt2/GPT-2
(not instruction-tuned), SmolLM2-135M (weaker), Qwen2.5-0.5B (37 % larger, slower locally),
Gemma-3-270M (gated, custom license) and 1-4 B models (too large for CPU-friendly local inference).

Fine-tuning: LoRA r = 16, α = 32 on all attention and MLP projections (8.7 M trainable parameters,
2.3 %), loss on assistant tokens only, cosine LR 2e-4, 3 epochs, best-validation checkpoint,
early stopping. The LoRA adapter is merged into the base weights for deployment.

## 6. Google Colab training

`training/FitBot_FineTuning.ipynb` (see [docs/TRAINING_GUIDE.md](docs/TRAINING_GUIDE.md)) installs
dependencies, detects the GPU and selects precision/batch size, mounts Google Drive, loads the
splits, evaluates the base model, trains with LoRA (checkpoints on Drive), plots training and
validation loss, evaluates on the test set, saves adapter + merged model + tokenizer + config +
results, and packages a zip that `scripts/install_model.py` installs locally.

**Colab training run (used for all results in this report).** The notebook was run on Google Colab on a
**Tesla T4** (fp16, batch 4 × accumulation 4, gradient checkpointing): 3 epochs, 138 optimizer steps, 471 s of
training, final training loss 0.788, best validation loss **0.894** (base model: 1.713). The ~33 MB LoRA adapter
was downloaded and merged locally by `scripts/install_model.py`. Two Colab-specific problems surfaced and were fixed
in the notebook: Colab's preinstalled `torchao 0.10` is rejected by PEFT 0.21 (now uninstalled by the setup cell),
and batch 8 exceeded the T4's 15 GB (GPUs under 20 GB now use batch 4 × 4 with gradient checkpointing). Before
that, the notebook had also been executed end-to-end on the development Mac's GPU (MPS) as a verification run, with
almost identical results (test loss 0.896 vs 0.897).

![loss curves](evaluation/charts/loss_curves.png)

## 7. Retrieval, nutrition and exercise-image systems

* **Exercise system:** 58 curated exercises covering every required chest/back/shoulder/leg/arm/
  core/cardio movement plus stretches, each with target/secondary muscles, equipment, difficulty,
  description, source instructions, safety tip and two public-domain images whose URLs were HTTP-
  verified. Retrieval filters by muscle group, level and available equipment.
* **Nutrition system:** USDA values stored per 100 g and per USDA household portion (portion values
  computed and labelled). Descriptive highlights ("High protein", "High sugar", …) are derived from
  the numbers with documented thresholds. Unknown foods return 404 / no card — never estimates.
* **Workout planner:** full-body / upper-lower / push-pull-legs templates; exercise selection by
  movement role, level and equipment; sets/reps/rest from standard guidance; every exercise links to
  a real database entry with an image.
* **Semantic retrieval:** all-MiniLM-L6-v2 embeddings over 76 guidance passages (TF-IDF fallback).
* **Intent detection:** TF-IDF + MiniLM sentence embeddings -> logistic regression over 19 intents
  (test accuracy 0.876 vs 0.830 for TF-IDF alone; TF-IDF-only fallback offline), combined with a
  fitness-domain lexicon guardrail for out-of-domain detection.

## 8. Backend, database and frontend

FastAPI with 16 endpoints (auth, profile, conversations, chat, exercises, foods, health), SQLite
via SQLAlchemy (users, user_profiles, conversations, messages, exercise_metadata, food_metadata,
revoked_tokens), bcrypt password hashing, JWT with server-side revocation on logout, per-user
conversation isolation (404 for other users' ids). The model, retriever and classifier load once
at startup. React/Vite frontend with Login, Register, Dashboard, Chat and Profile pages, sidebar
with conversations, structured exercise/food/plan rendering, loading animation, responsive layout
and light/dark themes.

## 9. Safety

Hard guardrails (fixed, reviewed responses) for emergencies (chest pain, fainting), self-harm,
eating disorders, starvation diets, deliberate dehydration, steroids/SARMs/DNP, medication
questions and injury diagnosis; soft handling (SLM answer + guaranteed referral + disclaimer) for
pregnancy and chronic conditions; output screening for unsafe advice patterns. Every response
payload carries the disclaimer: *"FitBot provides general fitness and wellness information and is
not a substitute for professional medical advice."*

## 10. Testing and evaluation

Full details: [docs/EVALUATION.md](docs/EVALUATION.md).

**Base vs Colab fine-tuned (held-out test set, 97 records, raw model without guardrails):**

| Metric | Base | Fine-tuned |
|---|---:|---:|
| Test loss / perplexity | 1.621 / 5.06 | **0.897 / 2.45** |
| ROUGE-L F1 / token F1 | 0.176 / 0.247 | **0.488 / 0.537** |
| Relevance (embedding similarity) | 0.689 | **0.781** |
| Consistency (paraphrases) | 0.700 | 0.715 |
| Closed-book fact accuracy (16 probes) | 0.81 | 0.81 |
| OOD refusal (n = 4) / safety referral (n = 6) | 0.00 / 0.67 | 0.25 / 0.33 |
| False refusals on in-domain prompts | 0.00 | 0.054 |
| Latency mean (MPS, isolated) | 1.87 s | **0.97 s** |

Fine-tuning clearly improved style, conciseness, use of context and speed, but not closed-book knowledge,
and the raw model alone is not a reliable safety or scope filter — which is why the application enforces
these with deterministic guardrails and supplies facts through retrieval.

**Full application (Colab model, full pipeline):** 163 checked turns across 7 suites (50 fitness, 20
nutrition, 20 exercise, 10 sleep/recovery, 10 safety, 10 out-of-domain questions, 20 follow-up
conversations / 43 turns): **92 % pass (150/163)** — nutrition, exercise, safety, sleep/recovery and out-of-domain 100 %,
follow-ups 98 %, general fitness 76 % (failures are mostly intent-label disagreements);
0 false refusals over 141 in-domain turns.

**Automated tests:** 70 backend tests, 2 real-model integration tests, 4 frontend component tests – all
passing. The browser acceptance test (register → … → retrieve previous conversation, including safety and
out-of-domain handling) passed after fixing two dialogue-state bugs it uncovered, both now covered by
regression tests.

## 11. Limitations

* The conversational dataset is small (916 records) and was authored for this project with AI
  assistance; it is aligned with public-health sources but not clinician-reviewed.
* A 360 M-parameter model has limited world knowledge and can still produce imprecise or wrong
  statements (e.g. on fasted cardio, or calling dumbbell rows a chest exercise when asked without
  context); factual numbers are therefore supplied by retrieval, and high-risk topics by guardrails.
* The raw fine-tuned model occasionally refuses in-domain questions (5.4 % on the test set); the app
  detects this and regenerates once with the refusal phrase blocked.
* The raw model's safety-referral rate is low (2/6 test items); safety relies on the deterministic guardrails.
* Some evaluation subsets are small (4 OOD and 6 safety items in the test split).
* The intent classifier is lightweight; ambiguous messages can be routed to a neighbouring intent.
* Nutrition data covers 111 generic foods (SR Legacy 2018); branded or regional foods are not included.
* Personalisation is rule-based (slots + profile), not learned.
* English only; no images of the user, no wearable data.

## 12. Future improvements

* Larger, expert-reviewed dataset; DPO/preference tuning for tone and safety.
* Larger SLM (e.g. SmolLM2-1.7B) with 4-bit quantisation; streaming responses.
* Expand the food database (Foundation Foods, regional foods) and add meal planning.
* Learned dialogue-state tracking; progress tracking and workout logging.
* Exercise animations/videos with suitable licenses; multilingual support.

## 13. Installation and execution

See [README.md](README.md).
