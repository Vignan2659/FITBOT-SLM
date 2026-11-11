import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import ExerciseCard from "../components/ExerciseCard.jsx";
import YogaCard from "../components/YogaCard.jsx";
import BandCard from "../components/BandCard.jsx";
import { IconCalendar, IconChat, IconDrop, IconDumbbell, IconFlame, IconLeaf, IconMoon } from "../components/Icons.jsx";

const QUICK = [
  { icon: IconDumbbell, label: "Chest exercises", prompt: "What exercises can I do for chest?" },
  { icon: IconCalendar, label: "3-day gym plan", prompt: "Give me a beginner 3-day gym workout" },
  { icon: IconFlame, label: "Lose weight", prompt: "I want to lose weight." },
  { icon: IconLeaf, label: "Post-workout food", prompt: "What should I eat after working out?" },
  { icon: IconDrop, label: "Hydration", prompt: "How much water should I drink a day?" },
  { icon: IconMoon, label: "Sleep & recovery", prompt: "How much should I sleep?" },
];
const GROUPS = ["chest", "back", "shoulders", "legs", "arms", "core", "cardio", "stretching"];
// yoga poses shown on the dashboard for each fitness level
const YOGA_PICKS = {
  beginner: ["downward-dog", "warrior-ii", "tree-pose", "childs-pose"],
  intermediate: ["triangle-pose", "boat-pose", "camel-pose", "three-legged-dog"],
  advanced: ["crow-pose", "wheel-pose", "wild-thing", "reverse-plank"],
};
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const LABEL = { weight_loss: "Weight loss", muscle_gain: "Muscle gain", strength: "Strength", endurance: "Endurance", general_fitness: "General fitness" };

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { conversations } = useOutletContext();
  const [group, setGroup] = useState("chest");
  const [exercises, setExercises] = useState([]);
  const [health, setHealth] = useState(null);
  const [yoga, setYoga] = useState([]);
  const [band, setBand] = useState(null);
  const profile = user?.profile || {};
  const level = profile.fitness_level || "";
  const [mine, setMine] = useState(true);       // show exercises picked for the person's level

  useEffect(() => {
    // with a level, the server puts that level's exercises first and leaves out anything above it
    const params = { muscle_group: group, ...(level && mine ? { level } : {}) };
    api.exercises(params).then((r) => setExercises(r.exercises)).catch(() => setExercises([]));
  }, [group, level, mine]);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);
  useEffect(() => {
    api.yogaPoses({ kind: "pose" })
      .then((r) => setYoga((YOGA_PICKS[level] || YOGA_PICKS.beginner).map((s) => r.poses.find((p) => p.slug === s)).filter(Boolean)))
      .catch(() => setYoga([]));
  }, [level]);

  useEffect(() => {
    api.bandSummary().then(setBand).catch(() => setBand(null));
  }, []);

  const start = (prompt) => navigate("/chat", { state: { prompt } });
  const slm = health?.engine?.slm;

  return (
    <div className="page">
      <section className="hero-card">
        <div>
          <h1>Hi {user?.name?.split(" ")[0]} 👋</h1>
          <p>What are we working on today?</p>
          <div className="profile-pills">
            <span className="pill">{profile.fitness_level ? `Level: ${profile.fitness_level}` : "Level not set"}</span>
            <span className="pill">{profile.goal ? `Goal: ${LABEL[profile.goal]}` : "Goal not set"}</span>
            {profile.equipment?.length > 0 && <span className="pill">Equipment: {profile.equipment.join(", ")}</span>}
            <Link to="/profile" className="pill pill-link">Edit profile</Link>
          </div>
        </div>
        <button className="btn btn-light" onClick={() => navigate("/chat")}><IconChat /> New chat</button>
      </section>

      <section>
        <h2 className="section-title">Quick start</h2>
        <div className="quick-grid">
          {QUICK.map(({ icon: Icon, label, prompt }) => (
            <button key={label} className="quick" onClick={() => start(prompt)}>
              <span className="quick-icon"><Icon /></span>
              <span><strong>{label}</strong><small>{prompt}</small></span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <div className="section-row">
          <h2 className="section-title">Your band</h2>
          <div className="seg">
            <button onClick={() => navigate("/bands")}>{band?.connected ? "Open Bands" : "Connect a band"}</button>
            {band?.connected && <button onClick={() => start("How did I do today? Look at my steps, sleep and stress.")}>Ask FitBot</button>}
          </div>
        </div>
        {band?.latest ? (
          <BandCard band={{ ...band.latest, is_today: band.latest.day === band.today }} title="Latest" />
        ) : (
          <p className="muted small level-tip">Apple Watch, Samsung, Google or Fitbit, Huawei, OnePlus, Noise, WHOOP and others: import your steps, heart rate, sleep and stress on the Bands page.</p>
        )}
      </section>

      <section className="stats">
        <div className="stat"><span>Conversations</span><strong>{conversations.length}</strong></div>
        <div className="stat"><span>Exercise library</span><strong>{health?.database?.exercises ?? "—"}</strong></div>
        <div className="stat"><span>USDA foods</span><strong>{health?.database?.foods ?? "—"}</strong></div>
        <div className="stat">
          <span>Language model</span>
          <strong className="stat-sm">{slm ? (slm.fine_tuned ? "FitBot (fine-tuned)" : "Base model") : "—"}</strong>
          {slm && <small>{slm.params_m}M params · {slm.device}</small>}
        </div>
      </section>

      <section>
        <div className="section-row">
          <h2 className="section-title">Exercise explorer</h2>
          {level && (
            <div className="seg level-seg" role="group" aria-label="Exercise level">
              <button className={mine ? "active" : ""} aria-pressed={mine} onClick={() => setMine(true)}>For my level ({cap(level)})</button>
              <button className={!mine ? "active" : ""} aria-pressed={!mine} onClick={() => setMine(false)}>All levels</button>
            </div>
          )}
          <div className="seg" role="tablist">
            {GROUPS.map((g) => (
              <button key={g} role="tab" aria-selected={g === group} className={g === group ? "active" : ""} onClick={() => setGroup(g)}>{g}</button>
            ))}
          </div>
        </div>
        {!level && <p className="muted small level-tip">Set your fitness level in <Link to="/profile">your profile</Link> to see exercises picked for it.</p>}
        <div className="card-grid">
          {exercises.slice(0, 8).map((e) => <ExerciseCard key={e.slug} exercise={e} mine={Boolean(level) && e.difficulty === cap(level)} />)}
        </div>
      </section>

      <section>
        <div className="section-row">
          <h2 className="section-title">Yoga</h2>
          <div className="seg">
            <button onClick={() => navigate("/yoga")}>All poses</button>
            <button onClick={() => navigate("/yoga?tab=routine")}>Build a routine</button>
            <button onClick={() => start(`Give me a 15 minute ${level || "beginner"} yoga routine`)}>Ask FitBot</button>
          </div>
        </div>
        <div className="card-grid">{yoga.map((p) => <YogaCard key={p.slug} pose={p} compact mine={Boolean(level) && p.difficulty === cap(level)} />)}</div>
      </section>

      {conversations.length > 0 && (
        <section>
          <h2 className="section-title">Recent conversations</h2>
          <ul className="recent">
            {conversations.slice(0, 5).map((c) => (
              <li key={c.id}><Link to={`/chat/${c.id}`}><strong>{c.title}</strong><span>{c.last_message}</span></Link></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
