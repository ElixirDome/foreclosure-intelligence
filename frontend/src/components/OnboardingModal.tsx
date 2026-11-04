import { useEffect, useState } from "react";
import api from "../api/client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (prefs: any) => void;
}

export default function OnboardingModal({ isOpen, onClose, onComplete }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [hierarchy, setHierarchy] = useState<Record<string, Record<string, string[]>>>({});
  const [saving, setSaving] = useState(false);

  // Preference state
  const [selectedState, setSelectedState] = useState("Punjab");
  const [selectedDistrict, setSelectedDistrict] = useState("Gurdaspur");
  const [selectedCity, setSelectedCity] = useState("Tehsil");
  const [propertyType, setPropertyType] = useState("residential");
  const [maxPrice, setMaxPrice] = useState<number | "">("");
  const [selectedBanks, setSelectedBanks] = useState<string[]>(["PNB"]);

  useEffect(() => {
    async function loadData() {
      try {
        const [hierRes, prefRes] = await Promise.all([
          api.get("/auth/locations/hierarchy"),
          api.get("/auth/me/preferences").catch(() => null),
        ]);
        setHierarchy(hierRes.data);

        if (prefRes?.data) {
          const d = prefRes.data;
          if (d.state) setSelectedState(d.state);
          if (d.district) setSelectedDistrict(d.district);
          if (d.city) setSelectedCity(d.city);
          if (d.max_reserve_price) setMaxPrice(Number(d.max_reserve_price));
          if (d.preferred_banks && d.preferred_banks.length > 0) setSelectedBanks(d.preferred_banks);
        }
      } catch (err) {
        console.error("Could not load onboarding hierarchy:", err);
      }
    }

    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const states = Object.keys(hierarchy);
  const districts = selectedState && hierarchy[selectedState] ? Object.keys(hierarchy[selectedState]) : [];
  const localities =
    selectedState && selectedDistrict && hierarchy[selectedState]?.[selectedDistrict]
      ? hierarchy[selectedState][selectedDistrict]
      : [];

  function handleStateChange(newState: string) {
    setSelectedState(newState);
    const firstDistrict = hierarchy[newState] ? Object.keys(hierarchy[newState])[0] : "";
    setSelectedDistrict(firstDistrict);
    const firstLocality = firstDistrict && hierarchy[newState]?.[firstDistrict] ? hierarchy[newState][firstDistrict][0] : "";
    setSelectedCity(firstLocality);
  }

  function handleDistrictChange(newDistrict: string) {
    setSelectedDistrict(newDistrict);
    const firstLocality = hierarchy[selectedState]?.[newDistrict] ? hierarchy[selectedState][newDistrict][0] : "";
    setSelectedCity(firstLocality);
  }

  function toggleBank(bank: string) {
    setSelectedBanks((prev) =>
      prev.includes(bank) ? prev.filter((b) => b !== bank) : [...prev, bank]
    );
  }

  async function handleSavePreferences() {
    try {
      setSaving(true);
      const payload = {
        state: selectedState,
        district: selectedDistrict,
        city: selectedCity || selectedDistrict,
        property_types: [propertyType],
        max_reserve_price: maxPrice ? Number(maxPrice) : null,
        preferred_banks: selectedBanks,
        onboarding_completed: true,
      };

      const res = await api.put("/auth/me/preferences", payload);
      onComplete(res.data);
      onClose();
    } catch (err) {
      console.error("Failed to save preferences:", err);
      alert("Failed to save preferences. Please check backend connection.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-card">
        {/* Progress Dots */}
        <div className="onboarding-progress">
          <div className={`onboarding-step-indicator ${step >= 1 ? "active" : ""}`}>1. Location & Scope</div>
          <div className="onboarding-step-line" />
          <div className={`onboarding-step-indicator ${step >= 2 ? "active" : ""}`}>2. Price & Banks</div>
          <div className="onboarding-step-line" />
          <div className={`onboarding-step-indicator ${step >= 3 ? "active" : ""}`}>3. Activation</div>
        </div>

        {/* Step 1: Research Scope */}
        {step === 1 && (
          <div className="onboarding-step-body">
            <div className="onboarding-header">
              <span className="onboarding-badge">🚀 WELCOME TO FORECLOSURE INTELLIGENCE</span>
              <h2>Set Your Local Research Desk</h2>
              <p className="onboarding-desc">
                Select the geographic territory and property category you want to monitor for bank e-auctions, reserve prices, and valuation discounts.
              </p>
            </div>

            <div className="onboarding-form">
              <div className="onboarding-field-group">
                <label>Target State</label>
                <select value={selectedState} onChange={(e) => handleStateChange(e.target.value)}>
                  {states.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div className="onboarding-field-group">
                <label>District / County</label>
                <select value={selectedDistrict} onChange={(e) => handleDistrictChange(e.target.value)}>
                  {districts.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div className="onboarding-field-group">
                <label>Primary Sub-Market / City / Locality (Optional)</label>
                <select value={selectedCity} onChange={(e) => setSelectedCity(e.target.value)}>
                  <option value="">All localities in {selectedDistrict}</option>
                  {localities.map((loc) => (
                    <option key={loc} value={loc}>
                      {loc}
                    </option>
                  ))}
                </select>
              </div>

              <div className="onboarding-field-group">
                <label>Supported Property Category</label>
                <div className="onboarding-radio-box selected">
                  <input
                    type="radio"
                    id="cat_res"
                    name="category"
                    checked={propertyType === "residential"}
                    onChange={() => setPropertyType("residential")}
                  />
                  <label htmlFor="cat_res">
                    <strong>🏡 Residential Properties (Default Supported Scope)</strong>
                    <span>Flats, apartments, villas, independent houses & residential land</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="onboarding-footer">
              <button type="button" className="onboarding-btn-ghost" onClick={onClose}>
                Skip for now (Explore all inventory)
              </button>
              <button
                type="button"
                className="onboarding-btn-primary"
                onClick={() => setStep(2)}
                disabled={!selectedState || !selectedDistrict}
              >
                Next: Pricing & Sources →
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Price & Banks */}
        {step === 2 && (
          <div className="onboarding-step-body">
            <div className="onboarding-header">
              <span className="onboarding-badge">FILTERS & INSTITUTIONS</span>
              <h2>Budget Range & Preferred Banks</h2>
              <p className="onboarding-desc">
                Optionally constrain your feed by maximum reserve price and specify preferred public auction portals.
              </p>
            </div>

            <div className="onboarding-form">
              <div className="onboarding-field-group">
                <label>Maximum Reserve Price (INR)</label>
                <div style={{ display: "flex", gap: 10 }}>
                  <input
                    type="number"
                    placeholder="e.g. 5000000 for ₹50 Lakh (leave blank for any)"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value ? Number(e.target.value) : "")}
                  />
                </div>
                <div className="desk-quick-pills" style={{ marginTop: 6 }}>
                  <button type="button" className="desk-mini-pill" onClick={() => setMaxPrice(3500000)}>
                    Under ₹35 Lakh
                  </button>
                  <button type="button" className="desk-mini-pill" onClick={() => setMaxPrice(6000000)}>
                    Under ₹60 Lakh
                  </button>
                  <button type="button" className="desk-mini-pill" onClick={() => setMaxPrice(10000000)}>
                    Under ₹1 Crore
                  </button>
                  <button type="button" className="desk-mini-pill" onClick={() => setMaxPrice("")}>
                    Any Price
                  </button>
                </div>
              </div>

              <div className="onboarding-field-group">
                <label>Preferred Foreclosure Portals</label>
                <div className="onboarding-bank-grid">
                  {[
                    { key: "PNB", name: "Punjab National Bank (PNB SARFAESI)" },
                    { key: "IBAPI", name: "IBAPI (e-Bkray Multi-Bank Aggregator)" },
                    { key: "SBI", name: "State Bank of India (Mega Auctions)" },
                  ].map((b) => (
                    <div
                      key={b.key}
                      className={`onboarding-bank-chip ${selectedBanks.includes(b.key) ? "selected" : ""}`}
                      onClick={() => toggleBank(b.key)}
                    >
                      <span>{selectedBanks.includes(b.key) ? "✓" : "+"}</span>
                      <span>{b.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="onboarding-footer">
              <button type="button" className="onboarding-btn-ghost" onClick={() => setStep(1)}>
                ← Back
              </button>
              <button
                type="button"
                className="onboarding-btn-primary"
                onClick={() => setStep(3)}
              >
                Review Summary →
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Summary & Activation */}
        {step === 3 && (
          <div className="onboarding-step-body">
            <div className="onboarding-header">
              <span className="onboarding-badge">CONFIRMATION</span>
              <h2>Confirm Your Research Desk</h2>
              <p className="onboarding-desc">
                Your feed will be filtered to active residential foreclosure opportunities matching your territory.
              </p>
            </div>

            <div className="onboarding-summary-card">
              <div className="onboarding-summary-row">
                <span className="summary-label">Target Territory:</span>
                <span className="summary-value">
                  {selectedDistrict}, {selectedState} {selectedCity ? `(${selectedCity})` : ""}
                </span>
              </div>

              <div className="onboarding-summary-row">
                <span className="summary-label">Asset Category:</span>
                <span className="summary-value">Residential Only (Non-residential excluded)</span>
              </div>

              <div className="onboarding-summary-row">
                <span className="summary-label">Reserve Price Ceiling:</span>
                <span className="summary-value">{maxPrice ? `Up to ₹${Number(maxPrice).toLocaleString()}` : "No ceiling"}</span>
              </div>

              <div className="onboarding-summary-row">
                <span className="summary-label">Monitored Portals:</span>
                <span className="summary-value">{selectedBanks.join(", ") || "All connected sources"}</span>
              </div>
            </div>

            <div className="onboarding-footer">
              <button type="button" className="onboarding-btn-ghost" onClick={() => setStep(2)}>
                ← Back
              </button>
              <button
                type="button"
                className="onboarding-btn-primary"
                onClick={handleSavePreferences}
                disabled={saving}
              >
                {saving ? "Activating Desk..." : "🚀 Activate Desk & Open Inventory"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
