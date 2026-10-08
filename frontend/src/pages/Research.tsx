import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { askRag, listDocuments } from "../api/rag";
import type { DocumentItem, RAGResponse } from "../api/types";
import RagResult from "../components/RagResult";

const SUGGESTIONS = [
  "Is this a good foreclosure investment?",
  "What is the reserve price?",
  "What risks should I check before bidding?",
  "Summarize comparable sales and valuation",
  "When is the e-auction scheduled?",
];

export default function Research() {
  const [question, setQuestion] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [mode, setMode] = useState<"hybrid" | "keyword" | "vector">("hybrid");
  const [multiSource, setMultiSource] = useState<"auto" | "on" | "off">("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RAGResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);

  useEffect(() => {
    listDocuments(30)
      .then(setDocuments)
      .catch(() => {
        /* optional */
      });
  }, []);

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault();
    if (!question.trim()) return;

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const ms =
        multiSource === "auto" ? null : multiSource === "on" ? true : false;

      const data = await askRag({
        question: question.trim(),
        property_id: propertyId ? Number(propertyId) : null,
        document_id: documentId ? Number(documentId) : null,
        mode,
        multi_source: ms,
        limit: 8,
      });
      setResult(data);
    } catch (err) {
      console.error(err);
      setError(
        "Could not run research query. Is the API running and are you logged in?",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="navbar">
        <Link to="/dashboard">Properties</Link>
        <Link to="/research">Research</Link>
        <Link to="/admin/import">Import</Link>
      </div>

      <h1>Research desk</h1>
      <p className="muted">
        Multi-source RAG: auction documents, properties, evidence, comparables,
        valuations, and deal signals.
      </p>

      <form className="research-form" onSubmit={handleSubmit}>
        <textarea
          rows={3}
          placeholder="Ask e.g. Is property 12 a good investment?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />

        <div className="research-controls">
          <label>
            Property ID
            <input
              type="number"
              min={1}
              placeholder="optional"
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
            />
          </label>

          <label>
            Document
            <select
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
            >
              <option value="">Any / all</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  #{d.id} {d.filename || d.title || d.source_name}
                </option>
              ))}
            </select>
          </label>

          <label>
            Retrieval mode
            <select
              value={mode}
              onChange={(e) =>
                setMode(e.target.value as "hybrid" | "keyword" | "vector")
              }
            >
              <option value="hybrid">Hybrid</option>
              <option value="keyword">Keyword</option>
              <option value="vector">Vector</option>
            </select>
          </label>

          <label>
            Multi-source
            <select
              value={multiSource}
              onChange={(e) =>
                setMultiSource(e.target.value as "auto" | "on" | "off")
              }
            >
              <option value="auto">Auto (investment questions)</option>
              <option value="on">Always on</option>
              <option value="off">Documents only</option>
            </select>
          </label>
        </div>

        <div className="suggestion-row">
          {SUGGESTIONS.map((s) => (
            <button
              type="button"
              key={s}
              className="chip"
              onClick={() => setQuestion(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Researching…" : "Ask"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && <RagResult result={result} />}
    </div>
  );
}
