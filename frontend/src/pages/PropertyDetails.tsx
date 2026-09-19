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

function PropertyDetails() {
  const { id } = useParams();
  const [property, setProperty] = useState<Property | null>(null);

  useEffect(() => {
    async function loadProperty() {
      const response = await api.get<Property>(`/properties/${id}`);
      setProperty(response.data);
    }

    loadProperty();
  }, [id]);

  if (!property) {
    return <div className="page">Loading...</div>;
  }

  return (
    <div className="page">
      <Link to="/dashboard">← Back to properties</Link>

      <div className="details-container">
        <div className="status">
          {property.foreclosure_status ?? "Unknown"}
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
              ₹{property.opening_bid?.toLocaleString("en-IN") ?? "N/A"}
            </span>
          </div>

          <div>
            <strong>Estimated value</strong>
            <span>
              ₹
              {property.estimated_value?.toLocaleString("en-IN") ??
                "N/A"}
            </span>
          </div>

          <div>
            <strong>Discount</strong>
            <span>
              {property.discount_percentage !== null
                ? `${property.discount_percentage}%`
                : "N/A"}
            </span>
          </div>

          <div>
            <strong>Deal score</strong>
            <span>
              {property.deal_score ?? "Not calculated"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PropertyDetails;