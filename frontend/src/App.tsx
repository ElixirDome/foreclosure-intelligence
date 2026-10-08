import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PropertyDetails from "./pages/PropertyDetails";
import Login from "./pages/Login";
import ProtectedRoute from "./components/ProtectedRoute";
import Import from "./pages/Import";
import Research from "./pages/Research";
import ErrorBoundary from "./components/ErrorBoundary";

function App() {
  return (
    <BrowserRouter>
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
        <Route
          path="/research"
          element={
            <ProtectedRoute>
              <ErrorBoundary>
                <Research />
              </ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/import"
          element={
            <ProtectedRoute>
              <Import />
            </ProtectedRoute>
          }
        />
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
      </Routes>
    </BrowserRouter>
  );
}

export default App;
