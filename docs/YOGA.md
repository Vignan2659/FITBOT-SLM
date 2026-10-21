# Yoga module

Yoga is part of FitBot itself, not a separate app. It has its own section in the web app (below Dashboard and Chat in the
sidebar), its own table in the database, its own endpoints, and it plugs into the same chat pipeline and retriever as the
rest of FitBot, so the model can answer yoga questions from real pose data.

```
FitBot
├── Dashboard            (now with a Yoga row)
├── Chat                 (yoga questions get pose cards or a timed routine)
└── Yoga
     ├── Yoga poses      search + filters (difficulty, goal, body area)
     ├── Categories      16 categories, each opens the filtered pose list
     ├── Goals           poses or a routine for each goal
     ├── Routine builder time, level, goal, focus area, morning or evening
     └── Pose page       motion figure, start → transition → final, steps, breathing, safety, related poses
```

## Dataset

`data/yoga/yoga_poses.json`, built by `scripts/yoga/build_yoga.py` from the pose files in `scripts/yoga/`.

| | |
|---|---|
| Records | 63 (60 poses, 3 breathing and meditation practices) |
| Difficulty | 35 beginner, 22 intermediate, 6 advanced |
| Goals | flexibility, mobility, strength, balance, core, stress relief, relaxation, recovery, weight management, posture, breathing, meditation |
| Body areas | back, shoulders, hips, legs, core, full body, chest, neck |
| Categories | Flexibility, Mobility, Strength, Balance, Core, Back, Shoulders, Hips, Hamstrings, Recovery, Relaxation, Stress relief, Breathing, Meditation (plus Posture and Weight management) |

Every record has the fields of the requested schema:

`name, alternative_names, category, difficulty, target_areas, benefits, instructions, breathing, duration,
recommended_repetitions, beginner_modification, advanced_variation, common_mistakes, safety_tips, contraindications,
equipment, suitable_for, image, motion_image, tags`

plus the fields FitBot needs for filtering, routines and the chat: `slug, sanskrit, kind, goals, body_areas, phase,
time_of_day, energy, sides, default_minutes, related, frames, frame_labels, photo_reference, image_license`.

All text was written for this project. It describes general wellness and avoids medical claims: benefits are phrased
as what a pose stretches or strengthens, every pose lists contraindications, and advanced poses tell the reader to learn
them with a qualified teacher.

Rebuild after editing a pose file:

```bash
python3 scripts/yoga/build_yoga.py
```

## Motion visuals

The exercise library shows two photos per exercise (start and end position) and swaps them on hover. Yoga follows the
same idea but goes one step further: each pose is described by two or three key positions (start, transition, final)
as joint angles of a simple figure, and the builder turns them into

* `frontend/public/yoga/<slug>.svg`: an animated figure that moves smoothly from start to final and back
  (SVG with SMIL animation, so it works inside a normal `<img>` tag with no JavaScript),
* `frontend/public/yoga/<slug>-1.svg` … `-3.svg`: one still per key position for the "How it moves" strip.

Side views draw the far arm and leg lighter so depth reads clearly. A figure is 8 to 13 KB, the whole set (244 files) is
about 0.9 MB, cards load them lazily, and the service worker caches them after first use. Visitors who ask their system
for reduced motion get the final still instead of the animation.

### Which visual data, and why this choice

| Option looked at | Verdict |
|---|---|
| Yoga-82 and similar research datasets | Lists of image links collected from the web; the images belong to their owners and are meant for research, so they cannot be shipped in this repository |
| Yoga pose image sets on Kaggle | Mostly scraped from image search with unclear or non commercial licences; static photos only |
| Wikimedia Commons yoga photos | Usable with attribution (often CC BY-SA), but one static photo per pose, mixed styles and backgrounds, and per image credit lines |
| free-exercise-db (already in FitBot) | Public domain and already used for exercise photos, but it only covers a handful of yoga-like movements |
| Original figures generated from joint angles | Consistent style, shows the movement (not just the final position), tiny files, and fully owned by the project |

FitBot therefore uses its own generated figures for every pose, and where the existing public domain exercise library
already has the same movement (Child's Pose, Cat Stretch, Bridge, Plank, Side Bridge, Locust, Pyramid, seated stretches)
the pose page also shows those photos as a "Photo reference" instead of downloading duplicates.

Mapping: pose record → `motion_image` and `frames` (generated figure) → optional `photo_reference` (existing exercise
photos) → yoga card and pose page.

### Licences

* Pose text, data and motion figures: original work for FitBot, MIT (see `LICENSE`).
* Photo references: free-exercise-db by yuhonas, public domain (Unlicense), the same source as the exercise library.
* General safety framing in the yoga guidance passages follows the US National Center for Complementary and
  Integrative Health page "Yoga: What You Need To Know" (US government work, public domain).

## Database

New table `yoga_poses`, re-synced from `data/yoga/yoga_poses.json` on every start, exactly like the exercise and food
tables:

```
yoga_poses
├── id, slug, name, sanskrit
├── difficulty, kind, phase
├── category, goals, body_areas      (JSON)
├── image_path, motion_asset_path
└── details                          (JSON: the full pose record)
```

The table is created automatically; no migration step is needed. `/health` now reports `yoga_poses` in its database
counts.

## API

All public and read only, like `/exercises`.

| Endpoint | What it returns |
|---|---|
| `GET /yoga/poses?difficulty=&goal=&area=&category=&kind=&q=` | pose summaries for cards; filters combine |
| `GET /yoga/poses/{slug}` | the full pose plus `related_poses` (also accepts a name, e.g. `downward dog`) |
| `GET /yoga/filters` | filter options with counts |
| `GET /yoga/routine?minutes=15&level=Beginner&goal=&area=&time_of_day=` | a timed routine (5 to 60 minutes) |

Through the web app the same endpoints are reached under `/api/yoga/...`.

## How yoga reaches the model

```
question
  → safety screening (unchanged; pregnancy and medical questions keep their existing path)
  → yoga understanding: pose names, "yoga" + routine / pose words, goal, body area, minutes, level, morning or evening
  → one of three answers
       detail   "Explain how to perform Warrior II"      full pose facts (steps, breathing, easier version, safety)
       list     "Which yoga poses target the hips?"     semantic search over pose documents + goal / area scoring
       routine  "I have 15 minutes. Give me a routine"  routine builder (exact minutes, level aware)
  → yoga guidance passages from the retriever's yoga collection
  → FitBot 4B writes the answer from that reference information
  → cards or the routine come straight from the data
```

* The retriever got two extra collections, `yoga` (13 guidance passages) and `yoga_poses` (one document per pose).
  They use the same MiniLM embedding model as the main knowledge base but are searched separately, so the results for
  every existing question are exactly what they were before.
* Questions that only mention yoga in passing ("Is yoga enough exercise?") stay with the normal pipeline and simply get
  one yoga guidance passage added.
* Names that are also normal exercises ("plank", "glute bridge", "child's pose") only switch to yoga when the word yoga
  is in the question, so existing exercise answers do not change.
* Follow ups work: "make it 30 minutes" or "I'm a beginner" after a yoga answer rebuilds the routine.
* Pain or injury words keep the answer to gentle beginner poses, drop poses whose contraindications mention that body
  area, and add a referral and the disclaimer. Advanced poses always come with the disclaimer.

The fine tuned model was not trained on yoga conversations; it answers from the reference lines it is given, which is
how it already handles the 871 exercises. A future dataset version can add yoga conversations built from this data.

## Routine builder

A routine follows the usual shape of a class: settle, warm up, main part, cool down, final relaxation. The main part
depends on the goal (calm goals and evenings use floor poses; strength, weight management, core and balance use
standing and core work). Poses are scored on goal, focus area, time of day and difficulty, never repeat, never include
inversions, and the holds are adjusted in half minute steps until the total matches the requested time exactly. Poses
done on each side show "1 min each side". Every step links to its pose page, and a routine can be logged in My workouts.

## Tests

* `backend/tests/test_yoga.py`: 23 tests for the dataset, visuals, API, routine builder, chat answers, follow ups,
  safety and unchanged behaviour of non yoga questions.
* `frontend/src/test/components.test.jsx`: yoga card, routine and chat message rendering.
* `e2e/test_e2e.py`: a browser test of the Yoga section, filters, pose page, routine builder and yoga chat.
