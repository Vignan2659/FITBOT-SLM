"""Fitness band support: export parsers for every brand, the import API, the summary, stress estimates and the
chat answers that use the person's own numbers."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import wearables as w
from tests.band_samples import T, build
from tests.conftest import GENERATED, register


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    return build(tmp_path_factory.mktemp("bands"))


def latest(parsed):
    return parsed.daily[max(parsed.daily)]


def test_apple_health_export(samples):
    p = w.parse_export(samples / "apple_export.zip")
    day = p.daily[T]
    assert p.format == "apple_health" and len(p.daily) == 10
    assert day["steps"] == 8000                      # the watch's count, not watch + phone added together
    assert day["resting_hr"] == 64 and day["max_hr"] == 131 and day["min_hr"] == 58
    assert day["sleep_minutes"] == 420               # asleep stages only; "in bed" is not counted
    assert day["spo2"] == 97 and day["hrv_ms"] == 60 and day["distance_km"] == 5.2
    assert p.workouts == [{"start": p.workouts[0]["start"], "activity": "Strength training", "minutes": 42.5,
                           "kcal": 310.0, "avg_hr": 128.0, "max_hr": 161.0, "distance_km": None, "steps": None}]


def test_samsung_health_export(samples):
    p = w.parse_export(samples / "samsung.zip")
    day = p.daily[T]
    assert p.format == "samsung_health" and day["steps"] == 7000 and day["stress"] == 50
    assert day["sleep_minutes"] == 420 and day["max_hr"] == 98
    assert p.workouts[0]["activity"] == "Running" and p.workouts[0]["start"].hour == 6    # UTC + 05:30 offset applied


def test_google_takeout_fitbit_and_fit(samples):
    p = w.parse_export(samples / "takeout.zip")
    day = p.daily[T]
    assert "fitbit" in p.format and "google_fit" in p.format
    assert day["steps"] == 8200 and day["resting_hr"] == 57.4 and day["hrv_ms"] == 41.5 and day["sleep_minutes"] == 431
    assert day["stress"] == 22                       # Fitbit score 78 (higher is better) is flipped
    assert "active_kcal" not in day                  # Google Fit only has total calories
    run = next(x for x in p.workouts if x["activity"] == "Run")
    assert run["distance_km"] == 4.02 and run["steps"] == 4100


def test_whoop_export(samples):
    p = w.parse_export(samples / "whoop.zip")
    day = p.daily[T]
    assert p.format == "whoop" and day["resting_hr"] == 54 and day["hrv_ms"] == 71 and day["stress"] == 34
    assert "steps" not in day and p.workouts[0]["activity"] == "Strength training"


def test_health_connect_export_for_oneplus_and_others(samples):
    for name in ("health_connect.zip", "hc.db"):
        p = w.parse_export(samples / name)
        assert p.format == "health_connect" and p.daily[T]["steps"] == 5900 and p.daily[T]["resting_hr"] == 59
        assert p.daily[T]["sleep_minutes"] == 420 and p.workouts[0]["activity"] == "Yoga"


def test_huawei_health_export(samples):
    p = w.parse_export(samples / "huawei.zip")
    day = p.daily[T]
    assert p.format == "huawei_health" and day["steps"] == 8100 and day["stress"] == 44 and day["resting_hr"] == 60
    assert day["distance_km"] == 6.0 and day["active_kcal"] == 350


def test_plain_csv_with_common_column_names(samples):
    p = w.parse_export(samples / "generic.csv")
    assert p.format == "csv" and latest(p) == {"steps": 10250, "sleep_minutes": 372.0, "resting_hr": 61.0,
                                               "hrv_ms": 51.0, "stress": 58.0}
    assert w.parse_export(_write(samples / "template.csv", w.TEMPLATE_CSV)).daily      # the template itself imports


def _write(path, text):
    path.write_text(text)
    return path


@pytest.mark.parametrize("name,text", [("empty.csv", ""), ("notes.csv", "name,colour\nx,red\n"),
                                       ("nodate.csv", "steps\n100\n"), ("bad.zip", "PK\x03\x04 not a zip")])
def test_unreadable_files_give_a_clear_error(samples, name, text):
    with pytest.raises(w.WearableError):
        w.parse_export(_write(samples / name, text))


def test_implausible_values_are_dropped(samples):
    p = w.parse_export(_write(samples / "odd.csv", "date,steps,resting heart rate,spo2\n2026-11-10,999999,300,97\n"))
    assert latest(p) == {"spo2": 97.0}


def test_stress_is_estimated_from_resting_heart_rate_and_hrv():
    days = {T - timedelta(days=i): {"resting_hr": 56.0, "hrv_ms": 60.0} for i in range(1, 12)}
    days[T] = {"resting_hr": 64.0, "hrv_ms": 45.0}
    w.add_stress_estimates(days)
    assert days[T]["stress"] > 80 and days[T]["stress_estimated"]           # well above the personal baseline
    assert days[T - timedelta(days=1)]["stress"] == 50                       # a usual day
    assert "stress" not in days[T - timedelta(days=10)]                      # too little history to estimate


def test_summary_and_context_lines():
    rows = [{"day": T - timedelta(days=i), "source": "apple", "steps": 8000 - 100 * i, "sleep_minutes": 400.0,
             "resting_hr": 56.0 + (8 if i == 0 else 0), "hrv_ms": 60.0} for i in range(20)]
    rows.append({"day": T, "source": "manual", "steps": 500, "stress": 30.0})
    s = w.build_summary(rows, [], T)
    assert s["connected"] and s["latest"]["steps"] == 8000 and s["latest"]["stress"] == 30     # sources merged
    assert len(s["series"]) == 14 and s["series"][-1]["day"] == T.isoformat()
    assert any("above your 4 week average" in i for i in s["insights"])
    lines = w.health_context(s)
    assert "8,000 steps" in lines[0] and "6 h 40 min of sleep" in lines[0] and "resting heart rate 64 bpm" in lines[0]
    assert w.health_context(w.build_summary([], [], T)) == []


# ---------------------------------------------------------------------------------------------- API
def upload(client, headers, path, brand):
    return client.post(f"/wearables/import?brand={brand}&filename={path.name}", content=path.read_bytes(), headers=headers)


def test_import_summary_and_delete(client, auth, samples):
    assert client.get("/wearables/summary").status_code == 401
    r = client.get("/wearables/summary", headers=auth["headers"])
    assert r.status_code == 200 and r.json()["connected"] is False

    r = upload(client, auth["headers"], samples / "apple_export.zip", "apple")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["format"] == "apple_health" and body["days"] == 10 and body["workouts"] == 1 and "steps" in body["metrics"]
    assert upload(client, auth["headers"], samples / "apple_export.zip", "apple").json()["new_workouts"] == 0   # no duplicates

    s = client.get(f"/wearables/summary?today={T}", headers=auth["headers"]).json()
    assert s["connected"] and s["today_row"]["steps"] == 8000 and s["week"]["steps"] and s["sources"] == ["apple"]
    assert s["workouts"][0]["activity"] == "Strength training" and len(s["imports"]) == 2

    # a second brand for the same day: totals take the larger source instead of adding up
    assert upload(client, auth["headers"], samples / "samsung.zip", "samsung").status_code == 201
    s = client.get(f"/wearables/summary?today={T}", headers=auth["headers"]).json()
    assert s["today_row"]["steps"] == 8000 and s["today_row"]["stress"] == 50 and s["sources"] == ["apple", "samsung"]

    assert client.delete("/wearables/data?source=samsung", headers=auth["headers"]).status_code == 204
    assert client.get(f"/wearables/summary?today={T}", headers=auth["headers"]).json()["sources"] == ["apple"]
    assert client.delete("/wearables/data", headers=auth["headers"]).status_code == 204
    assert client.get("/wearables/summary", headers=auth["headers"]).json()["connected"] is False


def test_import_rejects_bad_files_and_brands(client, auth, samples):
    r = client.post("/wearables/import?brand=apple&filename=x.csv", content=b"hello,world\n1,2\n", headers=auth["headers"])
    assert r.status_code == 422 and "date column" in r.json()["detail"]
    assert client.post("/wearables/import?brand=apple", content=b"", headers=auth["headers"]).status_code == 422
    assert client.post("/wearables/import?brand=nokia", content=b"x", headers=auth["headers"]).status_code == 422
    assert client.post("/wearables/import?brand=apple", content=b"x").status_code == 401


def test_manual_day_live_session_and_privacy(client, auth, samples):
    today = date.today()
    r = client.put("/wearables/day", json={"day": str(today), "steps": 6400, "sleep_minutes": 450, "stress": 41}, headers=auth["headers"])
    assert r.status_code == 200 and r.json()["saved"] == ["sleep_minutes", "steps", "stress"]
    assert client.put("/wearables/day", json={"day": str(today)}, headers=auth["headers"]).status_code == 422
    assert client.put("/wearables/day", json={"day": str(today), "resting_hr": 400}, headers=auth["headers"]).status_code == 422
    r = client.post("/wearables/live", json={"started_at": f"{today}T07:00:00", "minutes": 21.5, "avg_hr": 132, "max_hr": 168,
                                             "activity": "yoga", "device": "WHOOP 4.0"}, headers=auth["headers"])
    assert r.status_code == 201 and r.json()["activity"] == "Yoga"
    s = client.get("/wearables/summary", headers=auth["headers"]).json()
    assert s["today_row"]["steps"] == 6400 and s["workouts"][0]["avg_hr"] == 132 and "live" in s["sources"]

    _, _, other = register(client)                                    # another user sees none of it
    s2 = client.get("/wearables/summary", headers={"Authorization": f"Bearer {other}"}).json()
    assert s2["connected"] is False and s2["workouts"] == []


def test_brand_guides_and_template(client):
    b = client.get("/wearables/brands").json()
    ids = {x["id"] for x in b["brands"]}
    assert {"apple", "samsung", "google", "huawei", "oneplus", "noise", "whoop", "other"} == ids
    assert all(len(x["steps"]) == 3 and x["gives"] for x in b["brands"])
    t = client.get("/wearables/template.csv")
    assert t.status_code == 200 and t.text.startswith("date,steps,") and "attachment" in t.headers["content-disposition"]


# ---------------------------------------------------------------------------------------------- chat
def chat(client, headers, message, conversation_id=None):
    r = client.post("/chat", json={"message": message, "conversation_id": conversation_id}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_chat_without_band_data_points_to_the_bands_page(client, auth):
    out = chat(client, auth["headers"], "How many steps did I walk today?")
    assert out["category"] == "band" and "Bands" in out["answer"] and out["band"] is None
    assert out["model"]["generated"] is False
    out = chat(client, auth["headers"], "How can I improve my sleep?")           # general advice still works
    assert out["category"] != "band" and out["model"]["generated"]


def test_chat_uses_the_persons_own_band_numbers(client, auth):
    today = date.today()
    client.put("/wearables/day", json={"day": str(today), "steps": 9321, "sleep_minutes": 388, "resting_hr": 58, "stress": 72},
               headers=auth["headers"])
    out = chat(client, auth["headers"], "How many steps did I do today and how was my sleep?")
    assert out["category"] == "band" and out["band"]["steps"] == 9321 and out["band"]["is_today"]
    assert out["band"]["stress_label"] == "high" and out["sources"][0]["type"] == "band"
    system = GENERATED[-1][0]["content"]
    assert "9,321 steps" in system and "6 h 28 min of sleep" in system and "resting heart rate 58 bpm" in system
    assert out["exercises"] == [] and out["workout_plan"] is None

    conv = client.get(f"/conversations/{out['conversation_id']}", headers=auth["headers"]).json()
    assert conv["messages"][-1]["payload"]["band"]["steps"] == 9321                # the card survives a reload

    plan = chat(client, auth["headers"], "Give me a 3 day workout plan that fits my sleep and stress this week")
    assert plan["workout_plan"] and plan["band"]["steps"] == 9321                  # a plan, with the numbers attached
    assert "9,321 steps" in GENERATED[-1][0]["content"]

    other = chat(client, auth["headers"], "What exercises can I do for chest?")
    assert other["band"] is None and other["exercises"]                            # unrelated questions are unchanged


def test_emergency_heart_questions_still_hit_the_safety_guardrail(client, auth):
    out = chat(client, auth["headers"], "My heart rate is racing and I have chest pain, what should I do?")
    assert out["category"] == "medical_safety" and out["band"] is None
