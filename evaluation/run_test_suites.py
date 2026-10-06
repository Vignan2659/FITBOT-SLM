"""Run the FitBot test suites through the full pipeline with the REAL model.

    .venv/bin/python evaluation/run_test_suites.py                # model from backend settings
    .venv/bin/python evaluation/run_test_suites.py --model base   # base SmolLM2 (no fine-tuning)

Checks per question (whichever apply): routed intent, exercise cards (count, muscle group, level),
food cards, workout plan (days), guardrail / out-of-domain handling, disclaimer, follow-up detection,
keyword relevance of the generated answer, USDA number grounding, non-empty answer, latency.
Writes evaluation/test_suite_results.json and evaluation/test_suite_summary.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SUITES = ["fitness_questions", "nutrition_questions", "exercise_questions", "sleep_recovery_questions",
          "safety_questions", "out_of_domain_questions", "followup_conversations"]
NUM = re.compile(r"\d+(?:\.\d+)?")


def check(item: dict, r: dict) -> dict:
    c = {}
    ans = r["answer"].lower()
    c["non_empty"] = len(ans.strip()) > 10
    c["intent"] = r["intent"] in item["intents"]
    blob = ans + " " + " ".join(e["name"].lower() for e in r["exercises"]) + " " + \
        " ".join(f["name"].lower() for f in r["foods"])
    c["relevance_keyword"] = any(k.lower() in blob for k in item["keywords_any"])
    if "exercises_min" in item:
        c["exercise_cards"] = len(r["exercises"]) >= item["exercises_min"] and all(e["image_url"] for e in r["exercises"])
    if "group" in item and (r["exercises"] or r["workout_plan"]):
        groups = {e["muscle_group"] for e in r["exercises"]}
        c["muscle_group"] = groups <= {item["group"]} if groups else True
    if "level" in item and r["exercises"]:
        c["level"] = all(e["difficulty"] == item["level"] for e in r["exercises"])
    if "foods_min" in item:
        c["food_cards"] = len(r["foods"]) >= item["foods_min"]
    if item.get("plan"):
        c["workout_plan"] = bool(r["workout_plan"]) and all(
            e["sets"] and e["reps"] and e["image_url"] for d in r["workout_plan"]["days"] for e in d["exercises"])
        if "plan_days" in item and r["workout_plan"]:
            c["plan_days"] = len(r["workout_plan"]["days"]) == item["plan_days"]
    if item.get("guardrail"):
        c["guardrail"] = bool(r.get("safety")) and "not a substitute for professional medical advice" in ans
    if item.get("disclaimer"):
        c["disclaimer_and_referral"] = "not a substitute for professional medical advice" in ans and \
            bool(re.search(r"doctor|healthcare|provider|dietitian|professional", ans))
    if item.get("ood"):
        c["ood_refusal"] = ans.startswith("i'm focused on fitness")
    elif "medical_safety" not in item["intents"]:
        c["no_false_refusal"] = "focused on fitness, nutrition and wellness" not in ans
    if item.get("followup"):
        c["followup_detected"] = bool(r.get("is_followup"))
    if item.get("numbers_from_usda"):
        nums = [n for n in NUM.findall(r["answer"]) if n not in ("1", "2", "100")]
        ctx = " ".join(r.get("context_used", []))
        c["usda_numbers_grounded"] = bool(nums) and all(n in ctx for n in nums)
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="'base' or a path to a merged model (default: backend setting)")
    ap.add_argument("--out", default=str(ROOT / "evaluation" / "test_suite_results.json"))
    args = ap.parse_args()

    from app.core.config import get_settings
    from app.main import build_engine
    from app.ml.slm import FitBotSLM

    s = get_settings()
    if args.model == "base":
        slm = FitBotSLM(Path("/nonexistent"), s.fitbot_base_model, s.fitbot_device, s.fitbot_max_new_tokens)
    else:
        path = Path(args.model) if args.model else s.resolve(s.fitbot_model_path)
        slm = FitBotSLM(path, s.fitbot_base_model, s.fitbot_device, s.fitbot_max_new_tokens)
    engine, info = build_engine(s, generate=slm.generate)
    print("model:", slm.info()["model"], "| fine-tuned:", slm.fine_tuned, "| device:", slm.device)

    results, summary = {"model": slm.info(), "suites": {}}, {}
    for suite in SUITES:
        items = json.loads((ROOT / "evaluation" / "test_suites" / f"{suite}.json").read_text())
        rows = []
        convs = items if suite == "followup_conversations" else [{"name": f"q{i}", "turns": [it]} for i, it in enumerate(items)]
        for conv in convs:
            history, state = [], {}
            for item in conv["turns"]:
                t0 = time.time()
                r, state = engine.respond(item["q"], history, state, None)
                dt = time.time() - t0
                history += [{"role": "user", "content": item["q"]}, {"role": "assistant", "content": r["answer"]}]
                checks = check(item, r)
                rows.append({"conversation": conv.get("name"), "q": item["q"], "intent": r["intent"],
                             "answer": r["answer"], "exercises": [e["name"] for e in r["exercises"]],
                             "foods": [f["name"] for f in r["foods"]],
                             "plan": r["workout_plan"]["title"] if r["workout_plan"] else None,
                             "checks": checks, "passed": all(checks.values()), "seconds": round(dt, 2)})
        n = len(rows)
        check_names = sorted({k for r in rows for k in r["checks"]})
        summary[suite] = {
            "questions": n, "conversations": len(convs) if suite == "followup_conversations" else None,
            "pass_rate": round(sum(r["passed"] for r in rows) / n, 3),
            "check_pass_rates": {k: round(sum(r["checks"][k] for r in rows if k in r["checks"]) /
                                          max(1, sum(k in r["checks"] for r in rows)), 3) for k in check_names},
            "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        }
        results["suites"][suite] = rows
        print(f"{suite:28s} pass {summary[suite]['pass_rate']:.0%}  avg {summary[suite]['avg_seconds']}s")
    results["summary"] = summary
    Path(args.out).write_text(json.dumps(results, indent=1))

    md = [f"# FitBot test-suite results\n", f"Model: `{slm.info()['model']}` (fine-tuned: {slm.fine_tuned}, device: {slm.device})\n",
          "| Suite | Questions | Pass rate | Avg latency (s) | Weakest check |", "|---|---:|---:|---:|---|"]
    for k, v in summary.items():
        weakest = min(v["check_pass_rates"].items(), key=lambda kv: kv[1])
        md.append(f"| {k} | {v['questions']} | {v['pass_rate']:.0%} | {v['avg_seconds']} | {weakest[0]} ({weakest[1]:.0%}) |")
    md.append("\nPer-check pass rates:\n")
    for k, v in summary.items():
        md.append(f"* **{k}**: " + ", ".join(f"{c} {p:.0%}" for c, p in v["check_pass_rates"].items()))
    failures = [(s, r) for s, rows in results["suites"].items() for r in rows if not r["passed"]]
    md.append(f"\n## Failed questions ({len(failures)})\n")
    for s, r in failures:
        bad = [k for k, v in r["checks"].items() if not v]
        md.append(f"* [{s}] **{r['q']}** → intent `{r['intent']}`; failed: {', '.join(bad)}")
    out_md = Path(args.out).with_name(Path(args.out).stem.replace("results", "summary") + ".md")
    out_md.write_text("\n".join(md) + "\n")
    print("wrote", args.out, "and", out_md)


if __name__ == "__main__":
    main()
