import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";
import { analyzeInvestment, getPropertyEvidence, getPropertyDeal } from "../api/rag";
import type { EvidenceItem, DealIntelligence, RAGResponse } from "../api/types";
import RagResult from "../components/RagResult";
import type { DocumentItem } from "../api/types";
import { useAnalyst } from "../context/AnalystContext";

function formatINR(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "N/A";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  return `₹${n.toLocaleString("en-IN")}`;
}

function deduplicateDocuments(items: DocumentItem[]): DocumentItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    let sourceUrl = (item.source_url || "").trim();
    try {
      const parsed = new URL(sourceUrl);
      parsed.hash = "";
      parsed.hostname = parsed.hostname.toLowerCase();
      sourceUrl = parsed.toString();
    } catch {
      sourceUrl = sourceUrl.split("#", 1)[0];
    }

    // Title is part of the identity because some auction portals serve many
    // distinct notices from the same generic endpoint URL.
    const key = [
      sourceUrl,
      item.source_name,
      item.document_type,
      item.title || "",
    ].join("\u001f");

    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

interface Property {
  id: number;
  address: string;
  city?: string | null;
  locality?: string | null;
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
  bank_name?: string | null; branch_name?: string | null; possession_type?: string | null;
  property_unique_id?: string | null; auction_id?: string | null; property_images?: string[] | null;
  auction_start?: string | null; auction_end?: string | null; emd_deadline?: string | null;
  inspection_start?: string | null; inspection_end?: string | null; listing_url?: string | null;
  district?: string | null; state?: string | null; pincode?: string | null;
  property_sub_type?: string | null; increment_amount?: number | null;
  extra_data?: Record<string, unknown> | null;
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
  const { openAnalyst } = useAnalyst();

  const [property, setProperty] = useState<Property | null>(null);
  const [analysis, setAnalysis] = useState<PropertyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [, setAnalysisLoading] = useState(true);
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
  const [, setEvidence] = useState<EvidenceItem[]>([]);
  const [, setDealIntel] = useState<DealIntelligence | null>(null);

  const [favorites, setFavorites] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem("fc_favorites");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const isFavorited = id ? favorites.includes(Number(id)) : false;

  function toggleFavorite() {
    if (!id) return;
    const numId = Number(id);
    setFavorites((prev) => {
      const next = prev.includes(numId) ? prev.filter((item) => item !== numId) : [...prev, numId];
      localStorage.setItem("fc_favorites", JSON.stringify(next));
      return next;
    });
  }




  useEffect(() => {
    if (!id) return;

    getPropertyEvidence(Number(id))
      .then(setEvidence)
      .catch(() => setEvidence([]));

    getPropertyDeal(Number(id))
      .then(setDealIntel)
      .catch(() => setDealIntel(null));

    api.get<Array<{
      estimated_value: number | string;
      valuation_method: string;
      confidence: number | string | null;
    }>>("/properties/" + id + "/valuations")
      .then((response) => {
        const latest = response.data[0];
        setMarketValuation(latest ? {
          estimated_value: Number(latest.estimated_value),
          valuation_method: latest.valuation_method,
          confidence: latest.confidence == null ? null : Number(latest.confidence),
        } : null);
      })
      .catch(() => setMarketValuation(null));
  }, [id]);


  useEffect(() => {
    if (!id) return;
    setDocumentsLoading(true);
    api
      .get<DocumentItem[]>(`/properties/${id}/documents`)
      .then((res) => setDocuments(deduplicateDocuments(res.data)))
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

  useEffect(() => {
    if (!id) return;

    let active = true;
    let inFlight = false;

    async function refreshLiveData() {
      if (!active || inFlight || document.visibilityState === "hidden") return;
      inFlight = true;
      try {
        const results = await Promise.allSettled([
          api.get<Property>("/properties/" + id),
          api.get<PropertyAnalysis>("/properties/" + id + "/analysis"),
          api.get<DocumentItem[]>("/properties/" + id + "/documents"),
          getPropertyEvidence(Number(id)),
          getPropertyDeal(Number(id)),
          api.get<Array<{
            estimated_value: number | string;
            valuation_method: string;
            confidence: number | string | null;
          }>>("/properties/" + id + "/valuations"),
        ]);

        if (!active) return;
        if (results[0].status === "fulfilled") setProperty(results[0].value.data);
        if (results[1].status === "fulfilled") setAnalysis(results[1].value.data);
        if (results[2].status === "fulfilled") {
          setDocuments(deduplicateDocuments(results[2].value.data));
          setDocumentsLoading(false);
        }
        if (results[3].status === "fulfilled") setEvidence(results[3].value);
        if (results[4].status === "fulfilled") setDealIntel(results[4].value);
        if (results[5].status === "fulfilled") {
          const latest = results[5].value.data[0];
          setMarketValuation(latest ? {
            estimated_value: Number(latest.estimated_value),
            valuation_method: latest.valuation_method,
            confidence: latest.confidence == null ? null : Number(latest.confidence),
          } : null);
        }
      } catch (err) {
        console.error("Property refresh failed.", err);
      } finally {
        inFlight = false;
      }
    }

    const timer = window.setInterval(() => { void refreshLiveData(); }, 30_000);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") void refreshLiveData();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      active = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
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
        <div className="navbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 12 }}>
          <Link to="/dashboard">← Back to Feed</Link>
          <Link to="/research">Research AI</Link>
          <Link to="/admin/import">Bank Sources</Link>
        </div>

        <button
          type="button"
          onClick={toggleFavorite}
          style={{
            background: isFavorited ? "#f43f5e" : "var(--bg-surface)",
            color: isFavorited ? "#ffffff" : "var(--text-primary)",
            border: "1px solid var(--border-subtle)",
            borderRadius: 999,
            padding: "8px 16px",
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            transition: "all 0.2s ease",
          }}
        >
          <span>{isFavorited ? "❤️ Saved to Favorites" : "🤍 Save to Favorites"}</span>
        </button>
      </div>
      </div>
    );
  }

  const listingWebsiteUrl =
    property?.listing_url ||
    documents?.find((d) => d.source_url)?.source_url ||
    (property as any)?.source_url ||
    property?.extra_data?.listingUrl ||
    property?.extra_data?.source_url ||
    property?.extra_data?.detailUrl;

  return (
    <div className="page">
      <div className="navbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 12 }}>
          <Link to="/dashboard">← Back to Feed</Link>
          <Link to="/research">Research AI</Link>
          <Link to="/admin/import">Bank Sources</Link>
        </div>

        <button
          type="button"
          onClick={toggleFavorite}
          style={{
            background: isFavorited ? "#f43f5e" : "var(--bg-surface)",
            color: isFavorited ? "#ffffff" : "var(--text-primary)",
            border: "1px solid var(--border-subtle)",
            borderRadius: 999,
            padding: "8px 16px",
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            transition: "all 0.2s ease",
          }}
        >
          <span>{isFavorited ? "❤️ Saved to Favorites" : "🤍 Save to Favorites"}</span>
        </button>
      </div>

      <div className="bn-detail-hero">
        <div className="bn-detail-meta-bar">
          <span className="bn-bank-badge">
            🏦 BAANKNET LOT #{property.id}
          </span>
          <div className="bn-ribbon-badges">
            <span className="bn-pill bn-pill-type">
              🏡 {property.property_type ?? "Property"}
            </span>
            {property.auction_date && (
              <span className="bn-pill bn-pill-auction-date">
                📅 Auction: {property.auction_date}
              </span>
            )}
            <span className="bn-pill bn-pill-possession">
              🛡️ {property.foreclosure_status === "scheduled" ? "SARFAESI Scheduled" : (property.foreclosure_status ?? "Active")}
            </span>
            {analysis?.deal_score != null && (
              <span className="bn-pill" style={{ background: "#f5f3ff", color: "#6d28d9", border: "1px solid #ddd6fe" }}>
                ⭐ Deal score: {analysis.deal_score}
              </span>
            )}
          </div>
        </div>

        <h1 className="bn-detail-title">{property.address}</h1>
        <p className="muted">{[property.locality, property.city, property.district, property.state, property.pincode].filter(Boolean).join(", ")}</p>

        {property.property_images && property.property_images.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10, margin: "18px 0" }}>
            {property.property_images.map((src, index) => <a key={src} href={src} target="_blank" rel="noreferrer" style={{ display: "block", height: 180, overflow: "hidden", borderRadius: 10, background: "var(--bg-input)" }}><img src={src} alt={`Property view ${index + 1}`} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} /></a>)}
          </div>
        )}

        <div className="bn-detail-kpi-ribbon">
          <div className="bn-detail-kpi-item">
            <span>Reserve Price</span>
            <strong>{formatINR(property.reserve_price)}</strong>
          </div>

          <div className="bn-detail-kpi-item">
            <span>EMD (10%)</span>
            <strong>{formatINR(property.emd)}</strong>
          </div>

          <div className="bn-detail-kpi-item">
            <span>Super Built-up / Land Area</span>
            <strong>{property.area_sqft ? `${property.area_sqft.toLocaleString()} sq ft` : "As per notice"}</strong>
          </div>

          <div className="bn-detail-kpi-item">
            <span>Survey / Khasra No</span>
            <strong>{property.survey_number ?? "Refer Title"}</strong>
          </div>
        </div>

        <section className="official-particulars-section">
          <h3>Official auction particulars</h3>
          <div className="info-grid">
            <div><strong>Bank</strong><span>{property.bank_name || "Not disclosed"}</span></div>
            <div><strong>Branch</strong><span>{property.branch_name || "Not disclosed"}</span></div>
            <div><strong>Property / auction ID</strong><span>{property.property_unique_id || property.auction_id || "Not provided"}</span></div>
            <div><strong>Possession</strong><span>{property.possession_type || "Not specified"}</span></div>
            <div><strong>Reserve price</strong><span>{formatINR(property.reserve_price)}</span></div>
            <div><strong>EMD</strong><span>{formatINR(property.emd)}</span></div>
            <div><strong>Increment</strong><span>{formatINR(property.increment_amount)}</span></div>
            <div><strong>Auction starts</strong><span>{property.auction_start ? new Date(property.auction_start).toLocaleString("en-IN") : property.auction_date || "Not specified"}</span></div>
            <div><strong>Auction ends</strong><span>{property.auction_end ? new Date(property.auction_end).toLocaleString("en-IN") : "Not specified"}</span></div>
            <div><strong>EMD deadline</strong><span>{property.emd_deadline ? new Date(property.emd_deadline).toLocaleString("en-IN") : "Not specified"}</span></div>
            <div><strong>Inspection window</strong><span>{property.inspection_start || property.inspection_end ? `${property.inspection_start ? new Date(property.inspection_start).toLocaleString("en-IN") : "—"} – ${property.inspection_end ? new Date(property.inspection_end).toLocaleString("en-IN") : "—"}` : "Not specified"}</span></div>
            <div><strong>Property subtype</strong><span>{property.property_sub_type || "Not specified"}</span></div>
            <div><strong>Listing title</strong><span>{String(property.extra_data?.propertyHeading ?? "Not provided")}</span></div>
            <div><strong>Project</strong><span>{String(property.extra_data?.projectName ?? "Not specified")}</span></div>
            <div><strong>Furnishing</strong><span>{String(property.extra_data?.furnishedStatus ?? "Not specified")}</span></div>
            <div><strong>Carpet area</strong><span>{property.extra_data?.carpetAreaSqft != null ? `${String(property.extra_data.carpetAreaSqft)} sq ft` : "Not specified"}</span></div>
            <div><strong>Built-up area</strong><span>{property.extra_data?.builtupAreaSqft != null ? `${String(property.extra_data.builtupAreaSqft)} sq ft` : "Not specified"}</span></div>
            <div><strong>Type of action</strong><span>{String(property.extra_data?.typeOfAction ?? "Not specified")}</span></div>
            <div><strong>Branch address</strong><span>{String(property.extra_data?.branchAddress ?? "Not provided")}</span></div>
          </div>
          {listingWebsiteUrl && (
            <div style={{ marginTop: 20 }}>
              <a
                href={listingWebsiteUrl}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 18px",
                  borderRadius: 8,
                  background: "var(--accent-primary, #2563eb)",
                  color: "#ffffff",
                  fontWeight: 700,
                  fontSize: 14,
                  textDecoration: "none",
                }}
              >
                🌐 Open Bank Listing Website ↗
              </a>
            </div>
          )}
        </section>

        <section className="official-documents-section">
          <h3>Official auction documents</h3>
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
                const directSourceLink = listingWebsiteUrl || doc.source_url;
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
                      {directSourceLink && (
                        <a
                          className="doc-btn secondary"
                          href={directSourceLink}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Source link ↗
                        </a>
                      )}
                      {!pdfHref && !directSourceLink && (
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
        </section>
      </div>

      <div className="property-valuation-container analysis-container">
        <div className="valuation-tool-card" style={{ marginBottom: 24 }}>
          <h3>Market valuation</h3>

          <p className="muted">
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
            <div className="analysis-grid" style={{ marginTop: 16 }}>
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

        <div className="investment-tool-card">
          <div className="section-header-row">
            <h3>Is this worth a closer look?</h3>
            <button
              onClick={handleInvestmentAnalysis}
              disabled={investmentLoading}
            >
              {investmentLoading ? "Looking at the file…" : "Write investment note"}
            </button>
            <button
              type="button"
              className="desk-btn-primary"
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 8, fontSize: 13 }}
              onClick={() => openAnalyst(Number(id), property?.address, "Is this property a good foreclosure investment?")}
            >
              🤖 Open Contextual Research Analyst
            </button>
          </div>
          <p className="muted">
            Uses the notice, property details, and valuation comparables stored for this lot.
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
      </div>

    </div>
  );
}

export default PropertyDetails;