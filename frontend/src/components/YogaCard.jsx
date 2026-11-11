import { useState } from "react";
import { Link } from "react-router-dom";
import useMotion from "../hooks/useMotion.js";

const LEVEL_CLASS = { Beginner: "lvl-beg", Intermediate: "lvl-int", Advanced: "lvl-adv" };
export const toThumb = (url) => url.replace("/yoga/photos/", "/yoga/photos/thumb/");

// Credit line for a pose photo: photographer, licence (linked) and the page the photo comes from.
export function PhotoCredit({ photo }) {
  if (!photo) return null;
  return (
    <span className="photo-credit">
      Photo: {photo.author_url ? <a href={photo.author_url} target="_blank" rel="noreferrer">{photo.author}</a> : photo.author},{" "}
      {photo.license_url ? <a href={photo.license_url} target="_blank" rel="noreferrer">{photo.license}</a> : photo.license},{" "}
      <a href={photo.source} target="_blank" rel="noreferrer">{photo.source_name || "source"}</a>
    </span>
  );
}

// Real photos of the pose. The card rests on the finished pose; with the cursor on the picture it plays the
// photos in order (start position, then the pose) as a short motion, like the exercise cards.
export default function YogaCard({ pose, compact = false, mine = false }) {
  const [broken, setBroken] = useState(false);
  const urls = pose.image_urls?.length ? pose.image_urls : [pose.image].filter(Boolean);
  const frames = urls.map(toThumb);
  const motion = useMotion(frames, { rest: frames.length - 1 });
  const tags = (pose.category || []).slice(0, 3);
  return (
    <article className={`ex-card yoga-card ${compact ? "compact" : ""}`}>
      <div className={`ex-media yoga-card-media ${motion.playing ? "playing" : ""}`} {...motion.bind}>
        {frames.length && !broken ? (
          <img src={frames[motion.index]} alt={`${pose.name} demonstrated by a person`}
               loading="lazy" decoding="async" onError={() => setBroken(true)} />
        ) : (
          <div className="ex-noimg">Image unavailable</div>
        )}
        <span className={`badge ${LEVEL_CLASS[pose.difficulty] || ""}`}>{pose.difficulty}</span>
        {mine && <span className="badge badge-right badge-mine">Your level</span>}
        {frames.length > 1 && (
          <span className="motion-hint" aria-hidden="true">{motion.playing ? `${motion.index + 1} / ${frames.length}` : "▶ Motion"}</span>
        )}
      </div>
      <div className="ex-body">
        <h4 className="ex-name">{pose.name}</h4>
        {pose.sanskrit && <p className="yoga-sanskrit">{pose.sanskrit}</p>}
        {tags.length > 0 && <p className="yoga-tags">{tags.join(" • ")}</p>}
        {!compact && pose.duration && <p className="ex-desc">Hold: {pose.duration}{pose.sides ? " (both sides)" : ""}</p>}
        <Link className="btn btn-ghost btn-sm yoga-view" to={`/yoga/${pose.slug}`}>View pose</Link>
      </div>
    </article>
  );
}
