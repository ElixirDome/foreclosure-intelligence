import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";

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

  const history = [...valuations].sort(
    (a, b) => a.valuation_date.localeCompare(b.valuation_date) || a.id - b.id
  );
  const chartWidth = 720;
  const chartHeight = 250;
  const chartPadding = { top: 20, right: 24, bottom: 44, left: 78 };
  const plotWidth = chartWidth - chartPadding.left - chartPadding.right;
  const plotHeight = chartHeight - chartPadding.top - chartPadding.bottom;
  const historyValues = history.map((item) => item.estimated_value);
  const minValue = historyValues.length ? Math.min(...historyValues) : 0;
  const maxValue = historyValues.length ? Math.max(...historyValues) : 0;
  const valueRange = maxValue - minValue || Math.max(Math.abs(maxValue) * 0.1, 1);
  const chartMinValue = maxValue === minValue ? minValue - valueRange / 2 : minValue;
  const chartMaxValue = maxValue === minValue ? maxValue + valueRange / 2 : maxValue;
  const chartValueRange = chartMaxValue - chartMinValue;
  const chartPoints = history.map((item, index) => ({
    ...item,
    x: chartPadding.left + (
      history.length === 1 ? plotWidth / 2 : index * plotWidth / (history.length - 1)
    ),
    y: chartPadding.top + plotHeight - (
      (item.estimated_value - chartMinValue) / chartValueRange
    ) * plotHeight,
  }));

  if (loading) {
    return <div className="page">Loading property...</div>;
  }

  if (error || !property) {
    return (
      <div className="page">
        <p className="error">
          {error || "Property not found."}
        </p>
        <Link to="/dashboard">← Back to properties</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <Link to="/dashboard">← Back to properties</Link>

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
      {/* Valuation history */}
      <div className="analysis-container">
        <h2>Valuation history</h2>

        {valuationsLoading && <p>Loading valuations...</p>}

        {!valuationsLoading && valuations.length === 0 && (
          <p>No valuation records available.</p>
        )}

        {!valuationsLoading && valuations.length > 0 && (
          <>
            <div className="analysis-card" role="img" aria-label="Valuation history line chart">
              <svg
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                width="100%"
                style={{ display: "block", maxWidth: "100%" }}
                aria-hidden="true"
              >
                {[0, 0.5, 1].map((fraction) => {
                  const y = chartPadding.top + plotHeight * fraction;
                  const value = chartMaxValue - chartValueRange * fraction;
                  return (
                    <g key={fraction}>
                      <line
                        x1={chartPadding.left}
                        y1={y}
                        x2={chartWidth - chartPadding.right}
                        y2={y}
                        stroke="currentColor"
                        opacity="0.16"
                      />
                      <text
                        x={chartPadding.left - 10}
                        y={y + 4}
                        textAnchor="end"
                        fill="currentColor"
                        fontSize="11"
                      >
                        ₹{Math.round(value).toLocaleString("en-IN")}
                      </text>
                    </g>
                  );
                })}
                {chartPoints.length > 1 && (
                  <polyline
                    points={chartPoints.map((point) => `${point.x},${point.y}`).join(" ")}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                )}
                {chartPoints.map((point) => (
                  <g key={point.id}>
                    <circle cx={point.x} cy={point.y} r="5" fill="currentColor">
                      <title>
                        {point.valuation_date}: ₹{point.estimated_value.toLocaleString("en-IN")}
                      </title>
                    </circle>
                    <text
                      x={point.x}
                      y={chartHeight - 14}
                      textAnchor="middle"
                      fill="currentColor"
                      fontSize="10"
                    >
                      {point.valuation_date}
                    </text>
                  </g>
                ))}
              </svg>
            </div>
            <div className="analysis-grid">
              {history.map((valuation) => (
                <div className="analysis-card" key={valuation.id}>
                  <strong>Estimated value</strong>
                  <span>₹{valuation.estimated_value.toLocaleString("en-IN")}</span>
                  <strong>Method</strong>
                  <span>{valuation.valuation_method}</span>
                  <strong>Source</strong>
                  <span>{valuation.source ?? "N/A"}</span>
                  <strong>Confidence</strong>
                  <span>
                    {valuation.confidence !== null
                      ? `${(valuation.confidence * 100).toFixed(0)}%`
                      : "N/A"}
                  </span>
                  <strong>Date</strong>
                  <span>{valuation.valuation_date}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default PropertyDetails;