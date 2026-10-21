import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import YogaCard, { YogaMotion } from "../components/YogaCard.jsx";
import { IconChat, IconChevron, IconShield } from "../components/Icons.jsx";

const LEVEL_CLASS = { Beginner: "lvl-beg", Intermediate: "lvl-int", Advanced: "lvl-adv" };

function List({ title, items, ordered = false, className = "" }) {
  if (!items?.length) return null;
  const Tag = ordered ? "ol" : "ul";
  return (
    <section className={`panel pose-block ${className}`}>
      <h3>{title}</h3>
      <Tag>{items.map((x) => <li key={x}>{x}</li>)}</Tag>
    </section>
  );
}

export default function YogaPose() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [pose, setPose] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setPose(null);
    setError("");
    api.yogaPose(slug).then(setPose).catch((e) => setError(e.message));
    document.querySelector(".main .page")?.scrollTo?.(0, 0);
  }, [slug]);

  if (error) {
    return (
      <div className="page narrow">
        <div className="form-error" role="alert">{error}</div>
        <Link to="/yoga">Back to Yoga</Link>
      </div>
    );
  }
  if (!pose) return <div className="splash"><div className="spinner" aria-label="Loading" /></div>;

  const ask = () => navigate("/chat", { state: { prompt: `Explain how to perform ${pose.name}` } });
  return (
    <div className="page pose-page">
      <nav className="crumbs"><Link to="/yoga">Yoga</Link> <IconChevron width={14} height={14} className="rot-90" /> {pose.name}</nav>

      <section className="pose-hero">
        <YogaMotion pose={pose} className="pose-motion" />
        <div className="pose-head">
          <span className={`badge-sm ${LEVEL_CLASS[pose.difficulty]}`}>{pose.difficulty}</span>
          <h1 className="page-title">{pose.name}</h1>
          <p className="yoga-sanskrit">{[pose.sanskrit, ...pose.alternative_names.filter((n) => n !== pose.sanskrit)].slice(0, 3).join(" · ")}</p>
          <div className="chips">{pose.category.map((c) => <span key={c} className="chip">{c}</span>)}</div>
          <dl className="pose-facts">
            <dt>Hold</dt><dd>{pose.duration}</dd>
            <dt>Repetitions</dt><dd>{pose.recommended_repetitions}</dd>
            <dt>Targets</dt><dd>{pose.target_areas.join(", ")}</dd>
            <dt>Equipment</dt><dd>{pose.equipment}</dd>
          </dl>
          <button className="btn btn-primary btn-sm" onClick={ask}><IconChat width={16} height={16} /> Ask FitBot about this pose</button>
        </div>
      </section>

      <section className="panel">
        <h3>How it moves</h3>
        <ol className="frame-strip">
          {pose.frames.map((f, i) => (
            <li key={f}>
              <img src={f} alt={`${pose.name}, ${pose.frame_labels[i]?.toLowerCase()} position`} loading="lazy" decoding="async" width="320" height="240" />
              <span>{i + 1}. {pose.frame_labels[i]}</span>
            </li>
          ))}
        </ol>
      </section>

      <div className="pose-grid">
        <List title="Step by step" items={pose.instructions} ordered className="span-2" />
        <section className="panel pose-block">
          <h3>Breathing</h3>
          <p>{pose.breathing}</p>
          <h3>Benefits</h3>
          <ul>{pose.benefits.map((b) => <li key={b}>{b}</li>)}</ul>
        </section>
        <section className="panel pose-block">
          <h3>Make it easier</h3>
          <p>{pose.beginner_modification}</p>
          <h3>Make it harder</h3>
          <p>{pose.advanced_variation}</p>
        </section>
        <List title="Common mistakes" items={pose.common_mistakes} />
        <section className="panel pose-block pose-safety">
          <h3><IconShield width={16} height={16} /> Safety</h3>
          <ul>{pose.safety_tips.map((s) => <li key={s}>{s}</li>)}</ul>
          <h4>Skip or modify this pose with</h4>
          <ul>{pose.contraindications.map((s) => <li key={s}>{s}</li>)}</ul>
          <p className="muted small">General wellness information, not medical advice. Check with a doctor or physiotherapist
            if you have pain, an injury or a health condition.</p>
        </section>
      </div>

      {pose.photo_reference && (
        <section className="panel">
          <h3>Photo reference</h3>
          <p className="muted small">The same movement in FitBot's exercise library: <b>{pose.photo_reference.exercise}</b></p>
          <div className="photo-ref">
            {pose.photo_reference.image_urls.slice(0, 2).map((u, i) => (
              <img key={u} src={u} alt={`${pose.photo_reference.exercise}, photo ${i + 1}`} loading="lazy" decoding="async" />
            ))}
          </div>
          <p className="img-credit">Photos: free-exercise-db (public domain)</p>
        </section>
      )}

      {pose.related_poses?.length > 0 && (
        <section>
          <h2 className="section-title">Related poses</h2>
          <div className="card-grid">{pose.related_poses.map((p) => <YogaCard key={p.slug} pose={p} compact />)}</div>
        </section>
      )}
      <p className="img-credit">Motion figure: {pose.image_license}</p>
    </div>
  );
}
