"""Shared helper for the yoga pose files."""
from __future__ import annotations


def pose(**kw) -> dict:
    kw.setdefault("sides", False)
    kw.setdefault("time", "any")
    kw.setdefault("minutes", 1.0)
    kw.setdefault("equipment", "Yoga mat")
    kw.setdefault("related", [])
    kw.setdefault("tags", [])
    return kw
