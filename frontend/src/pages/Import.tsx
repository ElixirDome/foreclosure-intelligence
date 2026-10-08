import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";

interface SkippedProperty {
  property_id: number;
  address: string;
  reason: string;
}

interface ImportResponse {
  message: string;
  saved_count: number;
  skipped_count: number;
  properties: unknown[];
  skipped: SkippedProperty[];
}

function Import() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleImport(event: React.FormEvent) {
    event.preventDefault();

    if (!file) {
      setError("Please select a PDF.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const formData = new FormData();
      formData.append("file", file);

      const response = await api.post<ImportResponse>(
        "/properties/import",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      setResult(response.data);
    } catch (err: any) {
  console.error(err);

  const message =
    err.response?.data?.detail ||
    err.message ||
    "Import failed.";

  setError(message);
} finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <nav className="navbar">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/research">Research</Link>
        <Link to="/admin/import">Import</Link>
      </nav>

      <h1>Import Auction PDF</h1>
      <p>Upload an auction PDF to extract and save properties.</p>

      <form onSubmit={handleImport}>
        <input
          type="file"
          accept=".pdf"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
          }}
        />

        <button type="submit" disabled={loading}>
          {loading ? "Importing..." : "Import PDF"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="import-result">
          <h2>Import complete</h2>

          <p>
            Saved: <strong>{result.saved_count}</strong>
          </p>

          <p>
            Skipped duplicates: <strong>{result.skipped_count}</strong>
          </p>

          {result.skipped.length > 0 && (
            <div>
              <h3>Skipped properties</h3>

              {result.skipped.map((property) => (
                <div key={property.property_id}>
                  <strong>{property.address}</strong>
                  <span> — {property.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Import;