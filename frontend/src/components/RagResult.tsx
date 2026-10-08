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
  const structured = result.structured;

  return (
    <div className="rag-result">
      <div className="rag-meta">
        <span className="badge">{result.method}</span>
        <span className="muted">
          {result.context_kinds?.length
            ? result.context_kinds.join(" · ")
            : "no sources"}
        </span>
        <span className="muted">{result.chunks_used} doc chunks</span>
      </div>

      {structured && (
        <div className="structured-panel">
          <p className="structured-summary">{structured.summary}</p>

          {structured.deal_score != null && (
            <p className="deal-score-line">
              Deal score: <strong>{structured.deal_score.toFixed(0)}/100</strong>
              {structured.deal_rating ? ` (${structured.deal_rating})` : ""}
            </p>
          )}

          <div className="structured-columns">
            {structured.strengths?.length > 0 && (
              <div>
                <h4>Strengths</h4>
                <ul>
                  {structured.strengths.map((s) => (
                    <li key={s} className="pos">
                      + {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {structured.risks?.length > 0 && (
              <div>
                <h4>Risks</h4>
                <ul>
                  {structured.risks.map((r) => (
                    <li key={r} className="neg">
                      − {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {structured.due_diligence?.length > 0 && (
              <div>
                <h4>Due diligence</h4>
                <ul>
                  {structured.due_diligence.map((d) => (
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
        <pre className="answer-text">{result.answer}</pre>
      </div>

      {result.citations?.length > 0 && (
        <div className="citations">
          <h4>Citations / evidence</h4>
          <div className="citation-list">
            {result.citations.map((c, idx) => (
              <div className="citation-card" key={`${c.source_id}-${idx}`}>
                <div className="citation-head">
                  <span className={kindClass(c.kind)}>{c.kind}</span>
                  <span className="citation-title">
                    {c.title || c.source_id || `source ${idx + 1}`}
                  </span>
                  <span className="muted">
                    score {c.score?.toFixed?.(2) ?? c.score}
                    {c.page_number != null ? ` · p.${c.page_number}` : ""}
                  </span>
                </div>
                <p className="citation-excerpt">{c.excerpt}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
