import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
        <h1>Foreclosure Intelligence</h1>
        <p>Find and analyze auction properties.</p>
      </header>

      {/* Dashboard summary cards */}
      <div className="summary-grid">
        <div className="summary-card">
          <span>Total properties</span>
          <h2>{summary.total_properties}</h2>
        </div>

        <div className="summary-card">
          <span>Upcoming auctions</span>
          <h2>{summary.upcoming_auctions}</h2>
        </div>

        <div className="summary-card">
          <span>Properties with potential discounts</span>
          <h2>{summary.properties_with_estimates}</h2>
        </div>
      </div>

      <form className="filters" onSubmit={handleSearch}></form>
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
          <option value="price">Price</option>
          <option value="bedrooms">Bedrooms</option>
          <option value="bathrooms">Bathrooms</option>
          <option value="area_sqft">Area</option>
        </select>

        <select value={order} onChange={(e) => setOrder(e.target.value)}>
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
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

          <div className="property-grid">
            {properties.map((property) => (
              <Link
                to={`/properties/${property.id}`}
                className="property-card"
                key={property.id}
              >
                <div className="card-top">
                  <span className={`status status-${property.foreclosure_status ?? "unknown"}`}>
                    {property.foreclosure_status ?? "Unknown"}
                  </span>

                  {property.deal_score !== null && (
                    <span className="score">
                      Deal score {property.deal_score.toFixed(0)}
                    </span>
                  )}
                </div>

                <h2 className="property-address">
                  {property.address}
                </h2>

                <div className="property-price">
                  ₹{property.price?.toLocaleString("en-IN") ?? "N/A"}
                </div>

                <div className="property-meta">
                  <span>
                    {property.area_sqft
                      ? `${property.area_sqft.toLocaleString()} sq ft`
                      : "Area N/A"}
                  </span>

                  <span>
                    {property.property_type ?? "Type N/A"}
                  </span>

                  {property.bedrooms !== null && (
                    <span>{property.bedrooms} bed</span>
                  )}
                </div>

                <div className="deal-details">
                  {property.estimated_value !== null && (
                    <div>
                      <span>Estimated value</span>
                      <strong>
                        ₹{property.estimated_value.toLocaleString("en-IN")}
                      </strong>
                    </div>
                  )}

                  {property.discount_percentage !== null && (
                    <div>
                      <span>Discount</span>
                      <strong>
                        {property.discount_percentage.toFixed(1)}%
                      </strong>
                    </div>
                  )}
                </div>

                {property.survey_number && (
                  <div className="survey">
                    Survey No. {property.survey_number}
                  </div>
                )}

                {property.auction_date && (
                  <div className="auction">
                    Auction: {property.auction_date}
                  </div>
                )}

                <div className="card-footer">
                  View property →
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