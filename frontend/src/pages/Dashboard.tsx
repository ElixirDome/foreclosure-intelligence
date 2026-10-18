import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api/client";

interface PropertySource {
  source_name: string;
  source_url?: string | null;
  document_type?: string | null;
  title?: string | null;
  filename?: string | null;
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
  reserve_price?: number | null;
  emd?: number | null;
  opening_bid: number | null;
  estimated_value: number | null;
  property_type: string | null;
  survey_number: string | null;
  discount_percentage: number | null;
  deal_score: number | null;
  sources?: PropertySource[];
}

interface PropertyResponse {
  items: Property[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

function Dashboard() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem("access_token");
    navigate("/login");
  }
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minArea, setMinArea] = useState("");
  const [maxArea, setMaxArea] = useState("");

  const [bedrooms, setBedrooms] = useState("");
  const [minDiscount, setMinDiscount] = useState("");
  const [maxDiscount, setMaxDiscount] = useState("");
  const [sortBy, setSortBy] = useState("id");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [summary, setSummary] = useState({
    total_properties: 0,
    upcoming_auctions: 0,
    properties_with_estimates: 0,
    residential: 0,
    commercial: 0,
    sold: 0,
  });

  async function loadProperties() {
    try {
      setLoading(true);
      setError("");

      const params: Record<string, string | number> = {
        page,
        limit: 20,
        sort_by: sortBy,
        order,
      };

      if (search.trim()) params.search = search.trim();
      if (minPrice) params.min_price = Number(minPrice);
      if (maxPrice) params.max_price = Number(maxPrice);
      if (minArea) params.min_area = Number(minArea);
      if (maxArea) params.max_area = Number(maxArea);
      if (bedrooms) params.bedrooms = Number(bedrooms);
      if (minDiscount) params.min_discount = Number(minDiscount);
      if (maxDiscount) params.max_discount = Number(maxDiscount);
      if (status) params.foreclosure_status = status;
      if (propertyType) params.property_type = propertyType;

      const response = await api.get<PropertyResponse>(
        "/properties/",
        { params }
      );

      setProperties(response.data.items);
      setTotal(response.data.total);
      setPages(response.data.pages);


    } catch (err) {
      console.error(err);
      setError("Could not load properties.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProperties();
  }, [page]);

  useEffect(() => {
    api.get("/properties/summary")
      .then((response) => setSummary(response.data))
      .catch((err) => console.error("Could not load summary:", err));
  }, []);

  function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    loadProperties();
  }

  function clearFilters() {
    setSearch("");
    setStatus("");
    setPropertyType("");
    setMinPrice("");
    setMaxPrice("");
    setMinArea("");
    setMaxArea("");

    setTimeout(loadProperties, 0);
  }

  return (
    <div className="page">
      <nav className="navbar">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/research">Research</Link>
        <Link to="/admin/import">Import PDF</Link>
        <button onClick={handleLogout}>Logout</button>
      </nav>

      <header className="header">
        <h1>The desk</h1>
        <p>Auction inventory with sources, type, and discount at a glance.</p>
      </header>

      <div className="summary-grid">
        <div className="summary-card">
          <span>Total</span>
          <strong>{summary.total_properties}</strong>
        </div>
        <div className="summary-card">
          <span>Upcoming</span>
          <strong>{summary.upcoming_auctions}</strong>
        </div>
        <div className="summary-card">
          <span>Discounted</span>
          <strong>{summary.properties_with_estimates}</strong>
        </div>
        <div className="summary-card">
          <span>Residential</span>
          <strong>{summary.residential}</strong>
        </div>
        <div className="summary-card">
          <span>Commercial</span>
          <strong>{summary.commercial}</strong>
        </div>
        <div className="summary-card">
          <span>Sold</span>
          <strong>{summary.sold}</strong>
        </div>
      </div>

      <form className="filters" onSubmit={handleSearch}>
        <input
          type="text"
          placeholder="Search address..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="upcoming">Upcoming</option>
          <option value="active">Active</option>
          <option value="sold">Sold</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <input
          type="number"
          min="0"
          placeholder="Bedrooms"
          value={bedrooms}
          onChange={(e) => setBedrooms(e.target.value)}
        />

        <input
          type="number"
          min="0"
          max="100"
          placeholder="Min discount %"
          value={minDiscount}
          onChange={(e) => setMinDiscount(e.target.value)}
        />

        <input
          type="number"
          min="0"
          max="100"
          placeholder="Max discount %"
          value={maxDiscount}
          onChange={(e) => setMaxDiscount(e.target.value)}
        />

        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="id">Date added / ID</option>
          <option value="price">Reserve price</option>
          <option value="bedrooms">Bedrooms</option>
          <option value="bathrooms">Bathrooms</option>
          <option value="area_sqft">Area</option>
        </select>

        <select value={order} onChange={(e) => setOrder(e.target.value)}>
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
        <select
          value={propertyType}
          onChange={(e) => setPropertyType(e.target.value)}
          aria-label="Property type"
        >
          <option value="">All types</option>
          <option value="residential">Residential</option>
          <option value="commercial">Commercial</option>
        </select>

        <button type="submit">Search</button>

        <button
          type="button"
          onClick={clearFilters}
        >
          Clear
        </button>
      </form>

      {loading && <p>Loading properties...</p>}

      {error && <p>{error}</p>}

      {!loading && !error && (
        <>
          <div className="results-header">
            <h2>{total} properties found</h2>
            <p>Page {page} of {Math.max(pages, 1)}</p>
          </div>

          <div className="property-list">
            {properties.map((property) => (
              <Link
                to={`/properties/${property.id}`}
                className="property-row"
                key={property.id}
              >
                <div className="property-row-main">
                  <h3>{property.address}</h3>
                  <div className="property-row-meta">
                    <span className="type-badge">
                      {property.property_type ?? "type n/a"}
                    </span>
                    {property.locality || property.city
                      ? `${property.locality ?? ""}${property.locality && property.city ? ", " : ""}${property.city ?? ""}`
                      : null}
                    {property.area_sqft
                      ? ` · ${property.area_sqft.toLocaleString()} sq ft`
                      : ""}
                    {property.auction_date
                      ? ` · auction ${property.auction_date}`
                      : ""}
                  </div>
                  {property.sources && property.sources.length > 0 && (
                    <div>
                      {property.sources.slice(0, 3).map((src, idx) => {
                        const isPdf =
                          (src.filename && src.filename.toLowerCase().endsWith(".pdf")) ||
                          (src.source_url && src.source_url.toLowerCase().includes(".pdf")) ||
                          (src.document_type && src.document_type.toLowerCase().includes("notice"));
                        return (
                          <span key={idx} className="source-chip">
                            {src.source_url ? (
                              <a
                                href={src.source_url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {src.source_name}
                                {isPdf ? " · PDF" : ""} ↗
                              </a>
                            ) : (
                              <>
                                {src.source_name}
                                {isPdf ? " · PDF" : ""}
                              </>
                            )}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="property-row-side">
                  <div className="price">
                    Reserve ₹{property.reserve_price?.toLocaleString("en-IN") ?? "N/A"}
                  </div>
                  <div className="muted">
                    EMD ₹{property.emd?.toLocaleString("en-IN") ?? "—"}
                  </div>
                  <div className="muted">
                    {property.foreclosure_status ?? "unknown"}
                    {property.discount_percentage != null
                      ? ` · ${property.discount_percentage.toFixed(0)}% under est.`
                      : ""}
                  </div>
                  {property.deal_score != null && (
                    <div className="muted">Deal {property.deal_score.toFixed(0)}</div>
                  )}
                </div>
              </Link>
            ))}
          </div>

          <div className="pagination">
            <button
              type="button"
              disabled={page <= 1 || loading}
              onClick={() => setPage((current) => current - 1)}
            >
              Previous
            </button>

            <span>Page {page} of {Math.max(pages, 1)}</span>

            <button
              type="button"
              disabled={page >= pages || loading}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;