# FitBot – Fitness-Domain Small Language Model

FitBot is a conversational fitness and wellness assistant built around a **locally-running small
language model** (SmolLM2-360M-Instruct, LoRA fine-tuned on a Google Colab GPU) with retrieval over
real exercise and nutrition data, a React chat interface, a FastAPI backend, SQLite storage,
authentication, and a safety layer.

> FitBot provides general fitness and wellness information and is not a substitute for professional medical advice.

## Features

* Conversational answers about workouts, exercises, weight loss, muscle building, cardio, nutrition,
  food, hydration, pre/post-workout eating, sleep, recovery, stretching, equipment and lifestyle.
* **Exercise cards with real images** (58 curated exercises, 876 in the catalog) from the public-domain
  free-exercise-db: target muscles, equipment, difficulty, description, instructions, safety tip.
* **Food / nutrition cards with USDA FoodData Central values** (111 foods, SR Legacy, CC0) – exact
  values per 100 g and per USDA household portion (switchable): macros with energy split, % Daily Value
  (FDA, 2,000 kcal), protein per 100 kcal, cholesterol, fat breakdown, potassium, calcium, iron, magnesium,
  zinc, vitamins A/C/D/B12, caffeine and water; unknown foods or missing nutrients are never estimated.
* **Workout planner**: beginner→advanced, gym/home/dumbbell/bodyweight, 1–6 days, sets/reps/rest + images.
* **Follow-up context and personalisation** ("I'm a beginner" → "I only have dumbbells"), optional profile
  (age, height, weight, level, goal, diet, equipment, location).
* **Intent detection** (19 intents incl. out-of-domain) and semantic retrieval (sentence-transformers).
* **Safety**: guardrails for emergencies, eating disorders, starvation, dehydration, PEDs, medication and
  injury diagnosis; referral + disclaimer for medical topics; output screening.
* Accounts (bcrypt + JWT with server-side logout), private chat history, conversation management.
* **My workouts**: save plans from chat, log a plan day in one click or several exercises at once, weekly
  active-day chart, 🔥 streak and most-logged exercises (with best weight).
* 👍/👎 **feedback** on every answer (`scripts/export_feedback.py` exports ratings for review),
  **read aloud** and **voice input** (browser Web Speech API; the mic button appears only where supported).
* **Installable app (PWA)**: manifest + icons; the production build adds an offline app shell (service worker,
  `/api` is never cached).

## Project structure

```
FitBot/
├── backend/            FastAPI app (api/, core/, db/, services/, ml/) + pytest tests
├── frontend/           React + Vite app (pages, components, vitest tests)
├── data/
│   ├── raw/            downloaded sources (re-created by scripts, not committed)
│   ├── exercises/      exercises.json (curated) + catalog.json (full free-exercise-db)
│   ├── nutrition/      foods.json (USDA SR Legacy subset)
│   ├── knowledge/      knowledge_base.json (retrieval passages)
│   └── processed/      training.jsonl · validation.jsonl · test.jsonl · dataset_stats.json
├── models/             fine-tuned model + intent classifier (not committed)
├── training/           FitBot_FineTuning.ipynb (Colab) + generator + README
├── evaluation/         evaluate.py, run_test_suites.py, test_suites/, results, charts, reports
├── docs/               DATASET_RESEARCH · MODEL_SELECTION · ARCHITECTURE · TRAINING_GUIDE · EVALUATION
├── scripts/            data builders, intent classifier training, Colab packaging, model install
├── README.md · PROJECT_REPORT.md · .gitignore
```

## Technology stack

| Layer | Tech |
|---|---|
| Frontend | React 18, Vite 5, React Router, plain CSS (tokens, light/dark, responsive), Vitest |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2, SQLite, bcrypt, PyJWT, pytest |
| ML | PyTorch, Hugging Face Transformers, PEFT (LoRA), Datasets, Sentence Transformers, scikit-learn |
| Model | `HuggingFaceTB/SmolLM2-360M-Instruct` (Apache-2.0) fine-tuned with LoRA on Google Colab |
| Data | free-exercise-db (Unlicense), USDA FoodData Central SR Legacy (CC0), harshmakwana/fitness-intent (MIT) |

No paid or external LLM APIs are used; everything runs locally after setup.

## Installation

Prerequisites: Python 3.10+ (tested 3.12), Node.js 18+ (tested 20), ~3 GB disk.

```bash
cd FitBot
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt -r training/requirements.txt
cp backend/.env.example backend/.env       # then set a long random JWT_SECRET
cd frontend && npm install && cd ..
```

Build the data (already included in the repository; re-run to regenerate from the sources):

```bash
.venv/bin/python scripts/build_exercise_db.py
.venv/bin/python scripts/build_food_db.py
.venv/bin/python scripts/build_dataset.py
.venv/bin/python scripts/train_intent_classifier.py
```

## Training the SLM (Google Colab GPU)

```bash
.venv/bin/python scripts/package_for_colab.py        # -> FitBot_colab_data.zip
```

Upload the zip to `MyDrive/FitBot/`, open `training/FitBot_FineTuning.ipynb` in Colab with a GPU
runtime, *Run all*, download `fitbot-smollm2-360m-lora-adapter.zip` (≈35 MB; the installer merges it into the base model locally), then:

```bash
.venv/bin/python scripts/install_model.py ~/Downloads/fitbot-smollm2-360m-lora-adapter.zip
```

Details: [training/README.md](training/README.md) and [docs/TRAINING_GUIDE.md](docs/TRAINING_GUIDE.md).
If no fine-tuned model is installed the backend falls back to the base model and `/health` reports
`"fine_tuned": false`.

## Running

```bash
# terminal 1 – backend (http://127.0.0.1:8000, docs at /docs)
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000

# terminal 2 – frontend (http://localhost:5173)
cd frontend && npm run dev
```

## Testing and evaluation

```bash
cd backend && ../.venv/bin/python -m pytest            # API, auth, chat pipeline, safety, NLU, planner
cd backend && ../.venv/bin/python -m pytest -m slm     # end-to-end with the real fine-tuned model
cd frontend && npx vitest run                          # React component tests
.venv/bin/python -m pytest e2e -q                      # browser tests (Playwright) - needs both servers running
.venv/bin/python evaluation/evaluate.py                # base vs fine-tuned on the held-out test set
.venv/bin/python evaluation/run_test_suites.py         # 140 questions / 20 conversations, real model
```

### Results at a glance (model fine-tuned on Google Colab, Tesla T4)

| | Base SmolLM2-360M | Fine-tuned FitBot |
|---|---:|---:|
| Test perplexity | 5.06 | **2.45** |
| ROUGE-L F1 (test) | 0.176 | **0.488** |
| Mean latency per answer (Apple M5, MPS) | 1.87 s | **0.97 s** |

Full pipeline with the real model: **92 % of 163 checked turns pass** (nutrition, exercise, safety and
out-of-domain suites 100 %). All automated tests pass (78 backend, 2 real-model, 6 frontend, 5 end-to-end browser).
Details and limitations: [docs/EVALUATION.md](docs/EVALUATION.md),
[evaluation/evaluation_report.md](evaluation/evaluation_report.md).

## Dataset v2 and the 4B model (college GPU)

* **Dataset v2** (`data/processed_v2/`, see its `README.md`): 5,470 conversations built from all **871** cleaned
  exercises (was 58), USDA foods, the planner and new hand-written topics, balanced across 11 categories.
  Rebuild: `.venv/bin/python scripts/build_exercise_catalog_v2.py && .venv/bin/python scripts/build_dataset_v2.py`.
* **4B fine-tuning:** `training/FitBot_FineTuning_4B.ipynb` fine-tunes `Qwen/Qwen3-4B-Instruct-2507` with QLoRA on
  a 12 GB NVIDIA GPU. Package everything for the GPU PC with `.venv/bin/python scripts/package_for_gpu_pc.py`
  (→ `FitBot_4B_Training_Kit.zip`) and follow `training/COLLEGE_PC_GUIDE.md`.
* The running app still uses the 360M model and the 58-exercise catalog until the 4B model has been trained
  and evaluated.

## Documentation

* [PROJECT_REPORT.md](PROJECT_REPORT.md) – full project report
* [docs/DATASET_RESEARCH.md](docs/DATASET_RESEARCH.md) – datasets investigated and selected
* [docs/MODEL_SELECTION.md](docs/MODEL_SELECTION.md) – model comparison and choice
* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) – system design, database, API
* [docs/TRAINING_GUIDE.md](docs/TRAINING_GUIDE.md) – Colab training procedure
* [docs/EVALUATION.md](docs/EVALUATION.md) – methodology and results

## Data licenses and attribution

* Exercise data and images: [free-exercise-db](https://github.com/yuhonas/free-exercise-db) by yuhonas – Unlicense (public domain).
* Nutrition data: U.S. Department of Agriculture, Agricultural Research Service. FoodData Central, SR Legacy (2018). CC0 1.0.
* Intent examples: [harshmakwana/fitness-intent](https://huggingface.co/datasets/harshmakwana/fitness-intent) – MIT.
* Base model: [SmolLM2-360M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct) – Apache-2.0.
