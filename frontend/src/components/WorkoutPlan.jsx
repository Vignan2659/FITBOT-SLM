import { useState } from "react";

export default function WorkoutPlan({ plan }) {
  const [day, setDay] = useState(0);
  if (!plan?.days?.length) return null;
  const current = plan.days[Math.min(day, plan.days.length - 1)];

  return (
    <section className="plan">
      <header className="plan-head">
        <div>
          <h4>{plan.title}</h4>
          <p>{[plan.level, plan.split, plan.equipment].filter(Boolean).join(" · ")}</p>
        </div>
      </header>
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
