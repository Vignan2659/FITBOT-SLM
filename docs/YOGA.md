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
     └── Pose page       real photos of the pose, steps, breathing, safety, related poses
```

## Dataset

`data/yoga/yoga_poses.json`, built by `scripts/yoga/build_yoga.py` from the pose files in `scripts/yoga/`.

| | |
|---|---|
| Records | 61 (59 poses, 2 breathing practices), every one with real photos |
| Photos | 102 photos of real people (1 or 2 per pose) |
| Difficulty | 29 beginner, 26 intermediate, 6 advanced |
| Goals | flexibility, mobility, strength, balance, core, stress relief, relaxation, recovery, weight management, posture, breathing, meditation |
| Body areas | back, shoulders, hips, legs, core, full body, chest, neck |
| Categories | Flexibility, Mobility, Strength, Balance, Core, Back, Shoulders, Hips, Hamstrings, Recovery, Relaxation, Stress relief, Breathing, Meditation (plus Posture and Weight management) |

Every record has the fields of the requested schema:

`name, alternative_names, category, difficulty, target_areas, benefits, instructions, breathing, duration,
recommended_repetitions, beginner_modification, advanced_variation, common_mistakes, safety_tips, contraindications,
equipment, suitable_for, image, image_urls, tags`

plus the fields FitBot needs for filtering, routines and the chat: `slug, sanskrit, kind, goals, body_areas, phase,
time_of_day, energy, sides, default_minutes, related, photos` (each photo with its author, licence and source page).

All text was written for this project. It describes general wellness and avoids medical claims: benefits are phrased
as what a pose stretches or strengthens, every pose lists contraindications, and advanced poses tell the reader to learn
them with a qualified teacher.

Rebuild after editing a pose file:

```bash
python3 scripts/yoga/build_yoga.py
```

## Photos of real people

Every pose is shown with real photos of a person doing it, the same idea as the exercise library (photos, with a
second view on hover). There are no drawn or animated figures.

### Where the photos come from

The photos come from Wikimedia Commons, where every file has an explicit free licence. Most come from four consistent
studio series, so the cards look alike:

| Series on Wikimedia Commons | Photos used | Licence | Look |
|---|---|---|---|
| Kennguru, "Yoga-Asana Nina-Mel" | 29 | CC BY 3.0 | white studio background |
| Joseph Renger, asana series | 23 | CC BY-SA 3.0 | bright home studio |
| lululemon athletica | 13 | CC BY 2.0 | white studio background |
| Mr. Yoga | 11 | CC BY-SA 4.0 | light grey studio |
| Other individual photographers | 26 | CC BY, CC BY-SA or public domain | various |

Each photo was chosen by looking at it: one person, the whole body in frame, the pose clearly correct. The full list
with authors, licences and source pages is in [data/yoga/PHOTO_CREDITS.md](../data/yoga/PHOTO_CREDITS.md), and the
app shows the credit under every photo on the pose pages.

### Other datasets looked at

| Dataset | Why it is not used |
|---|---|
| [Yoga-82](https://sites.google.com/view/yoga-82/home) (28,000 images, 82 poses) | Only image links to third party websites, for non commercial research only; the photos cannot be shipped in this repository |
| Kaggle yoga pose image sets | Scraped from image search, with no rights from the people who took the photos |
| [Yoga Poses Dataset on GitHub](https://github.com/Manoj-2702/Yoga_Poses-Dataset) | Eight poses and no information about where the images come from |
| [Roboflow yoga image dataset](https://universe.roboflow.com/yogaposedata/yoga-image-dataset) | Only two poses (down dog and goddess) |

Those sets are built to train pose classifiers, not to show people how to do a pose. For FitBot, a smaller set of
clear, correctly credited photos per pose is more useful.

### Files and performance

* `frontend/public/yoga/photos/<slug>-<n>.jpg`: pose page size (longest side 800 px)
* `frontend/public/yoga/photos/thumb/<slug>-<n>.jpg`: card size (longest side 420 px), about 25 KB each

All 102 photos take 4.7 MB in total. Cards load only the small version and only when they scroll into view, and the
service worker caches the photos after the first visit. `scripts/yoga/process_photos.py` makes both sizes from
downloaded originals, and `data/yoga/photo_credits.json` lists which file belongs to which pose.

### Licences

* Pose text and data: written for FitBot, MIT (see `LICENSE`).
* Photos: each under its own licence (CC BY, CC BY-SA or public domain), credited per photo. Resizing does not change
  the licence; anyone reusing the photos must keep the credit and, for CC BY-SA photos, the same licence.
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
├── image_path, image_urls          (main photo, all photos)
└── details                          (JSON: the full pose record with photo credits)
```

The table is rebuilt from the data file automatically on every start, so no migration step is needed. `/health` now reports `yoga_poses` in its database
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

* `backend/tests/test_yoga.py`: 25 tests for the dataset, photos and credits, API, routine builder, chat answers, follow ups,
  safety and unchanged behaviour of non yoga questions.
* `frontend/src/test/components.test.jsx`: yoga card, routine and chat message rendering.
* `e2e/test_e2e.py`: a browser test of the Yoga section, filters, pose page, routine builder and yoga chat.
