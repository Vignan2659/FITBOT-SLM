"""Shared building blocks for the yoga pose files: key positions that many poses start from, and the pose helper."""
from __future__ import annotations

# ---- key positions (angles, see figure.py) -------------------------------------------------------------------
STAND = dict(torso=180, neck=180, l_ua=-4, r_ua=4, l_fa=-2, r_fa=2, l_th=-2, r_th=2, l_sh=-2, r_sh=2)
STAND_F = dict(l_ua=7, r_ua=-7, l_fa=5, r_fa=-5, l_th=2, r_th=-2, l_sh=1, r_sh=-1, l_ft=90, r_ft=-90)
ARMS_UP = dict(l_ua=172, r_ua=176, l_fa=176, r_fa=179)
ARMS_UP_F = dict(l_ua=165, r_ua=-165, l_fa=176, r_fa=-176)
TABLE = dict(torso=96, neck=104, l_ua=0, l_fa=0, r_ua=0, r_fa=0, l_th=0, r_th=0, l_sh=-90, r_sh=-90,
             l_ft=-90, r_ft=-90)
SEATED = dict(torso=180, neck=180, l_ua=12, r_ua=14, l_fa=8, r_fa=10, l_th=90, r_th=90, l_sh=90, r_sh=90,
              l_ft=170, r_ft=170)
SUPINE = dict(torso=-90, neck=-92, l_ua=90, r_ua=90, l_fa=90, r_fa=90, l_th=90, r_th=90, l_sh=90, r_sh=90,
              l_ft=172, r_ft=172)
SUPINE_KNEES = dict(SUPINE, l_th=140, r_th=140, l_sh=12, r_sh=12, l_ft=90, r_ft=90)
PRONE = dict(torso=90, neck=92, l_ua=-90, r_ua=-90, l_fa=-90, r_fa=-90, l_th=-90, r_th=-90, l_sh=-90, r_sh=-90,
             l_ft=-90, r_ft=-90)
CROSS_LEGGED_F = dict(l_th=72, r_th=-72, l_sh=-100, r_sh=100, l_ft=-150, r_ft=150, l_ua=22, r_ua=-22,
                      l_fa=62, r_fa=-62)
PLANK = dict(torso=100, neck=102, l_ua=0, r_ua=0, l_fa=0, r_fa=0, l_th=-80, r_th=-80, l_sh=-80, r_sh=-80,
             l_ft=-10, r_ft=-10)
DOG = dict(torso=44, neck=40, bend=-4, l_ua=40, r_ua=40, l_fa=40, r_fa=40, l_th=-38, r_th=-38, l_sh=-38,
           r_sh=-38, l_ft=90, r_ft=90)


def k(base: dict, **changes) -> dict:
    """A key position: a base position with some joints changed."""
    out = dict(base)
    out.update(changes)
    return out


def pose(**kw) -> dict:
    kw.setdefault("view", "side")
    kw.setdefault("anchor", None)
    kw.setdefault("sides", False)
    kw.setdefault("time", "any")
    kw.setdefault("minutes", 1.0)
    kw.setdefault("equipment", "Yoga mat")
    kw.setdefault("related", [])
    kw.setdefault("photo", None)
    kw.setdefault("tags", [])
    return kw
