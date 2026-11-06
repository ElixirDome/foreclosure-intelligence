import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";
import { analyzeInvestment, getPropertyEvidence, getPropertyDeal } from "../api/rag";
import type { EvidenceItem, DealIntelligence, RAGResponse, DocumentItem, PropertyAnalysis } from "../api/types";
import RagResult from "../components/RagResult";
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
  estimated_value?: number | null;
  property_type: string | null;
  survey_number: string | null;
  bank_name?: string | null;
  branch_name?: string | null;
  possession_type?: string | null;
  property_unique_id?: string | null;
  auction_id?: string | null;
  property_images?: string[] | null;
  auction_start?: string | null;
  auction_end?: string | null;
  emd_deadline?: string | null;
  inspection_start?: string | null;
  inspection_end?: string | null;
  listing_url?: string | null;
  district?: string | null;
  state?: string | null;
  pincode?: string | null;
  property_sub_type?: string | null;
  increment_amount?: number | null;
  extra_data?: Record<string, unknown> | null;
}

function PropertyDetails() {
  const { id } = useParams();
  const { openAnalyst } = useAnalyst();

  const [property, setProperty] = useState<Property | null>(null);
  const [analysis, setAnalysis] = useState<PropertyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [investmentResult, setInvestmentResult] = useState<RAGResponse | null>(null);
  const [investmentLoading, setInvestmentLoading] = useState(false);
  const [investmentError, setInvestmentError] = useState("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [, setEvidence] = useState<EvidenceItem[]>([]);
  const [dealIntel, setDealIntel] = useState<DealIntelligence | null>(null);

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
        question: `Is property ${id} a good foreclosure investment? What are the key red flags and legal considerations?`,
      });
      setInvestmentResult(result);
    } catch (err) {
      console.error(err);
      setInvestmentError("Could not run investment analysis.");
    } finally {
      setInvestmentLoading(false);
    }
  }

  useEffect(() => {
    async function loadProperty() {
      try {
        setLoading(true);
        setError("");

        const response = await api.get<Property>(`/properties/${id}`);
        setProperty(response.data);
      } catch (err) {
        console.error(err);
        setError("Could not load property details.");
      } finally {
        setLoading(false);
      }
    }

    async function loadAnalysis() {
      try {
        const response = await api.get<PropertyAnalysis>(
          `/properties/${id}/analysis`
        );
        setAnalysis(response.data);
      } catch (err) {
        console.error(err);
      }
    }

    if (id) {
      loadProperty();
      loadAnalysis();
    }
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
    return (
      <div className="page">
        <p className="loading">Loading property #{id}…</p>
      </div>
    );
  }

  if (error || !property) {
    return (
      <div className="page">
        <p className="error">{error || "Property not found."}</p>
        <Link to="/dashboard">← Back to listings</Link>
      </div>
    );
  }

  const listingWebsiteUrl =
    property?.listing_url ||
    (property as any)?.source_url ||
    property?.extra_data?.listingUrl ||
    property?.extra_data?.source_url ||
    property?.extra_data?.detailUrl;

  const assessmentLabel = analysis?.assessment_label || dealIntel?.assessment_label || "Further investigation required";

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
            <span
              className="bn-pill"
              style={{
                background:
                  assessmentLabel === "No major concerns identified in the available documents"
                    ? "#ecfdf5"
                    : assessmentLabel === "Important risks identified"
                      ? "#fef2f2"
                      : assessmentLabel === "Insufficient information"
                        ? "#fffbeb"
                        : "#eff6ff",
                color:
                  assessmentLabel === "No major concerns identified in the available documents"
                    ? "#065f46"
                    : assessmentLabel === "Important risks identified"
                      ? "#991b1b"
                      : assessmentLabel === "Insufficient information"
                        ? "#92400e"
                        : "#1e40af",
                border: "1px solid currentColor",
                fontWeight: 600,
              }}
            >
              🛡️ {assessmentLabel}
            </span>
          </div>
        </div>

        <h1 className="bn-detail-title">{property.address}</h1>
        <p className="muted">{[property.locality, property.city, property.district, property.state, property.pincode].filter(Boolean).join(", ")}</p>

        {property.property_images && property.property_images.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10, margin: "18px 0" }}>
            {property.property_images.map((src, index) => (
              <a key={src} href={src} target="_blank" rel="noreferrer" style={{ display: "block", height: 180, overflow: "hidden", borderRadius: 10, background: "var(--bg-input)" }}>
                <img src={src} alt={`Property view ${index + 1}`} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </a>
            ))}
          </div>
        )}

        <div className="bn-detail-kpi-ribbon">
          <div className="bn-detail-kpi-item">
            <span>Reserve Price</span>
            <strong>{formatINR(property.reserve_price)}</strong>
          </div>

          <div className="bn-detail-kpi-item">
            <span>EMD ({analysis?.emd_percentage != null ? `${analysis.emd_percentage.toFixed(1)}%` : "10%"})</span>
            <strong>{formatINR(property.emd)}</strong>
          </div>

          <div className="bn-detail-kpi-item">
            <span>Reserve Price / Sq Ft</span>
            <strong>
              {analysis?.reserve_price_per_sqft != null
                ? `₹${analysis.reserve_price_per_sqft.toLocaleString()}/sq ft`
                : property.reserve_price && property.area_sqft
                  ? `₹${Math.round(property.reserve_price / property.area_sqft).toLocaleString()}/sq ft`
                  : "Area not specified"}
            </strong>
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

        {/* Four Structured Intelligence Sections */}
        <section className="official-particulars-section" style={{ marginTop: 24 }}>
          <h3>A. Financial Intelligence</h3>
          <div className="info-grid">
            <div><strong>Reserve price</strong><span>{formatINR(property.reserve_price)}</span></div>
            <div><strong>EMD amount</strong><span>{formatINR(property.emd)}</span></div>
            <div><strong>EMD percentage</strong><span>{analysis?.emd_percentage != null ? `${analysis.emd_percentage.toFixed(1)}%` : (property.reserve_price && property.emd ? `${((property.emd / property.reserve_price) * 100).toFixed(1)}%` : "Not calculated")}</span></div>
            <div><strong>Property area</strong><span>{property.area_sqft ? `${property.area_sqft.toLocaleString()} sq ft` : "Not specified"}</span></div>
            <div><strong>Reserve rate / sq ft</strong><span>{analysis?.reserve_price_per_sqft != null ? `₹${analysis.reserve_price_per_sqft.toLocaleString()} / sq ft` : "Not specified"}</span></div>
            <div><strong>Disclosed outstanding dues</strong><span>{String(analysis?.disclosed_outstanding_dues || property.extra_data?.borrowerDues || property.extra_data?.outstandingDues || "None disclosed in notice")}</span></div>
            <div><strong>Increment amount</strong><span>{formatINR(property.increment_amount)}</span></div>
          </div>
          <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--bg-input, #f3f4f6)", borderRadius: 8, fontSize: 13, color: "var(--text-secondary, #4b5563)" }}>
            ℹ️ <strong>Market Valuation:</strong> Market valuation unavailable — verified comparable transaction data is not available.
          </div>
        </section>

        <section className="official-particulars-section" style={{ marginTop: 24 }}>
          <h3>B. Auction Intelligence</h3>
          <div className="info-grid">
            <div><strong>Bank name</strong><span>{property.bank_name || "Not disclosed"}</span></div>
            <div><strong>Branch</strong><span>{property.branch_name || "Not disclosed"}</span></div>
            <div><strong>Procedural auction status</strong><span>{property.foreclosure_status || "Scheduled"}</span></div>
            <div><strong>Auction starts</strong><span>{property.auction_start ? new Date(property.auction_start).toLocaleString("en-IN") : property.auction_date || "Not specified"}</span></div>
            <div><strong>Auction ends</strong><span>{property.auction_end ? new Date(property.auction_end).toLocaleString("en-IN") : "Not specified"}</span></div>
            <div><strong>EMD deadline</strong><span>{property.emd_deadline ? new Date(property.emd_deadline).toLocaleString("en-IN") : "Not specified"}</span></div>
            <div><strong>Inspection window</strong><span>{property.inspection_start || property.inspection_end ? `${property.inspection_start ? new Date(property.inspection_start).toLocaleString("en-IN") : "—"} – ${property.inspection_end ? new Date(property.inspection_end).toLocaleString("en-IN") : "—"}` : "Not specified"}</span></div>
            <div><strong>Auction platform / portal</strong><span>{String(analysis?.auction_platform || property.extra_data?.auctionPlatform || "e-Auction portal")}</span></div>
            <div><strong>Contact details</strong><span>{String(analysis?.contact_details || property.extra_data?.contactPerson || property.extra_data?.branchAddress || "Refer bank notice")}</span></div>
          </div>
          {listingWebsiteUrl && (
            <div style={{ marginTop: 16 }}>
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
                  background: "var(--accent-blue, #0095f6)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: 14,
                  textDecoration: "none",
                }}
              >
                Open Bank Listing Website
              </a>
            </div>
          )}
        </section>

        <section className="official-particulars-section" style={{ marginTop: 24 }}>
          <h3>C. Property and Legal Intelligence</h3>
          <div className="info-grid">
            <div><strong>Possession type</strong><span>{property.possession_type || analysis?.possession_type || "Not specified"}</span></div>
            <div><strong>Disclosed encumbrances</strong><span>{analysis?.disclosed_encumbrances && analysis.disclosed_encumbrances.length > 0 ? analysis.disclosed_encumbrances.join("; ") : "None disclosed by bank"}</span></div>
            <div><strong>Pending litigation</strong><span>{analysis?.pending_litigation && analysis.pending_litigation.length > 0 ? analysis.pending_litigation.join("; ") : "None mentioned in document"}</span></div>
            <div><strong>Title considerations</strong><span>{analysis?.title_concerns && analysis.title_concerns.length > 0 ? analysis.title_concerns.join("; ") : "No title defects disclosed in notice"}</span></div>
            <div><strong>Property discrepancies</strong><span>{analysis?.property_discrepancies && analysis.property_discrepancies.length > 0 ? analysis.property_discrepancies.join("; ") : "None noted"}</span></div>
          </div>
          <div style={{ marginTop: 14 }}>
            <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Important Conditions Specified by Bank:</h4>
            <ul style={{ paddingLeft: 18, fontSize: 13, color: "var(--text-secondary, #4b5563)", margin: 0 }}>
              <li>Sold on "As is where is, as is what is, and whatever there is" basis.</li>
              <li>Successful bidder must deposit 25% of purchase price (inclusive of EMD) on auction day or next working day.</li>
              <li>Balance 75% payable within 15 days of confirmation of sale.</li>
              <li>All statutory dues, stamp duty, transfer charges, and registration fees to be borne by purchaser.</li>
            </ul>
          </div>
        </section>

        <section className="official-particulars-section" style={{ marginTop: 24 }}>
          <h3>D. Transparent Assessment</h3>
          <div style={{ marginBottom: 12 }}>
            <span
              style={{
                display: "inline-block",
                padding: "6px 12px",
                borderRadius: 6,
                fontWeight: 700,
                fontSize: 14,
                background:
                  assessmentLabel === "No major concerns identified in the available documents"
                    ? "#ecfdf5"
                    : assessmentLabel === "Important risks identified"
                      ? "#fef2f2"
                      : assessmentLabel === "Insufficient information"
                        ? "#fffbeb"
                        : "#eff6ff",
                color:
                  assessmentLabel === "No major concerns identified in the available documents"
                    ? "#065f46"
                    : assessmentLabel === "Important risks identified"
                      ? "#991b1b"
                      : assessmentLabel === "Insufficient information"
                        ? "#92400e"
                        : "#1e40af",
              }}
            >
              Assessment Label: {assessmentLabel}
            </span>
          </div>

          {analysis?.important_concerns && analysis.important_concerns.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <strong style={{ fontSize: 13 }}>Important concerns identified:</strong>
              <ul style={{ paddingLeft: 18, fontSize: 13, margin: "4px 0" }}>
                {analysis.important_concerns.map((c) => <li key={c}>{c}</li>)}
              </ul>
            </div>
          )}

          {analysis?.missing_information && analysis.missing_information.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <strong style={{ fontSize: 13 }}>Missing information in notice:</strong>
              <ul style={{ paddingLeft: 18, fontSize: 13, margin: "4px 0" }}>
                {analysis.missing_information.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </div>
          )}

          {analysis?.possession_concerns && analysis.possession_concerns.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <strong style={{ fontSize: 13 }}>Possession considerations:</strong>
              <ul style={{ paddingLeft: 18, fontSize: 13, margin: "4px 0" }}>
                {analysis.possession_concerns.map((p) => <li key={p}>{p}</li>)}
              </ul>
            </div>
          )}
        </section>

        <section className="official-documents-section" style={{ marginTop: 24 }}>
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
                          Listing Page
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
        <div className="investment-tool-card">
          <div className="section-header-row">
            <h3>AI Underwriting and Due Diligence Assessment</h3>
            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={handleInvestmentAnalysis}
                disabled={investmentLoading}
              >
                {investmentLoading ? "Analyzing notice…" : "Run AI Underwriting"}
              </button>
              <button
                type="button"
                className="desk-btn-primary"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 8, fontSize: 13 }}
                onClick={() => openAnalyst(Number(id), property?.address, "What should I look for and are there any red flags for this property?")}
              >
                Ask Analyst in Chat
              </button>
            </div>
          </div>
          <p className="muted">
            Grounds analysis strictly in the original auction document and deterministic calculations. Distinguishes stated facts, calculated values, and inferred risks.
          </p>
          {investmentError && <p className="error">{investmentError}</p>}
          {investmentResult && <RagResult result={investmentResult} />}
          {!investmentResult && !investmentLoading && (
            <p className="muted">
              Click "Run AI Underwriting" for a concise SWOT note, or ask specific follow-up questions to the analyst.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default PropertyDetails;
