# FitBot – Dataset Research

All metadata below (licenses, row counts, fields) was collected on **2026‑10‑03** directly
from the Hugging Face Hub API (`/api/datasets/<id>`), the Hugging Face dataset viewer
API (`datasets-server.huggingface.co/size|first-rows|statistics`), the GitHub API and
the USDA FoodData Central download page. Sample rows were inspected manually.

FitBot needs three different kinds of data, so the research is split accordingly:

| Need | Used for | Selected source |
|------|----------|-----------------|
| **A. Conversational training data** | Fine‑tuning the SLM (instruction → response) | **FitBot Curated Conversational Dataset** (built in this project, grounded in B + C) |
| **B. Structured exercise data + images** | Exercise cards, workout planner, retrieval context | **free-exercise-db** (yuhonas), Unlicense / public domain |
| **C. Structured nutrition data** | Food cards, exact nutrient values, retrieval context | **USDA FoodData Central – SR Legacy**, CC0 1.0 |
| D. Intent / out‑of‑domain examples (supporting) | Training the intent + OOD classifier | **harshmakwana/fitness-intent**, MIT (+ FitBot's own labelled questions) |

---

## 1. Conversational datasets investigated (Hugging Face)

| Dataset | Rows | License (declared) | Fields | Assessment |
|---|---:|---|---|---|
| [its-myrto/fitness-question-answers](https://huggingface.co/datasets/its-myrto/fitness-question-answers) | 965 | **none declared** | `Question`, `Answer` | Relevant, short single‑turn QA "gathered from the web". **No license → cannot be redistributed or relied on.** All lower‑case. Rejected. |
| [HazSylvia/Fitness_Unformatted](https://huggingface.co/datasets/HazSylvia/Fitness_Unformatted) | 928 | MIT | `Human`, `Assistant` | Appears to be the same content as `its-myrto` with **all punctuation stripped** ("planks bicycle crunches and leg raises are great…"). Upstream provenance unclear and text quality is poor for generation. Rejected. |
| [onurSakar/GYM-Exercise](https://huggingface.co/datasets/onurSakar/GYM-Exercise) | 1,660 | **none declared** | `text` (Llama‑2 `[INST]` format) | Mixes fitness with off‑topic items (environmental noise, home toxins). No license. Rejected. |
| [hammamwahab/fitness-qa](https://huggingface.co/datasets/hammamwahab/fitness-qa) | 123,153 | Apache‑2.0 | `context`, `question`, `answer` | Large, but synthetic extractive QA from encyclopedic contexts (answers are copied context or "I don't have data on that"). Not conversational, no coaching style. Rejected for SFT. |
| [rodriguescarson/adaption-fitness-seed-c2](https://huggingface.co/datasets/rodriguescarson/adaption-fitness-seed-c2) | 1,881 | MIT | `original_prompt/completion`, `enhanced_*` | Workout‑plan generation only. Spot checks found **internal contradictions** (e.g. "8 sets of 15–20 pull‑ups" for intermediates, Leg Press inside a *dumbbell push* workout, plans labelled "flexibility" with no flexibility work). `enhanced_*` columns are empty in the sampled rows. Rejected (quality). |
| [MehulGupta03/fitness-recommendation-dataset](https://huggingface.co/datasets/MehulGupta03/fitness-recommendation-dataset) | 14,589 | Apache‑2.0 | `Sex, Age, Height, Weight, Hypertension, Diabetes, BMI, Fitness Goal, Exercises, Diet, Recommendation` | Tabular, templated recommendations; heavily keyed on medical conditions (hypertension/diabetes) which FitBot must *not* personalise on. Not conversational. Rejected. |
| [harshmakwana/fitness-intent](https://huggingface.co/datasets/harshmakwana/fitness-intent) | 960 / 120 / 120 | MIT | `text`, `intent` (6 balanced classes: find_exercise, generate_plan, get_nutrition_info, log_feeling, general_chat, out_of_scope) | Clean, balanced, licensed. **Not suitable for SFT** (no responses) but **useful as supporting data for the intent/out‑of‑domain classifier.** Selected (supporting). |

**Conclusion.** No public, permissively licensed dataset offered *high‑quality, conversational,
multi‑turn, safety‑aware* fitness + nutrition responses. The licensed ones were either
off‑format (extractive QA, tabular), internally inconsistent, or unlicensed. Training
an assistant on contradictory or unlicensed data would violate the project rules, so the
main conversational dataset was **built in this project** (Section 4).

## 2. Exercise datasets investigated

| Source | Size | License | Images | Assessment |
|---|---:|---|---|---|
| [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db) | **876 exercises** | **Unlicense (public domain)** – verified via GitHub API | 2 photos per exercise, served from `raw.githubusercontent.com` | Fields: `name, force, level, mechanic, equipment, primaryMuscles, secondaryMuscles, instructions[], category, images[]`. Levels: 525 beginner / 294 intermediate / 57 expert. **Selected.** |
| [RepDB/exercise-dataset](https://huggingface.co/datasets/RepDB/exercise-dataset) | 609 | `other` ("repdb-free") | WebP illustrations | Good quality but custom license requiring visible attribution; redistribution of animations not permitted. Not selected (licensing friction). |
| [Harrish27/exercise-dataset](https://huggingface.co/datasets/Harrish27/exercise-dataset) | – | – | – | A duplicate of RepDB. Rejected. |
| [wger.de API](https://wger.de/api/v2/) | 378 images (API count) | CC‑BY‑SA (per‑image license fields) | Partial coverage | Viable, but per‑image licensing and partial coverage. Kept as a documented alternative. |

**Image policy.** Every image URL in FitBot is constructed from the real `images[]`
paths of free-exercise-db (`https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/<path>`)
and **each URL used by the curated exercise set is checked with an HTTP request**
by `scripts/build_exercise_db.py`. No URL is invented.

## 3. Nutrition datasets investigated

| Source | Size | License | Assessment |
|---|---:|---|---|
| **[USDA FoodData Central – SR Legacy (2018‑04)](https://fdc.nal.usda.gov/download-datasets/)** | **7,793 foods** | **CC0 1.0 / public domain** | Lab‑derived values per 100 g with ~100+ nutrients, plus household portions with gram weights (e.g. "1 large egg = 50 g"). Static (final release), well suited to generic foods. **Selected.** |
| USDA FoodData Central – Foundation Foods (2026‑04) | smaller | CC0 1.0 | Highest analytical quality but limited coverage and fewer portion records. Documented alternative. |
| USDA FDC – Branded Foods | ~400k+ | CC0 1.0 | Brand/label data; not needed for generic advice. Not selected. |
| Open Food Facts | millions | ODbL | Crowd‑sourced, share‑alike; quality varies. Not selected. |

From SR Legacy, `scripts/build_food_db.py` extracts a curated subset of common
fitness‑relevant foods (protein sources, grains, fruit, vegetables, dairy, fats,
beverages, snacks) and stores, **exactly as published by USDA**: calories, protein,
carbohydrate, fat, fiber, sugars, sodium, saturated fat, potassium, calcium, iron,
plus portion gram weights. Per‑portion values are **computed** (value per 100 g ×
portion grams / 100) and labelled as such.

## 4. Selected main conversational dataset – FitBot Curated Conversational Dataset

| Property | Value |
|---|---|
| Source | Built in this repository by `scripts/build_dataset.py` |
| License | Released with the project (MIT) |
| Grounding | Exercise facts from free-exercise-db; nutrient numbers only from USDA SR Legacy; general guidance written to agree with public‑health guidance (U.S. HHS *Physical Activity Guidelines for Americans*, 2nd ed.; *Dietary Guidelines for Americans 2020–2025*; CDC/AASM adult sleep recommendation of ≥7 h) |
| Format | JSONL – `instruction`, `input`, `response`, `category`, plus `context` (retrieved facts, optional), `history` (previous turns, optional), `group_id` |
| Record types | single‑turn Q&A, follow‑ups with history, context‑grounded (RAG) answers, comparisons, "what should I do / avoid", safety redirections, out‑of‑domain refusals |
| Splits | train / validation / test, split **by `group_id`** (all paraphrases of one question stay in the same split → no test leakage) |

Final record counts, category distribution and cleaning statistics are produced by
the build script and recorded in [`data/processed/dataset_stats.json`](../data/processed/dataset_stats.json)
and summarised in the section *Final dataset statistics* below.

### Limitations

* The conversational responses were authored for this project (with assistance from
  an AI coding assistant during development) and reviewed against the public‑health
  sources above; they are **not** clinician‑validated.
* Size (~1k records) is appropriate for domain adaptation with LoRA but is small;
  the model's factual coverage is supplemented by retrieval (Sections 2–3).
* SR Legacy is a 2018 static release; values for modern products may differ.
* free-exercise-db photos vary in style; a few exercises have only generic images.
* English only.

## Final dataset statistics

Generated by `scripts/build_dataset.py` (seed 42) - see `data/processed/dataset_stats.json`.

| Item | Value |
|---|---:|
| Raw records generated | 927 |
| Removed as duplicates | 11 |
| Removed as empty / length / unsafe / contradictory | 0 / 0 / 0 / 0 |
| **Clean records** | **916** |
| Train / validation / test | 726 / 93 / 97 |
| Groups train / validation / test | 379 / 49 / 49 |
| Test inputs also present in train (normalised) | 0 |
| Records with retrieved context / history / profile | 632 / 52 / 27 |
| Average response length | 50.3 words |

**By category:** food 200, workout_exercises 190, cardio_endurance 49, home_workouts 47, stretching_flexibility 46, nutrition 44, workout_planning 41, out_of_domain 41, medical_safety 40, weight_loss 36, muscle_building 27, hydration 27, recovery_sleep 27, pre_post_workout 26, gym_workouts 21, fitness_equipment 17, exercise_safety 15, healthy_lifestyle 13, greeting 9

**By intent:** food_search 200, exercise_search 182, nutrition_question 73, home_workout 59, stretching 46, medical_safety 41, out_of_domain 41, workout_plan 40, cardio 37, weight_loss 34, hydration 27, muscle_gain 25, general_fitness 23, gym_workout 21, equipment 17, recovery 16, exercise_safety 14, sleep 11, greeting 9

**By source:** seed 329, exercise_db 191, usda 183, conversation 85, planner 48, safety 40, ood 40 (seed = hand-written Q&A with paraphrases; conversation = multi-turn; exercise_db / usda / planner = grounded in structured data; safety / ood = refusal and redirection examples)
