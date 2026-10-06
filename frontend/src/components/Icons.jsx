// Small inline SVG icon set (stroke icons, inherit currentColor).
const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2,
  strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

export const IconDumbbell = (p) => (
  <svg {...base} {...p}><path d="M6.5 6.5v11M17.5 6.5v11M3 9.5v5M21 9.5v5M6.5 12h11" /></svg>
);
export const IconPlus = (p) => <svg {...base} {...p}><path d="M12 5v14M5 12h14" /></svg>;
export const IconChat = (p) => <svg {...base} {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>;
export const IconHome = (p) => <svg {...base} {...p}><path d="M3 10.5 12 3l9 7.5V21H3z" /><path d="M9 21v-7h6v7" /></svg>;
export const IconUser = (p) => <svg {...base} {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></svg>;
export const IconLogout = (p) => <svg {...base} {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></svg>;
export const IconTrash = (p) => <svg {...base} {...p}><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" /></svg>;
export const IconSend = (p) => <svg {...base} {...p}><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" /></svg>;
export const IconMenu = (p) => <svg {...base} {...p}><path d="M3 6h18M3 12h18M3 18h18" /></svg>;
export const IconX = (p) => <svg {...base} {...p}><path d="M18 6 6 18M6 6l12 12" /></svg>;
export const IconShield = (p) => <svg {...base} {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>;
export const IconBook = (p) => <svg {...base} {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z" /><path d="M4 19.5V21h16" /></svg>;
export const IconLeaf = (p) => <svg {...base} {...p}><path d="M11 20A7 7 0 0 1 4 13c0-6 7-10 16-10 0 9-4 16-10 16" /><path d="M4 21c4-6 8-9 12-11" /></svg>;
export const IconMoon = (p) => <svg {...base} {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></svg>;
export const IconCalendar = (p) => <svg {...base} {...p}><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>;
export const IconFlame = (p) => <svg {...base} {...p}><path d="M12 22c4 0 7-3 7-7 0-5-5-7-5-12-3 2-5 5-5 8-1-1-2-2-2-4-2 2-2 5-2 8 0 4 3 7 7 7z" /></svg>;
export const IconDrop = (p) => <svg {...base} {...p}><path d="M12 2.7 6.3 9a7.5 7.5 0 1 0 11.4 0z" /></svg>;
export const IconChevron = (p) => <svg {...base} {...p}><path d="m6 9 6 6 6-6" /></svg>;
