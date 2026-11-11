"""Fitness band and smartwatch data: reading the export files of each brand's phone app.

No brand lets a web app on a laptop read the watch directly; the data lives in the phone app (Apple Health, Samsung
Health, Google Fit / Health Connect, Fitbit, Huawei Health, WHOOP ...). Every one of those apps can export the user's
data as a file, so FitBot imports that file. Everything stays on the user's machine: nothing is sent to a cloud service.

`parse_export(path, filename)` works out which format a file is (it does not trust the brand the user picked) and
returns the same structure for all of them:

    Parsed.daily     {date: {steps, distance_km, active_kcal, resting_hr, avg_hr, max_hr, min_hr, hrv_ms, stress,
                             sleep_minutes, spo2}}      (only the keys the file had data for)
    Parsed.workouts  [{start, activity, minutes, kcal, avg_hr, max_hr, distance_km, steps}]

Stress is stored on a 0 to 100 scale where higher means more stress. Brands that only give a "recovery" or "stress
management" score (higher is better) are flipped so the direction is the same everywhere.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import statistics
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

METRICS = ("steps", "distance_km", "active_kcal", "resting_hr", "avg_hr", "max_hr", "min_hr", "hrv_ms", "stress",
           "sleep_minutes", "spo2")
MAX_DAYS = 400          # only the last ~13 months are kept, so the database stays small

BRANDS = [
    {"id": "apple", "name": "Apple Watch", "app": "Apple Health (iPhone)", "file": "export.zip",
     "steps": ["Open the Health app on your iPhone and tap your picture at the top right.",
               "Scroll down and tap Export All Health Data, then Export.",
               "Save export.zip to Files or AirDrop it to this Mac, then upload it here."],
     "gives": ["steps", "heart rate", "resting heart rate", "HRV", "sleep", "blood oxygen", "workouts"],
     "live_hr": False, "note": "Apple Watch does not broadcast heart rate over Bluetooth, so live heart rate is not available."},
    {"id": "samsung", "name": "Samsung Galaxy Watch", "app": "Samsung Health", "file": "samsunghealth_*.zip or its CSV files",
     "steps": ["Open Samsung Health and go to Settings (the three dots or the gear).",
               "Tap Download personal data and confirm. The files are saved in Download/Samsung Health.",
               "Zip that folder (or pick the CSV files) and upload it here."],
     "gives": ["steps", "heart rate", "stress", "sleep", "blood oxygen", "workouts"], "live_hr": False,
     "note": "Galaxy Watch needs a heart rate broadcast app from the Play Store for live heart rate."},
    {"id": "google", "name": "Google Pixel Watch / Fitbit", "app": "Fitbit or Google Fit (Google Takeout)", "file": "takeout-*.zip",
     "steps": ["Go to takeout.google.com in a browser and sign in.",
               "Choose Deselect all, then tick Fitbit (and Fit if you use Google Fit) and create the export.",
               "Download the takeout zip when Google emails you, and upload it here."],
     "gives": ["steps", "heart rate", "resting heart rate", "HRV", "stress score", "sleep", "workouts"], "live_hr": False,
     "note": "Fitbit Charge 6 can broadcast heart rate: turn on 'HR on equipment' and use Live heart rate."},
    {"id": "huawei", "name": "Huawei Watch / Band", "app": "Huawei Health", "file": "the zip Huawei emails you",
     "steps": ["Open Huawei Health, tap Me, then your profile and Privacy centre (or Account centre).",
               "Tap Request your data, choose Health and send the request.",
               "Download the zip from the email Huawei sends (unzip it with the password you chose and zip it again without one), then upload it here."],
     "gives": ["steps", "heart rate", "resting heart rate", "stress", "sleep", "workouts"], "live_hr": True,
     "note": "Many Huawei watches can broadcast heart rate: Settings on the watch, then HR data broadcasts."},
    {"id": "oneplus", "name": "OnePlus Watch / Band", "app": "OHealth with Health Connect", "file": "Health Connect export zip",
     "steps": ["In OHealth, open Settings and turn on sharing with Health Connect.",
               "On the phone go to Settings, Health Connect, Manage data, Export and import, Export now.",
               "Send the zip to this Mac and upload it here."],
     "gives": ["steps", "heart rate", "sleep", "blood oxygen", "workouts"], "live_hr": False, "note": ""},
    {"id": "noise", "name": "Noise smartwatch", "app": "NoiseFit with Google Fit or Apple Health", "file": "Google Takeout zip, Apple Health export.zip or the FitBot CSV",
     "steps": ["In NoiseFit, open Profile and connect Google Fit (Android) or Apple Health (iPhone).",
               "Export from Google Takeout (Fit) or from Apple Health as described for those brands.",
               "Or download the FitBot CSV template below and type your daily numbers from the NoiseFit app."],
     "gives": ["steps", "heart rate", "sleep", "stress (from the template)"], "live_hr": False, "note": ""},
    {"id": "whoop", "name": "WHOOP", "app": "WHOOP", "file": "my_whoop_data_*.zip",
     "steps": ["Open the WHOOP app, go to More, App settings, Data export.",
               "Request the export; WHOOP emails you a zip.",
               "Download the zip and upload it here."],
     "gives": ["resting heart rate", "HRV", "recovery", "sleep", "blood oxygen", "workouts"], "live_hr": True,
     "note": "WHOOP can broadcast heart rate: Device settings, Broadcast heart rate."},
    {"id": "other", "name": "Any other band", "app": "FitBot CSV template", "file": "a CSV file",
     "steps": ["Garmin, Amazfit, Xiaomi, boAt, Fire-Boltt and others: export a CSV from the app if it offers one.",
               "Or download the FitBot CSV template and fill one row per day.",
               "Upload the CSV here. FitBot recognises the common column names."],
     "gives": ["steps", "heart rate", "HRV", "stress", "sleep", "calories", "distance"], "live_hr": True,
     "note": "Garmin, Polar, Coros, Amazfit and chest straps can broadcast heart rate for Live heart rate."},
]
BRAND_IDS = {b["id"] for b in BRANDS}
TEMPLATE_CSV = ("date,steps,distance_km,active_calories,resting_heart_rate,average_heart_rate,max_heart_rate,hrv_ms,"
                "stress,sleep_hours,spo2\n2026-11-10,8450,6.1,410,58,72,148,62,35,7.4,97\n")


class WearableError(ValueError):
    """The file could not be read as a fitness export (shown to the user)."""


# ---------------------------------------------------------------------------------------------- accumulator
@dataclass
class Parsed:
    format: str = "unknown"
    daily: dict[date, dict] = field(default_factory=dict)
    workouts: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Acc:
    """Collects raw readings and turns them into one row per day."""

    def __init__(self, fmt: str):
        self.fmt = fmt
        self.sums: dict[tuple[date, str], dict[str, float]] = {}      # (day, metric) -> {source: total}
        self.last: dict[tuple[date, str], float] = {}                  # (day, metric) -> latest value
        self.hr: dict[date, list[float]] = {}                           # day -> [sum, count, min, max]
        self.avg: dict[tuple[date, str], list[float]] = {}             # (day, metric) -> [sum, count]
        self.workouts: list[dict] = []
        self.notes: list[str] = []

    def add(self, day: date, metric: str, value: float, source: str = "") -> None:
        """Totals (steps, distance, energy, sleep). Kept per source app, because a phone and a watch both count the
        same steps; the biggest source wins instead of adding them up."""
        if value and value > 0:
            self.sums.setdefault((day, metric), {})
            self.sums[(day, metric)][source] = self.sums[(day, metric)].get(source, 0.0) + value

    def set(self, day: date, metric: str, value: float | None) -> None:
        if value is not None and value > 0:
            self.last[(day, metric)] = value

    def mean(self, day: date, metric: str, value: float | None) -> None:
        if value is not None and value > 0:
            a = self.avg.setdefault((day, metric), [0.0, 0])
            a[0] += value
            a[1] += 1

    def heart(self, day: date, bpm: float | None) -> None:
        if bpm is None or not 25 <= bpm <= 240:
            return
        h = self.hr.setdefault(day, [0.0, 0, bpm, bpm])
        h[0] += bpm
        h[1] += 1
        h[2], h[3] = min(h[2], bpm), max(h[3], bpm)

    def workout(self, start: datetime | None, activity: str, minutes: float | None, kcal: float | None = None,
                avg_hr: float | None = None, max_hr: float | None = None, distance_km: float | None = None,
                steps: float | None = None) -> None:
        if start is None or not minutes or minutes <= 0 or minutes > 24 * 60:
            return
        clean = lambda v, lo, hi: round(float(v), 1) if v is not None and lo < float(v) <= hi else None
        self.workouts.append({"start": start.replace(tzinfo=None), "activity": tidy_activity(activity),
                              "minutes": round(float(minutes), 1), "kcal": clean(kcal, 0, 20000),
                              "avg_hr": clean(avg_hr, 25, 240), "max_hr": clean(max_hr, 25, 260),
                              "distance_km": round(float(distance_km), 2) if distance_km and distance_km > 0 else None,
                              "steps": int(steps) if steps and steps > 0 else None})

    def result(self) -> Parsed:
        daily: dict[date, dict] = {}
        for (day, metric), by_source in self.sums.items():
            daily.setdefault(day, {})[metric] = max(by_source.values())
        for (day, metric), (total, n) in self.avg.items():
            daily.setdefault(day, {})[metric] = total / n
        for (day, metric), v in self.last.items():
            daily.setdefault(day, {})[metric] = v
        for day, (total, n, lo, hi) in self.hr.items():
            row = daily.setdefault(day, {})
            row.setdefault("avg_hr", total / n)
            row.setdefault("min_hr", lo)
            row.setdefault("max_hr", hi)
        cutoff = (max(daily) if daily else date.today()) - timedelta(days=MAX_DAYS)
        out = {}
        for day, row in daily.items():
            if day < cutoff or day > date.today() + timedelta(days=1):
                continue
            row = {k: v for k, v in row.items() if k in METRICS and v is not None and _plausible(k, v)}
            if "steps" in row:
                row["steps"] = int(round(row["steps"]))
            for k in row:
                if k != "steps":
                    row[k] = round(float(row[k]), 2 if k == "distance_km" else 1)
            if row:
                out[day] = row
        seen, workouts = set(), []
        for w in sorted(self.workouts, key=lambda w: w["start"]):
            key = (w["start"].replace(second=0, microsecond=0), w["activity"])
            if key in seen or w["start"].date() < cutoff:
                continue
            seen.add(key)
            workouts.append(w)
        return Parsed(format=self.fmt, daily=out, workouts=workouts, notes=self.notes)


LIMITS = {"steps": (1, 150000), "distance_km": (0.01, 300), "active_kcal": (1, 15000), "resting_hr": (25, 130),
          "avg_hr": (25, 220), "max_hr": (30, 250), "min_hr": (20, 200), "hrv_ms": (3, 400), "stress": (0, 100),
          "sleep_minutes": (20, 20 * 60), "spo2": (60, 100)}


def _plausible(metric: str, value: float) -> bool:
    lo, hi = LIMITS[metric]
    return lo <= value <= hi


ACTIVITY_NAMES = {"walking": "Walking", "running": "Running", "cycling": "Cycling", "biking": "Cycling", "yoga": "Yoga",
                  "swimming": "Swimming", "hiking": "Hiking", "elliptical": "Elliptical", "rowing": "Rowing",
                  "traditionalstrengthtraining": "Strength training", "functionalstrengthtraining": "Strength training",
                  "highintensityintervaltraining": "HIIT", "weightlifting": "Strength training",
                  "strength training": "Strength training", "weights": "Strength training"}


def tidy_activity(name: str) -> str:
    n = re.sub(r"^HKWorkoutActivityType", "", str(name or "Workout")).strip()
    key = n.lower().replace("_", " ")
    if key.replace(" ", "") in ACTIVITY_NAMES:
        return ACTIVITY_NAMES[key.replace(" ", "")]
    if key in ACTIVITY_NAMES:
        return ACTIVITY_NAMES[key]
    n = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n).replace("_", " ").strip()
    return (n[:1].upper() + n[1:])[:60] or "Workout"


# ---------------------------------------------------------------------------------------------- small helpers
def num(v) -> float | None:
    try:
        f = float(str(v).replace(",", "").strip())
        return f if f == f else None           # NaN -> None
    except (TypeError, ValueError):
        return None


DATE_FORMATS = ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d",
                "%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d", "%d %b %Y", "%b %d, %Y")


def parse_dt(value) -> datetime | None:
    """A timestamp in any of the formats the exports use. The local wall clock time is kept (the day a reading
    belongs to is the day on the person's own calendar)."""
    if value is None:
        return None
    if re.fullmatch(r"(19|20)\d{6}", str(value).strip()):          # 20261110 (Huawei writes days as numbers)
        value = str(value).strip()
    elif isinstance(value, (int, float)) or re.fullmatch(r"\d{10,16}", str(value).strip()):
        n = float(value)
        while n > 1e11:                      # milliseconds, microseconds, nanoseconds -> seconds
            n /= 1000
        return datetime.fromtimestamp(n, tz=timezone.utc).replace(tzinfo=None) if n > 1e8 else None
    s = str(value).strip().replace("Z", "+0000")
    s = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", s)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def shift(dt: datetime | None, offset: str | None) -> datetime | None:
    """Apply a 'UTC+0530' style offset (Samsung stores UTC plus the offset in a separate column)."""
    m = re.search(r"([+-])(\d{2}):?(\d{2})", offset or "")
    if dt is None or not m:
        return dt
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return dt + delta if m.group(1) == "+" else dt - delta


def read_csv(text: str, skip_meta: bool = False) -> list[dict]:
    lines = text.lstrip("﻿").splitlines()
    if skip_meta and lines and lines[0].count(",") <= 3 and len(lines) > 1:
        lines = lines[1:]                    # Samsung: the first line is "com.samsung.health.x,version,count"
    return list(csv.DictReader(lines))


def col(row: dict, *suffixes: str):
    """Value of the first column whose name ends with one of the suffixes (Samsung prefixes its column names)."""
    for suffix in suffixes:
        for k, v in row.items():
            if k and (k == suffix or k.endswith("." + suffix)) and v not in (None, ""):
                return v
    return None


# ---------------------------------------------------------------------------------------------- Apple Health
APPLE = "HKQuantityTypeIdentifier"


def parse_apple(xml_file) -> Parsed:
    acc = Acc("apple_health")
    root, seen = None, 0
    for event, el in ElementTree.iterparse(xml_file, events=("start", "end")):
        if event == "start":
            if root is None:
                root = el
            continue
        tag = el.tag
        seen += 1
        if seen % 50000 == 0 and root is not None and tag in ("Record", "Workout"):
            root.clear()                     # exports hold millions of records: drop the ones already read
        if tag == "Record":
            a = el.attrib
            t, start = a.get("type", ""), parse_dt(a.get("startDate"))
            if start is not None:
                day, v, unit, src = start.date(), num(a.get("value")), a.get("unit", ""), a.get("sourceName", "")
                if t == APPLE + "StepCount":
                    acc.add(day, "steps", v or 0, src)
                elif t == APPLE + "HeartRate":
                    acc.heart(day, v)
                elif t == APPLE + "RestingHeartRate":
                    acc.set(day, "resting_hr", v)
                elif t == APPLE + "HeartRateVariabilitySDNN":
                    acc.mean(day, "hrv_ms", v)
                elif t == APPLE + "ActiveEnergyBurned":
                    acc.add(day, "active_kcal", (v or 0) / (4.184 if unit.lower() == "kj" else 1), src)
                elif t == APPLE + "DistanceWalkingRunning":
                    acc.add(day, "distance_km", (v or 0) * (1.609344 if unit == "mi" else 0.001 if unit == "m" else 1), src)
                elif t == APPLE + "OxygenSaturation":
                    acc.mean(day, "spo2", (v or 0) * (100 if (v or 0) <= 1 else 1))
                elif t == "HKCategoryTypeIdentifierSleepAnalysis" and "Asleep" in a.get("value", ""):
                    end = parse_dt(a.get("endDate"))
                    if end and end > start:           # a night belongs to the day you wake up
                        acc.add(end.date(), "sleep_minutes", (end - start).total_seconds() / 60, src)
            el.clear()
        elif tag == "Workout":
            a = el.attrib
            minutes = num(a.get("duration"))
            if minutes and a.get("durationUnit", "min") in ("s", "sec"):
                minutes /= 60
            kcal, dist = num(a.get("totalEnergyBurned")), num(a.get("totalDistance"))
            if dist and a.get("totalDistanceUnit") == "mi":
                dist *= 1.609344
            avg_hr = max_hr = None
            for st in el.findall("WorkoutStatistics"):
                st_type = st.get("type", "")
                if st_type == APPLE + "ActiveEnergyBurned" and kcal is None:
                    kcal = num(st.get("sum"))
                elif st_type == APPLE + "DistanceWalkingRunning" and dist is None:
                    dist = num(st.get("sum"))
                    if dist and st.get("unit") == "mi":
                        dist *= 1.609344
                elif st_type == APPLE + "HeartRate":
                    avg_hr, max_hr = num(st.get("average")), num(st.get("maximum"))
            acc.workout(parse_dt(a.get("startDate")), a.get("workoutActivityType", "Workout"), minutes, kcal, avg_hr,
                        max_hr, dist)
            el.clear()
        elif tag in ("ActivitySummary", "Me", "ExportDate", "Correlation", "ClinicalRecord"):
            el.clear()
    return acc.result()


# ---------------------------------------------------------------------------------------------- Google Fit (Takeout)
def parse_google_fit(text: str) -> Parsed:
    acc = Acc("google_fit")
    for row in read_csv(text):
        d = parse_dt(row.get("Date"))
        if d is None:
            continue
        day = d.date()
        acc.add(day, "steps", num(row.get("Step count")) or 0)
        acc.add(day, "distance_km", (num(row.get("Distance (m)")) or 0) / 1000)
        acc.set(day, "avg_hr", num(row.get("Average heart rate (bpm)")))
        acc.set(day, "max_hr", num(row.get("Max heart rate (bpm)")))
        acc.set(day, "min_hr", num(row.get("Min heart rate (bpm)")))
        sleep_ms = num(row.get("Sleep duration (ms)"))
        if sleep_ms:
            acc.add(day, "sleep_minutes", sleep_ms / 60000)
        for k, v in row.items():
            m = re.fullmatch(r"(.+) duration \(ms\)", k or "")
            ms = num(v)
            if m and ms and not re.search(r"sleep|inactive|still", m.group(1), re.I) and ms >= 5 * 60000:
                acc.workout(datetime(day.year, day.month, day.day, 12), m.group(1), ms / 60000)
    acc.notes.append("Google Fit only exports total calories (including the energy your body uses at rest), so calories are left out.")
    return acc.result()


# ---------------------------------------------------------------------------------------------- Fitbit (Takeout)
def parse_fitbit(z: zipfile.ZipFile, names: list[str]) -> Parsed:
    acc = Acc("fitbit")

    def load(name):
        try:
            return json.loads(z.read(name).decode("utf-8", "replace"))
        except (ValueError, KeyError):
            return []

    for name in names:
        base = name.rsplit("/", 1)[-1].lower()
        if re.match(r"steps-\d{4}-\d{2}-\d{2}\.json$", base):
            for r in load(name):
                d = parse_dt(r.get("dateTime"))
                if d:
                    acc.add(d.date(), "steps", num(r.get("value")) or 0)
        elif re.match(r"distance-\d{4}-\d{2}-\d{2}\.json$", base):
            for r in load(name):                        # centimetres
                d = parse_dt(r.get("dateTime"))
                if d:
                    acc.add(d.date(), "distance_km", (num(r.get("value")) or 0) / 100000)
        elif re.match(r"heart_rate-\d{4}-\d{2}-\d{2}\.json$", base):
            for r in load(name):
                d = parse_dt(r.get("dateTime"))
                if d and isinstance(r.get("value"), dict):
                    acc.heart(d.date(), num(r["value"].get("bpm")))
        elif base.startswith("resting_heart_rate-") and base.endswith(".json"):
            for r in load(name):
                v = r.get("value") or {}
                d = parse_dt(v.get("date") if isinstance(v, dict) else None) or parse_dt(r.get("dateTime"))
                if d and isinstance(v, dict):
                    acc.set(d.date(), "resting_hr", num(v.get("value")))
        elif re.match(r"sleep-\d{4}-\d{2}-\d{2}\.json$", base):
            for r in load(name):
                d = parse_dt(r.get("dateOfSleep"))
                if d:
                    acc.add(d.date(), "sleep_minutes", num(r.get("minutesAsleep")) or 0, str(r.get("logId", "")))
        elif re.match(r"exercise-\d+\.json$", base):
            for r in load(name):
                dur = num(r.get("activeDuration")) or num(r.get("duration"))
                dist = num(r.get("distance"))
                if dist and str(r.get("distanceUnit", "")).lower().startswith("mile"):
                    dist *= 1.609344
                acc.workout(parse_dt(r.get("startTime")), r.get("activityName", "Workout"), (dur or 0) / 60000,
                            num(r.get("calories")), num(r.get("averageHeartRate")), None, dist, num(r.get("steps")))
        elif base.startswith("daily heart rate variability summary") and base.endswith(".csv"):
            for r in read_csv(z.read(name).decode("utf-8", "replace")):
                d = parse_dt(r.get("timestamp"))
                if d:
                    acc.set(d.date(), "hrv_ms", num(r.get("rmssd")))
        elif base == "stress score.csv":
            for r in read_csv(z.read(name).decode("utf-8", "replace")):
                d, score = parse_dt(r.get("DATE")), num(r.get("STRESS_SCORE"))
                if d and score:                          # Fitbit's score: higher = fewer signs of stress
                    acc.set(d.date(), "stress", max(1.0, 100 - score))
    acc.notes.append("Fitbit's stress management score is shown reversed, so a higher number means more stress.")
    return acc.result()


# ---------------------------------------------------------------------------------------------- Samsung Health
SAMSUNG_TYPES = {1001: "Walking", 1002: "Running", 11007: "Cycling", 13001: "Hiking", 14001: "Swimming",
                 15001: "Strength training", 15002: "Strength training", 15005: "Elliptical", 9002: "Yoga",
                 10007: "Pilates", 15003: "Circuit training", 15006: "Rowing"}


def parse_samsung(files: dict[str, str]) -> Parsed:
    acc = Acc("samsung_health")
    for name, text in files.items():
        base = name.rsplit("/", 1)[-1].lower()
        if "sleep_stage" in base or "sleep_combined" in base or "sleep_data" in base or not base.endswith(".csv"):
            continue
        rows = read_csv(text, skip_meta=True)
        if "pedometer_day_summary" in base or "step_daily_trend" in base:
            for r in rows:
                d = parse_dt(col(r, "day_time"))
                if d:                                    # several devices each write a row: the biggest wins
                    src = str(col(r, "deviceuuid") or col(r, "source_pkg_name") or "")
                    acc.add(d.date(), "steps", num(col(r, "step_count", "count")) or 0, src)
                    acc.add(d.date(), "distance_km", (num(col(r, "distance")) or 0) / 1000, src)
                    acc.add(d.date(), "active_kcal", num(col(r, "calorie")) or 0, src)
        elif "tracker.heart_rate" in base or base.startswith("com.samsung.health.heart_rate"):
            for r in rows:
                d = shift(parse_dt(col(r, "start_time")), col(r, "time_offset"))
                if d:
                    acc.heart(d.date(), num(col(r, "heart_rate")))
        elif "shealth.stress" in base and "histogram" not in base:
            for r in rows:
                d = shift(parse_dt(col(r, "start_time")), col(r, "time_offset"))
                if d:
                    acc.mean(d.date(), "stress", num(col(r, "score")))
        elif re.search(r"shealth\.sleep\.\d|health\.sleep\.\d", base):
            for r in rows:
                off = col(r, "time_offset")
                s, e = shift(parse_dt(col(r, "start_time")), off), shift(parse_dt(col(r, "end_time")), off)
                if s and e and e > s:
                    acc.add(e.date(), "sleep_minutes", (e - s).total_seconds() / 60, str(col(r, "deviceuuid") or ""))
        elif "oxygen_saturation" in base:
            for r in rows:
                d = shift(parse_dt(col(r, "start_time")), col(r, "time_offset"))
                if d:
                    acc.mean(d.date(), "spo2", num(col(r, "spo2")))
        elif re.search(r"shealth\.exercise\.\d|health\.exercise\.\d", base):
            for r in rows:
                start = shift(parse_dt(col(r, "start_time")), col(r, "time_offset"))
                code = int(num(col(r, "exercise_type")) or 0)
                acc.workout(start, SAMSUNG_TYPES.get(code, "Workout"), (num(col(r, "duration")) or 0) / 60000,
                            num(col(r, "calorie")), num(col(r, "mean_heart_rate")), num(col(r, "max_heart_rate")),
                            (num(col(r, "distance")) or 0) / 1000 or None, num(col(r, "count")))
    return acc.result()


# ---------------------------------------------------------------------------------------------- Huawei Health
def parse_huawei(docs: dict[str, object]) -> Parsed:
    """Huawei's privacy export is a set of JSON files. The exact layout changes between app versions, so this walks
    the whole document and picks up the three shapes that carry data: sample points, daily sport totals and
    workout summaries."""
    acc = Acc("huawei_health")

    def sample(p: dict) -> None:
        key = str(p.get("key", "")).upper()
        start, end, v = parse_dt(p.get("startTime")), parse_dt(p.get("endTime")), num(p.get("value"))
        if start is None:
            return
        day = start.date()
        if "HEARTRATE" in key or "HEART_RATE" in key:
            acc.set(day, "resting_hr", v) if "REST" in key else acc.heart(day, v)
        elif "STRESS" in key:
            acc.mean(day, "stress", v)
        elif "SPO2" in key or "OXYGEN" in key:
            acc.mean(day, "spo2", v)
        elif "SLEEP" in key and "AWAKE" not in key and "NOON" not in key and end and end > start:
            acc.add(end.date(), "sleep_minutes", (end - start).total_seconds() / 60)
        elif "STEP" in key:
            acc.add(day, "steps", v or 0)

    def walk(node) -> None:
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            if isinstance(node.get("samplePoints"), list):
                for p in node["samplePoints"]:
                    if isinstance(p, dict):
                        sample(p)
            if "recordDay" in node and isinstance(node.get("sportBasicInfos"), list):
                d = parse_dt(node["recordDay"])
                for info in node["sportBasicInfos"]:
                    if d and isinstance(info, dict):
                        src = str(node.get("sportType", ""))     # one total per sport type; they overlap, so take the biggest
                        acc.add(d.date(), "steps", num(info.get("steps")) or 0, src)
                        acc.add(d.date(), "distance_km", (num(info.get("distance")) or 0) / 1000, src)
                        acc.add(d.date(), "active_kcal", (num(info.get("calorie")) or 0) / 1000, src)
            if "totalTime" in node and ("totalCalories" in node or "totalDistance" in node):
                acc.workout(parse_dt(node.get("startTime")), HUAWEI_TYPES.get(int(num(node.get("sportType")) or 0), "Workout"),
                            (num(node.get("totalTime")) or 0) / 60000, (num(node.get("totalCalories")) or 0) / 1000 or None,
                            num(node.get("avgHeartRate")), num(node.get("maxHeartRate")),
                            (num(node.get("totalDistance")) or 0) / 1000 or None, num(node.get("totalSteps")))
            for k, v in node.items():
                if k != "samplePoints" and isinstance(v, (list, dict)):
                    walk(v)

    for doc in docs.values():
        walk(doc)
    acc.notes.append("Huawei changes its export layout between app versions; if numbers are missing, use the CSV template.")
    return acc.result()


HUAWEI_TYPES = {4: "Running", 5: "Walking", 3: "Cycling", 7: "Swimming", 137: "Yoga", 10: "Hiking", 101: "Strength training",
                13: "Elliptical", 102: "Running", 264: "Running", 257: "Walking", 259: "Cycling"}


# ---------------------------------------------------------------------------------------------- WHOOP
def parse_whoop(files: dict[str, str]) -> Parsed:
    acc = Acc("whoop")
    for name, text in files.items():
        base = name.rsplit("/", 1)[-1].lower()
        rows = read_csv(text)
        if base.startswith("physiological_cycles"):
            for r in rows:
                d = parse_dt(r.get("Wake onset")) or parse_dt(r.get("Cycle start time"))
                if d is None:
                    continue
                day = d.date()
                acc.set(day, "resting_hr", num(r.get("Resting heart rate (bpm)")))
                acc.set(day, "hrv_ms", num(r.get("Heart rate variability (ms)")))
                acc.set(day, "avg_hr", num(r.get("Average HR (bpm)")))
                acc.set(day, "max_hr", num(r.get("Max HR (bpm)")))
                acc.set(day, "spo2", num(r.get("Blood oxygen %")))
                acc.add(day, "sleep_minutes", num(r.get("Asleep duration (min)")) or 0)
                rec = num(r.get("Recovery score %"))
                if rec is not None:                      # recovery: higher is better -> flipped into a stress number
                    acc.set(day, "stress", max(1.0, 100 - rec))
        elif base.startswith("workouts"):
            for r in rows:
                acc.workout(parse_dt(r.get("Workout start time")), r.get("Activity name", "Workout"),
                            num(r.get("Duration (min)")), num(r.get("Energy burned (cal)")), num(r.get("Average HR (bpm)")),
                            num(r.get("Max HR (bpm)")), (num(r.get("Distance (meters)")) or 0) / 1000 or None)
    acc.notes.append("WHOOP has no step count. Stress is 100 minus the WHOOP recovery score. WHOOP's daily energy includes resting energy, so it is left out.")
    return acc.result()


# ---------------------------------------------------------------------------------------------- Health Connect
HC_EXERCISE = {79: "Walking", 56: "Running", 8: "Cycling", 83: "Yoga", 74: "Swimming", 37: "Hiking", 70: "Strength training",
               81: "Strength training", 36: "HIIT", 25: "Elliptical", 53: "Rowing", 57: "Running", 13: "Calisthenics"}


def parse_health_connect(db_path: str) -> Parsed:
    """Android's Health Connect export is a SQLite database. Table and column names are looked up at run time,
    because they differ a little between Android versions."""
    acc = Acc("health_connect")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]

        def rows(pattern: str, exclude: str = "$^"):
            for t in tables:
                if re.search(pattern, t, re.I) and not re.search(exclude, t, re.I):
                    cols = [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')]
                    for r in con.execute(f'SELECT * FROM "{t}"'):
                        yield dict(zip(cols, tuple(r)))

        def when(r: dict, *keys: str) -> datetime | None:
            for k in keys:
                if r.get(k) is not None:
                    dt = parse_dt(r[k])
                    off = next((r[o] for o in ("zone_offset", "start_zone_offset", "end_zone_offset") if r.get(o) is not None), None)
                    return dt + timedelta(seconds=float(off)) if dt and off is not None else dt
            return None

        src = lambda r: str(r.get("app_info_id") or r.get("device_info_id") or "")
        for r in rows(r"^steps_record", "cadence"):
            d = when(r, "start_time", "end_time", "time")
            if d:
                acc.add(d.date(), "steps", num(r.get("count")) or 0, src(r))
        for r in rows(r"^distance_record"):
            d = when(r, "start_time", "end_time")
            if d:
                acc.add(d.date(), "distance_km", (num(r.get("distance")) or 0) / 1000, src(r))
        for r in rows(r"^active_calories_burned_record"):
            d = when(r, "start_time", "end_time")
            if d:
                acc.add(d.date(), "active_kcal", num(r.get("energy")) or 0, src(r))
        for r in rows(r"^heart_rate_record_series"):
            d = when(r, "epoch_millis", "time")
            if d:
                acc.heart(d.date(), num(r.get("beats_per_minute")))
        for r in rows(r"^resting_heart_rate_record"):
            d = when(r, "time", "start_time")
            if d:
                acc.set(d.date(), "resting_hr", num(r.get("beats_per_minute")))
        for r in rows(r"^heart_rate_variability"):
            d = when(r, "time", "start_time")
            if d:
                acc.mean(d.date(), "hrv_ms", num(r.get("heart_rate_variability_millis")))
        for r in rows(r"^oxygen_saturation_record"):
            d = when(r, "time", "start_time")
            if d:
                acc.mean(d.date(), "spo2", num(r.get("percentage")))
        for r in rows(r"^sleep_session_record"):
            s, e = when(r, "start_time"), when(r, "end_time")
            if s and e and e > s:
                acc.add(e.date(), "sleep_minutes", (e - s).total_seconds() / 60, src(r))
        for r in rows(r"^exercise_session_record"):
            s, e = when(r, "start_time"), when(r, "end_time")
            if s and e and e > s:
                acc.workout(s, r.get("title") or HC_EXERCISE.get(int(num(r.get("exercise_type")) or 0), "Workout"),
                            (e - s).total_seconds() / 60)
    finally:
        con.close()
    for key, by_source in acc.sums.items():               # Health Connect stores energy in calories, not kcal
        if key[1] == "active_kcal" and max(by_source.values()) > 20000:
            for s in by_source:
                by_source[s] /= 1000
    return acc.result()


# ---------------------------------------------------------------------------------------------- any CSV
SYNONYMS = {
    "date": ["date", "day", "datetime", "timestamp", "time", "start time", "start_time", "recorded at", "cycle start time"],
    "steps": ["steps", "step count", "step_count", "total steps", "total_steps", "stepcount"],
    "distance_km": ["distance (km)", "distance_km", "distance km", "km"],
    "distance_m": ["distance (m)", "distance_m", "distance (meters)", "distance in meters", "distance"],
    "active_kcal": ["active calories", "active_calories", "calories", "calories burned", "active energy", "kcal",
                    "energy burned (cal)", "calories (kcal)", "active kilocalories"],
    "resting_hr": ["resting heart rate", "resting_heart_rate", "resting hr", "rhr", "resting heart rate (bpm)", "resting_hr"],
    "avg_hr": ["average heart rate", "average_heart_rate", "avg heart rate", "avg hr", "heart rate", "heart_rate", "bpm",
               "average hr (bpm)", "average heart rate (bpm)", "avg_hr"],
    "max_hr": ["max heart rate", "max_heart_rate", "max hr", "max hr (bpm)", "max heart rate (bpm)", "maximum heart rate"],
    "min_hr": ["min heart rate", "min_heart_rate", "min hr", "min heart rate (bpm)"],
    "hrv_ms": ["hrv", "hrv_ms", "hrv (ms)", "heart rate variability", "heart rate variability (ms)", "rmssd", "sdnn", "avg hrv"],
    "stress": ["stress", "stress score", "stress level", "stress_score", "average stress", "avg stress", "stress_level"],
    "sleep_hours": ["sleep hours", "sleep_hours", "sleep (hours)", "sleep (h)", "hours of sleep", "sleep duration (h)",
                    "total sleep (h)", "sleep"],
    "sleep_minutes": ["sleep minutes", "sleep_minutes", "sleep (min)", "asleep duration (min)", "sleep duration (min)",
                      "total sleep (min)", "minutes asleep", "minutesasleep"],
    "spo2": ["spo2", "spo2 (%)", "blood oxygen", "blood oxygen %", "oxygen saturation", "blood oxygen (%)"],
}


def parse_generic_csv(text: str) -> Parsed:
    rows = read_csv(text)
    if not rows:
        raise WearableError("This CSV file is empty.")
    header = {(h or "").strip().lower(): h for h in rows[0].keys()}
    cols = {field: next((header[s] for s in names if s in header), None) for field, names in SYNONYMS.items()}
    if not cols["date"]:
        raise WearableError("This CSV has no date column. Use the FitBot template: one row per day with a 'date' column.")
    if not any(v for k, v in cols.items() if k != "date"):
        raise WearableError("No steps, heart rate, sleep or stress columns were recognised in this CSV. "
                            "Download the FitBot CSV template to see the column names.")
    acc = Acc("csv")
    for r in rows:
        d = parse_dt(r.get(cols["date"]))
        if d is None:
            continue
        day, get = d.date(), lambda f: num(r.get(cols[f])) if cols[f] else None
        acc.add(day, "steps", get("steps") or 0)
        acc.add(day, "distance_km", get("distance_km") or ((get("distance_m") or 0) / 1000))
        acc.add(day, "active_kcal", get("active_kcal") or 0)
        acc.add(day, "sleep_minutes", get("sleep_minutes") or ((get("sleep_hours") or 0) * 60))
        for f in ("resting_hr", "avg_hr", "hrv_ms", "stress", "spo2"):
            acc.mean(day, f, get(f))
        if get("max_hr"):
            acc.last[(day, "max_hr")] = max(acc.last.get((day, "max_hr"), 0), get("max_hr"))
        if get("min_hr"):
            acc.last[(day, "min_hr")] = min(acc.last.get((day, "min_hr"), 999), get("min_hr"))
    return acc.result()


# ---------------------------------------------------------------------------------------------- format detection
def parse_export(path: str | Path, filename: str = "") -> Parsed:
    """Read an export file of any supported brand. Raises WearableError with a message for the user."""
    path = Path(path)
    name = (filename or path.name).lower()
    with open(path, "rb") as fh:
        head = fh.read(600)
    try:
        if head.startswith(b"PK"):
            parsed = _parse_zip(path)
        elif head.startswith(b"SQLite format 3"):
            parsed = parse_health_connect(str(path))
        elif b"<HealthData" in head or b"<?xml" in head[:60]:
            parsed = parse_apple(str(path))
        elif head.lstrip()[:1] in (b"[", b"{"):
            parsed = parse_huawei({name: json.loads(path.read_text(encoding="utf-8", errors="replace"))})
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            first = text.lstrip("﻿").split("\n", 1)[0]
            if "com.samsung" in first:
                parsed = parse_samsung({name if name.endswith(".csv") else name + ".csv": text})
            elif "Step count" in first and "Move Minutes count" in first:
                parsed = parse_google_fit(text)
            elif "Cycle start time" in first or "Workout start time" in first:
                parsed = parse_whoop({"physiological_cycles.csv" if "Recovery score" in first else "workouts.csv": text})
            else:
                parsed = parse_generic_csv(text)
    except WearableError:
        raise
    except (zipfile.BadZipFile, ElementTree.ParseError, sqlite3.DatabaseError, json.JSONDecodeError, UnicodeError, csv.Error) as e:
        raise WearableError(f"This file could not be read ({type(e).__name__}). Please upload the export file exactly "
                            "as the app created it.") from e
    if not parsed.daily and not parsed.workouts:
        raise WearableError("No steps, heart rate, sleep or workout data was found in this file. Check that it is the "
                            "health data export, or use the FitBot CSV template.")
    return parsed


def _parse_zip(path: Path) -> Parsed:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        low = [n.lower() for n in names]
        if sum(z.getinfo(n).file_size for n in names) > 8 * 1024 ** 3:
            raise WearableError("This export is too large to read (over 8 GB unpacked).")
        text = lambda n: z.read(n).decode("utf-8", "replace")
        apple = next((n for n, l in zip(names, low) if l.endswith("export.xml") and "cda" not in l), None)
        if apple:
            with z.open(apple) as fh:
                return parse_apple(fh)
        db = next((n for n, l in zip(names, low) if l.endswith(".db")), None)
        if db:
            with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
                with z.open(db) as src:
                    while chunk := src.read(1 << 20):
                        tmp.write(chunk)
                tmp.flush()
                return parse_health_connect(tmp.name)
        if any("com.samsung" in l and l.endswith(".csv") for l in low):
            return parse_samsung({n: text(n) for n, l in zip(names, low) if "com.samsung" in l and l.endswith(".csv")
                                  and z.getinfo(n).file_size < 300 * 1024 ** 2})
        if any(l.rsplit("/", 1)[-1].startswith("physiological_cycles") for l in low):
            return parse_whoop({n: text(n) for n, l in zip(names, low) if l.endswith(".csv")})
        fitbit = [n for n, l in zip(names, low) if re.search(r"(steps|heart_rate|resting_heart_rate|sleep|distance)-\d{4}-\d{2}-\d{2}\.json$|exercise-\d+\.json$|stress score\.csv$|heart rate variability summary", l)]
        fit = next((n for n, l in zip(names, low) if l.endswith("daily activity metrics.csv")), None)
        if fitbit or fit:
            parts = ([parse_fitbit(z, fitbit)] if fitbit else []) + ([parse_google_fit(text(fit))] if fit else [])
            return merge_parsed(parts)
        huawei = [n for n, l in zip(names, low) if l.endswith(".json") and re.search(r"health detail|sport per minute|motion path", l)]
        if huawei:
            docs = {}
            for n in huawei:
                try:
                    docs[n] = json.loads(text(n))
                except ValueError:
                    continue
            return parse_huawei(docs)
        csvs = [n for n, l in zip(names, low) if l.endswith(".csv")]
        if csvs:
            parts = []
            for n in csvs[:40]:
                try:
                    parts.append(parse_generic_csv(text(n)))
                except WearableError:
                    continue
            if parts:
                return merge_parsed(parts)
    raise WearableError("This zip is not a health export FitBot knows. Supported: Apple Health, Samsung Health, "
                        "Google Takeout (Fitbit or Fit), Health Connect, Huawei Health, WHOOP, or a CSV file.")


def merge_parsed(parts: list[Parsed]) -> Parsed:
    out = Parsed(format="+".join(dict.fromkeys(p.format for p in parts)))
    for p in parts:
        for day, row in p.daily.items():
            merged = out.daily.setdefault(day, {})
            for k, v in row.items():
                merged[k] = max(merged[k], v) if k in merged and k in ("steps", "distance_km", "active_kcal", "sleep_minutes", "max_hr") else merged.get(k, v)
        out.workouts += p.workouts
        out.notes += [n for n in p.notes if n not in out.notes]
    return out


# ---------------------------------------------------------------------------------------------- summaries
def merge_sources(rows: list[dict]) -> dict:
    """One day's rows from several sources -> one row. Totals take the largest source, the rest the first value."""
    out: dict = {}
    for r in rows:
        for k in METRICS:
            v = r.get(k)
            if v is None:
                continue
            if k in ("steps", "distance_km", "active_kcal", "sleep_minutes", "max_hr"):
                out[k] = max(out.get(k, 0), v)
            elif k == "min_hr":
                out[k] = min(out.get(k, 999), v)
            else:
                out.setdefault(k, v)
    return out


def add_stress_estimates(days: dict[date, dict]) -> None:
    """Bands without a stress score still give resting heart rate and HRV. When either moves away from the person's
    own recent average, that usually reflects strain (poor sleep, hard training, illness, mental stress). This turns
    that shift into a 0 to 100 estimate: 50 = your usual, higher = more strain. It is a wellness estimate, not a
    medical measurement, and is flagged as estimated."""
    ordered = sorted(days)
    for i, day in enumerate(ordered):
        row = days[day]
        if row.get("stress") is not None:
            continue
        past = [days[d] for d in ordered[max(0, i - 28):i]]
        score, used = 50.0, False
        for key, weight in (("resting_hr", 3.0), ("hrv_ms", -0.8)):
            base = [p[key] for p in past if p.get(key)]
            if row.get(key) and len(base) >= 5:
                median = statistics.median(base)
                score += weight * (row[key] - median) / median * 100
                used = True
        if used:
            row["stress"] = round(min(100.0, max(1.0, score)), 1)
            row["stress_estimated"] = True


def fmt_sleep(minutes: float | None) -> str:
    if not minutes:
        return "no data"
    return f"{int(minutes // 60)} h {int(round(minutes % 60)):02d} min"


def stress_word(score: float | None) -> str:
    if score is None:
        return "no data"
    return "low" if score < 30 else "normal" if score < 60 else "high" if score < 80 else "very high"


def build_summary(rows: list[dict], workouts: list[dict], today: date, days: int = 14) -> dict:
    """Everything the Bands page, the dashboard card and the chat need, from the stored daily rows."""
    by_day: dict[date, list[dict]] = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(r)
    merged = {d: merge_sources(rs) for d, rs in by_day.items()}
    add_stress_estimates(merged)
    window = [today - timedelta(days=i) for i in reversed(range(days))]
    series = [{"day": d.isoformat(), **{k: merged.get(d, {}).get(k) for k in METRICS},
               "stress_estimated": bool(merged.get(d, {}).get("stress_estimated"))} for d in window]
    have = sorted(d for d in merged if d <= today)
    latest_day = have[-1] if have else None
    latest = {"day": latest_day.isoformat(), **merged[latest_day]} if latest_day else None

    def avg(key: str, start: int, end: int):
        vals = [merged[d][key] for d in (today - timedelta(days=i) for i in range(start, end)) if d in merged and merged[d].get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    week = {k: avg(k, 0, 7) for k in ("steps", "sleep_minutes", "resting_hr", "hrv_ms", "stress", "active_kcal")}
    prev = {k: avg(k, 7, 14) for k in ("steps", "sleep_minutes", "resting_hr", "hrv_ms", "stress")}
    base = {k: avg(k, 1, 29) for k in ("resting_hr", "hrv_ms")}
    recent_workouts = [w for w in workouts if w["start"].date() >= today - timedelta(days=days)]
    insights: list[str] = []
    if week["steps"]:
        line = f"You averaged {week['steps']:,.0f} steps a day over the last 7 days"
        if prev["steps"]:
            change = (week["steps"] - prev["steps"]) / prev["steps"] * 100
            line += f", {'up' if change >= 0 else 'down'} {abs(change):.0f}% on the week before"
        insights.append(line + ".")
    if week["sleep_minutes"]:
        short = week["sleep_minutes"] < 7 * 60
        insights.append(f"Sleep averaged {fmt_sleep(week['sleep_minutes'])} a night this week"
                        + (". Most adults do best with 7 to 9 hours, so an earlier night would help recovery." if short else ", inside the 7 to 9 hours most adults need."))
    if latest and latest.get("resting_hr") and base["resting_hr"]:
        diff = latest["resting_hr"] - base["resting_hr"]
        if diff >= 5:
            insights.append(f"Resting heart rate is {diff:.0f} bpm above your 4 week average. That often follows poor sleep, "
                            "hard training or coming down with something, so an easier day is a sensible choice.")
        elif diff <= -3:
            insights.append(f"Resting heart rate is {abs(diff):.0f} bpm below your 4 week average, a sign you are well recovered.")
    if latest and latest.get("stress") is not None and latest["stress"] >= 70:
        insights.append("Stress is high on your latest day. Slow breathing, a walk or a gentle yoga routine can help you settle.")
    if recent_workouts:
        mins = sum(w["minutes"] for w in recent_workouts)
        insights.append(f"Your band recorded {len(recent_workouts)} workouts ({mins:.0f} minutes) in the last {days} days.")
    return {"connected": bool(merged or workouts), "today": today.isoformat(), "latest": latest,
            "today_row": {"day": today.isoformat(), **merged[today]} if today in merged else None,
            "series": series, "week": week, "previous_week": prev, "baseline": base, "insights": insights,
            "days_with_data": len(merged), "first_day": have[0].isoformat() if have else None,
            "sources": sorted({r["source"] for r in rows} | {w["source"] for w in workouts})}


HEALTH_RE = re.compile(
    r"\b(my|i|me|today|yesterday|last night|this week)\b.*\b(steps?|step count|heart ?rate|pulse|bpm|hrv|stress|sleep|slept|"
    r"recover(y|ed)?|readiness|calories burn(ed|t)?|band|watch|tracker|wearable)\b|"
    r"\b(steps?|heart ?rate|hrv|stress|sleep|recovery|readiness)\b.*\b(my|today|yesterday|last night|this week|band|watch)\b|"
    r"\b(am i|should i) (recovered|rested|ready|train|work ?out|rest)\b", re.I)


# Asks for the person's own recorded numbers ("how many steps did I do today", "what is my resting heart rate",
# "how did I sleep last night", "am I recovered enough to train today"), as opposed to general advice
# ("how much should I sleep", "what should my heart rate be when running").
_METRIC = r"(steps?|step count|heart ?rate|pulse|bpm|hrv|stress( level| score)?|sleep|slept|recover(y|ed)|readiness|calories|distance|walk(ed)?)"
_WHEN = r"(today|yesterday|last night|tonight|this (week|morning)|last week|so far|right now|currently|latest|recent(ly)?|these days)"
BAND_QUESTION_RE = re.compile(
    rf"^(?!.*\bshould (my|i)\b(?!.*\b{_WHEN}\b))(?:"
    rf"(?=.*\b{_METRIC}\b)(?=.*\b(my|i|me)\b)(?=.*\b({_WHEN}|did i|have i)\b)"
    rf"|.*\b(what(\'s| is| was| are| were)|show( me)?|tell me|check|how(\'s| is| was| are))\b.{{0,12}}\bmy\b.{{0,24}}\b{_METRIC}\b"
    rf"|.*\b(am i|should i)\b.{{0,30}}\b(recovered|rested|ready|train|work ?out|exercise|rest)\b.*\b{_WHEN}\b"
    rf"|.*\bmy (band|watch|tracker|wearable)\b)", re.I | re.S)
NO_BAND_MESSAGE = ("I don't have any fitness band data for you yet. Open Bands in the menu, choose your band (Apple Watch, "
                   "Samsung, Google or Fitbit, Huawei, OnePlus, Noise, WHOOP and others) and upload the export file from its "
                   "phone app. After that I can answer with your own steps, heart rate, sleep and stress.")


def health_context(summary: dict | None) -> list[str]:
    """Reference lines about the person's own band data for the SLM (written as guidance passages, the format the
    model paraphrases best). Returns [] when there is no band data."""
    if not summary or not summary.get("latest"):
        return []
    d, w, b = summary["latest"], summary["week"], summary["baseline"]
    when = "today" if d["day"] == summary["today"] else f"on {d['day']} (the latest day with band data)"
    facts = []
    if d.get("steps") is not None:
        facts.append(f"{d['steps']:,} steps")
    if d.get("distance_km"):
        facts.append(f"{d['distance_km']:.1f} km")
    if d.get("active_kcal"):
        facts.append(f"{d['active_kcal']:.0f} active kcal")
    if d.get("sleep_minutes"):
        facts.append(f"{fmt_sleep(d['sleep_minutes'])} of sleep")
    if d.get("resting_hr"):
        facts.append(f"resting heart rate {d['resting_hr']:.0f} bpm")
    if d.get("avg_hr"):
        facts.append(f"average heart rate {d['avg_hr']:.0f} bpm")
    if d.get("hrv_ms"):
        facts.append(f"HRV {d['hrv_ms']:.0f} ms")
    if d.get("stress") is not None:
        facts.append(f"stress {d['stress']:.0f} out of 100 ({stress_word(d['stress'])}{', estimated' if d.get('stress_estimated') else ''})")
    lines = [f"Guidance (Your fitness band data): The person's own band recorded {when}: {', '.join(facts)}. "
             "Use these exact numbers; do not change them."]
    avgs = []
    if w.get("steps"):
        avgs.append(f"{w['steps']:,.0f} steps a day")
    if w.get("sleep_minutes"):
        avgs.append(f"{fmt_sleep(w['sleep_minutes'])} of sleep a night")
    if w.get("resting_hr"):
        avgs.append(f"resting heart rate {w['resting_hr']:.0f} bpm")
    if b.get("resting_hr") and d.get("resting_hr"):
        diff = d["resting_hr"] - b["resting_hr"]
        avgs.append(f"latest resting heart rate is {abs(diff):.0f} bpm {'above' if diff > 0 else 'below'} the 4 week average")
    if avgs:
        lines.append(f"Guidance (Your last 7 days from the band): Averages: {'; '.join(avgs)}. "
                     + " ".join(summary["insights"][:2]))
    return lines


def health_card(summary: dict | None) -> dict | None:
    """The numbers shown under a chat answer that used band data (so they never depend on the model's wording)."""
    if not summary or not summary.get("latest"):
        return None
    d = summary["latest"]
    return {"day": d["day"], "is_today": d["day"] == summary["today"], "sources": summary["sources"],
            **{k: d.get(k) for k in METRICS}, "stress_estimated": bool(d.get("stress_estimated")),
            "stress_label": stress_word(d.get("stress")), "week": summary["week"]}
