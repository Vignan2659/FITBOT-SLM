# FitBot – Architecture

## 1. Overview

```
┌────────────── React + Vite frontend (frontend/) ──────────────┐
│ Login · Register · Dashboard · Chat · Profile                  │
│ Exercise cards (images) · Food cards (USDA) · Workout plans    │
└───────────────┬────────────────────────────────────────────────┘
                │ JSON over HTTP (JWT bearer token), Vite proxy /api → :8000
┌───────────────▼──────────── FastAPI backend (backend/app) ─────┐
│ api/        auth · conversations · chat · exercises · foods · health
│ core/       settings (.env) · bcrypt hashing · JWT + revocation
│ db/         SQLAlchemy models · SQLite · seeding from data/
│ services/   chat_engine (pipeline) · nlu · safety · catalog · planner
│ ml/         prompting (shared with training) · retriever · slm
└───────────────┬────────────────────────────────────────────────┘
                │ loaded once at startup (FastAPI lifespan)
┌───────────────▼────────────────────────────────────────────────┐
│ Fine tuned Qwen3-4B (merged QLoRA)     · all-MiniLM-L6-v2       │
│ intent classifier (TF-IDF+MiniLM → LR) · SQLite (fitbot.db)     │
└────────────────────────────────────────────────────────────────┘
```

Training happens **off-machine on an NVIDIA GPU** (see [TRAINING_GUIDE.md](TRAINING_GUIDE.md)); the
exported model is installed into `models/` and loaded by the backend.

## 2. Chat pipeline (`backend/app/services/chat_engine.py`)

```
user message
 │
 ├─1 Safety screen (services/safety.py)
 │     hard risk (emergency, self-harm, eating disorder, starvation, dehydration, PEDs,
 │     medication, injury diagnosis) ──► reviewed guardrail response + disclaimer ──► done
 │     soft risk (pregnancy, chronic condition) ──► flagged, continue
 │
 ├─1b Yoga understanding (services/yoga.py): pose names, or "yoga" + routine / pose words
 │     ──► yoga cards, pose details or a timed routine + yoga guidance, then the SLM answers (see docs/YOGA.md)
 │
 ├─2 Intent detection (services/nlu.py)
 │     TF-IDF(word+char) ⊕ MiniLM embedding → logistic regression  ⊕  fitness-domain lexicon guardrail
 │     out_of_domain ──► fixed scope message ──► done
 │
 ├─3 Slots + dialogue state  (muscle group, level, equipment, location, goal, days, diet, foods, exercises)
 │     "I'm a beginner" / "I only have dumbbells" = constraint-only follow up → keep previous intent/topic
 │     state is stored per conversation (conversations.state JSON); profile fills missing slots
 │
 ├─4 Retrieval
 │     structured: exercise DB (filters by group/level/equipment) · USDA foods (by name or topic)
 │                 · workout planner (multi-day plan or single-muscle workout)
 │     semantic:   knowledge-base passages via sentence-transformers (TF-IDF fallback)
 │
 ├─5 Prompt (ml/prompting.py, identical to training format)
 │     system prompt + user profile + "Reference information" lines + last exchange + question
 │
 ├─6 Fine tuned SLM generation (ml/slm.py, greedy, repetition_penalty 1.1, ≤220 tokens)
 │     if the model emits its out of scope refusal for an in domain question, regenerate once with the
 │     refusal phrase blocked (bad_words_ids)
 │
 ├─7 Output safety: unsafe-advice patterns → safe fallback; medical intents → referral + disclaimer
 │
 └─8 Structured response
       {answer, category/intent, exercises[], foods[], workout_plan, sources[], safety, model}
```

Why this design:

* **The SLM writes every normal answer.** Cards, plans and numbers come from structured data so
  that the model never needs to invent an exact nutrient value, an exercise image URL or a set/rep
  scheme – reducing hallucinations (the model was trained on the same context format).
* **Guardrails are deterministic** for the small set of high-risk situations and for out of domain
  questions, so behaviour there does not depend on generation quality.
* **One prompt builder** (`prompting.py`) is used by `scripts/build_dataset.py` and the backend, so
  training and inference prompts match token-for-token.

## 3. Data flow and sources

| Store | Built by | Used for |
|---|---|---|
| `data/exercises/exercises_v2.json` (871, used by the app), `exercises.json` (58 curated, v1) and `catalog.json` (876 raw) | `scripts/build_exercise_catalog_v2.py` / `scripts/build_exercise_db.py` from free-exercise-db (Unlicense) | exercise cards, planner, dataset grounding, `exercise_metadata` table |
| `data/nutrition/foods.json` (111 foods) | `scripts/build_food_db.py` from USDA SR Legacy (CC0) | food cards, nutrition context, dataset grounding, `food_metadata` table |
| `data/knowledge/knowledge_base.json` (76 passages) | written for the project, aligned with HHS/DGA/CDC/NASEM/ISSN/ACSM sources | semantic retrieval context |
| `data/processed/*.jsonl` | `scripts/build_dataset.py` | SLM fine tuning (train/val/test) |
| `models/intent_classifier.joblib` | `scripts/train_intent_classifier.py` | intent + out of domain detection |

## 4. Database (SQLite + SQLAlchemy, `backend/app/db/models.py`)

| Table | Key columns |
|---|---|
| `users` | id, email (unique), name, password_hash (bcrypt), created_at |
| `user_profiles` | user_id (1:1), age, height_cm, weight_kg, fitness_level, goal, dietary_preference, equipment (JSON), location |
| `conversations` | id, user_id (FK, cascade), title, state (JSON dialogue state), created_at, updated_at |
| `messages` | id, conversation_id (FK, cascade), role, content, intent, payload (JSON cards/plan/sources), created_at |
| `exercise_metadata` | name, slug, muscle_group, description, target/secondary muscles, equipment, difficulty, instructions, safety_tips, image_url(s), image_license |
| `food_metadata` | name, fdc_id, usda_description, group, tags, aliases, per_100g (JSON), portion (JSON), highlights, source, source_url |
| `yoga_poses` | slug, name, sanskrit, difficulty, kind, phase, category / goals / body_areas (JSON), image_path, motion_asset_path, details (JSON full pose record) |
| `revoked_tokens` | jti, expires_at (server-side logout) |
| `saved_plans` | id, user_id (FK, cascade), title, plan (JSON, as returned by `/chat`), created_at |
| `workout_logs` | id, user_id (FK, cascade), day, exercise, sets, reps, weight_kg, minutes, notes, created_at |
| `message_feedback` | id, user_id, message_id (FK, cascade; unique per user), rating (+1 / -1), created_at |

Metadata tables are re-synced from `data/` at every startup. SQLite foreign keys are enabled so
deleting a user/conversation cascades to its messages.

## 5. Authentication

* Passwords hashed with **bcrypt** (12 rounds); never stored or returned in plain text.
* **JWT** (HS256, `JWT_SECRET` from `.env`) with `sub`, `jti`, `iat`, `exp` (24 h default).
* `/auth/logout` stores the token's `jti` in `revoked_tokens`; every authenticated request checks it,
  so a logged-out token is rejected immediately.
* Conversation, plan, workout-log and feedback endpoints filter by `user_id`; another user's id returns
  **404** (no information leak).

## 6. API

| Method | Path | Auth | Description |
|---|---|:-:|---|
| POST | `/auth/register` | – | create account → token + user |
| POST | `/auth/login` | – | email + password → token |
| GET | `/auth/me` | ✓ | current user + profile |
| POST | `/auth/logout` | ✓ | revoke current token |
| GET / PUT | `/auth/profile` | ✓ | read / update personalisation profile |
| POST | `/conversations` | ✓ | new conversation |
| GET | `/conversations` | ✓ | list own conversations (newest first) |
| GET | `/conversations/{id}` | ✓ | conversation with messages and stored cards |
| DELETE | `/conversations/{id}` | ✓ | delete conversation (+ messages) |
| POST | `/chat` | ✓ | `{message, conversation_id?}` → structured answer (creates conversation if needed) |
| GET | `/exercises` | – | filters: `muscle_group`, `difficulty`, `equipment`, `q` |
| GET | `/exercises/{name}` | – | by name, slug or alias |
| GET | `/foods` | – | filters: `group`, `tag`, `q` |
| GET | `/foods/{name}` | – | by name or alias; 404 instead of estimating unknown foods |
| POST / GET | `/plans` | ✓ | save a workout plan from a chat answer / list own saved plans |
| DELETE | `/plans/{id}` | ✓ | remove a saved plan |
| POST | `/workouts` | ✓ | log 1–30 entries (`day`, `exercise`, optional sets/reps/weight_kg/minutes/notes) |
| GET | `/workouts` | ✓ | own log, newest first (`limit`) |
| DELETE | `/workouts/{id}` | ✓ | delete an entry |
| GET | `/workouts/stats` | ✓ | active days per week (`weeks`), current streak, totals, most-logged exercises; `today` = browser's local date |
| PUT | `/messages/{id}/feedback` | ✓ | `{rating: 1 / -1 / 0}` on an assistant answer (0 clears); returned as `feedback` in `/conversations/{id}` |
| GET | `/health` | – | status, DB counts, loaded model info (`fine_tuned` flag) |

Interactive docs: `http://localhost:8000/docs`.

Example `/chat` response (abridged):

```json
{
  "conversation_id": 12, "conversation_title": "What exercises can I do for chest?",
  "answer": "Here are some effective chest exercises: ...",
  "category": "exercise_search", "intent": "exercise_search", "intent_confidence": 0.93, "is_followup": false,
  "exercises": [{"name": "Bench Press", "image_url": "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/Barbell_Bench_Press_-_Medium_Grip/0.jpg",
                 "target_muscles": ["Chest"], "secondary_muscles": ["Forearms", "Shoulders"], "equipment": "Barbell",
                 "difficulty": "Intermediate", "instructions": ["..."], "safety_tips": ["..."]}],
  "foods": [], "workout_plan": null,
  "sources": [{"type": "exercises", "title": "free-exercise-db (public domain)"}],
  "safety": null,
  "disclaimer": "FitBot provides general fitness and wellness information and is not a substitute for professional medical advice.",
  "model": {"generated": true, "generation_seconds": 1.4}
}
```

## 7. Frontend (`frontend/src`)

| Area | Files |
|---|---|
| Routing / auth guard | `App.jsx`, `context/AuthContext.jsx` (token in localStorage, auto-logout on 401) |
| API | `api/client.js` |
| Layout | `components/AppLayout.jsx` – sidebar: New chat, nav, previous conversations (delete), user, logout; mobile drawer |
| Pages | `Login`, `Register`, `Dashboard` (quick-start prompts, stats, exercise explorer, recent chats), `Chat` (voice input), `Workouts` (log form, weekly chart, streak, saved plans, recent activity), `Profile` |
| Structured rendering | `Message.jsx`, `ExerciseCard.jsx` (image, target, equipment, difficulty, View instructions, safety tip), `FoodCard.jsx` (kcal, macro bar, fiber/sugar/sodium, USDA link), `WorkoutPlan.jsx` (day tabs, sets × reps, rest, difficulty, image, Save plan / Log day), answer actions (read aloud, 👍/👎) |
| Branding / PWA | `PartnerBadge.jsx` (client logo on login and sidebar), `public/manifest.json`, icons, `public/sw.js` (registered in production builds only) |
| Styling | `styles.css` – design tokens, light/dark, responsive (sidebar becomes a drawer < 820 px) |
