import { Link } from "react-router-dom";
import { IconWatch } from "./Icons.jsx";

export const BRAND_NAMES = { apple: "Apple Watch", samsung: "Samsung", google: "Google / Fitbit", huawei: "Huawei", oneplus: "OnePlus",
  noise: "Noise", whoop: "WHOOP", other: "Other band", manual: "Typed in", live: "Live heart rate" };

export function fmtSleep(minutes) {
  if (!minutes) return "—";
  return `${Math.floor(minutes / 60)} h ${String(Math.round(minutes % 60)).padStart(2, "0")} min`;
}
export const fmtInt = (v) => (v == null ? "—" : Math.round(v).toLocaleString());
export const stressWord = (v) => (v == null ? "" : v < 30 ? "low" : v < 60 ? "normal" : v < 80 ? "high" : "very high");

// The tiles of one day of band data: [key, label, value, small print]
export function bandTiles(d) {
  if (!d) return [];
  const hr = d.resting_hr != null ? ["Resting heart rate", `${Math.round(d.resting_hr)} bpm`, d.avg_hr ? `average ${Math.round(d.avg_hr)} bpm` : ""]
    : d.avg_hr != null ? ["Heart rate", `${Math.round(d.avg_hr)} bpm`, d.max_hr ? `max ${Math.round(d.max_hr)} bpm` : "average"] : null;
  return [
    d.steps != null && ["steps", "Steps", fmtInt(d.steps), d.distance_km ? `${d.distance_km.toFixed(1)} km` : ""],
    hr && ["hr", ...hr],
    d.sleep_minutes != null && ["sleep", "Sleep", fmtSleep(d.sleep_minutes), d.sleep_minutes < 420 ? "under 7 hours" : ""],
    d.stress != null && ["stress", "Stress", `${Math.round(d.stress)} / 100`, `${stressWord(d.stress)}${d.stress_estimated ? " · estimated" : ""}`],
    d.hrv_ms != null && ["hrv", "HRV", `${Math.round(d.hrv_ms)} ms`, ""],
    d.active_kcal != null && ["kcal", "Active energy", `${fmtInt(d.active_kcal)} kcal`, ""],
    d.spo2 != null && ["spo2", "Blood oxygen", `${Math.round(d.spo2)}%`, ""],
  ].filter(Boolean);
}

export function dayLabel(iso, isToday) {
  if (isToday) return "Today";
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

// Shown under a chat answer that used the person's own band numbers, and on the dashboard.
export default function BandCard({ band, title }) {
  if (!band) return null;
  const tiles = bandTiles(band);
  if (!tiles.length) return null;
  return (
    <section className="band-card" aria-label="Your fitness band data">
      <header>
        <span className="band-card-title"><IconWatch width={16} height={16} /> {title || "From your band"} · {dayLabel(band.day, band.is_today)}</span>
        <Link to="/bands" className="band-card-link">Open Bands</Link>
      </header>
      <div className="band-tiles">
        {tiles.map(([key, label, value, note]) => (
          <div key={key} className={`band-tile band-${key}`}><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>
        ))}
      </div>
      <p className="band-note">Wellness numbers from your own band, not a medical reading.</p>
    </section>
  );
}
