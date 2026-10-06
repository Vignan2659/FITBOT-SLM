import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import PartnerBadge from "./PartnerBadge.jsx";
import { IconChat, IconDumbbell, IconHome, IconLogout, IconMenu, IconPlus, IconTrash, IconUser, IconX } from "./Icons.jsx";

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [conversations, setConversations] = useState([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => setOpen(false), [location.pathname]);

  const activeId = location.pathname.startsWith("/chat/") ? Number(location.pathname.split("/")[2]) : null;

  async function remove(id, e) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    try {
      await api.deleteConversation(id);
      setConversations((cs) => cs.filter((c) => c.id !== id));
      if (activeId === id) navigate("/chat");
    } catch (err) {
      setError(err.message);
    }
  }

  async function doLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="app-shell">
      <header className="mobile-bar">
        <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Open menu"><IconMenu /></button>
        <span className="brand-sm"><IconDumbbell /> FitBot</span>
      </header>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand"><span className="brand-mark"><IconDumbbell /></span>FitBot</div>
          <button className="icon-btn only-mobile" onClick={() => setOpen(false)} aria-label="Close menu"><IconX /></button>
        </div>
        <button className="btn btn-primary btn-block" onClick={() => navigate("/chat")}>
          <IconPlus /> New chat
        </button>
        <nav className="nav">
          <NavLink to="/dashboard"><IconHome /> Dashboard</NavLink>
          <NavLink to="/chat" end><IconChat /> Chat</NavLink>
          <NavLink to="/profile"><IconUser /> Profile</NavLink>
        </nav>
        <div className="conv-heading">Previous conversations</div>
        {error && <div className="side-error">{error}</div>}
        <ul className="conv-list">
          {conversations.length === 0 && <li className="conv-empty">No conversations yet</li>}
          {conversations.map((c) => (
            <li key={c.id}>
              <NavLink to={`/chat/${c.id}`} className={`conv-item ${activeId === c.id ? "active" : ""}`} title={c.title}>
                <span className="conv-title">{c.title}</span>
                <button className="conv-del" onClick={(e) => remove(c.id, e)} aria-label={`Delete ${c.title}`}>
                  <IconTrash width={15} height={15} />
                </button>
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="sidebar-foot">
          <PartnerBadge compact />
          <div className="user-chip">
            <span className="avatar">{user?.name?.[0]?.toUpperCase() || "?"}</span>
            <div className="user-meta"><strong>{user?.name}</strong><span>{user?.email}</span></div>
          </div>
          <button className="btn btn-ghost btn-block" onClick={doLogout}><IconLogout /> Log out</button>
        </div>
      </aside>
      <main className="main">
        <Outlet context={{ conversations, refreshConversations }} />
      </main>
    </div>
  );
}
