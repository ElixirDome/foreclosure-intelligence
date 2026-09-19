import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minArea, setMinArea] = useState("");
  const [maxArea, setMaxArea] = useState("");

  async function loadProperties() {
    try {
      setLoading(true);
      setError("");

      const params: Record<string, string | number> = {
        page: 1,
        limit: 20,
      };

      if (minPrice) params.min_price = Number(minPrice);
      if (maxPrice) params.max_price = Number(maxPrice);
      if (minArea) params.min_area = Number(minArea);
      if (maxArea) params.max_area = Number(maxArea);
      if (status) params.foreclosure_status = status;

      const response = await api.get<PropertyResponse>(
        "/properties/",
        { params }
      );

      let results = response.data.items;

      /*
        Your backend currently doesn't have an address search parameter,
        so we perform the text search on the returned properties.
      */
      if (search.trim()) {
        const query = search.toLowerCase();

        results = results.filter((property) =>
          property.address.toLowerCase().includes(query)
        );
      }

      setProperties(results);
    } catch (err) {
      console.error(err);
      setError("Could not load properties.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProperties();
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
      <header className="header">
        <h1>Foreclosure Intelligence</h1>
        <p>Find and analyze auction properties.</p>
      </header>

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
          placeholder="Min price"
          value={minPrice}
          onChange={(e) => setMinPrice(e.target.value)}
        />

        <input
          type="number"
          placeholder="Max price"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
        />

        <input
          type="number"
          placeholder="Min area"
          value={minArea}
          onChange={(e) => setMinArea(e.target.value)}
        />

        <input
          type="number"
          placeholder="Max area"
          value={maxArea}
          onChange={(e) => setMaxArea(e.target.value)}
        />

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
            <h2>{properties.length} properties</h2>
          </div>

          <div className="property-grid">
            {properties.map((property) => (
              <Link
                to={`/properties/${property.id}`}
                className="property-card"
                key={property.id}
              >
                <div className="card-top">
                  <span className="status">
                    {property.foreclosure_status ?? "Unknown"}
                  </span>

                  {property.deal_score !== null && (
                    <span className="score">
                      Score {property.deal_score}
                    </span>
                  )}
                </div>

                <h2>{property.address}</h2>

                <div className="price">
                  ₹
                  {property.price?.toLocaleString("en-IN") ??
                    "N/A"}
                </div>

                <div className="details">
                  <span>
                    {property.area_sqft
                      ? `${property.area_sqft} sq ft`
                      : "Area N/A"}
                  </span>

                  <span>
                    {property.property_type ?? "Type N/A"}
                  </span>
                </div>

                {property.survey_number && (
                  <div className="survey">
                    Survey No: {property.survey_number}
                  </div>
                )}

                {property.auction_date && (
                  <div className="auction">
                    Auction: {property.auction_date}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;