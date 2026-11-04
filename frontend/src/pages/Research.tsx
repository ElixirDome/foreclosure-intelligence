import { useState, useRef, useEffect } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { analyzeInvestment, askRag } from "../api/rag";
import type { RAGResponse } from "../api/types";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  structured?: RAGResponse["structured"];
  citations?: RAGResponse["citations"];
  timestamp: string;
}

const QUICK_PROMPTS = [
  "Which residential lots have the highest estimated discount?",
  "What legal risks should I verify before bidding on SARFAESI lots?",
  "Summarize the latest PNB e-auction properties on the desk",
  "How are market comparables calculated for valuation?",
];

const PROPERTY_PROMPTS = [
  "Is this property a good investment opportunity?",
  "What was the basis for this property's valuation?",
  "What due diligence checks should I complete before bidding?",
];

export default function Research() {
  const [params, setParams] = useSearchParams();
  const propertyIdParam = params.get("property_id");
  const propertyId = propertyIdParam ? Number(propertyIdParam) : null;

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const prompts = propertyId ? PROPERTY_PROMPTS : QUICK_PROMPTS;

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function sendMessage(text: string) {
    const q = text.trim();
    if (!q || loading) return;

    const userMsg: ChatMessage = {
      id: "u_" + Date.now(),
      role: "user",
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      let data: RAGResponse;
      const isInvestQuery =
        /\b(invest|good buy|evaluat|basis|deal|worth)\b/i.test(q) && propertyId != null;

      if (isInvestQuery && propertyId != null) {
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

      const botText = data.answer || data.structured?.summary || "No response generated.";
      const botMsg: ChatMessage = {
        id: "a_" + Date.now(),
        role: "assistant",
        text: botText,
        structured: data.structured,
        citations: data.citations,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      console.error("RAG Error:", err);
      const errMsg: ChatMessage = {
        id: "err_" + Date.now(),
        role: "assistant",
        text: "I encountered an error retrieving data. Please ensure the backend is running and you are logged in.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void sendMessage(input);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  }

  function clearChat() {
    setMessages([]);
    setInput("");
  }

  function clearScope() {
    params.delete("property_id");
    setParams(params);
  }

  return (
    <div className="ai-chat-page">
      {/* Minimalist Header */}
      <header className="ai-chat-header">
        <div className="ai-chat-header-left">
          <Link to="/dashboard" className="ai-back-link">
            ← Desk
          </Link>
          <div className="ai-title-wrap">
            <span className="ai-avatar-icon">🤖</span>
            <div className="ai-title-text">
              <h2>Research Analyst</h2>
              <div className="ai-status-indicator">
                <span className="ai-status-dot"></span>
                <span>Active · Multi-Source RAG</span>
              </div>
            </div>
          </div>
        </div>

        <div className="ai-chat-header-right">
          {propertyId && (
            <div className="ai-scope-badge">
              <span>Scoped to Lot #{propertyId}</span>
              <button type="button" onClick={clearScope} title="Clear property scope">
                ✕
              </button>
            </div>
          )}

          {messages.length > 0 && (
            <button type="button" className="ai-btn-ghost" onClick={clearChat} title="Clear conversation">
              Clear Chat
            </button>
          )}

          <Link to="/admin/import" className="ai-btn-ghost">
            Bank Sources
          </Link>
        </div>
      </header>

      {/* Main Chat Stream */}
      <main className="ai-chat-body">
        {messages.length === 0 && (
          <div className="ai-empty-hero">
            <div className="ai-empty-icon">⚡</div>
            <h3>How can I help with your foreclosure analysis?</h3>
            <p>
              Ask about property valuation, auction terms, reserve prices, or comparative market data.
            </p>

            <div className="ai-prompt-grid">
              {prompts.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="ai-prompt-chip"
                  onClick={() => void sendMessage(p)}
                >
                  <span className="ai-prompt-arrow">↳</span>
                  <span>{p}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="ai-messages-list">
          {messages.map((m) => (
            <div key={m.id} className={`ai-message-row ${m.role}`}>
              {m.role === "assistant" && (
                <div className="ai-bot-avatar">🤖</div>
              )}

              <div className="ai-message-bubble">
                <div className="ai-message-content">
                  <p>{m.text}</p>

                  {m.structured && (
                    <div className="ai-structured-note">
                      {m.structured.strengths && m.structured.strengths.length > 0 && (
                        <div className="ai-note-block positive">
                          <strong>Supporting Factors:</strong>
                          <ul>
                            {m.structured.strengths.map((s, idx) => (
                              <li key={idx}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {m.structured.risks && m.structured.risks.length > 0 && (
                        <div className="ai-note-block negative">
                          <strong>Risk Factors:</strong>
                          <ul>
                            {m.structured.risks.map((r, idx) => (
                              <li key={idx}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {m.structured.recommendation && (
                        <div className="ai-note-block recommendation">
                          <strong>Bottom Line:</strong> {m.structured.recommendation}
                        </div>
                      )}
                    </div>
                  )}

                  {m.citations && m.citations.length > 0 && (
                    <div className="ai-citations-strip">
                      <span className="ai-citation-label">Sources:</span>
                      {m.citations.slice(0, 4).map((c, idx) => (
                        <span key={idx} className="ai-citation-pill" title={c.excerpt || c.title || undefined}>
                          📄 {c.title || c.source_name || "Notice"}
                          {c.page_number != null ? ` (p.${c.page_number})` : ""}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <span className="ai-timestamp">{m.timestamp}</span>
              </div>
            </div>
          ))}

          {loading && (
            <div className="ai-message-row assistant">
              <div className="ai-bot-avatar">🤖</div>
              <div className="ai-message-bubble loading-bubble">
                <div className="ai-typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Floating Modern Input Bar */}
      <footer className="ai-input-dock">
        <form className="ai-input-bar" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              propertyId
                ? `Ask about Lot #${propertyId} (e.g. reserve price, comparables, risks)...`
                : "Ask anything about auction inventory, legal risks, or valuations..."
            }
            disabled={loading}
          />
          <button
            type="submit"
            className="ai-send-btn"
            disabled={loading || !input.trim()}
            title="Send Message"
          >
            ↑
          </button>
        </form>
      </footer>
    </div>
  );
}
