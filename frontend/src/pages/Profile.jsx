import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const EQUIPMENT = ["none", "dumbbells", "resistance bands", "kettlebells", "barbell", "full gym"];
const empty = { age: "", height_cm: "", weight_kg: "", fitness_level: "", goal: "", dietary_preference: "", equipment: [], location: "" };

export default function Profile() {
  const { refresh } = useAuth();
  const [params] = useSearchParams();
  const [form, setForm] = useState(empty);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.getProfile().then((p) => setForm({ ...empty, ...Object.fromEntries(Object.entries(p).map(([k, v]) => [k, v ?? (k === "equipment" ? [] : "")])) }));
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleEq = (eq) => setForm((f) => ({ ...f, equipment: f.equipment.includes(eq) ? f.equipment.filter((x) => x !== eq) : [...f.equipment, eq] }));

  async function save(e) {
    e.preventDefault();
    setStatus("");
    setError("");
    const num = (v) => (v === "" || v === null ? null : Number(v));
    const body = {
      age: num(form.age), height_cm: num(form.height_cm), weight_kg: num(form.weight_kg),
      fitness_level: form.fitness_level || null, goal: form.goal || null,
      dietary_preference: form.dietary_preference || null, equipment: form.equipment, location: form.location || null,
    };
    try {
      await api.updateProfile(body);
      await refresh();
      setStatus("Profile saved. FitBot will use it to personalise suggestions.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page narrow">
      <h1 className="page-title">Your profile</h1>
      {params.get("welcome") && <div className="notice">Welcome! Tell FitBot a little about you - every field is optional.</div>}
      <p className="muted">Used only for general personalisation (e.g. beginner-friendly exercises, home vs gym plans). FitBot does not give medical advice based on your profile.</p>
      <form className="form profile-form" onSubmit={save}>
        <div className="grid-3">
          <label>Age<input type="number" min={13} max={100} value={form.age} onChange={set("age")} /></label>
          <label>Height (cm)<input type="number" min={100} max={250} step="0.1" value={form.height_cm} onChange={set("height_cm")} /></label>
          <label>Weight (kg)<input type="number" min={30} max={300} step="0.1" value={form.weight_kg} onChange={set("weight_kg")} /></label>
        </div>
        <div className="grid-2">
          <label>Fitness level
            <select value={form.fitness_level} onChange={set("fitness_level")}>
              <option value="">Not set</option><option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
            </select>
          </label>
          <label>Goal
            <select value={form.goal} onChange={set("goal")}>
              <option value="">Not set</option><option value="weight_loss">Weight loss</option>
              <option value="muscle_gain">Muscle gain</option><option value="strength">Strength</option>
              <option value="endurance">Endurance</option><option value="general_fitness">General fitness</option>
            </select>
          </label>
          <label>Dietary preference
            <select value={form.dietary_preference} onChange={set("dietary_preference")}>
              <option value="">Not set</option><option value="none">No preference</option>
              <option value="vegetarian">Vegetarian</option><option value="vegan">Vegan</option>
              <option value="non_vegetarian">Non-vegetarian</option>
            </select>
          </label>
          <label>Workout location
            <select value={form.location} onChange={set("location")}>
              <option value="">Not set</option><option value="home">Home</option><option value="gym">Gym</option>
              <option value="outdoors">Outdoors</option><option value="mixed">Mixed</option>
            </select>
          </label>
        </div>
        <fieldset>
          <legend>Available equipment</legend>
          <div className="chips">
            {EQUIPMENT.map((eq) => (
              <button type="button" key={eq} className={`chip chip-toggle ${form.equipment.includes(eq) ? "on" : ""}`}
                      aria-pressed={form.equipment.includes(eq)} onClick={() => toggleEq(eq)}>{eq}</button>
            ))}
          </div>
        </fieldset>
        {error && <div className="form-error" role="alert">{error}</div>}
        {status && <div className="form-ok" role="status">{status}</div>}
        <button className="btn btn-primary">Save profile</button>
      </form>
    </div>
  );
}
