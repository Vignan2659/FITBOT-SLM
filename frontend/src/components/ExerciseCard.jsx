import { useState } from "react";
import { IconChevron } from "./Icons.jsx";

const LEVEL_CLASS = { Beginner: "lvl-beg", Intermediate: "lvl-int", Advanced: "lvl-adv" };

export default function ExerciseCard({ exercise }) {
  const [open, setOpen] = useState(false);
  const [frame, setFrame] = useState(0);
  const [broken, setBroken] = useState(false);
  const images = exercise.image_urls?.length ? exercise.image_urls : [exercise.image_url].filter(Boolean);
  const muscles = [...(exercise.target_muscles || []), ...(exercise.secondary_muscles || []).slice(0, 2)];

  return (
    <article className="ex-card">
      <div className="ex-media" onMouseEnter={() => setFrame(1)} onMouseLeave={() => setFrame(0)}>
        {images.length && !broken ? (
          <img src={images[Math.min(frame, images.length - 1)]} alt={`${exercise.name} demonstration`} loading="lazy"
               onError={() => setBroken(true)} />
        ) : (
          <div className="ex-noimg">Image unavailable</div>
        )}
        <span className={`badge ${LEVEL_CLASS[exercise.difficulty] || ""}`}>{exercise.difficulty}</span>
      </div>
      <div className="ex-body">
        <h4 className="ex-name">{exercise.name}</h4>
        <dl className="ex-meta">
          <dt>Target</dt>
          <dd>{muscles.join(" • ")}</dd>
          <dt>Equipment</dt>
          <dd>{exercise.equipment}</dd>
        </dl>
        {exercise.description && <p className="ex-desc">{exercise.description}</p>}
        <button className="link-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? "Hide instructions" : "View instructions"}
          <IconChevron className={open ? "rot" : ""} width={16} height={16} />
        </button>
        {open && (
          <div className="ex-instructions">
            <ol>{(exercise.instructions || []).map((s, i) => <li key={i}>{s}</li>)}</ol>
            {exercise.safety_tips?.length > 0 && (
              <p className="safety-tip"><strong>Safety tip:</strong> {exercise.safety_tips[0]}</p>
            )}
            <p className="img-credit">Image: free-exercise-db (public domain)</p>
          </div>
        )}
      </div>
    </article>
  );
}
