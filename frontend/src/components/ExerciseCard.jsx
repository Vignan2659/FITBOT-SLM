import { useState } from "react";
import { IconChevron } from "./Icons.jsx";
import useMotion from "../hooks/useMotion.js";

const LEVEL_CLASS = { Beginner: "lvl-beg", Intermediate: "lvl-int", Advanced: "lvl-adv" };

export default function ExerciseCard({ exercise, mine = false }) {
  const [open, setOpen] = useState(false);
  const [broken, setBroken] = useState(false);
  const images = exercise.image_urls?.length ? exercise.image_urls : [exercise.image_url].filter(Boolean);
  const motion = useMotion(images, { rest: 0 });    // start and finish photos play as a motion on hover
  const muscles = [...(exercise.target_muscles || []), ...(exercise.secondary_muscles || []).slice(0, 2)];

  return (
    <article className="ex-card">
      <div className={`ex-media ${motion.playing ? "playing" : ""}`} {...motion.bind}>
        {images.length && !broken ? (
          <img src={images[motion.index]} alt={`${exercise.name} demonstration`} loading="lazy"
               onError={() => setBroken(true)} />
        ) : (
          <div className="ex-noimg">Image unavailable</div>
        )}
        <span className={`badge ${LEVEL_CLASS[exercise.difficulty] || ""}`}>{exercise.difficulty}</span>
        {mine && <span className="badge badge-right badge-mine">Your level</span>}
        {images.length > 1 && (
          <span className="motion-hint" aria-hidden="true">{motion.playing ? `${motion.index + 1} / ${images.length}` : "▶ Motion"}</span>
        )}
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
