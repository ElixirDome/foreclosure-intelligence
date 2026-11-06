import { useEffect, useState, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api from "../api/client";
import { useAnalyst } from "../context/AnalystContext";
import OnboardingModal from "../components/OnboardingModal";

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
  emd_percentage?: number | null;
  reserve_price_per_sqft?: number | null;
  opening_bid: number | null;
  estimated_value: number | null;
  property_type: string | null;
  survey_number: string | null;
  discount_percentage?: number | null;
  deal_score?: number | null;
  sources?: PropertySource[];
  bank_name?: string | null; branch_name?: string | null; possession_type?: string | null;
  property_unique_id?: string | null; auction_id?: string | null; property_images?: string[] | null;
  auction_start?: string | null; auction_end?: string | null; emd_deadline?: string | null;
  inspection_start?: string | null; inspection_end?: string | null; listing_url?: string | null;
  district?: string | null; state?: string | null;
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
  const [searchParams] = useSearchParams();
  const { openAnalyst } = useAnalyst();

  // Onboarding & Preferences State
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [userPreferences, setUserPreferences] = useState<{
    state?: string;
    district?: string;
    city?: string;
    onboarding_completed?: boolean;
  } | null>(null);

  // Dark Mode Theme State
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return (localStorage.getItem("fc_theme") as "dark" | "light") || "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("fc_theme", theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }

  // Favorites System
  const [favorites, setFavorites] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem("fc_favorites");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  function toggleFavorite(id: number, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setFavorites((prev) => {
      const next = prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id];
      localStorage.setItem("fc_favorites", JSON.stringify(next));
      return next;
    });
  }

  // Quick Filter Stories
  const [activeStory, setActiveStory] = useState<"all" | "favs" | "live" | "physical" | "local" | "comm">("all");

  // Check if user needs onboarding or analyst open requested
  useEffect(() => {
    if (searchParams.get("analyst") === "open") {
      openAnalyst();
    }

    api.get("/auth/me/preferences")
      .then((res) => {
        if (res.data) {
          setUserPreferences(res.data);
          if (res.data.onboarding_completed === false) {
            setOnboardingOpen(true);
          }
        }
      })
      .catch(() => {
        // Dev / unauthenticated fallback
      });
  }, [searchParams]);

  function handleOnboardingComplete(prefs: any) {
    setUserPreferences(prefs);
    if (prefs.district || prefs.city) {
      setSearch(prefs.district || prefs.city || "");
    }
    loadProperties();
  }

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

  async function loadProperties(
    pageOverride?: number,
    filterOverrides?: Partial<{
      search: string;
      status: string;
      propertyType: string;
      minPrice: string;
      maxPrice: string;
      minArea: string;
      maxArea: string;
      bedrooms: string;
    }>
  ) {
    try {
      setLoading(true);
      setError("");

      const targetPage = pageOverride ?? page;
      const curSearch = filterOverrides?.search !== undefined ? filterOverrides.search : search;
      const curStatus = filterOverrides?.status !== undefined ? filterOverrides.status : status;
      const curType = filterOverrides?.propertyType !== undefined ? filterOverrides.propertyType : propertyType;
      const curMinPrice = filterOverrides?.minPrice !== undefined ? filterOverrides.minPrice : minPrice;
      const curMaxPrice = filterOverrides?.maxPrice !== undefined ? filterOverrides.maxPrice : maxPrice;
      const curMinArea = filterOverrides?.minArea !== undefined ? filterOverrides.minArea : minArea;
      const curMaxArea = filterOverrides?.maxArea !== undefined ? filterOverrides.maxArea : maxArea;
      const curBedrooms = filterOverrides?.bedrooms !== undefined ? filterOverrides.bedrooms : bedrooms;

      const params: Record<string, string | number> = {
        page: targetPage,
        limit: 20,
        sort_by: sortBy,
        order,
      };

      if (curSearch.trim()) params.search = curSearch.trim();
      if (curMinPrice) params.min_price = Number(curMinPrice);
      if (curMaxPrice) params.max_price = Number(curMaxPrice);
      if (curMinArea) params.min_area = Number(curMinArea);
      if (curMaxArea) params.max_area = Number(curMaxArea);
      if (curBedrooms) params.bedrooms = Number(curBedrooms);
      if (curStatus) params.foreclosure_status = curStatus;
      if (curType) params.property_type = curType;

      const response = await api.get<any>("/properties/", { params });

      const items = Array.isArray(response.data) ? response.data : (response.data?.items || []);
      setProperties(items);
      setTotal(response.data?.total ?? items.length);
      setPages(response.data?.pages ?? 1);
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

  // Real-Time Live Feed & Streaming State
  const [streamStatus, setStreamStatus] = useState<"live" | "reconnecting" | "polling">("polling");
  const [justAddedIds, setJustAddedIds] = useState<number[]>([]);
  const [liveToasts, setLiveToasts] = useState<Array<{ id: string; message: string; hiddenProperty: Property }>>([]);

  function dismissToast(id: string) {
    setLiveToasts((prev) => prev.filter((t) => t.id !== id));
  }

  // Ref to hold current filter values so SSE event handler doesn't suffer from stale closures
  const filtersRef = useRef({
    search, status, propertyType, minPrice, maxPrice, minArea, maxArea,
    bedrooms, sortBy, order, page,
    activeStory, userPreferences, favorites,
  });

  useEffect(() => {
    filtersRef.current = {
      search, status, propertyType, minPrice, maxPrice, minArea, maxArea,
      bedrooms, sortBy, order, page,
      activeStory, userPreferences, favorites,
    };
  }, [
    search, status, propertyType, minPrice, maxPrice, minArea, maxArea,
    bedrooms, sortBy, order, page,
    activeStory, userPreferences, favorites,
  ]);

  // Live SSE Connection with Adaptive Polling Fallback
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let fallbackInterval: number | null = null;
    let isMounted = true;

    async function refreshCurrentPage() {
      const filters = filtersRef.current;
      const params: Record<string, string | number> = {
        page: filters.page,
        limit: 20,
        sort_by: filters.sortBy,
        order: filters.order,
      };
      if (filters.search.trim()) params.search = filters.search.trim();
      if (filters.minPrice) params.min_price = Number(filters.minPrice);
      if (filters.maxPrice) params.max_price = Number(filters.maxPrice);
      if (filters.minArea) params.min_area = Number(filters.minArea);
      if (filters.maxArea) params.max_area = Number(filters.maxArea);
      if (filters.bedrooms) params.bedrooms = Number(filters.bedrooms);
      if (filters.status) params.foreclosure_status = filters.status;
      if (filters.propertyType) params.property_type = filters.propertyType;

      const [propertiesResult, summaryResult] = await Promise.allSettled([
        api.get<PropertyResponse>("/properties/", { params }),
        api.get("/properties/summary"),
      ]);
      if (!isMounted) return;
      if (propertiesResult.status === "fulfilled") {
        // Reconcile existing rows too; updates must not wait for a new property ID.
        setProperties(propertiesResult.value.data.items);
        setTotal(propertiesResult.value.data.total);
        setPages(propertiesResult.value.data.pages);
      }
      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value.data);
      }
    }

    function startPollingFallback() {
      if (fallbackInterval) return;
      setStreamStatus("polling");
      fallbackInterval = window.setInterval(() => {
        void refreshCurrentPage();
      }, 15000);
    }

    function stopPollingFallback() {
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
        fallbackInterval = null;
      }
    }

    function connectSSE() {
      const token = localStorage.getItem("access_token");
      if (!token) {
        startPollingFallback();
        return;
      }

      const baseUrl = api.defaults.baseURL || "http://127.0.0.1:8000";
      const sseUrl = `${baseUrl}/properties/stream?token=${encodeURIComponent(token)}`;

      try {
        eventSource = new EventSource(sseUrl);

        eventSource.onopen = () => {
          if (!isMounted) return;
          setStreamStatus("live");
          stopPollingFallback();
        };

        eventSource.addEventListener("connected", () => {
          if (!isMounted) return;
          setStreamStatus("live");
          stopPollingFallback();
        });

        eventSource.addEventListener("ping", () => {
          if (!isMounted) return;
          setStreamStatus("live");
        });

        eventSource.addEventListener("property_created", (event: MessageEvent) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            const propId = Number(data.property_id || data.id);
            if (!propId) return;

            const newProp: Property = {
              id: propId,
              address: data.address || "Auction Property",
              city: data.city || null,
              locality: data.locality || null,
              price: data.price ?? data.reserve_price ?? null,
              reserve_price: data.reserve_price ?? null,
              emd: data.emd ?? null,
              opening_bid: data.opening_bid ?? null,
              estimated_value: data.estimated_value ?? null,
              property_type: data.property_type ?? "Residential Property",
              auction_date: data.auction_date ?? null,
              foreclosure_status: data.foreclosure_status ?? "scheduled",
              deal_score: data.deal_score ?? null,
              discount_percentage: data.discount_percentage ?? null,
              bedrooms: data.bedrooms ?? null,
              bathrooms: data.bathrooms ?? null,
              area_sqft: data.area_sqft ?? null,
              survey_number: data.survey_number ?? null,
              sources: data.sources ?? [],
            };

            // Keep server-side sorting, filters and pagination authoritative.
            void refreshCurrentPage();

            // Trigger visual 8-second highlight badge
            setJustAddedIds((prev) => (prev.includes(newProp.id) ? prev : [...prev, newProp.id]));
            setTimeout(() => {
              if (isMounted) {
                setJustAddedIds((prev) => prev.filter((id) => id !== newProp.id));
              }
            }, 8000);

            // Counts are reconciled from the server; duplicate SSE delivery cannot inflate them.

            // Filter awareness verification
            const {
              search: curSearch,
              status: curStatus,
              propertyType: curType,
              minPrice: curMin,
              maxPrice: curMax,
              activeStory: curStory,
              userPreferences: curPrefs,
            } = filtersRef.current;

            let matches = true;

            if (curSearch.trim()) {
              const q = curSearch.toLowerCase();
              const hit =
                (newProp.address && newProp.address.toLowerCase().includes(q)) ||
                (newProp.city && newProp.city.toLowerCase().includes(q)) ||
                (newProp.locality && newProp.locality.toLowerCase().includes(q));
              if (!hit) matches = false;
            }

            if (curStatus && newProp.foreclosure_status !== curStatus) {
              matches = false;
            }

            if (curType) {
              const isComm = newProp.property_type?.toLowerCase().includes("commercial");
              if (curType === "residential" && isComm) matches = false;
              if (curType === "commercial" && !isComm) matches = false;
            }

            if (curMin && (newProp.reserve_price == null || newProp.reserve_price < Number(curMin))) {
              matches = false;
            }

            if (curMax && (newProp.reserve_price == null || newProp.reserve_price > Number(curMax))) {
              matches = false;
            }

            if (curStory === "physical" && !(newProp.possession_type?.toLowerCase().includes("physical"))) {
              matches = false;
            }

            if (
              curStory === "live" &&
              !(
                newProp.foreclosure_status === "scheduled" ||
                newProp.foreclosure_status === "active" ||
                newProp.foreclosure_status === "upcoming"
              )
            ) {
              matches = false;
            }

            if (curStory === "local") {
              const loc = (curPrefs?.district || curPrefs?.city || "").toLowerCase();
              if (
                loc &&
                !((newProp.city && newProp.city.toLowerCase().includes(loc)) ||
                  (newProp.address && newProp.address.toLowerCase().includes(loc)))
              ) {
                matches = false;
              }
            }

            if (!matches) {
              const tid = `${newProp.id}-${Date.now()}`;
              const locationLabel =
                [newProp.locality, newProp.city].filter(Boolean).join(", ") || newProp.address;
              setLiveToasts((prev) => [
                ...prev.slice(-2),
                {
                  id: tid,
                  message: `⚡ 1 new property in "${locationLabel}" is hidden by your filter`,
                  hiddenProperty: newProp,
                },
              ]);
            }
          } catch (e) {
            console.error("Error processing property_created event:", e);
          }
        });

        eventSource.addEventListener("property_updated", (event: MessageEvent) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            const propId = Number(data.property_id || data.id);
            if (!propId) return;

            setProperties((prev) =>
              prev.map((p) => {
                if (p.id === propId) {
                  return {
                    ...p,
                    address: data.address ?? p.address,
                    city: data.city ?? p.city,
                    locality: data.locality ?? p.locality,
                    property_type: data.property_type ?? p.property_type,
                    reserve_price: data.reserve_price ?? p.reserve_price,
                    opening_bid: data.opening_bid ?? p.opening_bid,
                    price: data.price ?? data.reserve_price ?? p.price,
                    emd: data.emd ?? p.emd,
                    area_sqft: data.area_sqft ?? p.area_sqft,
                    survey_number: data.survey_number ?? p.survey_number,
                    foreclosure_status: data.foreclosure_status ?? p.foreclosure_status,
                    auction_date: data.auction_date ?? p.auction_date,
                    discount_percentage: data.discount_percentage ?? p.discount_percentage,
                    deal_score: data.deal_score ?? p.deal_score,
                  };
                }
                return p;
              })
            );

            // Reconcile membership and summary if fields affect filters or sorting.
            void refreshCurrentPage();
          } catch (e) {
            console.error("Error processing property_updated event:", e);
          }
        });

        eventSource.onerror = () => {
          if (!isMounted) return;
          setStreamStatus("reconnecting");
          startPollingFallback();
        };
      } catch (err) {
        console.error("Failed to connect SSE:", err);
        startPollingFallback();
      }
    }

    connectSSE();

    return () => {
      isMounted = false;
      if (eventSource) {
        eventSource.close();
      }
      stopPollingFallback();
    };
  }, []);

  useEffect(() => {
    api.get("/properties/summary")
      .then((response) => setSummary(response.data))
      .catch((err) => console.error("Could not load summary:", err));
  }, []);

  function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setPage(1);
    loadProperties(1);
  }

  function clearFilters() {
    setSearch("");
    setStatus("");
    setPropertyType("");
    setMinPrice("");
    setMaxPrice("");
    setMinArea("");
    setMaxArea("");
    setBedrooms("");
    setActiveStory("all");
    setPage(1);

    loadProperties(1, {
      search: "",
      status: "",
      propertyType: "",
      minPrice: "",
      maxPrice: "",
      minArea: "",
      maxArea: "",
      bedrooms: "",
    });
  }

  // Filter properties by active story tab
  const displayedProperties = properties.filter((prop) => {
    if (activeStory === "favs") {
      return favorites.includes(prop.id);
    }
    if (activeStory === "live") {
      const st = (prop.foreclosure_status || "").toLowerCase();
      return st === "scheduled" || st === "active" || st === "upcoming";
    }
    if (activeStory === "physical") {
      return prop.possession_type?.toLowerCase().includes("physical");
    }
    if (activeStory === "local") {
      const loc = (userPreferences?.district || userPreferences?.city || "").toLowerCase();
      if (!loc) return true;
      return (prop.city?.toLowerCase().includes(loc) || prop.address?.toLowerCase().includes(loc));
    }
    if (activeStory === "comm") {
      return prop.property_type?.toLowerCase().includes("commercial");
    }
    // Default: residential only (exclude confirmed commercial)
    return !prop.property_type?.toLowerCase().includes("commercial");
  });

  return (
    <div className="page" style={{ padding: "0 16px 40px" }}>
      {/* Instagram-Style Sticky Frosted Header */}
      <nav className="ig-navbar">
        <div className="ig-nav-inner">
          <Link to="/dashboard" className="ig-nav-brand">
            <span style={{ fontSize: 24 }}>⚡</span>
            <span className="ig-brand-gradient">FORECLOSURE.AI</span>
          </Link>

          <form onSubmit={handleSearch} style={{ flex: "0 1 360px", margin: "0 12px" }}>
            <input
              type="text"
              placeholder="🔍 Search city, locality, bank..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                borderRadius: 999,
                padding: "8px 16px",
                color: "var(--text-primary)",
                fontSize: 13,
              }}
            />
          </form>

          <div className="ig-nav-actions">
            {/* Live Feed Status Pill */}
            <div
              className={`ig-live-pill ${streamStatus}`}
              title={
                streamStatus === "live"
                  ? "Real-time updates active via Server-Sent Events"
                  : streamStatus === "reconnecting"
                  ? "Reconnecting to real-time event stream..."
                  : "Fallback background polling active (15s)"
              }
            >
              <span
                className={`ig-live-dot ${
                  streamStatus === "live" ? "green" : streamStatus === "reconnecting" ? "amber" : "gray"
                }`}
              />
              <span>{streamStatus === "live" ? "Live Feed" : streamStatus === "reconnecting" ? "Reconnecting" : "Polling"}</span>
            </div>

            <button
              type="button"
              className={`ig-nav-pill ig-fav-pill ${activeStory === "favs" ? "active" : ""}`}
              onClick={() => setActiveStory(activeStory === "favs" ? "all" : "favs")}
              title="Filter favorited properties"
            >
              <span>❤️</span>
              <span>Saved ({favorites.length})</span>
            </button>

            <Link to="/admin/import" className="ig-nav-pill">
              <span>📡</span>
              <span>Bank Sources</span>
            </Link>

            <Link to="/research" className="ig-nav-pill">
              <span>🤖</span>
              <span>AI Research</span>
            </Link>

            <button
              type="button"
              className="ig-theme-toggle"
              onClick={toggleTheme}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>

            <button
              type="button"
              className="ig-nav-pill"
              onClick={handleLogout}
              style={{ color: "#ef4444" }}
              title="Logout"
            >
              <span>🚪</span>
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Stories / Filter Reel */}
      <div className="ig-stories-bar">
        <button
          type="button"
          className={`ig-story-pill ${activeStory === "all" ? "active" : ""}`}
          onClick={() => setActiveStory("all")}
        >
          <span>🏡</span>
          <span>All Residential ({summary.residential || total})</span>
        </button>

        <button
          type="button"
          className={`ig-story-pill ${activeStory === "favs" ? "active" : ""}`}
          onClick={() => setActiveStory("favs")}
        >
          <span>⭐</span>
          <span>Saved Favorites ({favorites.length})</span>
        </button>

        <button
          type="button"
          className={`ig-story-pill ${activeStory === "live" ? "active" : ""}`}
          onClick={() => setActiveStory("live")}
        >
          <span>⚡</span>
          <span>Upcoming &amp; Live ({summary.upcoming_auctions})</span>
        </button>

        <button
          type="button"
          className={`ig-story-pill ${activeStory === "physical" ? "active" : ""}`}
          onClick={() => setActiveStory("physical")}
        >
          <span>🔑</span>
          <span>Physical Possession</span>
        </button>

        <button
          type="button"
          className={`ig-story-pill ${activeStory === "local" ? "active" : ""}`}
          onClick={() => setActiveStory("local")}
        >
          <span>📍</span>
          <span>{userPreferences?.district || userPreferences?.city || "Local Territory"}</span>
        </button>

        {summary.commercial > 0 && (
          <button
            type="button"
            className={`ig-story-pill ${activeStory === "comm" ? "active" : ""}`}
            onClick={() => setActiveStory("comm")}
          >
            <span>🏢</span>
            <span>Commercial Archive ({summary.commercial})</span>
          </button>
        )}
      </div>

      {/* Summary KPI Strip */}
      <div className="banknet-kpi-grid" style={{ marginBottom: 20 }}>
        <div className="banknet-kpi-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-subtle)" }}>
          <span className="banknet-kpi-label" style={{ color: "var(--text-muted)" }}>Total Inventory</span>
          <strong className="banknet-kpi-val" style={{ color: "var(--text-primary)" }}>{summary.total_properties}</strong>
        </div>
        <div className="banknet-kpi-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-subtle)" }}>
          <span className="banknet-kpi-label" style={{ color: "var(--text-muted)" }}>Live Auctions</span>
          <strong className="banknet-kpi-val" style={{ color: "var(--accent-amber)" }}>{summary.upcoming_auctions}</strong>
        </div>
        <div className="banknet-kpi-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-subtle)" }}>
          <span className="banknet-kpi-label" style={{ color: "var(--text-muted)" }}>Active Opportunities</span>
          <strong className="banknet-kpi-val" style={{ color: "var(--accent-emerald)" }}>{summary.upcoming_auctions}</strong>
        </div>
        <div className="banknet-kpi-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-subtle)" }}>
          <span className="banknet-kpi-label" style={{ color: "var(--text-muted)" }}>Residential</span>
          <strong className="banknet-kpi-val" style={{ color: "var(--text-primary)" }}>{summary.residential}</strong>
        </div>
        <div className="banknet-kpi-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-subtle)" }}>
          <span className="banknet-kpi-label" style={{ color: "var(--text-muted)" }}>Commercial</span>
          <strong className="banknet-kpi-val" style={{ color: "var(--text-primary)" }}>{summary.commercial}</strong>
        </div>
        <div className="banknet-kpi-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-subtle)" }}>
          <span className="banknet-kpi-label" style={{ color: "var(--text-muted)" }}>Settled / Sold</span>
          <strong className="banknet-kpi-val" style={{ color: "var(--text-muted)" }}>{summary.sold}</strong>
        </div>
      </div>

      {/* Advanced Search & Filter Toolbar */}
      <form
        className="filters"
        onSubmit={handleSearch}
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border-subtle)",
          padding: 16,
          borderRadius: 16,
          marginBottom: 24,
        }}
      >
        <input
          type="text"
          placeholder="Filter by city, address or street..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--border-subtle)" }}
        />

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--border-subtle)" }}
        >
          <option value="">All statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="upcoming">Upcoming</option>
          <option value="active">Active</option>
          <option value="sold">Sold</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <select
          value={propertyType}
          onChange={(e) => setPropertyType(e.target.value)}
          style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--border-subtle)" }}
        >
          <option value="">All asset types</option>
          <option value="residential">Residential</option>
          <option value="commercial">Commercial</option>
        </select>

        <input
          type="number"
          min="0"
          placeholder="Bedrooms (BHK)"
          value={bedrooms}
          onChange={(e) => setBedrooms(e.target.value)}
          style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--border-subtle)", width: 130 }}
        />

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--border-subtle)" }}
        >
          <option value="id">Sort by: Date Added</option>
          <option value="price">Sort by: Reserve Price</option>
          <option value="area_sqft">Sort by: Area</option>
        </select>

        <select
          value={order}
          onChange={(e) => setOrder(e.target.value)}
          style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--border-subtle)" }}
        >
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>

        <button type="submit" style={{ background: "var(--ig-gradient)", color: "#fff", border: "none", fontWeight: 700, borderRadius: 8, padding: "10px 18px", cursor: "pointer" }}>
          Apply
        </button>

        <button
          type="button"
          onClick={clearFilters}
          style={{ background: "transparent", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)", borderRadius: 8, padding: "10px 14px", cursor: "pointer" }}
        >
          Reset
        </button>
      </form>

      {loading && <p style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>Loading properties feed...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ fontSize: "1.2rem", margin: 0, color: "var(--text-primary)" }}>
              {activeStory === "favs" ? `Saved Favorites (${displayedProperties.length})` : `${total} Auction Lots Available`}
            </h2>
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Page {page} of {Math.max(pages, 1)}
            </span>
          </div>

          {displayedProperties.length === 0 && (
            <div style={{ textAlign: "center", padding: "60px 20px", background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: 16 }}>
              <span style={{ fontSize: 40, display: "block", marginBottom: 12 }}>
                {activeStory === "favs" ? "💔" : "🔍"}
              </span>
              <h3 style={{ margin: "0 0 8px", color: "var(--text-primary)" }}>
                {activeStory === "favs" ? "No favorited properties yet" : "No auctions matched your filters"}
              </h3>
              <p style={{ color: "var(--text-secondary)", margin: 0 }}>
                {activeStory === "favs"
                  ? "Click the heart icon (❤️) on any property card to save it to your watchlist."
                  : "Try clearing your filters or searching for another city."}
              </p>
            </div>
          )}

          {/* Bank-auction marketplace listings */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: 20 }}>
            {displayedProperties.map((property) => {
              const bankName = property.bank_name || property.sources?.[0]?.source_name || "Bank auction";
              const locationText = [property.locality, property.city, property.district, property.state].filter(Boolean).join(", ");
              const isFavorited = favorites.includes(property.id);
              const isNewlyAdded = justAddedIds.includes(property.id);
              const image = property.property_images?.[0];
              const officialUrl =
                property.listing_url ||
                property.sources?.find((source) => source.source_url)?.source_url ||
                (property as any)?.extra_data?.listingUrl ||
                (property as any)?.extra_data?.source_url ||
                (property as any)?.extra_data?.detailUrl;
              const money = (value: number | null | undefined) => value == null ? "Not disclosed" : `₹${Number(value).toLocaleString("en-IN")}`;
              const dateLabel = (value?: string | null) => value ? new Date(value).toLocaleString("en-IN", { dateStyle: "medium", ...(value.includes("T") ? { timeStyle: "short" as const } : {}) }) : "Not specified";
              return (
                <article key={property.id} className="property-card" style={{ overflow: "hidden", border: "1px solid var(--border-subtle)", borderRadius: 14, background: "var(--bg-card)", color: "var(--text-primary)", display: "flex", flexDirection: "column", minWidth: 0 }}>
                  <div style={{ position: "relative", height: 220, background: "var(--bg-input)" }}>
                    {image ? <img src={image} alt={property.address} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} onError={(event) => { event.currentTarget.style.display = "none"; }} /> : <div style={{ height: "100%", display: "grid", placeItems: "center", color: "var(--text-muted)", gap: 6 }}><span>Property image not provided by source</span></div>}
                    <span style={{ position: "absolute", top: 12, left: 12, background: "rgba(15,23,42,.88)", color: "#fff", padding: "5px 10px", borderRadius: 6, fontSize: 12, fontWeight: 700 }}>{property.foreclosure_status || "Status unavailable"}</span>
                    <button type="button" onClick={(event) => toggleFavorite(property.id, event)} aria-label={isFavorited ? "Remove saved property" : "Save property"} style={{ position: "absolute", top: 10, right: 10, border: 0, borderRadius: "50%", width: 38, height: 38, background: "rgba(15,23,42,.88)", color: "#fff", cursor: "pointer", fontSize: 18 }}>{isFavorited ? "♥" : "♡"}</button>
                    {isNewlyAdded && <span style={{ position: "absolute", bottom: 10, left: 12, background: "#166534", color: "#fff", padding: "4px 8px", borderRadius: 5, fontSize: 11 }}>JUST ADDED</span>}
                  </div>
                  <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, flex: 1 }}>
                    <div><div style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 700 }}>{bankName}{property.branch_name ? ` · ${property.branch_name}` : ""}</div><h3 style={{ fontSize: 17, lineHeight: 1.35, margin: "5px 0" }}>{property.address}</h3></div>
                    <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>{locationText || "Location details not provided"}</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, padding: 12, borderRadius: 9, background: "var(--bg-input)" }}>
                      <div><div className="field-label" style={{ fontSize: 11 }}>RESERVE PRICE</div><strong style={{ fontSize: 18 }}>{money(property.reserve_price)}</strong></div>
                      <div><div className="field-label" style={{ fontSize: 11 }}>EMD</div><strong>{money(property.emd)}</strong></div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "9px 12px", fontSize: 13 }}>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Property type</span><div style={{ fontWeight: 500 }}>{property.property_type || "Not specified"}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Area</span><div style={{ fontWeight: 500 }}>{property.area_sqft ? `${property.area_sqft.toLocaleString("en-IN")} sq ft` : "As per notice"}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Possession</span><div style={{ fontWeight: 500 }}>{property.possession_type || "Not specified"}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Property ID</span><div style={{ fontWeight: 500 }}>{property.property_unique_id || property.auction_id || `#${property.id}`}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Auction starts</span><div style={{ fontWeight: 500 }}>{dateLabel(property.auction_start || property.auction_date)}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Auction ends</span><div style={{ fontWeight: 500 }}>{dateLabel(property.auction_end)}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>EMD deadline</span><div style={{ fontWeight: 500 }}>{dateLabel(property.emd_deadline)}</div></div>
                      <div><span className="field-label" style={{ fontSize: 11 }}>Inspection</span><div style={{ fontWeight: 500 }}>{property.inspection_start || property.inspection_end ? `${dateLabel(property.inspection_start)} – ${dateLabel(property.inspection_end)}` : "Not specified"}</div></div>
                    </div>
                    {property.reserve_price_per_sqft != null && (
                      <div style={{ color: "var(--accent-blue, #0095f6)", fontSize: 13, fontWeight: 600 }}>
                        Rate: ₹{property.reserve_price_per_sqft.toLocaleString()}/sq ft
                      </div>
                    )}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: "auto", paddingTop: 8 }}>
                      <Link to={`/properties/${property.id}`} style={{ flex: 1, minWidth: 130, textAlign: "center", textDecoration: "none", padding: "10px 12px", borderRadius: 7, background: "var(--accent-blue, #0095f6)", color: "#fff", fontWeight: 700, fontSize: 13 }}>View property</Link>
                      <button type="button" onClick={() => openAnalyst(property.id, property.address)} style={{ padding: "10px 12px", borderRadius: 7, border: "1px solid var(--border-subtle)", background: "transparent", color: "var(--text-primary)", cursor: "pointer" }}>Ask analyst</button>
                      {officialUrl && <a href={officialUrl} target="_blank" rel="noreferrer" style={{ padding: "10px 12px", borderRadius: 7, border: "1px solid var(--border-subtle)", color: "var(--accent-blue, #0095f6)", textDecoration: "none", fontSize: 13, fontWeight: 600 }}>Source listing</a>}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="pagination" style={{ marginTop: 24, justifyContent: "center" }}>
            <button
              type="button"
              disabled={page <= 1 || loading}
              onClick={() => setPage((current) => current - 1)}
              style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)", padding: "8px 16px", borderRadius: 8 }}
            >
              ← Previous
            </button>

            <span style={{ color: "var(--text-secondary)", margin: "0 14px", alignSelf: "center" }}>
              Page {page} of {Math.max(pages, 1)}
            </span>

            <button
              type="button"
              disabled={page >= pages || loading}
              onClick={() => setPage((current) => current + 1)}
              style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)", padding: "8px 16px", borderRadius: 8 }}
            >
              Next →
            </button>
          </div>
        </>
      )}
      {/* Real-Time Filter Awareness Toast Stack */}
      {liveToasts.length > 0 && (
        <div className="ig-toast-container">
          {liveToasts.map((toast) => (
            <div className="ig-live-toast" key={toast.id}>
              <span style={{ fontSize: 20 }}>⚡</span>
              <div className="ig-toast-msg">{toast.message}</div>
              <button
                type="button"
                className="ig-toast-action-btn"
                onClick={() => {
                  clearFilters();
                  dismissToast(toast.id);
                }}
              >
                Show All
              </button>
              <button
                type="button"
                className="ig-toast-close-btn"
                onClick={() => dismissToast(toast.id)}
                title="Dismiss"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <OnboardingModal
        isOpen={onboardingOpen}
        onClose={() => setOnboardingOpen(false)}
        onComplete={handleOnboardingComplete}
      />
    </div>
  );
}

export default Dashboard;
