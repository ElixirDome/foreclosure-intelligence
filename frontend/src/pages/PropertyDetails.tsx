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
}

function PropertyDetails() {
  const { id } = useParams();

  const [property, setProperty] = useState<Property | null>(null);
  const [analysis, setAnalysis] = useState<PropertyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [error, setError] = useState("");

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
    </div>
  );
}

export default PropertyDetails;