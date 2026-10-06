import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import Message from "../components/Message.jsx";
import { IconDumbbell, IconMic, IconSend } from "../components/Icons.jsx";

// Voice input via the browser's Web Speech API (Chrome, Edge, Safari); the button is hidden elsewhere.
const SpeechRecognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export const SUGGESTIONS = [
  "What exercises can I do for chest?",
  "Give me a beginner 3-day gym workout",
  "What should I eat after working out?",
  "How much protein does an egg contain?",
  "How much should I sleep?",
  "What drinks should I limit for weight loss?",
];

export default function Chat() {
  const { id } = useParams();
  const conversationId = id ? Number(id) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const { refreshConversations } = useOutletContext();
  const [messages, setMessages] = useState([]);
  const [title, setTitle] = useState("New chat");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingConv, setLoadingConv] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);
  const textRef = useRef(null);
  const skipLoad = useRef(false);
  const inFlight = useRef(false);
  const handledPreset = useRef(null);   // location.key of the quick-start prompt already sent
  const recognition = useRef(null);
  const [listening, setListening] = useState(false);

  useEffect(() => () => recognition.current?.abort(), []);

  function toggleVoice() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const rec = new SpeechRecognition();
    rec.lang = "en-US";
    rec.interimResults = true;
    const before = input ? `${input.trim()} ` : "";
    rec.onresult = (e) => setInput(before + Array.from(e.results).map((r) => r[0].transcript).join(""));
    rec.onerror = (e) => {
      if (e.error === "not-allowed") setError("Microphone access was blocked. Allow it in the browser to use voice input.");
      else if (e.error !== "no-speech" && e.error !== "aborted") setError("Voice input is not available right now.");
    };
    rec.onend = () => { setListening(false); textRef.current?.focus(); };
    recognition.current = rec;
    setError("");
    setListening(true);
    rec.start();
  }

  // load an existing conversation
  useEffect(() => {
    setError("");
    if (!conversationId) {
      // don't wipe a question that a dashboard quick-start has just sent (StrictMode re-runs this effect)
      if (handledPreset.current !== location.key) {
        setMessages([]);
        setTitle("New chat");
      }
      return;
    }
    if (skipLoad.current) {
      skipLoad.current = false;
      return;
    }
    setLoadingConv(true);
    api.getConversation(conversationId)
      .then((c) => { setMessages(c.messages); setTitle(c.title); })
      .catch((e) => setError(e.status === 404 ? "Conversation not found." : e.message))
      .finally(() => setLoadingConv(false));
  }, [conversationId]);

  // a prompt passed from the dashboard starts a new chat immediately - exactly once per navigation
  // (React StrictMode runs effects twice in development, which used to send the question twice)
  useEffect(() => {
    const preset = location.state?.prompt;
    if (preset && !conversationId && handledPreset.current !== location.key) {
      handledPreset.current = location.key;
      navigate(location.pathname, { replace: true, state: {} });
      send(preset);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || sending || inFlight.current) return;
    inFlight.current = true;   // synchronous guard: state updates are async, a double Enter/click could slip through
    recognition.current?.abort();
    setInput("");
    setError("");
    const tempId = `tmp-${Date.now()}`;
    setMessages((m) => [...m, { id: tempId, role: "user", content: message }]);
    setSending(true);
    try {
      const r = await api.chat(message, conversationId);
      const bot = {
        id: r.message_id, role: "assistant", content: r.answer, intent: r.intent,
        payload: { exercises: r.exercises, foods: r.foods, workout_plan: r.workout_plan, sources: r.sources,
                   safety: r.safety, category: r.category, is_followup: r.is_followup, model: r.model },
      };
      setMessages((m) => [...m, bot]);
      setTitle(r.conversation_title);
      if (!conversationId) {
        skipLoad.current = true;
        navigate(`/chat/${r.conversation_id}`, { replace: true });
      }
      refreshConversations();
    } catch (e) {
      setError(e.message);
      setMessages((m) => m.filter((x) => x.id !== tempId));
      setInput(message);
    } finally {
      setSending(false);
      inFlight.current = false;
      textRef.current?.focus();
    }
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="chat">
      <header className="chat-head">
        <h1 title={title}>{title}</h1>
      </header>
      <div className="chat-scroll">
        {loadingConv && <div className="center muted">Loading conversation...</div>}
        {!loadingConv && messages.length === 0 && (
          <div className="empty">
            <div className="empty-mark"><IconDumbbell width={28} height={28} /></div>
            <h2>How can I help you train today?</h2>
            <p className="muted">Ask about exercises, workout plans, nutrition, hydration, sleep or recovery.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => <button key={s} className="suggestion" onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {messages.map((m) => <Message key={m.id} msg={m} />)}
        {sending && (
          <div className="msg msg-bot">
            <div className="bot-avatar" aria-hidden><IconDumbbell width={16} height={16} /></div>
            <div className="typing" aria-label="FitBot is thinking"><span /><span /><span /></div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="composer-wrap">
        {error && <div className="form-error" role="alert">{error}</div>}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <textarea ref={textRef} rows={1} value={input} placeholder={listening ? "Listening..." : "Ask FitBot about workouts, food, sleep..."}
                    onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} maxLength={2000} aria-label="Message" />
          {SpeechRecognition && (
            <button type="button" className={`mic-btn ${listening ? "on" : ""}`} onClick={toggleVoice}
                    aria-label={listening ? "Stop voice input" : "Voice input"} title={listening ? "Stop listening" : "Speak your question"}>
              <IconMic />
            </button>
          )}
          <button className="send-btn" disabled={!input.trim() || sending} aria-label="Send message"><IconSend /></button>
        </form>
        <p className="disclaimer">FitBot provides general fitness and wellness information and is not a substitute for professional medical advice.</p>
      </div>
    </div>
  );
}
