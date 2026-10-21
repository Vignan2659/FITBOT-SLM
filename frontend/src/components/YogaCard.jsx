import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const LEVEL_CLASS = { Beginner: "lvl-beg", Intermediate: "lvl-int", Advanced: "lvl-adv" };

// true when the visitor asked the system for less motion: show the final still instead of the animated figure
export function useReducedMotion() {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduced, setReduced] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.(query).matches);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return undefined;
    const on = () => setReduced(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return reduced;
}

// The motion figure: animated SVG (start -> transition -> final) loaded lazily like the exercise photos.
export function YogaMotion({ pose, className = "" }) {
  const reduced = useReducedMotion();
  const [broken, setBroken] = useState(false);
  const src = reduced ? pose.image : pose.motion_image;
  return (
    <div className={`yoga-media ${className}`}>
      {src && !broken ? (
        <img src={src} alt={`${pose.name}: how the pose moves from start to final position`} loading="lazy"
             decoding="async" width="320" height="240" onError={() => setBroken(true)} />
      ) : (
        <div className="ex-noimg">Visual unavailable</div>
      )}
    </div>
  );
}

export default function YogaCard({ pose, compact = false }) {
  const tags = (pose.category || []).slice(0, 3);
  return (
    <article className={`ex-card yoga-card ${compact ? "compact" : ""}`}>
      <div className="ex-media yoga-card-media">
        <YogaMotion pose={pose} />
        <span className={`badge ${LEVEL_CLASS[pose.difficulty] || ""}`}>{pose.difficulty}</span>
        {pose.sides && <span className="badge badge-right">Both sides</span>}
      </div>
      <div className="ex-body">
        <h4 className="ex-name">{pose.name}</h4>
        {pose.sanskrit && <p className="yoga-sanskrit">{pose.sanskrit}</p>}
        {tags.length > 0 && <p className="yoga-tags">{tags.join(" • ")}</p>}
        {!compact && pose.duration && <p className="ex-desc">Hold: {pose.duration}</p>}
        <Link className="btn btn-ghost btn-sm yoga-view" to={`/yoga/${pose.slug}`}>View pose</Link>
      </div>
    </article>
  );
}
