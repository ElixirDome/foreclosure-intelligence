import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { askRag } from "../api/rag";
import type { RAGResponse } from "../api/types";
import RagResult from "./RagResult";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  result?: RAGResponse;
}

const SUGGESTIONS = [
  "Is this a good investment?",
  "What is the reserve price?",
  "What are the main risks?",
  "Summarize valuation and comparables",
];

function propertyIdFromPath(pathname: string): number | null {
  const m = pathname.match(/^\/properties\/(\d+)/);
  return m ? Number(m[1]) : null;
}

export default function ChatBot() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "Ask about a property, auction notice, risks, or whether a deal is worth bidding on. I’ll use documents, comps, and valuations when available.",
    },
  ]);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const location = useLocation();
  const propertyIdFromRoute = propertyIdFromPath(location.pathname);

  useEffect(() => {
    if (open) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || loading) return;

    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setLoading(true);

    try {
      const result = await askRag({
        question: q,
        property_id: propertyIdFromRoute,
        multi_source: true,
        mode: "hybrid",
        limit: 8,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: result.structured?.summary || result.answer.slice(0, 280),
          result,
        },
      ]);
    } catch (err) {
      console.error(err);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: "Sorry — I couldn’t reach the research API. Is the backend running?",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  return (
    <div className="chatbot-root">
      {open && (
        <div className="chatbot-panel" role="dialog" aria-label="Research chat">
          <div className="chatbot-header">
            <div>
              <strong>Research assistant</strong>
              <div className="muted chatbot-sub">
                Multi-source RAG
                {propertyIdFromRoute
                  ? ` · property #${propertyIdFromRoute}`
                  : " · all sources"}
              </div>
            </div>
            <button
              type="button"
              className="chatbot-icon-btn"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
            >
              ×
            </button>
          </div>

          <div className="chatbot-messages">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={
                  msg.role === "user" ? "chat-bubble user" : "chat-bubble bot"
                }
              >
                <p>{msg.text}</p>
                {msg.result && (
                  <div className="chat-rag-embed">
                    <RagResult result={msg.result} />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble bot muted">Researching…</div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="chatbot-suggestions">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className="chip"
                disabled={loading}
                onClick={() => void send(s)}
              >
                {s}
              </button>
            ))}
          </div>

          <form className="chatbot-input-row" onSubmit={onSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about investments, notices, risks…"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className="chatbot-fab"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close research chat" : "Open research chat"}
      >
        {open ? "×" : "AI"}
      </button>
    </div>
  );
}
