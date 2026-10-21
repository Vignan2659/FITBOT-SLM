import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import YogaCard, { PhotoCredit } from "../components/YogaCard.jsx";
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
  const [shown, setShown] = useState(0);

  useEffect(() => {
    setPose(null);
    setError("");
    setShown(0);
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
        <figure className="pose-photo">
          <img src={pose.photos[shown]?.url || pose.image} alt={`${pose.name} demonstrated by a person`} decoding="async" />
          <figcaption><PhotoCredit photo={pose.photos[shown]} /></figcaption>
          {pose.photos.length > 1 && (
            <div className="photo-thumbs" role="tablist" aria-label="Photos of this pose">
              {pose.photos.map((ph, i) => (
                <button key={ph.url} role="tab" aria-selected={i === shown} className={i === shown ? "on" : ""}
                        onClick={() => setShown(i)} aria-label={`Photo ${i + 1}`}>
                  <img src={ph.url.replace("/yoga/photos/", "/yoga/photos/thumb/")} alt="" loading="lazy" decoding="async" />
                </button>
              ))}
            </div>
          )}
        </figure>
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

      {pose.related_poses?.length > 0 && (
        <section>
          <h2 className="section-title">Related poses</h2>
          <div className="card-grid">{pose.related_poses.map((p) => <YogaCard key={p.slug} pose={p} compact />)}</div>
        </section>
      )}
      <p className="img-credit">Photos from Wikimedia Commons, used under their free licences (credited on each photo).</p>
    </div>
  );
}
