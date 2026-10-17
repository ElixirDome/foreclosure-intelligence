import { useState } from "react";
import type { RAGResponse } from "../api/types";

type Props = {
  result: RAGResponse;
  compact?: boolean;
};

function kindLabel(kind?: string | null) {
  if (!kind) return "Source";
  const k = kind.toLowerCase();
  if (k.includes("evidence")) return "Evidence";
  if (k.includes("compar")) return "Comparable";
  if (k.includes("valu")) return "Valuation";
  if (k.includes("deal")) return "Deal signal";
  if (k.includes("propert")) return "Property";
  return "Document";
}

export default function RagResult({ result, compact = false }: Props) {
  const [showEvidence, setShowEvidence] = useState(false);
  const structured = result.structured;
  const citations = result.citations ?? [];
  const strengths = structured?.strengths ?? [];
  const risks = structured?.risks ?? [];
  const diligence = structured?.due_diligence ?? [];
  const rating = structured?.deal_rating;
  const score = structured?.deal_score;

  const verdict =
    rating ||
    (score != null && score >= 70
      ? "Worth a closer look"
      : score != null && score >= 45
        ? "Mixed"
        : score != null
          ? "Cautious"
          : null);

  return (
    <article className={`brief-result ${compact ? "brief-compact" : ""}`}>
      {verdict && (
        <p className="brief-verdict">{verdict}</p>
      )}

      {structured?.summary && (
        <p className="brief-summary">{structured.summary}</p>
      )}

      {!structured?.summary && result.answer && (
        <p className="brief-summary">{result.answer}</p>
      )}

      {(strengths.length > 0 || risks.length > 0) && (
        <div className="brief-two-col">
          {strengths.length > 0 && (
            <section>
              <h4>What supports it</h4>
              <ul>
                {strengths.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </section>
          )}
          {risks.length > 0 && (
            <section>
              <h4>What can go wrong</h4>
              <ul>
                {risks.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {diligence.length > 0 && (
        <section className="brief-section">
          <h4>Before you bid</h4>
          <ol>
            {diligence.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ol>
        </section>
      )}

      {structured?.recommendation && (
        <section className="brief-section">
          <h4>Bottom line</h4>
          <p>{structured.recommendation}</p>
        </section>
      )}

      {structured?.summary && result.answer && result.answer !== structured.summary && (
        <details className="brief-details">
          <summary>Full answer</summary>
          <p className="brief-summary">{result.answer}</p>
        </details>
      )}

      {citations.length > 0 && (
        <div className="brief-evidence-wrap">
          <button
            type="button"
            className="link-btn"
            onClick={() => setShowEvidence((v) => !v)}
            aria-expanded={showEvidence}
          >
            {showEvidence ? "Hide evidence" : "View evidence"}
          </button>
          {showEvidence && (
            <ul className="brief-evidence-list">
              {citations.map((c, idx) => (
                <li key={`${c.source_id ?? "c"}-${idx}`}>
                  <span className="evidence-kind">{kindLabel(c.kind)}</span>
                  <strong>{c.title || c.source_name || "Source"}</strong>
                  {c.excerpt && <p>{c.excerpt}</p>}
                  <span className="muted tiny">
                    {[c.source_name, c.page_number != null ? `p.${c.page_number}` : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {citations.length === 0 && !result.answer && !structured && (
        <p className="muted">
          No supporting material was found for this question. Try naming a
          city, bank, or opening a property first.
        </p>
      )}
    </article>
  );
}
