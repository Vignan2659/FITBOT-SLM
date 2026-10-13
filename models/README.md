# Models

| Path | In git? | Created by |
|---|---|---|
| `intent_classifier.joblib` | yes (6.5 MB) | `scripts/train_intent_classifier.py` (saved with scikit-learn 1.9.1) |
| `fitbot-qwen3-4b/adapter/` | no | `scripts/setup_model.py` downloads it from the GitHub release |
| `fitbot-qwen3-4b/merged/` | no (7.5 GB) | `scripts/setup_model.py` merges the adapter into Qwen3-4B-Instruct-2507; the backend loads this |
