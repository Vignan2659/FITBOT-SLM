import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, localDate } from "../api/client.js";
import WorkoutPlan from "../components/WorkoutPlan.jsx";
import { IconChat, IconTrash } from "../components/Icons.jsx";

const EMPTY = { day: localDate(), exercise: "", sets: "", reps: "", weight_kg: "", minutes: "", notes: "" };
const NUMERIC = ["sets", "reps", "weight_kg", "minutes"];

function shortDate(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function longDate(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function dose(w) {
  const parts = [];
  if (w.sets && w.reps) parts.push(`${w.sets} × ${w.reps}`);
  else if (w.sets) parts.push(`${w.sets} sets`);
  else if (w.reps) parts.push(`${w.reps} reps`);
  if (w.weight_kg != null) parts.push(`${w.weight_kg} kg`);
  if (w.minutes) parts.push(`${w.minutes} min`);
  return parts.join(" · ");
}

// Active days per week, last 8 weeks (no chart library needed).
function WeekChart({ weeks }) {
  return (
    <div className="week-chart" role="img"
         aria-label={`Active days per week: ${weeks.map((w) => `${shortDate(w.week_start)} ${w.active_days}`).join(", ")}`}>
      {weeks.map((w) => (
        <div key={w.week_start} className="week-col">
          <span className="week-val">{w.active_days || ""}</span>
          <div className="week-bar"><div style={{ height: `${(w.active_days / 7) * 100}%` }} /></div>
          <span className="week-lbl">{shortDate(w.week_start)}</span>
        </div>
      ))}
    </div>
  );
}

export default function Workouts() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [plans, setPlans] = useState([]);
  const [names, setNames] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, l, p] = await Promise.all([api.workoutStats(localDate()), api.listWorkouts(60), api.listPlans()]);
      setStats(s);
      setLogs(l);
      setPlans(p);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    api.exercises().then((r) => setNames(r.exercises.map((e) => e.name))).catch(() => setNames([]));
  }, [refresh]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    setOk("");
    const entry = { day: form.day, exercise: form.exercise.trim(), notes: form.notes.trim() || null };
    for (const k of NUMERIC) entry[k] = form[k] === "" ? null : Number(form[k]);
    setSaving(true);
    try {
      await api.logWorkouts([entry]);
      setOk(`Logged ${entry.exercise}.`);
      setForm((f) => ({ ...EMPTY, day: f.day }));
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function removeLog(id) {
    try {
      await api.deleteWorkout(id);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  async function removePlan(id) {
    if (!window.confirm("Remove this saved plan?")) return;
    try {
      await api.deletePlan(id);
      setPlans((ps) => ps.filter((p) => p.id !== id));
    } catch (e) {
      setError(e.message);
    }
  }

  const byDay = logs.reduce((acc, w) => ((acc[w.day] ||= []).push(w), acc), {});

  return (
    <div className="page workouts">
      <header>
        <h1 className="page-title">My workouts</h1>
        <p className="muted">Log what you train, keep your saved plans and watch your consistency grow.</p>
      </header>
      {error && <div className="form-error" role="alert">{error}</div>}

      <section className="stats">
        <div className="stat"><span>This week</span><strong>{stats?.this_week ?? "—"}</strong><small>active days</small></div>
        <div className="stat"><span>Current streak</span><strong>{stats?.current_streak ?? "—"}</strong><small>days in a row</small></div>
        <div className="stat"><span>Active days</span><strong>{stats?.active_days ?? "—"}</strong><small>all time</small></div>
        <div className="stat"><span>Exercises logged</span><strong>{stats?.total_entries ?? "—"}</strong><small>entries</small></div>
      </section>

      <div className="wk-grid">
        <section className="panel">
          <h2 className="section-title">Log an exercise</h2>
          <form className="form log-form" onSubmit={submit}>
            <label>Date<input type="date" value={form.day} max={localDate()} onChange={set("day")} required /></label>
            <label className="span-2">Exercise
              <input list="exercise-names" value={form.exercise} onChange={set("exercise")} maxLength={80} required
                     placeholder="e.g. Barbell Squat or Running" />
            </label>
            <datalist id="exercise-names">{names.map((n) => <option key={n} value={n} />)}</datalist>
            <label>Sets<input type="number" min="1" max="50" value={form.sets} onChange={set("sets")} /></label>
            <label>Reps<input type="number" min="1" max="500" value={form.reps} onChange={set("reps")} /></label>
            <label>Weight (kg)<input type="number" min="0" max="1000" step="0.5" value={form.weight_kg} onChange={set("weight_kg")} /></label>
            <label>Minutes<input type="number" min="1" max="1440" value={form.minutes} onChange={set("minutes")} /></label>
            <label className="span-2">Notes<input value={form.notes} onChange={set("notes")} maxLength={200} placeholder="Optional" /></label>
            <div className="span-2 log-submit">
              <button className="btn btn-primary" disabled={saving || !form.exercise.trim()}>{saving ? "Saving..." : "Log exercise"}</button>
              {ok && <span className="form-ok">{ok}</span>}
            </div>
          </form>
        </section>

        <section className="panel">
          <h2 className="section-title">Active days per week</h2>
          {stats ? <WeekChart weeks={stats.weeks} /> : <p className="muted">Loading...</p>}
          {stats?.top_exercises?.length > 0 && (
            <>
              <h3 className="sub-title">Most logged</h3>
              <ul className="top-list">
                {stats.top_exercises.map((t) => (
                  <li key={t.exercise}>
                    <span>{t.exercise}</span>
                    <span className="muted">{t.times}×{t.best_weight_kg != null ? ` · best ${t.best_weight_kg} kg` : ""}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      <section>
        <h2 className="section-title">Saved plans</h2>
        {plans.length === 0 ? (
          <div className="empty-panel">
            <p className="muted">No saved plans yet. Ask FitBot for a plan in chat and press <b>Save plan</b>.</p>
            <button className="btn btn-ghost" onClick={() => navigate("/chat", { state: { prompt: "Give me a beginner 3-day gym workout" } })}>
              <IconChat /> Get a 3-day plan
            </button>
          </div>
        ) : (
          <div className="saved-plans">
            {plans.map((p) => (
              <div key={p.id} className="saved-plan">
                <div className="saved-plan-meta">
                  <span className="muted">Saved {longDate(p.created_at.slice(0, 10))}</span>
                  <button className="link-btn danger" onClick={() => removePlan(p.id)}>Remove</button>
                </div>
                <WorkoutPlan plan={p.plan} onLogged={refresh} />
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="section-title">Recent activity</h2>
        {logs.length === 0 ? (
          <p className="muted">Nothing logged yet. Use the form above, or press <b>Log … as done</b> on a saved plan.</p>
        ) : (
          <div className="log-days">
            {Object.entries(byDay).map(([day, items]) => (
              <div key={day} className="log-day">
                <h3>{longDate(day)}</h3>
                <ul>
                  {items.map((w) => (
                    <li key={w.id} className="log-row">
                      <div>
                        <strong>{w.exercise}</strong>
                        <span className="muted">{[dose(w), w.notes].filter(Boolean).join(" · ")}</span>
                      </div>
                      <button className="icon-btn" onClick={() => removeLog(w.id)} aria-label={`Delete ${w.exercise} entry`}>
                        <IconTrash width={15} height={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
