import { IconDumbbell, IconLeaf, IconMoon, IconShield } from "../components/Icons.jsx";
import PartnerBadge from "../components/PartnerBadge.jsx";

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="auth">
      <section className="auth-hero">
        <div className="brand brand-light"><span className="brand-mark"><IconDumbbell /></span>FitBot</div>
        <h1>Your fitness, nutrition &amp; recovery assistant.</h1>
        <p>Powered by a small language model fine-tuned for fitness, running locally - with real exercise images and USDA nutrition data.</p>
        <ul className="auth-points">
          <li><IconDumbbell /> Exercise cards &amp; workout plans</li>
          <li><IconLeaf /> Nutrition facts from USDA FoodData Central</li>
          <li><IconMoon /> Sleep, hydration &amp; recovery guidance</li>
          <li><IconShield /> Safety-first answers</li>
        </ul>
        <PartnerBadge />
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <h2>{title}</h2>
          <p className="muted">{subtitle}</p>
          {children}
        </div>
        <p className="disclaimer">FitBot provides general fitness and wellness information and is not a substitute for professional medical advice.</p>
      </section>
    </div>
  );
}
