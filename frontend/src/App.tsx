import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PropertyDetails from "./pages/PropertyDetails";
import Login from "./pages/Login";
import ProtectedRoute from "./components/ProtectedRoute";
import Import from "./pages/Import";
import ErrorBoundary from "./components/ErrorBoundary";
import ChatBot from "./components/ChatBot";
import { AnalystProvider } from "./context/AnalystContext";
import api from "./api/client";

function DocumentDownloadRedirect() {
  const { id } = useParams<{ id: string }>();
  useEffect(() => {
    if (id) {
      const backendUrl = api.defaults.baseURL || "http://127.0.0.1:8000";
      window.location.href = `${backendUrl}/documents/${id}/file`;
    }
  }, [id]);

  return (
    <div style={{ padding: 32, textAlign: "center", color: "var(--color-text-secondary, #666)" }}>
      Opening auction document...
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AnalystProvider>
        <ChatBot />
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          {/* Unified routing: Research page redirects cleanly to primary dashboard with analyst open */}
          <Route
            path="/research"
            element={<Navigate to="/dashboard?analyst=open" replace />}
          />
          <Route
            path="/admin/import"
            element={
              <ProtectedRoute>
                <Import />
              </ProtectedRoute>
            }
          />
          {/* Route aliases for seamless navigation */}
          <Route path="/import" element={<Navigate to="/admin/import" replace />} />
          <Route path="/admin" element={<Navigate to="/admin/import" replace />} />
          <Route path="/properties" element={<Navigate to="/dashboard" replace />} />
          <Route path="/documents/:id/file" element={<DocumentDownloadRedirect />} />

          <Route
            path="/properties/:id"
            element={
              <ProtectedRoute>
                <ErrorBoundary>
                  <PropertyDetails />
                </ErrorBoundary>
              </ProtectedRoute>
            }
          />
          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AnalystProvider>
    </BrowserRouter>
  );
}

export default App;
