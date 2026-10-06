"""Train FitBot's intent + out-of-domain classifier.

Data
  * FitBot dataset inputs with their intent labels (same train/validation/test split as the SLM data)
  * harshmakwana/fitness-intent (MIT, 960/120/120) mapped to FitBot intents (mainly adds out-of-scope
    and varied phrasing)
  * EXTRA: short hand-written examples for intents that are rare in the main dataset

Model: TF-IDF (word 1-2 grams + char 2-5 grams) + all-MiniLM-L6-v2 sentence embeddings -> multinomial logistic
regression (app.ml.intent.HybridIntentClassifier). A TF-IDF-only model is bundled as an offline fallback and is
also reported for comparison (embedding weight and C were chosen on the validation split).
Outputs: models/intent_classifier.joblib, evaluation/intent_classifier_report.json
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import sys

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ml.intent import HybridIntentClassifier  # noqa: E402

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_WEIGHT, HYBRID_C = 1.0, 8.0
RAW = ROOT / "data" / "raw" / "fitness_intent"

MAP = {"find_exercise": "exercise_search", "out_of_scope": "out_of_domain", "get_nutrition_info": "nutrition_question",
       "general_chat": "general_fitness", "log_feeling": "general_fitness", "generate_plan": "workout_plan"}

EXTRA = {
    "sleep": ["how many hours of sleep", "i can't sleep at night", "is 6 hours of sleep enough", "best time to go to bed",
              "does sleep help recovery", "tips for falling asleep faster", "should i nap after training",
              "how much sleep for muscle growth", "sleep schedule for athletes", "i wake up tired every day",
              "how much rest do i need at night", "is sleeping 9 hours too much"],
    "recovery": ["how long to recover after leg day", "my muscles are sore", "how to recover faster",
                 "should i take a rest day", "is foam rolling useful", "what is a deload week", "active recovery ideas",
                 "how long should soreness last", "do massages help recovery", "recovery after a marathon",
                 "how many rest days per week", "is it ok to train sore muscles"],
    "hydration": ["how much water during a workout", "is sparkling water ok", "should i drink electrolytes",
                  "best drink after running", "how to stay hydrated in summer", "is tea dehydrating",
                  "how many glasses of water a day", "is soda bad for me", "energy drinks before gym"],
    "equipment": ["what dumbbells should i buy", "are adjustable dumbbells worth it", "best resistance bands",
                  "do i need a weight bench", "is a pull up bar worth buying", "what shoes for lifting",
                  "should i buy a treadmill", "kettlebell weight for beginners", "what is a smith machine",
                  "do i need lifting gloves", "is a yoga mat necessary", "what equipment for a home gym"],
    "stretching": ["stretches for tight hamstrings", "how to warm up properly", "best cool down stretches",
                   "how long to hold a stretch", "mobility routine for hips", "should i stretch every day",
                   "stretches for lower back stiffness", "dynamic stretching examples", "how to do the splits safely"],
    "cardio": ["how to run longer without stopping", "best cardio to burn fat", "is swimming good cardio",
               "how many minutes of cardio a day", "hiit or steady state", "how to improve vo2 max",
               "beginner running plan", "is cycling good for knees", "cardio for beginners at home",
               "how does hiit work", "hiit sessions per week", "benefits of hiit training", "tabata intervals", "interval training explained"],
    "home_workout": ["workout i can do at home", "no equipment workout", "home workout with dumbbells",
                     "exercises in my bedroom", "apartment friendly workout", "bodyweight routine for home",
                     "home workout for weight loss", "living room exercises"],
    "gym_workout": ["what machines should i use at the gym", "first day at the gym", "gym routine for beginners",
                    "how to use the cable machine", "how long should i stay at the gym", "gym etiquette tips",
                    "what to do at the gym", "lat pulldown machine tips"],
    "weight_loss": ["how to lose 10 kg", "how to burn belly fat", "calorie deficit explained",
                    "why am i not losing weight", "best diet for fat loss", "how to cut body fat",
                    "lose weight fast", "foods to avoid for weight loss"],
    "muscle_gain": ["how to bulk up", "how to gain muscle mass", "how to get bigger arms", "lean bulk tips",
                    "how much protein to build muscle", "hypertrophy training", "how to get stronger"],
    "food_search": ["calories in a banana", "protein in chicken breast", "is rice healthy", "how much fat in avocado",
                    "nutrition facts of oats", "carbs in sweet potato", "how much protein in eggs", "is peanut butter good"],
    "nutrition_question": ["what should i eat after workout", "healthy breakfast ideas", "how much protein per day",
                           "are carbs bad", "vegetarian protein sources", "healthy snacks", "what to eat before gym",
                           "is creatine safe"],
    "exercise_safety": ["how to avoid injury when lifting", "is it safe to lift heavy", "proper form for squats",
                        "should i use a spotter", "how to lift safely", "is it ok to work out when sick"],
    "medical_safety": ["i have chest pain when running", "i think i broke my ankle", "can i exercise with diabetes",
                       "i am pregnant can i run", "what medicine for muscle pain", "i fainted at the gym",
                       "i make myself vomit after eating", "how to use steroids safely", "i have a hernia can i lift",
                       "my knee is swollen after running", "can i take supplements with my medication",
                       "i have high blood pressure"],
    "greeting": ["hello", "hi there", "good morning", "hey fitbot", "thanks", "thank you", "who are you", "what can you do"],
    "out_of_domain": ["what is the weather tomorrow", "who won the election", "write a python script", "tell me a story",
                      "what is the capital of italy", "how to cook pasta carbonara", "best laptop to buy",
                      "solve this math problem", "who is the richest person", "how to fix my wifi",
                      "recommend a song", "what's the stock price of apple", "translate this to french",
                      "how do i file my taxes", "what is machine learning"],
    "workout_plan": ["make me a workout plan", "weekly training schedule", "3 day split for beginners",
                     "give me a 4 day program", "plan my workouts for the month", "push pull legs routine"],
    "exercise_search": ["exercises for chest", "best back exercises", "how to do a deadlift", "leg exercises",
                        "what muscles do squats work", "shoulder exercises with dumbbells", "ab exercises"],
    "general_fitness": ["how to stay motivated", "benefits of exercise", "how many steps per day",
                        "how to start getting fit", "healthy habits", "is it too late to start exercising"],
}


def load_split(name: str) -> list[tuple[str, str]]:
    path = ROOT / "data" / "processed" / f"{name}.jsonl"
    return [(r["input"], r["intent"]) for r in map(json.loads, path.read_text().splitlines())]


def load_hf_intent() -> dict[str, list[tuple[str, str]]]:
    RAW.mkdir(parents=True, exist_ok=True)
    out = {}
    for split in ("train", "validation", "test"):
        f = RAW / f"{split}.jsonl"
        if not f.exists():
            from datasets import load_dataset
            ds = load_dataset("harshmakwana/fitness-intent", split=split)
            f.write_text("\n".join(json.dumps(r) for r in ds))
        rows = [json.loads(l) for l in f.read_text().splitlines()]
        mapped = []
        for r in rows:
            label = MAP[r["intent"]]
            if r["intent"] == "generate_plan" and any(w in r["text"].lower() for w in ("meal", "diet", "eating", "food")):
                label = "nutrition_question"
            mapped.append((r["text"], label))
        out[split] = mapped
    return out


def build_model() -> Pipeline:
    feats = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
    ])
    return Pipeline([("features", feats),
                     ("clf", LogisticRegression(C=8.0, max_iter=3000, class_weight="balanced"))])


def fit_hybrid(data: list[tuple[str, str]], encode) -> HybridIntentClassifier:
    X, y = [t for t, _ in data], [l for _, l in data]
    fallback = build_model().fit(X, y)
    feats = fallback.named_steps["features"]
    emb = np.asarray(encode(X), dtype=np.float64) * EMBED_WEIGHT
    clf = LogisticRegression(C=HYBRID_C, max_iter=4000, class_weight="balanced")
    clf.fit(hstack([feats.transform(X), csr_matrix(emb)]).tocsr(), y)
    model = HybridIntentClassifier(feats, clf, fallback, EMBED_MODEL, EMBED_WEIGHT)
    model.set_encoder(encode)
    return model


def scores(model, data: list[tuple[str, str]]) -> dict:
    X, y = [t for t, _ in data], [l for _, l in data]
    pred = model.predict(X)
    out = {"accuracy": round(accuracy_score(y, pred), 4), "macro_f1": round(f1_score(y, pred, average="macro"), 4),
           "per_class": classification_report(y, pred, output_dict=True, zero_division=0)}
    # out-of-domain detection as a binary task
    yb = [l == "out_of_domain" for l in y]
    pb = [p == "out_of_domain" for p in pred]
    tp = sum(a and b for a, b in zip(yb, pb)); fp = sum(b and not a for a, b in zip(yb, pb))
    fn = sum(a and not b for a, b in zip(yb, pb))
    out["ood_precision"] = round(tp / max(tp + fp, 1), 4)
    out["ood_recall"] = round(tp / max(tp + fn, 1), 4)
    return out


def main() -> None:
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(EMBED_MODEL, device="cpu")
    encode = lambda texts: st.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)

    hf = load_hf_intent()
    train = load_split("training") + hf["train"] + [(t, k) for k, ts in EXTRA.items() for t in ts]
    val = load_split("validation") + hf["validation"]
    test = load_split("test") + hf["test"]
    fb = load_split("test")
    model = fit_hybrid(train, encode)

    report = {"model": f"TF-IDF + {EMBED_MODEL} embeddings -> logistic regression (C={HYBRID_C})",
              "train_size": len(train), "validation_size": len(val), "test_size": len(test),
              "train_label_counts": dict(Counter(y for _, y in train).most_common())}
    for name, data in (("validation", val), ("test", test)):
        report[name] = scores(model, data)
    # FitBot-only test subset (excluding the external dataset)
    report["test_fitbot_only_accuracy"] = round(accuracy_score([y for _, y in fb], model.predict([t for t, _ in fb])), 4)
    # previous TF-IDF-only model on the same splits, for comparison
    tfidf_only = model.fallback
    report["tfidf_only_baseline"] = {
        **{name: {k: v for k, v in scores(tfidf_only, data).items() if k != "per_class"}
           for name, data in (("validation", val), ("test", test))},
        "test_fitbot_only_accuracy": round(accuracy_score([y for _, y in fb], tfidf_only.predict([t for t, _ in fb])), 4)}

    # final model trained on train+validation for deployment (test stays untouched)
    final = fit_hybrid(train + val, encode)
    (ROOT / "models").mkdir(exist_ok=True)
    joblib.dump(final, ROOT / "models" / "intent_classifier.joblib")
    (ROOT / "evaluation" / "intent_classifier_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: (v if not isinstance(v, dict) or "accuracy" not in v else
                          {kk: v[kk] for kk in ("accuracy", "macro_f1", "ood_precision", "ood_recall")})
                      for k, v in report.items() if k != "train_label_counts"}, indent=2))


if __name__ == "__main__":
    main()
