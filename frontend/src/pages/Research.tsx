import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { analyzeInvestment, askRag } from "../api/rag";
import type { RAGResponse } from "../api/types";
import RagResult from "../components/RagResult";

const GENERAL = [
  "Which residential lots look most discounted?",
  "What risks should I watch before bidding?",
  "Summarize upcoming auctions on the desk",
];

const ABOUT_PROPERTY = [
  "Is this a good investment?",
  "On what basis was this property evaluated?",
  "What should I check before bidding?",
];

type Turn =
  | { role: "user"; text: string }
  | { role: "assistant"; result: RAGResponse };

export default function Research() {
  const [params] = useSearchParams();
  const propertyIdParam = params.get("property_id");
  const propertyId = propertyIdParam ? Number(propertyIdParam) : null;

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  const suggestions = propertyId ? ABOUT_PROPERTY : GENERAL;

  async function runAsk(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    setQuestion("");
    setError("");
    setTurns((t) => [...t, { role: "user", text: q }]);
    setLoading(true);
    try {
      let data: RAGResponse;
      const invest =
        /\b(invest|good buy|evaluat|basis|deal|worth)\b/i.test(q) && propertyId;

      if (invest && propertyId) {
        data = await analyzeInvestment({
          property_id: propertyId,
          question: q,
        });
      } else {
        data = await askRag({
          question: q,
          property_id: propertyId,
          multi_source: true,
          limit: 8,
        });
      }
      setTurns((t) => [...t, { role: "assistant", result: data }]);
    } catch (err) {
      console.error(err);
      setError(
        "Could not answer that. Check that you are logged in and the API is running.",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void runAsk(question);
  }

  return (
    <div className="page desk-page">
      <nav className="navbar">
        <Link to="/dashboard">Desk</Link>
        <Link to="/research">Research</Link>
        <Link to="/admin/import">Import</Link>
      </nav>

      <header className="desk-header">
        <h1>Research</h1>
        <p className="muted">
          Ask in plain language. Name a place, or open a property and ask about
          that lot. There is nothing to configure.
        </p>
        {propertyId && (
          <p className="context-chip">
            Scoped to property #{propertyId} ·{" "}
            <Link to={`/properties/${propertyId}`}>Open lot</Link>
          </p>
        )}
      </header>

      <div className="conversation">
        {turns.length === 0 && (
          <p className="muted lead">
            {propertyId
              ? "Ask whether this lot is worth a closer look, how it was valued, or what to check before bidding."
              : "Try a desk-wide question, or open a property first for a tighter answer."}
          </p>
        )}

        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <p key={i} className="user-turn">
              {turn.text}
            </p>
          ) : (
            <RagResult key={i} result={turn.result} />
          ),
        )}

        {loading && <p className="muted">Looking at what is on file…</p>}
        {error && <p className="error-text">{error}</p>}
      </div>

      {turns.length === 0 && (
        <div className="suggestion-row">
          {suggestions.map((s) => (
            <button key={s} type="button" className="chip" onClick={() => void runAsk(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form className="ask-bar" onSubmit={handleSubmit}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={propertyId ? "Ask about this lot" : "Ask a question"}
          aria-label="Question"
        />
        <button type="submit" disabled={loading || !question.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
