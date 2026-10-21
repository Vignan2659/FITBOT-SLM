"""Motion figures for the Yoga module.

Every yoga pose is described by two or three key positions (start, transition, final) written as joint angles of a
simple stick figure. This module turns those angles into:

* an animated SVG that moves smoothly through start -> transition -> final and back (SMIL, works inside <img>),
* one still SVG per key position, used for the "how it moves" strip on the pose page.

Angles are absolute and in degrees: 0 points straight down, 90 points to the front (the figure faces right in a side
view), 180 points up and -90 points behind. Side views draw the far limbs in a lighter colour so the pose reads in
depth; front views attach the limbs at the shoulders and hips.

The drawings are original work made for FitBot (MIT, like the rest of the repository), so they need no third party
image licence.
"""
from __future__ import annotations

import math

# segment lengths (SVG units)
L = {"torso": 55, "neck": 14, "head": 11.5, "ua": 31, "fa": 30, "th": 47, "sh": 44, "ft": 13}
SHOULDER_W, HIP_W = 13, 8              # half widths, front view only
W, H, GROUND, PAD = 320, 240, 222, 10  # canvas
NEAR, FAR, BODY = "#0f766e", "#86c9c0", "#0f766e"
STROKE = {"limb": 11, "torso": 18, "neck": 9}

ANGLE_KEYS = ("bend", "torso", "neck", "l_ua", "l_fa", "r_ua", "r_fa", "l_th", "l_sh", "l_ft", "r_th", "r_sh", "r_ft")
DEFAULT = {"bend": 0, "torso": 180, "neck": 180, "l_ua": -4, "l_fa": -2, "r_ua": 4, "r_fa": 2,
           "l_th": -2, "l_sh": -2, "l_ft": 90, "r_th": 2, "r_sh": 2, "r_ft": 90}


def _dir(a: float) -> tuple[float, float]:
    r = math.radians(a)
    return math.sin(r), math.cos(r)


def _add(p, a, length):
    d = _dir(a)
    return p[0] + d[0] * length, p[1] + d[1] * length


def full(angles: dict) -> dict:
    out = dict(DEFAULT)
    out.update(angles)
    return out


def joints(angles: dict, view: str = "side") -> dict:
    """Joint positions with the hip centre at (0, 0)."""
    a = full(angles)
    hip = (0.0, 0.0)
    shoulder = _add(hip, a["torso"], L["torso"])
    head = _add(shoulder, a["neck"], L["neck"] + L["head"] * 0.55)
    sw, hw = (SHOULDER_W, HIP_W) if view == "front" else (0.0, 0.0)
    mid = ((hip[0] + shoulder[0]) / 2, (hip[1] + shoulder[1]) / 2)
    spine = _add(mid, a["torso"] + 90, a["bend"])   # bend > 0 rounds the back, < 0 arches it
    j = {"hip": hip, "shoulder": shoulder, "head": head, "spine": spine}
    for side, sign in (("l", 1), ("r", -1)):
        sh = _add(shoulder, a["torso"] - 90, sign * sw)
        hp = _add(hip, a["torso"] - 90, sign * hw)
        el = _add(sh, a[f"{side}_ua"], L["ua"])
        wr = _add(el, a[f"{side}_fa"], L["fa"])
        kn = _add(hp, a[f"{side}_th"], L["th"])
        an = _add(kn, a[f"{side}_sh"], L["sh"])
        ft_len = L["ft"] * (0.55 if view == "front" else 1.0)
        to = _add(an, a[f"{side}_ft"], ft_len)
        j.update({f"{side}_shoulder": sh, f"{side}_hip": hp, f"{side}_elbow": el, f"{side}_wrist": wr,
                  f"{side}_knee": kn, f"{side}_ankle": an, f"{side}_toe": to})
    return j


def _segments(j: dict, view: str) -> list[tuple[str, list, str, float]]:
    """(id, points, colour, width) in drawing order (back to front)."""
    far, near = ("l", "r")
    far_c = FAR if view == "side" else NEAR
    segs = []
    for s, c in ((far, far_c),):
        segs += [(f"{s}leg", [j[f"{s}_hip"], j[f"{s}_knee"], j[f"{s}_ankle"], j[f"{s}_toe"]], c, STROKE["limb"]),
                 (f"{s}arm", [j[f"{s}_shoulder"], j[f"{s}_elbow"], j[f"{s}_wrist"]], c, STROKE["limb"])]
    if view == "front":
        segs.append(("torso", [j["l_hip"], j["l_shoulder"], j["r_shoulder"], j["r_hip"], j["l_hip"]], BODY, 13))
    else:
        segs.append(("torso", ["Q", j["hip"], j["spine"], j["shoulder"]], BODY, STROKE["torso"]))
    segs.append(("neck", [j["shoulder"], j["head"]], BODY, STROKE["neck"]))
    s = near
    segs += [(f"{s}leg", [j[f"{s}_hip"], j[f"{s}_knee"], j[f"{s}_ankle"], j[f"{s}_toe"]], NEAR, STROKE["limb"]),
             (f"{s}arm", [j[f"{s}_shoulder"], j[f"{s}_elbow"], j[f"{s}_wrist"]], NEAR, STROKE["limb"])]
    return segs


def _extent(j: dict) -> tuple[float, float, float, float]:
    xs = [p[0] for p in j.values()]
    ys = [p[1] for p in j.values()]
    hx, hy = j["head"]
    r = L["head"]
    m = STROKE["limb"] / 2
    return (min(xs + [hx - r]) - m, min(ys + [hy - r]) - m, max(xs + [hx + r]) + m, max(ys + [hy + r]) + m)


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def _lerp(a: dict, b: dict, t: float) -> dict:
    fa, fb = full(a), full(b)
    return {k: fa[k] + (fb[k] - fa[k]) * t for k in ANGLE_KEYS}


def timeline(keyframes: list[dict], steps: int = 9) -> list[tuple[float, dict]]:
    """(time in seconds, angles): hold start, move, hold, move, hold final, return to start."""
    holds = [0.9, 0.6, 2.2] if len(keyframes) == 3 else [1.0, 2.2]
    moves = [1.3, 1.3] if len(keyframes) == 3 else [1.6]
    back = 1.6
    t, out = 0.0, []
    for i, k in enumerate(keyframes):
        out.append((t, full(k)))
        t += holds[i]
        out.append((t, full(k)))
        nxt = keyframes[i + 1] if i + 1 < len(keyframes) else keyframes[0]
        dur = moves[i] if i + 1 < len(keyframes) else back
        for s in range(1, steps):
            out.append((t + dur * s / steps, _lerp(k, nxt, _ease(s / steps))))
        t += dur
    out.append((t, full(keyframes[0])))
    return out


def layout(frames: list[dict], view: str, anchor: str | None) -> list[dict]:
    """Ground every frame, keep the anchor joint still, centre and fit the whole motion in the canvas."""
    placed = []
    ax0 = None
    for ang in frames:
        j = joints(ang, view)
        x0, y0, x1, y1 = _extent(j)
        dy = GROUND - y1
        if anchor:
            ax = j[anchor][0]
            if ax0 is None:
                ax0 = ax
            dx = ax0 - ax
        else:
            dx = 0.0
        placed.append({k: (p[0] + dx, p[1] + dy) for k, p in j.items()})
    ext = [_extent(j) for j in placed]
    x0 = min(e[0] for e in ext)
    x1 = max(e[2] for e in ext)
    y0 = min(e[1] for e in ext)
    scale = min(1.0, (W - 2 * PAD) / (x1 - x0), (GROUND - PAD) / (GROUND - y0))
    cx = (x0 + x1) / 2
    out = []
    for j in placed:
        out.append({k: (W / 2 + (p[0] - cx) * scale, GROUND - (GROUND - p[1]) * scale) for k, p in j.items()})
    return out, scale


def _d(points) -> str:
    if points and points[0] == "Q":   # quadratic curve: start, control, end
        (x0, y0), (x1, y1), (x2, y2) = points[1:]
        return f"M{x0:.1f} {y0:.1f} Q{x1:.1f} {y1:.1f} {x2:.1f} {y2:.1f}"
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)


def _svg_open(title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{title}">'
            f'<title>{title}</title>'
            f'<rect x="28" y="{GROUND}" width="{W - 56}" height="6" rx="3" fill="#dfe9e6"/>')


def still_svg(angles: dict, view: str, title: str, placed: dict | None = None, scale: float = 1.0) -> str:
    j = placed or layout([angles], view, None)[0][0]
    parts = [_svg_open(title)]
    for sid, pts, colour, width in _segments(j, view):
        join = "round"
        fill = "none"
        parts.append(f'<path d="{_d(pts)}" fill="{fill}" stroke="{colour}" stroke-width="{width * scale:.1f}" '
                     f'stroke-linecap="round" stroke-linejoin="{join}"/>')
    hx, hy = j["head"]
    parts.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{L["head"] * scale:.1f}" fill="{BODY}"/>')
    parts.append("</svg>")
    return "".join(parts)


def motion_svgs(keyframes: list[dict], view: str = "side", anchor: str | None = None,
                title: str = "Yoga pose") -> tuple[str, list[str]]:
    """Animated SVG and one still SVG per key position."""
    tl = timeline(keyframes)
    total = tl[-1][0]
    placed, scale = layout([a for _, a in tl], view, anchor)
    key_times = ";".join(f"{t / total:.4f}" for t, _ in tl)
    per_frame = [_segments(j, view) for j in placed]
    parts = [_svg_open(title)]
    for idx, (sid, pts, colour, width) in enumerate(per_frame[0]):
        values = ";".join(_d(f[idx][1]) for f in per_frame)
        parts.append(f'<path d="{_d(pts)}" fill="none" stroke="{colour}" stroke-width="{width * scale:.1f}" '
                     f'stroke-linecap="round" stroke-linejoin="round">'
                     f'<animate attributeName="d" dur="{total:.1f}s" repeatCount="indefinite" '
                     f'keyTimes="{key_times}" values="{values}"/></path>')
    cxs = ";".join(f"{j['head'][0]:.1f}" for j in placed)
    cys = ";".join(f"{j['head'][1]:.1f}" for j in placed)
    hx, hy = placed[0]["head"]
    parts.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{L["head"] * scale:.1f}" fill="{BODY}">'
                 f'<animate attributeName="cx" dur="{total:.1f}s" repeatCount="indefinite" keyTimes="{key_times}" values="{cxs}"/>'
                 f'<animate attributeName="cy" dur="{total:.1f}s" repeatCount="indefinite" keyTimes="{key_times}" values="{cys}"/>'
                 f'</circle>')
    parts.append("</svg>")
    # stills share the motion's layout so the three key positions line up with the animation
    key_idx = [i for i, (t, a) in enumerate(tl) if any(a == full(k) for k in keyframes)]
    stills = []
    for n, k in enumerate(keyframes):
        i = next(i for i in key_idx if tl[i][1] == full(k))
        stills.append(still_svg(k, view, f"{title}, step {n + 1}", placed[i], scale))
    return "".join(parts), stills
