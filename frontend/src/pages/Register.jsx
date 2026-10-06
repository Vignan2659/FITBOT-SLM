import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import AuthShell from "./AuthShell.jsx";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) return setError("Password must be at least 8 characters.");
    if (form.password !== form.confirm) return setError("Passwords do not match.");
    setBusy(true);
    try {
      await register(form.name, form.email, form.password);
      navigate("/profile?welcome=1");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Start chatting with FitBot in seconds.">
      <form onSubmit={submit} className="form">
        <label>Name<input autoComplete="name" value={form.name} onChange={set("name")} required maxLength={120} /></label>
        <label>Email<input type="email" autoComplete="email" value={form.email} onChange={set("email")} required /></label>
        <label>Password<input type="password" autoComplete="new-password" value={form.password} onChange={set("password")} required minLength={8} /></label>
        <label>Confirm password<input type="password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} required /></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Creating account..." : "Create account"}</button>
      </form>
      <p className="switch">Already have an account? <Link to="/login">Log in</Link></p>
    </AuthShell>
  );
}
