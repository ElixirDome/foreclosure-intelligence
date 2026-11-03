import { useState, type FormEvent } from "react";
import api from "../api/client";

interface Preferences {
  state?: string;
  district?: string;
  city?: string;
  locality?: string;
  onboarding_completed?: boolean;
}

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (preferences: Preferences) => void;
}

export default function OnboardingModal({
  isOpen,
  onClose,
  onComplete,
}: OnboardingModalProps) {
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [city, setCity] = useState("");
  const [locality, setLocality] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const response = await api.put<Preferences>("/auth/me/preferences", {
        state: state.trim() || null,
        district: district.trim() || null,
        city: city.trim() || null,
        locality: locality.trim() || null,
        onboarding_completed: true,
      });
      onComplete(response.data);
      onClose();
    } catch (err) {
      console.error("Could not save location preferences:", err);
      setError("Could not save your preferences. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "grid",
        placeItems: "center",
        padding: 20,
        background: "rgba(0,0,0,.65)",
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        style={{
          width: "min(100%, 460px)",
          padding: 24,
          borderRadius: 16,
          background: "var(--bg-card, #171717)",
          color: "var(--text-primary, #fff)",
          border: "1px solid var(--border-subtle, #444)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <h2 id="onboarding-title">Personalise your property feed</h2>
          <button type="button" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <p>Choose a location to make local auction discovery more relevant.</p>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
          <label>
            State
            <input value={state} onChange={(e) => setState(e.target.value)} placeholder="e.g. Karnataka" />
          </label>
          <label>
            District
            <input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="e.g. Bengaluru Urban" />
          </label>
          <label>
            City
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Bengaluru" />
          </label>
          <label>
            Locality (optional)
            <input value={locality} onChange={(e) => setLocality(e.target.value)} placeholder="e.g. Whitefield" />
          </label>
          {error && <p role="alert" style={{ color: "#ef4444" }}>{error}</p>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" onClick={onClose} disabled={saving}>Skip for now</button>
            <button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save preferences"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
