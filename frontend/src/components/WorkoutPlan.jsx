import { useState } from "react";
import { api, localDate } from "../api/client.js";
import { IconBookmark, IconCheck } from "./Icons.jsx";

// One log entry per exercise of a plan day; the plan's dose (often a range such as "2-3 x 10-12")
// is kept as a note rather than guessing exact numbers.
export function planDayEntries(day, date = localDate()) {
  return day.exercises.map((e) => ({ day: date, exercise: e.name, notes: `${day.day}: ${e.sets} × ${e.reps}`.slice(0, 200) }));
}

// saveable: show "Save plan" (chat answers). onLogged: show "Log this day" (My workouts) and call it afterwards.
export default function WorkoutPlan({ plan, saveable = false, onLogged }) {
  const [day, setDay] = useState(0);
  const [saved, setSaved] = useState(false);
  const [logged, setLogged] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!plan?.days?.length) return null;
  const dayIndex = Math.min(day, plan.days.length - 1);
  const current = plan.days[dayIndex];

  async function run(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const save = () => run(async () => { await api.savePlan(plan); setSaved(true); });
  const logDay = () => run(async () => {
    await api.logWorkouts(planDayEntries(current));
    setLogged((l) => ({ ...l, [dayIndex]: true }));
    onLogged?.();
  });

  return (
    <section className="plan">
      <header className="plan-head">
        <div>
          <h4>{plan.title}</h4>
          <p>{[plan.level, plan.split, plan.equipment].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="plan-actions">
          {saveable && (
            <button className="btn btn-ghost btn-sm" onClick={save} disabled={busy || saved}>
              {saved ? <><IconCheck width={15} height={15} /> Saved to My workouts</> : <><IconBookmark width={15} height={15} /> Save plan</>}
            </button>
          )}
          {onLogged && (
            <button className="btn btn-primary btn-sm" onClick={logDay} disabled={busy || logged[dayIndex]}>
              {logged[dayIndex] ? <><IconCheck width={15} height={15} /> Logged today</> : <><IconCheck width={15} height={15} /> Log {current.day} as done</>}
            </button>
          )}
        </div>
      </header>
      {error && <div className="form-error" role="alert">{error}</div>}
      {plan.days.length > 1 && (
        <div className="plan-tabs" role="tablist">
          {plan.days.map((d, i) => (
            <button key={i} role="tab" aria-selected={i === day} className={i === day ? "active" : ""} onClick={() => setDay(i)}>
              {d.day}
            </button>
          ))}
        </div>
      )}
      <div className="plan-day">
        <div className="plan-focus">{current.focus}</div>
        <ol className="plan-list">
          {current.exercises.map((e, i) => (
            <li key={`${e.name}-${i}`} className="plan-row">
              {e.image_url ? <img src={e.image_url} alt={e.name} loading="lazy" /> : <div className="plan-noimg" />}
              <div className="plan-ex">
                <strong>{e.name}</strong>
                <span>{(e.target_muscles || []).join(", ")}</span>
              </div>
              <div className="plan-dose">
                <b>{e.sets} × {e.reps}</b>
                <span>Rest {e.rest}</span>
              </div>
              <span className={`badge-sm lvl-${(e.difficulty || "").slice(0, 3).toLowerCase()}`}>{e.difficulty}</span>
            </li>
          ))}
        </ol>
      </div>
      {plan.notes?.length > 0 && (
        <ul className="plan-notes">{plan.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      )}
    </section>
  );
}
