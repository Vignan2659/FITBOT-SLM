import { useState } from "react";
import { Link } from "react-router-dom";
import { api, localDate } from "../api/client.js";
import { IconCheck, IconClock } from "./Icons.jsx";

// A timed yoga routine (from the chat or the routine builder). Every step links to its pose page.
export default function YogaRoutine({ routine, loggable = true }) {
  const [logged, setLogged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!routine?.steps?.length) return null;

  async function logSession() {
    setBusy(true);
    setError("");
    try {
      await api.logWorkouts([{ day: localDate(), exercise: routine.title.slice(0, 80), minutes: Math.round(routine.minutes),
                               notes: routine.steps.map((s) => s.name).join(", ").slice(0, 200) }]);
      setLogged(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="plan yoga-routine">
      <header className="plan-head">
        <div>
          <h4>{routine.title}</h4>
          <p><IconClock width={13} height={13} /> {routine.minutes} min · {routine.steps.length} poses · {routine.level}</p>
        </div>
        {loggable && (
          <div className="plan-actions">
            <button className="btn btn-ghost btn-sm" onClick={logSession} disabled={busy || logged}>
              <IconCheck width={15} height={15} /> {logged ? "Logged in My workouts" : "Log as done"}
            </button>
          </div>
        )}
      </header>
      {error && <div className="form-error" role="alert">{error}</div>}
      <ol className="plan-list">
        {routine.steps.map((s) => (
          <li key={s.slug} className="plan-row yoga-step">
            <img src={s.image} alt="" loading="lazy" decoding="async" width="64" height="48" />
            <div className="plan-ex">
              <Link to={`/yoga/${s.slug}`}><strong>{s.order}. {s.name}</strong></Link>
              <span>{s.phase} · {s.cue}</span>
            </div>
            <div className="plan-dose"><b>{s.duration}</b><span>{s.difficulty}</span></div>
          </li>
        ))}
      </ol>
      {routine.notes?.length > 0 && <ul className="plan-notes">{routine.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </section>
  );
}
