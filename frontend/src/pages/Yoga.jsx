import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import YogaCard from "../components/YogaCard.jsx";
import YogaRoutine from "../components/YogaRoutine.jsx";
import { IconChat, IconSearch } from "../components/Icons.jsx";

const TABS = [
  { id: "poses", label: "Yoga poses" },
  { id: "categories", label: "Categories" },
  { id: "goals", label: "Goals" },
  { id: "routine", label: "Routine builder" },
];
const LEVELS = ["Beginner", "Intermediate", "Advanced"];
// the goal and body area filters shown as chips (the API supports a few more)
const GOAL_CHIPS = ["flexibility", "strength", "weight_management", "stress_relief", "relaxation", "mobility", "recovery", "balance"];
const AREA_CHIPS = ["back", "shoulders", "hips", "legs", "core", "full_body"];
const GOAL_TEXT = {
  flexibility: "Lengthen tight hamstrings, hips and shoulders.",
  strength: "Build legs, core and shoulders with bodyweight holds.",
  weight_management: "Dynamic standing poses that raise the heart rate.",
  stress_relief: "Slow poses and breathing that help you settle.",
  relaxation: "Restful floor poses for the evening.",
  mobility: "Move the spine and hips through their range.",
  recovery: "Easy stretches for rest days and after training.",
  balance: "One leg poses that train steadiness and focus.",
  posture: "Open the chest and strengthen the back.",
  core: "Hold strong positions that train the trunk.",
  breathing: "Simple breathing practices.",
  meditation: "Seated and lying practices for attention.",
};
const PAGE = 12;

export default function Yoga() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? params.get("tab") : "poses";
  const [poses, setPoses] = useState([]);
  const [facets, setFacets] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [level, setLevel] = useState(params.get("level") || "");
  const [goal, setGoal] = useState(params.get("goal") || "");
  const [area, setArea] = useState(params.get("area") || "");
  const [category, setCategory] = useState(params.get("category") || "");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    // the whole library is small (summaries only), so it is fetched once and filtered in the browser
    Promise.all([api.yogaPoses(), api.yogaFilters()])
      .then(([p, f]) => { setPoses(p.poses); setFacets(f); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const setTab = (id, extra = {}) => setParams({ tab: id, ...extra });
  const label = (list, value) => list?.find((x) => x.value === value)?.label || value;

  const filtered = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return poses.filter((p) => {
      if (level && p.difficulty !== level) return false;
      if (goal && !p.goals.includes(goal)) return false;
      if (area && !(p.body_areas.includes(area) || (area === "full_body" && p.body_areas.length >= 3))) return false;
      if (category && !p.category.includes(category)) return false;
      if (!words.length) return true;
      const hay = `${p.name} ${p.sanskrit} ${p.category.join(" ")} ${p.target_areas.join(" ")}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  }, [poses, q, level, goal, area, category]);

  useEffect(() => setShown(PAGE), [q, level, goal, area, category]);
  const clear = () => { setQ(""); setLevel(""); setGoal(""); setArea(""); setCategory(""); };
  const active = q || level || goal || area || category;

  return (
    <div className="page">
      <section className="hero-card yoga-hero">
        <div>
          <h1>Yoga</h1>
          <p>{facets ? `${facets.total} poses and practices` : "Poses and practices"} shown by real people, with step
            by step instructions, safety notes and routines built for your goal and time.</p>
        </div>
        <button className="btn btn-light" onClick={() => navigate("/chat", { state: { prompt: "Give me a 15 minute beginner yoga routine" } })}>
          <IconChat /> Ask FitBot
        </button>
      </section>

      <div className="seg yoga-tabs" role="tablist" aria-label="Yoga sections">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""}
                  onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}

      {tab === "poses" && (
        <section className="yoga-browse">
          <div className="yoga-filters">
            <label className="yoga-search">
              <IconSearch width={16} height={16} />
              <input type="search" placeholder="Search poses, Sanskrit names or body areas" value={q}
                     onChange={(e) => setQ(e.target.value)} aria-label="Search yoga poses" />
            </label>
            <div className="filter-row" role="group" aria-label="Difficulty">
              <span className="filter-label">Difficulty</span>
              <div className="chips">
                {LEVELS.map((l) => (
                  <button key={l} className={`chip chip-toggle ${level === l ? "on" : ""}`} aria-pressed={level === l}
                          onClick={() => setLevel(level === l ? "" : l)}>{l}</button>
                ))}
              </div>
            </div>
            <div className="filter-row" role="group" aria-label="Goal">
              <span className="filter-label">Goal</span>
              <div className="chips">
                {GOAL_CHIPS.map((g) => (
                  <button key={g} className={`chip chip-toggle ${goal === g ? "on" : ""}`} aria-pressed={goal === g}
                          onClick={() => setGoal(goal === g ? "" : g)}>{label(facets?.goals, g)}</button>
                ))}
              </div>
            </div>
            <div className="filter-row" role="group" aria-label="Body area">
              <span className="filter-label">Body area</span>
              <div className="chips">
                {AREA_CHIPS.map((a) => (
                  <button key={a} className={`chip chip-toggle ${area === a ? "on" : ""}`} aria-pressed={area === a}
                          onClick={() => setArea(area === a ? "" : a)}>{label(facets?.body_areas, a)}</button>
                ))}
              </div>
            </div>
            <div className="filter-foot">
              <span className="muted">{loading ? "Loading poses..." : `${filtered.length} of ${poses.length} poses`}
                {category && <> · category <b>{category}</b></>}</span>
              {active && <button className="link-btn" onClick={clear}>Clear filters</button>}
            </div>
          </div>
          {!loading && filtered.length === 0 && (
            <div className="empty-panel"><p>No poses match these filters.</p><button className="btn btn-ghost btn-sm" onClick={clear}>Clear filters</button></div>
          )}
          <div className="card-grid yoga-grid">{filtered.slice(0, shown).map((p) => <YogaCard key={p.slug} pose={p} />)}</div>
          {filtered.length > shown && (
            <button className="btn btn-ghost yoga-more" onClick={() => setShown((n) => n + PAGE)}>
              Show more ({filtered.length - shown} left)
            </button>
          )}
        </section>
      )}

      {tab === "categories" && (
        <section className="tile-grid">
          {(facets?.categories || []).map((c) => {
            const count = poses.filter((p) => p.category.includes(c)).length;
            const sample = poses.find((p) => p.category.includes(c));
            return (
              <button key={c} className="yoga-tile" onClick={() => { clear(); setCategory(c); setTab("poses", { category: c }); }}>
                {sample && <img src={sample.thumb || sample.image} alt="" loading="lazy" decoding="async" width="96" height="72" />}
                <span><strong>{c}</strong><small>{count} poses</small></span>
              </button>
            );
          })}
        </section>
      )}

      {tab === "goals" && (
        <section className="tile-grid goal-grid">
          {(facets?.goals || []).map((g) => (
            <div key={g.value} className="yoga-tile goal-tile">
              <span><strong>{g.label}</strong><small>{GOAL_TEXT[g.value]}</small><small>{g.count} poses</small></span>
              <div className="goal-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => { clear(); setGoal(g.value); setTab("poses", { goal: g.value }); }}>See poses</button>
                <button className="btn btn-primary btn-sm" onClick={() => setTab("routine", { goal: g.value })}>Build routine</button>
              </div>
            </div>
          ))}
        </section>
      )}

      {tab === "routine" && <RoutineBuilder initialGoal={params.get("goal") || ""} goals={facets?.goals || []} areas={facets?.body_areas || []} />}

      <p className="disclaimer yoga-disclaimer">Yoga in FitBot is general fitness and wellness information, not a treatment for any
        medical condition. Move within a comfortable range and check with a doctor or physiotherapist if you have pain,
        an injury, a health condition or are pregnant.</p>
    </div>
  );
}

function RoutineBuilder({ initialGoal, goals, areas }) {
  const [form, setForm] = useState({ minutes: "15", level: "Beginner", goal: initialGoal, area: "", time_of_day: "" });
  const [routine, setRoutine] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function build(e) {
    e?.preventDefault();
    setBusy(true);
    setError("");
    try {
      const params = Object.fromEntries(Object.entries(form).filter(([, v]) => v));
      setRoutine(await api.yogaRoutine(params));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { build(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="routine-builder">
      <form className="form routine-form panel" onSubmit={build}>
        <label>Time
          <select value={form.minutes} onChange={set("minutes")}>
            {[5, 10, 15, 20, 30, 45, 60].map((m) => <option key={m} value={m}>{m} minutes</option>)}
          </select>
        </label>
        <label>Experience
          <select value={form.level} onChange={set("level")}>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select>
        </label>
        <label>Goal
          <select value={form.goal} onChange={set("goal")}>
            <option value="">Balanced practice</option>
            {goals.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
          </select>
        </label>
        <label>Focus area
          <select value={form.area} onChange={set("area")}>
            <option value="">Whole body</option>
            {areas.filter((a) => a.value !== "full_body").map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </label>
        <label>Time of day
          <select value={form.time_of_day} onChange={set("time_of_day")}>
            <option value="">Any time</option><option value="morning">Morning</option><option value="evening">Evening</option>
          </select>
        </label>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Building..." : "Build routine"}</button>
      </form>
      {error && <div className="form-error" role="alert">{error}</div>}
      {routine && <YogaRoutine routine={routine} />}
    </section>
  );
}
