import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, localDate } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { BRAND_NAMES, bandTiles, dayLabel, fmtInt, fmtSleep } from "../components/BandCard.jsx";
import { IconBluetooth, IconChat, IconHeart, IconTrash, IconUpload, IconWatch } from "../components/Icons.jsx";
import useHeartRate, { bluetoothSupported, sessionStats } from "../hooks/useHeartRate.js";

const CHARTS = [
  { key: "steps", label: "Steps", show: fmtInt },
  { key: "sleep_minutes", label: "Sleep", show: fmtSleep },
  { key: "resting_hr", label: "Resting heart rate", show: (v) => `${Math.round(v)} bpm` },
  { key: "stress", label: "Stress", show: (v) => `${Math.round(v)} / 100` },
  { key: "hrv_ms", label: "HRV", show: (v) => `${Math.round(v)} ms` },
  { key: "active_kcal", label: "Active energy", show: (v) => `${fmtInt(v)} kcal` },
];
const ACTIVITIES = ["Workout", "Strength training", "Yoga", "Running", "Walking", "Cycling", "HIIT"];
const ZONES = [[0.9, "Maximum", "z5"], [0.8, "Hard", "z4"], [0.7, "Moderate", "z3"], [0.6, "Light", "z2"], [0, "Very light", "z1"]];

// Bars for the last days of one metric; days without data stay empty.
function DayChart({ series, metric }) {
  const values = series.map((d) => d[metric.key]);
  const max = Math.max(...values.filter((v) => v != null), 1);
  return (
    <div className="band-chart" role="img" aria-label={`${metric.label} for the last ${series.length} days`}>
      {series.map((d, i) => {
        const v = d[metric.key];
        const date = new Date(`${d.day}T12:00:00`);
        return (
          <div key={d.day} className="band-col" title={v == null ? `${d.day}: no data` : `${d.day}: ${metric.show(v)}`}>
            <div className="band-bar">{v != null && <div style={{ height: `${Math.max(4, (v / max) * 100)}%` }} className={i === series.length - 1 ? "now" : ""} />}</div>
            <span className="band-lbl">{date.getDate()}</span>
          </div>
        );
      })}
    </div>
  );
}

function LiveHeartRate({ age, onSaved }) {
  const hr = useHeartRate();
  const [activity, setActivity] = useState("Workout");
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [, tick] = useState(0);
  const stats = sessionStats(hr.samples);
  const maxHr = age ? 220 - age : 190;
  const zone = hr.bpm ? ZONES.find(([share]) => hr.bpm >= share * maxHr) : null;
  const seconds = hr.startedAt && hr.samples.length ? Math.round((hr.samples[hr.samples.length - 1].t - hr.startedAt.getTime()) / 1000) : 0;

  useEffect(() => {
    if (hr.status !== "live") return undefined;
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [hr.status]);

  async function save() {
    setError("");
    try {
      const r = await api.bandSaveLive({ started_at: `${localDate(hr.startedAt)}T${hr.startedAt.toTimeString().slice(0, 8)}`,
        minutes: Math.max(seconds / 60, 0.1), avg_hr: stats.avg, max_hr: stats.max, activity, device: hr.device });
      setSaved(`Saved: ${r.activity}, ${Math.round(r.minutes)} min, average ${Math.round(r.avg_hr)} bpm.`);
      hr.disconnect();
      hr.reset();
      onSaved();
    } catch (e) {
      setError(e.message);
    }
  }

  const recent = hr.samples.slice(-90);
  const lo = Math.min(...recent.map((s) => s.bpm), 60) - 5;
  const hi = Math.max(...recent.map((s) => s.bpm), 100) + 5;
  const points = recent.map((s, i) => `${(i / Math.max(recent.length - 1, 1)) * 300},${60 - ((s.bpm - lo) / (hi - lo)) * 60}`).join(" ");

  return (
    <section className="panel live-panel">
      <h2 className="section-title"><IconHeart /> Live heart rate</h2>
      <p className="muted small">
        Shows your heart rate during a workout or yoga session, straight from the band over Bluetooth. Turn on heart rate
        broadcast on the band first (WHOOP, Huawei, Garmin, Polar, Amazfit, Fitbit Charge 6 and chest straps have it; Apple Watch does not).
      </p>
      {!bluetoothSupported && <p className="notice">Live heart rate needs Chrome or Edge. This browser has no Bluetooth support.</p>}
      {hr.status !== "live" ? (
        <button className="btn btn-primary" onClick={hr.connect} disabled={!bluetoothSupported || hr.status === "connecting"}>
          <IconBluetooth /> {hr.status === "connecting" ? "Connecting..." : "Connect a band"}
        </button>
      ) : (
        <div className="live-box">
          <div className={`live-bpm ${zone ? zone[2] : ""}`}>
            <strong>{hr.bpm ?? "--"}</strong><span>bpm</span>
            {zone && <em>{zone[1]} zone</em>}
          </div>
          <div className="live-side">
            <div className="live-stats">
              <span>Time <b>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</b></span>
              <span>Average <b>{stats.avg ?? "--"}</b></span>
              <span>Max <b>{stats.max ?? "--"}</b></span>
            </div>
            {recent.length > 1 && <svg className="live-line" viewBox="0 0 300 60" preserveAspectRatio="none" aria-hidden><polyline points={points} /></svg>}
            <div className="live-actions">
              <span className="muted small">{hr.device}</span>
              <select value={activity} onChange={(e) => setActivity(e.target.value)} aria-label="Activity">
                {ACTIVITIES.map((a) => <option key={a}>{a}</option>)}
              </select>
              <button className="btn btn-primary btn-sm" onClick={save} disabled={hr.samples.length < 5}>Save session</button>
              <button className="btn btn-ghost btn-sm" onClick={hr.disconnect}>Disconnect</button>
            </div>
          </div>
        </div>
      )}
      {(hr.error || error) && <p className="form-error">{hr.error || error}</p>}
      {saved && <p className="form-ok">{saved}</p>}
      {zone && <p className="muted small">Zones use a maximum of {maxHr} bpm{age ? " (220 minus your age)" : " (add your age in your profile for your own zones)"}.</p>}
    </section>
  );
}

const EMPTY_DAY = { steps: "", sleep_hours: "", resting_hr: "", avg_hr: "", stress: "", hrv_ms: "", active_kcal: "", distance_km: "" };
const DAY_FIELDS = [["steps", "Steps", 1], ["sleep_hours", "Sleep (hours)", 0.1], ["resting_hr", "Resting heart rate", 1], ["avg_hr", "Average heart rate", 1],
  ["stress", "Stress (0 to 100)", 1], ["hrv_ms", "HRV (ms)", 1], ["active_kcal", "Active kcal", 1], ["distance_km", "Distance (km)", 0.1]];

export default function Bands() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [brands, setBrands] = useState([]);
  const [brand, setBrand] = useState("apple");
  const [summary, setSummary] = useState(null);
  const [metric, setMetric] = useState("steps");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [day, setDay] = useState({ day: localDate(), ...EMPTY_DAY });
  const [dayMsg, setDayMsg] = useState("");
  const fileInput = useRef(null);

  const load = useCallback(() => api.bandSummary().then(setSummary).catch((e) => setError(e.message)), []);
  useEffect(() => {
    api.bandBrands().then((r) => setBrands(r.brands)).catch(() => setBrands([]));
    load();
  }, [load]);

  const current = brands.find((b) => b.id === brand);
  const latest = summary?.latest;
  const tiles = bandTiles(latest);
  const charts = useMemo(() => CHARTS.filter((c) => summary?.series?.some((d) => d[c.key] != null)), [summary]);
  const chart = charts.find((c) => c.key === metric) || charts[0];

  async function importFile(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.bandImport(brand, file));
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveDay(e) {
    e.preventDefault();
    setDayMsg("");
    const n = (v) => (v === "" ? null : Number(v));
    try {
      await api.bandSaveDay({ day: day.day, steps: n(day.steps), sleep_minutes: day.sleep_hours === "" ? null : Number(day.sleep_hours) * 60,
        resting_hr: n(day.resting_hr), avg_hr: n(day.avg_hr), stress: n(day.stress), hrv_ms: n(day.hrv_ms),
        active_kcal: n(day.active_kcal), distance_km: n(day.distance_km) });
      setDay({ day: day.day, ...EMPTY_DAY });
      setDayMsg("Saved.");
      await load();
    } catch (err) {
      setDayMsg(err.message);
    }
  }

  async function removeAll() {
    if (!window.confirm("Delete all your band data from FitBot? This cannot be undone.")) return;
    await api.bandDelete();
    setResult(null);
    await load();
  }

  return (
    <div className="page bands-page">
      <section className="hero-card bands-hero">
        <div>
          <h1><IconWatch width={26} height={26} /> Fitness bands</h1>
          <p>Bring in your steps, heart rate, sleep, stress and workouts from your band or watch. Everything stays on this computer.</p>
        </div>
        {summary?.connected && (
          <button className="btn btn-light" onClick={() => navigate("/chat", { state: { prompt: "How did I do today? Look at my steps, sleep and stress." } })}>
            <IconChat /> Ask FitBot about my day
          </button>
        )}
      </section>

      {summary?.connected && latest && (
        <section>
          <div className="section-row">
            <h2 className="section-title">{dayLabel(latest.day, latest.day === summary.today)}</h2>
            <span className="muted small">{summary.days_with_data} days of data · {summary.sources.map((s) => BRAND_NAMES[s] || s).join(", ")}</span>
          </div>
          <div className="band-tiles big">
            {tiles.map(([key, label, value, note]) => (
              <div key={key} className={`band-tile band-${key}`}><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>
            ))}
          </div>
          {summary.insights.length > 0 && <ul className="band-insights">{summary.insights.map((t) => <li key={t}>{t}</li>)}</ul>}
          <p className="band-note">Wellness numbers, not medical readings. Stress marked "estimated" is worked out from how your resting heart rate and HRV compare with your own last 4 weeks.</p>
        </section>
      )}

      {chart && (
        <section className="panel">
          <div className="section-row">
            <h2 className="section-title">Last {summary.series.length} days</h2>
            <div className="seg" role="tablist">
              {charts.map((c) => <button key={c.key} role="tab" aria-selected={c.key === chart.key} className={c.key === chart.key ? "active" : ""} onClick={() => setMetric(c.key)}>{c.label}</button>)}
            </div>
          </div>
          <DayChart series={summary.series} metric={chart} />
          {summary.week[chart.key] != null && <p className="muted small">7 day average: {chart.show(summary.week[chart.key])}</p>}
        </section>
      )}

      {summary?.workouts?.length > 0 && (
        <section className="panel">
          <h2 className="section-title">Workouts from your band</h2>
          <ul className="band-workouts">
            {summary.workouts.slice(0, 8).map((x) => (
              <li key={x.id}>
                <strong>{x.activity}</strong>
                <span className="muted">{new Date(x.start).toLocaleDateString(undefined, { day: "numeric", month: "short" })} · {Math.round(x.minutes)} min
                  {x.avg_hr ? ` · average ${Math.round(x.avg_hr)} bpm` : ""}{x.kcal ? ` · ${Math.round(x.kcal)} kcal` : ""}{x.distance_km ? ` · ${x.distance_km.toFixed(1)} km` : ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="wk-grid">
        <section className="panel">
          <h2 className="section-title"><IconUpload /> {summary?.connected ? "Update your data" : "Connect your band"}</h2>
          <p className="muted small">A band keeps its data in its phone app, so FitBot reads the export file of that app. Pick your band:</p>
          <div className="seg brand-seg" role="tablist" aria-label="Band brand">
            {brands.map((b) => <button key={b.id} role="tab" aria-selected={b.id === brand} className={b.id === brand ? "active" : ""} onClick={() => { setBrand(b.id); setResult(null); setError(""); }}>{b.name}</button>)}
          </div>
          {current && (
            <>
              <p className="brand-app">Export from <b>{current.app}</b></p>
              <ol className="brand-steps">{current.steps.map((s) => <li key={s}>{s}</li>)}</ol>
              <p className="muted small">Brings in: {current.gives.join(", ")}.{current.note ? ` ${current.note}` : ""}</p>
              {(brand === "noise" || brand === "other") && <p><a className="btn btn-ghost btn-sm" href="/api/wearables/template.csv" download>Download the CSV template</a></p>}
              <form className="form band-upload" onSubmit={importFile}>
                <label>Export file ({current.file})
                  <input ref={fileInput} type="file" accept=".zip,.xml,.csv,.json,.db" onChange={(e) => setFile(e.target.files[0] || null)} />
                </label>
                <button className="btn btn-primary" disabled={!file || busy}><IconUpload /> {busy ? "Reading the file..." : "Import"}</button>
              </form>
              {busy && <p className="muted small">Large Apple Health exports can take a minute or two.</p>}
            </>
          )}
          {error && <p className="form-error">{error}</p>}
          {result && (
            <div className="notice">
              Imported {result.days} days and {result.workouts} workouts{result.first_day ? ` (${result.first_day} to ${result.last_day})` : ""}.
              {result.notes.map((n) => <span key={n} className="import-note"> {n}</span>)}
            </div>
          )}
        </section>

        <LiveHeartRate age={user?.profile?.age} onSaved={load} />
      </div>

      <details className="panel band-manual">
        <summary>Type in a day by hand</summary>
        <form className="form band-day-form" onSubmit={saveDay}>
          <label>Date<input type="date" value={day.day} max={localDate()} onChange={(e) => setDay({ ...day, day: e.target.value })} required /></label>
          {DAY_FIELDS.map(([key, label, step]) => (
            <label key={key}>{label}<input type="number" min="0" step={step} value={day[key]} onChange={(e) => setDay({ ...day, [key]: e.target.value })} /></label>
          ))}
          <div className="log-submit"><button className="btn btn-primary">Save day</button>{dayMsg && <span className="form-ok">{dayMsg}</span>}</div>
        </form>
      </details>

      {summary?.imports?.length > 0 && (
        <section className="panel">
          <div className="section-row">
            <h2 className="section-title">Imported files</h2>
            <button className="btn btn-ghost btn-sm" onClick={removeAll}><IconTrash width={15} height={15} /> Delete all band data</button>
          </div>
          <ul className="band-workouts">
            {summary.imports.map((i) => (
              <li key={i.id}><strong>{BRAND_NAMES[i.source] || i.source}</strong>
                <span className="muted">{i.filename} · {i.days} days, {i.workouts} workouts{i.last_day ? ` · up to ${i.last_day}` : ""}</span></li>
            ))}
          </ul>
        </section>
      )}
      {summary?.connected && !summary.imports?.length && (
        <p><button className="btn btn-ghost btn-sm" onClick={removeAll}><IconTrash width={15} height={15} /> Delete all band data</button></p>
      )}
    </div>
  );
}
