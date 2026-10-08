import type { RAGResponse } from "../api/types";

interface Props {
  result: RAGResponse;
}

function kindClass(kind: string): string {
  switch (kind) {
    case "document":
      return "badge badge-doc";
    case "property":
      return "badge badge-prop";
    case "comparable":
      return "badge badge-comp";
    case "valuation":
      return "badge badge-val";
    case "deal":
      return "badge badge-deal";
    case "evidence":
      return "badge badge-ev";
    default:
      return "badge";
  }
}

export default function RagResult({ result }: Props) {
  if (!result) {
    return null;
  }

  const structured = result.structured ?? null;
  const strengths = structured?.strengths ?? [];
  const risks = structured?.risks ?? [];
  const diligence = structured?.due_diligence ?? [];
  const citations = result.citations ?? [];

  return (
    <div className="rag-result">
      <div className="rag-meta">
        <span className="badge">{result.method ?? "rag"}</span>
        <span className="muted">
          {result.context_kinds?.length
            ? result.context_kinds.join(" · ")
            : "no sources"}
        </span>
        <span className="muted">{result.chunks_used ?? 0} doc chunks</span>
      </div>

      {structured && (
        <div className="structured-panel">
          {structured.summary && (
            <p className="structured-summary">{structured.summary}</p>
          )}

          {structured.deal_score != null && (
            <p className="deal-score-line">
              Deal score:{" "}
              <strong>{Number(structured.deal_score).toFixed(0)}/100</strong>
              {structured.deal_rating ? ` (${structured.deal_rating})` : ""}
            </p>
          )}

          <div className="structured-columns">
            {strengths.length > 0 && (
              <div>
                <h4>Strengths</h4>
                <ul>
                  {strengths.map((s) => (
                    <li key={s} className="pos">
                      + {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {risks.length > 0 && (
              <div>
                <h4>Risks</h4>
                <ul>
                  {risks.map((r) => (
                    <li key={r} className="neg">
                      − {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {diligence.length > 0 && (
              <div>
                <h4>Due diligence</h4>
                <ul>
                  {diligence.map((d) => (
                    <li key={d}>· {d}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {structured.recommendation && (
            <div className="recommendation">
              <strong>Recommendation</strong>
              <p>{structured.recommendation}</p>
            </div>
          )}
        </div>
      )}

      <div className="answer-block">
        <h4>Answer</h4>
        <pre className="answer-text">{result.answer ?? ""}</pre>
      </div>

      {citations.length > 0 && (
        <div className="citations">
          <h4>Citations / evidence</h4>
          <div className="citation-list">
            {citations.map((c, idx) => (
              <div className="citation-card" key={`${c.source_id ?? "c"}-${idx}`}>
                <div className="citation-head">
                  <span className={kindClass(c.kind || "document")}>
                    {c.kind || "document"}
                  </span>
                  <span className="citation-title">
                    {c.title || c.source_id || `source ${idx + 1}`}
                  </span>
                  <span className="muted">
                    score{" "}
                    {typeof c.score === "number"
                      ? c.score.toFixed(2)
                      : String(c.score ?? "")}
                    {c.page_number != null ? ` · p.${c.page_number}` : ""}
                  </span>
                </div>
                {c.excerpt && (
                  <p className="citation-excerpt">{c.excerpt}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
