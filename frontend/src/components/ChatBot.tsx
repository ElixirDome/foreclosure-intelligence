import { useState, useRef, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api/client";
import { askRag } from "../api/rag";
import type { RAGResponse } from "../api/types";
import { useAnalyst } from "../context/AnalystContext";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  property_id?: number | null;
  structured?: RAGResponse["structured"];
  citations?: RAGResponse["citations"];
  timestamp: string;
}

const GENERAL_PROMPTS = [
  "Show the latest residential auctions in Gurdaspur",
  "How do I connect a foreclosure source to Foreclosure Intelligence?",
  "What risks should I check before bidding on SARFAESI lots?",
  "Find properties below 40 Lakh reserve price",
];

const PROPERTY_PROMPTS = [
  "What is this property's estimated market value?",
  "How was the property value calculated?",
  "What are its EMD and reserve price?",
  "Show me the original auction notice for this property",
];

export default function ChatBot() {
  const location = useLocation();
  const {
    isOpen,
    openAnalyst,
    closeAnalyst,
    activePropertyId,
    activePropertyAddress,
    clearPropertyScope,
    consumePendingPrompt,
  } = useAnalyst();

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    // Initial friendly greeting
    return [
      {
        id: "intro_1",
        role: "assistant",
        text: "Hello! I am your Foreclosure Research Analyst. I provide evidence-backed valuations, auction status details, comparable sales explanations, and portal onboarding guidance.",
        timestamp: "Just now",
      },
    ];
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Check for auto-triggered prompts from context
  useEffect(() => {
    if (isOpen) {
      const prompt = consumePendingPrompt();
      if (prompt) {
        sendMessage(prompt);
      } else {
        setTimeout(() => inputRef.current?.focus(), 150);
      }
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, isOpen]);

  // Hide entirely on login page
  if (location.pathname === "/login") return null;

  async function sendMessage(textToSend: string) {
    const q = textToSend.trim();
    if (!q || loading) return;

    const userMsg: ChatMessage = {
      id: "u_" + Date.now(),
      role: "user",
      text: q,
      property_id: activePropertyId,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const history = messages.slice(-6).map((m) => ({
      role: m.role,
      text: m.text,
      property_id: m.property_id,
    }));

    try {
      const data = await askRag({
        question: q,
        property_id: activePropertyId,
        conversation_history: history,
      });

      const botText = data.answer || data.structured?.summary || "No data was returned for this inquiry.";
      const botMsg: ChatMessage = {
        id: "a_" + Date.now(),
        role: "assistant",
        text: botText,
        property_id: activePropertyId,
        structured: data.structured,
        citations: data.citations,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      console.error("Analyst Error:", err);
      const errMsg: ChatMessage = {
        id: "err_" + Date.now(),
        role: "assistant",
        text: "I encountered an error retrieving that information. Please ensure the backend is running and you are signed in.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const promptSuggestions = activePropertyId ? PROPERTY_PROMPTS : GENERAL_PROMPTS;

  return (
    <>
      {/* Floating Trigger Pill (When Drawer is Closed) */}
      {!isOpen && (
        <button
          type="button"
          className="analyst-floating-trigger"
          onClick={() => openAnalyst()}
          title="Open Research Analyst"
        >
          <div className="trigger-pulse-dot" />
          <span className="trigger-icon">🤖</span>
          <span className="trigger-label">Research Analyst</span>
          {activePropertyId && <span className="trigger-scope-badge">Lot #{activePropertyId}</span>}
        </button>
      )}

      {/* Slide-over Drawer / Docked AI Panel */}
      {isOpen && (
        <aside className="analyst-drawer" aria-label="Foreclosure Research Analyst">
          {/* Header */}
          <header className="analyst-drawer-header">
            <div className="analyst-header-info">
              <div className="analyst-title-row">
                <span className="analyst-bot-icon">🤖</span>
                <span className="analyst-title">Research Analyst</span>
                <span className="analyst-live-pill">🟢 Multi-Source RAG</span>
              </div>
              {activePropertyId ? (
                <div className="analyst-scope-tag">
                  <span>📌 Scoped to {activePropertyAddress || `Lot #${activePropertyId}`}</span>
                  <button
                    type="button"
                    className="scope-clear-btn"
                    onClick={clearPropertyScope}
                    title="Clear property focus to search across all inventory"
                  >
                    ✕ Clear
                  </button>
                </div>
              ) : (
                <span className="analyst-subtitle">Portfolio & Macro Discovery Mode</span>
              )}
            </div>

            <div className="analyst-header-actions">
              <button
                type="button"
                className="analyst-tool-btn"
                onClick={() =>
                  setMessages([
                    {
                      id: "intro_reset",
                      role: "assistant",
                      text: "Chat cleared. What property or auction market would you like to explore?",
                      timestamp: "Just now",
                    },
                  ])
                }
                title="Clear conversation"
              >
                🗑️
              </button>
              <button
                type="button"
                className="analyst-tool-btn"
                onClick={closeAnalyst}
                title="Close Analyst Drawer"
              >
                ✕
              </button>
            </div>
          </header>

          {/* Quick Prompts Strip */}
          <div className="analyst-quick-prompts">
            {promptSuggestions.map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="analyst-prompt-chip"
                onClick={() => sendMessage(p)}
                disabled={loading}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Messages Stream */}
          <div className="analyst-messages-stream">
            {messages.map((m) => {
              // Extract action links and regular citations
              const actionCitations = m.citations?.filter((c) => c.kind === "action" && Boolean(c.source_id)) || [];
              const sourceCitations = m.citations?.filter((c) => c.kind !== "action") || [];

              return (
                <div key={m.id} className={`analyst-msg-row ${m.role}`}>
                  {m.role === "assistant" && <div className="analyst-avatar">🤖</div>}

                  <div className="analyst-msg-bubble">
                    <div className="analyst-msg-text">
                      {m.text.split("\n\n").map((para, i) => {
                        if (para.startsWith("### ") || para.startsWith("#### ")) {
                          return (
                            <h4 key={i} className="analyst-msg-heading">
                              {para.replace(/^#+\s*/, "")}
                            </h4>
                          );
                        }
                        if (para.startsWith("- ") || para.startsWith("* ")) {
                          const items = para.split("\n").filter((l) => l.trim().length > 0);
                          return (
                            <ul key={i} className="analyst-msg-list">
                              {items.map((item, j) => (
                                <li key={j}>{item.replace(/^[-*]\s*/, "")}</li>
                              ))}
                            </ul>
                          );
                        }
                        return <p key={i}>{para}</p>;
                      })}

                      {/* Structured Analysis Notes */}
                      {m.structured && (
                        <div className="analyst-structured-grid">
                          {m.structured.strengths && m.structured.strengths.length > 0 && (
                            <div className="analyst-note-box positive">
                              <strong>Supporting Evidence:</strong>
                              <ul>
                                {m.structured.strengths.map((s, idx) => (
                                  <li key={idx}>+ {s}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {m.structured.risks && m.structured.risks.length > 0 && (
                            <div className="analyst-note-box negative">
                              <strong>Identified Risks:</strong>
                              <ul>
                                {m.structured.risks.map((r, idx) => (
                                  <li key={idx}>- {r}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {m.structured.recommendation && (
                            <div className="analyst-note-box recommendation">
                              <strong>Bottom Line:</strong> {m.structured.recommendation}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Action Links Buttons */}
                      {actionCitations.length > 0 && (
                        <div className="analyst-action-bar">
                          {actionCitations.map((act, idx) => {
                            const targetUrl = act.source_id || "/dashboard";
                            const isDocumentFile = targetUrl.startsWith("/documents/") || targetUrl.includes("/file");
                            const isExternal = targetUrl.startsWith("http");

                            if (isExternal || isDocumentFile) {
                              const backendBase = api.defaults.baseURL || "http://127.0.0.1:8000";
                              const href = isExternal
                                ? targetUrl
                                : `${backendBase}${targetUrl}`;
                              return (
                                <a
                                  key={idx}
                                  href={href}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="analyst-action-pill"
                                >
                                  {act.title} ↗
                                </a>
                              );
                            }

                            return (
                              <Link
                                key={idx}
                                to={targetUrl}
                                className="analyst-action-pill"
                              >
                                {act.title} →
                              </Link>
                            );
                          })}
                        </div>
                      )}

                      {/* Source Citations with Strict Deduplication */}
                      {(() => {
                        const seenKeys = new Set<string>();
                        const uniqueCitations = sourceCitations.filter((c) => {
                          const key = `${c.document_id ?? ""}-${c.page_number ?? ""}-${c.title || c.source_name || ""}`;
                          if (seenKeys.has(key)) return false;
                          seenKeys.add(key);
                          return true;
                        });
                        if (uniqueCitations.length === 0) return null;
                        return (
                          <div className="analyst-citations-wrap">
                            <span className="analyst-citations-label">Sources:</span>
                            {uniqueCitations.slice(0, 4).map((c, idx) => (
                              <span
                                key={idx}
                                className="analyst-citation-chip"
                                title={c.excerpt || c.title || undefined}
                              >
                                📄 {c.title || c.source_name || "Notice"}
                                {c.page_number != null ? ` (p.${c.page_number})` : ""}
                              </span>
                            ))}
                          </div>
                        );
                      })()}
                    </div>

                    <span className="analyst-timestamp">{m.timestamp}</span>
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="analyst-msg-row assistant">
                <div className="analyst-avatar">🤖</div>
                <div className="analyst-msg-bubble loading">
                  <div className="analyst-typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Dock Input Bar */}
          <footer className="analyst-dock-input">
            <form
              className="analyst-input-form"
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  activePropertyId
                    ? `Ask about Lot #${activePropertyId} (valuation, EMD, notice, comparables)...`
                    : "Ask about auctions, reserve prices, locations, or source setup..."
                }
                disabled={loading}
              />
              <button
                type="submit"
                className="analyst-send-btn"
                disabled={loading || !input.trim()}
                title="Send to Research Analyst"
              >
                ↑
              </button>
            </form>
          </footer>
        </aside>
      )}
    </>
  );
}
