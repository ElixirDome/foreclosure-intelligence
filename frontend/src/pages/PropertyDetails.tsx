import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";
import { analyzeInvestment, getPropertyEvidence, getPropertyDeal } from "../api/rag";
import type { EvidenceItem, DealIntelligence, RAGResponse } from "../api/types";
import RagResult from "../components/RagResult";

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
  estimated_value: number | null;
  property_type: string | null;
  survey_number: string | null;
  discount_percentage: number | null;
  deal_score: number | null;
}
interface PropertyAnalysis {
  estimated_value: number | null;
  opening_bid: number | null;
  discount_amount: number | null;
  discount_percentage: number | null;
  deal_rating: string | null;
  deal_score: number | null;
  valuation_confidence: number | null;
}

interface PropertyValuation {
  id: number;
  property_id: number;
  estimated_value: number;
  valuation_method: string;
  source: string | null;
  confidence: number | null;
  valuation_date: string;
}

function PropertyDetails() {
  const { id } = useParams();

  const [property, setProperty] = useState<Property | null>(null);
  const [analysis, setAnalysis] = useState<PropertyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [error, setError] = useState("");

  const [valuations, setValuations] = useState<PropertyValuation[]>([]);
  const [valuationsLoading, setValuationsLoading] = useState(true);

  const [valuationValue, setValuationValue] = useState("");
  const [valuationMethod, setValuationMethod] = useState("");
  const [valuationSource, setValuationSource] = useState("");
  const [valuationConfidence, setValuationConfidence] = useState("");
  const [valuationSubmitting, setValuationSubmitting] = useState(false);
  const [valuationError, setValuationError] = useState("");

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

  async function handleAddValuation() {
    try {
      setValuationSubmitting(true);
      setValuationError("");

      await api.post(`/properties/${id}/valuations`, {
        estimated_value: Number(valuationValue),
        valuation_method: valuationMethod,
        source: valuationSource || null,
        confidence: valuationConfidence
          ? Number(valuationConfidence)
          : null,
      });

      const response = await api.get<PropertyValuation[]>(
        `/properties/${id}/valuations`
      );

      setValuations(response.data);

      setValuationValue("");
      setValuationMethod("");
      setValuationSource("");
      setValuationConfidence("");
    } catch (err) {
      console.error(err);
      setValuationError("Could not save valuation.");
    } finally {
      setValuationSubmitting(false);
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

  useEffect(() => {
    async function loadValuations() {
      try {
        setValuationsLoading(true);

        const response = await api.get<PropertyValuation[]>(
          `/properties/${id}/valuations`
        );

        setValuations(response.data);
      } catch (err) {
        console.error(err);
      } finally {
        setValuationsLoading(false);
      }
    }

    loadValuations();
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

        <div className="big-price">
          ₹{property.price?.toLocaleString("en-IN") ?? "N/A"}
        </div>

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
            <strong>Opening bid</strong>
            <span>
              ₹
              {property.opening_bid?.toLocaleString("en-IN") ??
                "N/A"}
            </span>
          </div>

          <div>
            <strong>Estimated value</strong>
            <span>
              ₹
              {property.estimated_value?.toLocaleString(
                "en-IN"
              ) ?? "N/A"}
            </span>
          </div>
          <div className="analysis-card">
            <strong>Valuation confidence</strong>
            <span>
              {analysis.valuation_confidence !== null
                ? `${(analysis.valuation_confidence * 100).toFixed(0)}%`
                : "N/A"}
            </span>
          </div>
        </div>
      </div>

      <div className="analysis-container">
        <h2>Deal analysis</h2>

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
              <strong>Opening bid</strong>
              <span>
                ₹
                {analysis.opening_bid?.toLocaleString(
                  "en-IN"
                ) ?? "N/A"}
              </span>
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
                ₹{marketValuation.estimated_value.toLocaleString("en-IN")}
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
      {/* Add valuation */}
      <div className="analysis-container">
        <h2>Add valuation</h2>

        <div className="valuation-form">
          <input
            type="number"
            placeholder="Estimated value"
            value={valuationValue}
            onChange={(e) => setValuationValue(e.target.value)}
          />

          <input
            type="text"
            placeholder="Valuation method"
            value={valuationMethod}
            onChange={(e) => setValuationMethod(e.target.value)}
          />

          <input
            type="text"
            placeholder="Source"
            value={valuationSource}
            onChange={(e) => setValuationSource(e.target.value)}
          />

          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            placeholder="Confidence (0–1)"
            value={valuationConfidence}
            onChange={(e) => setValuationConfidence(e.target.value)}
          />

          <button
            onClick={handleAddValuation}
            disabled={
              valuationSubmitting ||
              !valuationValue ||
              !valuationMethod
            }
          >
            {valuationSubmitting ? "Saving..." : "Add valuation"}
          </button>

          {valuationError && (
            <p className="error">{valuationError}</p>
          )}
        </div>
      </div>

      {/* Multi-source investment analysis (Phase 11 RAG) */}
      <div className="analysis-container">
        <div className="section-header-row">
          <h2>Investment analysis (multi-source RAG)</h2>
          <button
            onClick={handleInvestmentAnalysis}
            disabled={investmentLoading}
          >
            {investmentLoading ? "Analyzing…" : "Run investment analysis"}
          </button>
        </div>
        <p className="muted">
          Pulls auction documents, this property, evidence, comparables,
          valuations, and deal signals into one cited answer.
        </p>
        {investmentError && <p className="error">{investmentError}</p>}
        {investmentResult && <RagResult result={investmentResult} />}
        {!investmentResult && !investmentLoading && (
          <p className="muted">Click the button to generate a structured recommendation.</p>
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

      {/* Valuation history */}
      <div className="analysis-container">
        <h2>Valuation history</h2>

        {valuationsLoading && <p>Loading valuations...</p>}

        {!valuationsLoading && valuations.length === 0 && (
          <p>No valuation records available.</p>
        )}

        {!valuationsLoading && valuations.length > 0 && (
          <div className="analysis-grid">
            {valuations.map((valuation) => (
              <div className="analysis-card" key={valuation.id}>
                <strong>Estimated value</strong>
                <span>
                  ₹{valuation.estimated_value.toLocaleString("en-IN")}
                </span>

                <strong>Method</strong>
                <span>{valuation.valuation_method}</span>

                <strong>Source</strong>
                <span>{valuation.source ?? "N/A"}</span>

                <strong>Confidence</strong>
                <span>
                  {valuation.confidence !== null
                    ? `${valuation.confidence * 100}%`
                    : "N/A"}
                </span>

                <strong>Date</strong>
                <span>{valuation.valuation_date}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default PropertyDetails;