import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { NavBar } from "./components/NavBar";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { DashboardPage } from "./pages/Dashboard";
import { IntegrationDetailPage } from "./pages/IntegrationDetail";
import { WebhooksPage } from "./pages/Webhooks";
import { WebhookDetailPage } from "./pages/WebhookDetail";
import { SyncJobsPage } from "./pages/SyncJobs";
import { ActivityPage } from "./pages/Activity";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="p-10 text-center text-graphite-500">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return (
    <>
      <NavBar />
      {children}
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <DashboardPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/integrations/:id"
        element={
          <ProtectedLayout>
            <IntegrationDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/webhooks"
        element={
          <ProtectedLayout>
            <WebhooksPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/webhooks/:id"
        element={
          <ProtectedLayout>
            <WebhookDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/sync-jobs"
        element={
          <ProtectedLayout>
            <SyncJobsPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/activity"
        element={
          <ProtectedLayout>
            <ActivityPage />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
