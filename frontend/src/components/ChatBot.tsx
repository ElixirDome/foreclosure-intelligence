import { useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { analyzeInvestment, askRag } from "../api/rag";
import type { RAGResponse } from "../api/types";
import RagResult from "./RagResult";

type Turn =
  | { role: "user"; text: string }
  | { role: "assistant"; result: RAGResponse };

const ABOUT = [
  "Is this a good investment?",
  "On what basis was this evaluated?",
  "What should I check before bidding?",
];

const GENERAL = [
  "Which residential lots look discounted?",
  "What risks matter most before bidding?",
];

export default function ChatBot() {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  const propertyId = useMemo(() => {
    const m = location.pathname.match(/^\/properties\/(\d+)/);
    return m ? Number(m[1]) : null;
  }, [location.pathname]);

  // Hide on login
  if (location.pathname === "/login") return null;

  const suggestions = propertyId ? ABOUT : GENERAL;

  async function send(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    setDraft("");
    setError("");
    setTurns((t) => [...t, { role: "user", text: q }]);
    setLoading(true);
    try {
      let data: RAGResponse;
      const invest =
        propertyId != null &&
        /\b(invest|good|evaluat|basis|deal|worth)\b/i.test(q);

      if (invest && propertyId != null) {
        data = await analyzeInvestment({ property_id: propertyId, question: q });
      } else {
        data = await askRag({
          question: q,
          property_id: propertyId,
          multi_source: true,
          limit: 6,
        });
      }
      setTurns((t) => [...t, { role: "assistant", result: data }]);
    } catch (err) {
      console.error(err);
      setError("Could not answer. Are you logged in?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatbot-root">
      {open && (
        <div className="chatbot-panel" role="dialog" aria-label="Research">
          <div className="chatbot-header">
            <div>
              <strong>Research</strong>
              <p className="chatbot-sub muted">
                {propertyId
                  ? `Property #${propertyId}`
                  : "Whole desk"}
              </p>
            </div>
            <button
              type="button"
              className="chatbot-icon-btn"
              aria-label="Close"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </div>

          <div className="chatbot-messages">
            {turns.length === 0 && (
              <p className="muted">
                {propertyId
                  ? "Ask about this lot in plain language."
                  : "Ask about the desk, or open a property for a tighter note."}
              </p>
            )}
            {turns.map((turn, i) =>
              turn.role === "user" ? (
                <div key={i} className="chat-bubble user">
                  <p>{turn.text}</p>
                </div>
              ) : (
                <div key={i} className="chat-bubble bot">
                  <RagResult result={turn.result} compact />
                </div>
              ),
            )}
            {loading && <p className="muted">Looking at what is on file…</p>}
            {error && <p className="error-text">{error}</p>}
          </div>

          {turns.length === 0 && (
            <div className="chatbot-suggestions">
              {suggestions.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => void send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          <form
            className="chatbot-input-row"
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask a question"
              aria-label="Question"
            />
            <button type="submit" disabled={loading || !draft.trim()}>
              Ask
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className="chatbot-fab"
        aria-label={open ? "Close research" : "Open research"}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "×" : "?"}
      </button>
    </div>
  );
}
