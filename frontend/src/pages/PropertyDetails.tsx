import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";
import { analyzeInvestment, getPropertyEvidence, getPropertyDeal } from "../api/rag";
import type { EvidenceItem, DealIntelligence, RAGResponse } from "../api/types";
import RagResult from "../components/RagResult";
import type { DocumentItem } from "../api/types";

function formatINR(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "N/A";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  return `₹${n.toLocaleString("en-IN")}`;
}

interface Property {
  id: number;
  address: string;
  price: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  area_sqft: number | null;
  auction_date: string | null;
  foreclosure_status: string | null;
  opening_bid: number | null;
  reserve_price: number | null;
  emd: number | null;
  estimated_value: number | null;
  property_type: string | null;
  survey_number: string | null;
  discount_percentage: number | null;
  deal_score: number | null;
}
interface PropertyAnalysis {
  estimated_value: number | null;
  opening_bid: number | null;
  reserve_price: number | null;
  emd: number | null;
  discount_amount: number | null;
  discount_percentage: number | null;
  deal_rating: string | null;
  deal_score: number | null;
  valuation_confidence: number | null;
}

function PropertyDetails() {
  const { id } = useParams();

  const [property, setProperty] = useState<Property | null>(null);
  const [analysis, setAnalysis] = useState<PropertyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [error, setError] = useState("");

  const [marketValuation, setMarketValuation] = useState<{
    estimated_value: number;
    valuation_method: string;
    confidence: number | null;
  } | null>(null);

  const [marketValuationLoading, setMarketValuationLoading] = useState(false);
  const [marketValuationError, setMarketValuationError] = useState("");

  const [investmentResult, setInvestmentResult] = useState<RAGResponse | null>(null);
  const [investmentLoading, setInvestmentLoading] = useState(false);
  const [investmentError, setInvestmentError] = useState("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [dealIntel, setDealIntel] = useState<DealIntelligence | null>(null);



  useEffect(() => {
    if (!id) return;

    getPropertyEvidence(Number(id))
      .then(setEvidence)
      .catch(() => setEvidence([]));

    getPropertyDeal(Number(id))
      .then(setDealIntel)
      .catch(() => setDealIntel(null));
  }, [id]);


  useEffect(() => {
    if (!id) return;
    setDocumentsLoading(true);
    api
      .get<DocumentItem[]>(`/properties/${id}/documents`)
      .then((res) => setDocuments(res.data))
      .catch(() => setDocuments([]))
      .finally(() => setDocumentsLoading(false));
  }, [id]);

  async function handleInvestmentAnalysis() {
    if (!id) return;
    try {
      setInvestmentLoading(true);
      setInvestmentError("");
      const result = await analyzeInvestment({
        property_id: Number(id),
        question: `Is property ${id} a good foreclosure investment?`,
      });
      setInvestmentResult(result);
    } catch (err) {
      console.error(err);
      setInvestmentError("Could not run investment analysis.");
    } finally {
      setInvestmentLoading(false);
    }
  }

  async function handleMarketValuation() {
    try {
      setMarketValuationLoading(true);
      setMarketValuationError("");

      const response = await api.post(
        `/properties/${id}/market-valuation`
      );

      setMarketValuation(response.data);

      // Refresh property analysis because the new valuation
      // can affect deal score and confidence.
      const analysisResponse = await api.get<PropertyAnalysis>(
        `/properties/${id}/analysis`
      );
      setAnalysis(analysisResponse.data);

      const [propertyResponse, dealResponse] = await Promise.all([
        api.get<Property>(`/properties/${id}`),
        getPropertyDeal(Number(id)),
      ]);
      setProperty(propertyResponse.data);
      setDealIntel(dealResponse);
    } catch (err) {
      console.error(err);
      setMarketValuationError(
        "Could not calculate market valuation."
      );
    } finally {
      setMarketValuationLoading(false);
    }
  }
  useEffect(() => {
    async function loadProperty() {
      try {
        setLoading(true);
        setError("");

        const response = await api.get<Property>(
          `/properties/${id}`
        );

        setProperty(response.data);
      } catch (err) {
        console.error(err);
        setError("Could not load property.");
      } finally {
        setLoading(false);
      }
    }

    loadProperty();
  }, [id]);

  useEffect(() => {
    async function loadAnalysis() {
      try {
        setAnalysisLoading(true);

        const response = await api.get<PropertyAnalysis>(
          `/properties/${id}/analysis`
        );

        setAnalysis(response.data);
      } catch (err) {
        console.error(err);
      } finally {
        setAnalysisLoading(false);
      }
    }

    loadAnalysis();
  }, [id]);

  if (loading) {
    return <div className="page">Loading property...</div>;
  }

  if (error || !property) {
    return (
      <div className="page">
        <p className="error">
          {error || "Property not found."}
        </p>
        <div className="navbar">
        <Link to="/dashboard">← Properties</Link>
        <Link to="/research">Research</Link>
      </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="navbar">
        <Link to="/dashboard">← Properties</Link>
        <Link to="/research">Research</Link>
      </div>

      <div className="details-container">
        <div className="card-top">
          <span className="status">
            {property.foreclosure_status ?? "Unknown"}
          </span>

          {analysis?.deal_score !== null &&
            analysis?.deal_score !== undefined && (
              <span className="score">
                Deal score: {analysis.deal_score}
              </span>
            )}
        </div>

        <h1>{property.address}</h1>

        <div className="info-grid">
          <div>
            <strong>Property type</strong>
            <span>{property.property_type ?? "N/A"}</span>
          </div>

          <div>
            <strong>Area</strong>
            <span>
              {property.area_sqft
                ? `${property.area_sqft} sq ft`
                : "N/A"}
            </span>
          </div>

          <div>
            <strong>Survey number</strong>
            <span>{property.survey_number ?? "N/A"}</span>
          </div>

          <div>
            <strong>Auction date</strong>
            <span>{property.auction_date ?? "N/A"}</span>
          </div>

          <div>
            <strong>Reserve price</strong>
            <span>{formatINR(property.reserve_price)}</span>
          </div>

          <div>
            <strong>EMD</strong>
            <span>{formatINR(property.emd)}</span>
          </div>
          <div className="analysis-card">
            <strong>Valuation confidence</strong>
            <span>
              {analysis?.valuation_confidence != null
                ? `${(analysis.valuation_confidence * 100).toFixed(0)}%`
                : "N/A"}
            </span>
          </div>
        </div>
      </div>

      <div className="deal-analysis-unified">
        <div className="analysis-container">
        <h2>Deal Analysis</h2>

        {analysisLoading && <p>Calculating analysis...</p>}

        {!analysisLoading && analysis && (
          <div className="analysis-grid">
            <div className="analysis-card">
              <strong>Estimated value</strong>
              <span>
                ₹
                {analysis.estimated_value?.toLocaleString(
                  "en-IN"
                ) ?? "N/A"}
              </span>
            </div>

            <div className="analysis-card">
              <strong>Reserve price</strong>
              <span>{analysis.reserve_price != null ? formatINR(analysis.reserve_price) : "N/A"}</span>
            </div>

            <div className="analysis-card">
              <strong>EMD</strong>
              <span>{analysis.emd != null ? formatINR(analysis.emd) : "N/A"}</span>
            </div>

            <div className="analysis-card">
              <strong>Discount</strong>
              <span>
                {analysis.discount_percentage !== null
                  ? `${analysis.discount_percentage}%`
                  : "N/A"}
              </span>
            </div>

            <div className="analysis-card">
              <strong>Discount amount</strong>
              <span>
                ₹
                {analysis.discount_amount?.toLocaleString(
                  "en-IN"
                ) ?? "N/A"}
              </span>
            </div>

            <div className="analysis-card">
              <strong>Deal rating</strong>
              <span>
                {analysis.deal_rating ?? "N/A"}
              </span>
            </div>

            <div className="analysis-card">
              <strong>Deal score</strong>
              <span>
                {analysis.deal_score ?? "N/A"}
              </span>
            </div>
          </div>
        )}

        {!analysisLoading && !analysis && (
          <p>Analysis unavailable.</p>
        )}
      </div>
      <div className="analysis-container">
        <h2>Market valuation</h2>

        <p>
          Estimate the property's market value using the comparable
          sales already stored in the system.
        </p>

        <button
          onClick={handleMarketValuation}
          disabled={marketValuationLoading}
        >
          {marketValuationLoading
            ? "Calculating..."
            : "Calculate market valuation"}
        </button>

        {marketValuationError && (
          <p className="error">{marketValuationError}</p>
        )}

        {marketValuation && (
          <div className="analysis-grid">
            <div className="analysis-card">
              <strong>Estimated market value</strong>
              <span>
                {formatINR(marketValuation.estimated_value)}
              </span>
            </div>

            <div className="analysis-card">
              <strong>Method</strong>
              <span>{marketValuation.valuation_method}</span>
            </div>

            <div className="analysis-card">
              <strong>Confidence</strong>
              <span>
                {marketValuation.confidence !== null
                  ? `${(marketValuation.confidence * 100).toFixed(0)}%`
                  : "N/A"}
              </span>
            </div>
          </div>
        )}
      </div>
      <div className="analysis-container">
        <div className="section-header-row">
          <h2>Is this worth a closer look?</h2>
          <button
            onClick={handleInvestmentAnalysis}
            disabled={investmentLoading}
          >
            {investmentLoading ? "Looking at the file…" : "Write investment note"}
          </button>
        </div>
        <p className="muted">
          Uses the notice, evidence, comparables, and valuations already stored
          for this lot. Supporting excerpts stay under View evidence.
          {" "}
          <Link to={`/research?property_id=${id}`}>Open in Research →</Link>
        </p>
        {investmentError && <p className="error">{investmentError}</p>}
        {investmentResult && <RagResult result={investmentResult} />}
        {!investmentResult && !investmentLoading && (
          <p className="muted">
            Generate a short note, or use the corner research chat with the same
            questions.
          </p>
        )}
      </div>

      {/* Deal intelligence factors */}
      {dealIntel && (
        <div className="analysis-container">
          <h2>Deal intelligence</h2>
          <div className="analysis-grid">
            <div className="analysis-card">
              <strong>Deal score</strong>
              <span>{dealIntel.deal_score ?? "N/A"}</span>
            </div>
            <div className="analysis-card">
              <strong>Rating</strong>
              <span>{dealIntel.deal_rating ?? "N/A"}</span>
            </div>
            <div className="analysis-card">
              <strong>Comparables</strong>
              <span>{dealIntel.comparable_count}</span>
            </div>
            <div className="analysis-card">
              <strong>Reserve price</strong>
              <span>{dealIntel.reserve_price != null ? formatINR(dealIntel.reserve_price) : "N/A"}</span>
            </div>
            <div className="analysis-card">
              <strong>EMD</strong>
              <span>{dealIntel.emd != null ? formatINR(dealIntel.emd) : "N/A"}</span>
            </div>
            <div className="analysis-card">
              <strong>Comparable-based estimate</strong>
              <span>{dealIntel.estimated_value != null ? formatINR(dealIntel.estimated_value) : "Insufficient evidence"}</span>
            </div>
          </div>
          {dealIntel.factors?.length > 0 && (
            <ul className="factor-list">
              {dealIntel.factors.map((f, i) => (
                <li key={i} className={f.direction === "+" ? "pos" : f.direction === "-" ? "neg" : ""}>
                  {f.direction} {f.label}
                </li>
              ))}
            </ul>
          )}
          {dealIntel.explanation && (
            <pre className="answer-text">{dealIntel.explanation}</pre>
          )}
        </div>
      )}

      
      <div className="analysis-container">
        <h2>Source documents</h2>
        {documentsLoading && <p className="muted">Loading documents…</p>}
        {!documentsLoading && documents.length === 0 && (
          <p className="muted">
            No documents linked to this property yet. Import a sale notice or run
            ingestion to attach PDFs.
          </p>
        )}
        {!documentsLoading && documents.length > 0 && (
          <ul className="document-list">
            {documents.map((doc) => {
              const isPdf =
                (doc.mime_type && doc.mime_type.includes("pdf")) ||
                (doc.filename && doc.filename.toLowerCase().endsWith(".pdf")) ||
                (doc.source_url && doc.source_url.toLowerCase().includes(".pdf"));
              const fileHref = `${api.defaults.baseURL}/documents/${doc.id}/file`;
              const pdfHref =
                isPdf && doc.source_url && doc.source_url.toLowerCase().includes(".pdf")
                  ? doc.source_url
                  : isPdf
                    ? fileHref
                    : null;
              return (
                <li key={doc.id} className="document-row">
                  <div>
                    <strong>
                      {doc.title || doc.filename || doc.document_type}
                    </strong>
                    <div className="muted tiny">
                      {doc.source_name}
                      {doc.document_type ? ` · ${doc.document_type}` : ""}
                      {doc.filename ? ` · ${doc.filename}` : ""}
                    </div>
                  </div>
                  <div className="document-actions">
                    {pdfHref && (
                      <a
                        className="doc-btn"
                        href={pdfHref}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open PDF
                      </a>
                    )}
                    {doc.source_url && (
                      <a
                        className="doc-btn secondary"
                        href={doc.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Source link
                      </a>
                    )}
                    {!pdfHref && !doc.source_url && (
                      <a className="doc-btn secondary" href={fileHref} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Field-level evidence */}
      <div className="analysis-container">
        <h2>Source evidence</h2>
        {evidence.length === 0 && (
          <p className="muted">No field-level evidence linked yet.</p>
        )}
        {evidence.length > 0 && (
          <div className="citation-list">
            {evidence.map((e) => (
              <div className="citation-card" key={e.id}>
                <div className="citation-head">
                  <span className="badge badge-ev">{e.field}</span>
                  <span className="citation-title">{e.value}</span>
                  <span className="muted">
                    doc #{e.document_id}
                    {e.page_number != null ? ` · p.${e.page_number}` : ""}
                    {e.extraction_method ? ` · ${e.extraction_method}` : ""}
                  </span>
                </div>
                {e.source_text && (
                  <p className="citation-excerpt">{e.source_text}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      </div>

    </div>
  );
}

export default PropertyDetails;