import { useState } from "react";
import { Link } from "react-router-dom";

const LEVEL_CLASS = { Beginner: "lvl-beg", Intermediate: "lvl-int", Advanced: "lvl-adv" };

// Credit line for a Wikimedia Commons photo: author, licence (linked) and source page.
export function PhotoCredit({ photo }) {
  if (!photo) return null;
  return (
    <span className="photo-credit">
      Photo: {photo.author},{" "}
      {photo.license_url ? <a href={photo.license_url} target="_blank" rel="noreferrer">{photo.license}</a> : photo.license},{" "}
      <a href={photo.source} target="_blank" rel="noreferrer">Wikimedia Commons</a>
    </span>
  );
}

// Real photo of the pose. Like the exercise cards, a second photo (another view) shows on hover.
export default function YogaCard({ pose, compact = false }) {
  const [frame, setFrame] = useState(0);
  const [broken, setBroken] = useState(false);
  const urls = pose.image_urls?.length ? pose.image_urls : [pose.image].filter(Boolean);
  const thumbs = urls.map((u) => u.replace("/yoga/photos/", "/yoga/photos/thumb/"));
  const tags = (pose.category || []).slice(0, 3);
  return (
    <article className={`ex-card yoga-card ${compact ? "compact" : ""}`}>
      <div className="ex-media yoga-card-media" onMouseEnter={() => setFrame(1)} onMouseLeave={() => setFrame(0)}>
        {thumbs.length && !broken ? (
          <img src={thumbs[Math.min(frame, thumbs.length - 1)]} alt={`${pose.name} demonstrated by a person`}
               loading="lazy" decoding="async" onError={() => setBroken(true)} />
        ) : (
          <div className="ex-noimg">Image unavailable</div>
        )}
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
