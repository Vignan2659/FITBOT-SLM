// Client branding shown in the app (login/register panel and sidebar).
export default function PartnerBadge({ compact = false }) {
  return (
    <div className={`partner-badge ${compact ? "partner-compact" : ""}`}>
      <span className="partner-label">Prepared for</span>
      <img src="/veltris-logo.png" alt="Veltris - Innovate, Accelerate, Transform" />
    </div>
  );
}
