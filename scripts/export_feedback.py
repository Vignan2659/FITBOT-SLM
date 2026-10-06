"""Export 👍/👎 ratings on FitBot answers for review (e.g. to find answers worth fixing in the dataset).

    .venv/bin/python scripts/export_feedback.py            ->  evaluation/feedback_export.jsonl + summary

Each row: rating, intent, the user question that preceded the answer, the answer, timestamp.
No names or e-mail addresses are exported.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Message, MessageFeedback  # noqa: E402


def main() -> None:
    out = ROOT / "evaluation" / "feedback_export.jsonl"
    rows = []
    with SessionLocal() as db:
        for fb in db.scalars(select(MessageFeedback).order_by(MessageFeedback.id)):
            answer = db.get(Message, fb.message_id)
            question = db.scalar(select(Message).where(Message.conversation_id == answer.conversation_id,
                                                       Message.id < answer.id, Message.role == "user")
                                 .order_by(Message.id.desc()).limit(1))
            rows.append({"rating": fb.rating, "intent": answer.intent, "question": question.content if question else None,
                         "answer": answer.content, "rated_at": fb.created_at.isoformat()})
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    by_intent = Counter((r["intent"], r["rating"]) for r in rows)
    print(f"{len(rows)} ratings ({sum(r['rating'] > 0 for r in rows)} up, {sum(r['rating'] < 0 for r in rows)} down)"
          f" -> {out.relative_to(ROOT)}")
    for intent in sorted({i for i, _ in by_intent}, key=str):
        print(f"  {intent or '-':20s} up {by_intent[(intent, 1)]:3d}   down {by_intent[(intent, -1)]:3d}")


if __name__ == "__main__":
    main()
