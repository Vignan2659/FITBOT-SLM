# FitBot dataset v2

Built by `scripts/build_dataset_v2.py` for fine tuning the 4B model (`training/FitBot_FineTuning_4B.ipynb`).
No external AI APIs; every exercise fact comes from free-exercise-db (871 cleaned exercises, `data/exercises/exercises_v2.json`), every food number from USDA FoodData Central, plans from the FitBot planner, and the remaining answers are hand written FitBot guidance (`scripts/dataset_content_v2/`).

**5,470 records** = 916 from v1 (unchanged, same splits) + 4,554 new.

| Split | Records |
|---|---:|
| train | 4,382 |
| validation | 527 |
| test | 561 |
| test_v1 (subset of test: the original 97 v1 test records, for comparing with the 360M model) | 97 |

| Category | Plan | Built | Train | Validation | Test |
|---|---:|---:|---:|---:|---:|
| Exercises (gym, home, outdoor, muscle, equipment) | 1,600 | 1,587 | 1,276 | 158 | 153 |
| Exercise instructions, form & safety | 500 | 534 | 423 | 54 | 57 |
| Workout plans & combinations | 400 | 450 | 359 | 42 | 49 |
| Beginner questions | 300 | 226 | 181 | 20 | 25 |
| General fitness | 600 | 624 | 498 | 60 | 66 |
| Nutrition & USDA foods | 700 | 826 | 663 | 77 | 86 |
| Sleep, hydration, recovery, cardio, stretching | 400 | 357 | 294 | 26 | 37 |
| Weight loss / muscle gain | 200 | 185 | 140 | 26 | 19 |
| Medical-safety referrals | 150 | 157 | 126 | 16 | 15 |
| Off topic refusals | 150 | 164 | 131 | 17 | 16 |
| Multi turn follow-ups | 400 | 360 | 291 | 31 | 38 |

* Exercises covered: **871** (all cleaned exercises; questions about an exercise use the same train/validation/test split as its photos in `data/image_dataset/`).
* Records with reference context: 4,349; with conversation history: 324; with a user profile: 252.
* Average answer length: 50.4 words.
* Questions include casual and typo variants ("hey, ...", "... pls", swapped letters) of hand written questions.
* Cleaning: duplicates (normalised question + history + profile) removed, conflicting answers to the same question removed, unsafe phrases blocked, and every number in a USDA answer must appear in its reference data (answers that quoted values not given to the model were dropped).
* Leakage: no group (paraphrases of one question / one conversation / one exercise) spans two splits; test questions also found in training after normalisation: 0.

Format: identical to v1 (`instruction, input, response, category, intent, context, history, profile, group_id, source, split, messages`) plus `table_category` and `dataset_version`. `messages` is produced by `backend/app/ml/prompting.py`, the same prompt builder the app uses.
