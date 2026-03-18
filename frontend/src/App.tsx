import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import ProtectedRoute from "./components/ProtectedRoute";
import { PublicLayout } from "./components/PublicLayout";
import { useVersionCheck } from "./hooks/useVersionCheck";
import HomePage from "./pages/HomePage";
import SignUpPage from "./pages/SignUpPage";
import SignInPage from "./pages/SignInPage";
import GoogleCallbackPage from "./pages/GoogleCallbackPage";
import MagicLinkVerifyPage from "./pages/MagicLinkVerifyPage";
import ProfilePage from "./pages/ProfilePage";
import WorkspacesPage from "./pages/WorkspacesPage";
import WorkspaceDetailPage from "./pages/WorkspaceDetailPage";
import CreateWorkspacePage from "./pages/CreateWorkspacePage";
import GitHubSetupPage from "./pages/GitHubSetupPage";
import CoderAgentPage from "./pages/CoderAgentPage";
import PollingStatusPage from "./pages/PollingStatusPage";
import TestSuitesPage from "./pages/TestSuitesPage";
import TestSuiteDetailPage from "./pages/TestSuiteDetailPage";
import TestRunResultsPage from "./pages/TestRunResultsPage";
import CIRunDetailPage from "./pages/CIRunDetailPage";
import TestGenerationTasksPage from "./pages/TestGenerationTasksPage";
import TestGenerationDetailPage from "./pages/TestGenerationDetailPage";
import ContactPage from "./pages/ContactPage";
import NotFoundPage from "./pages/NotFoundPage";

function App() {
  // Auto-reload when new version is deployed (production only)
  useVersionCheck();

  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            {/* Public routes with shared layout */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/signup" element={<SignUpPage />} />
              <Route path="/signin" element={<SignInPage />} />
              <Route path="/contact" element={<ContactPage />} />
            </Route>

            {/* Auth callback routes (no layout needed) */}
            <Route
              path="/auth/google/callback"
              element={<GoogleCallbackPage />}
            />
            <Route path="/auth/verify" element={<MagicLinkVerifyPage />} />

            {/* Protected routes */}
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces"
              element={
                <ProtectedRoute>
                  <WorkspacesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/new"
              element={
                <ProtectedRoute>
                  <CreateWorkspacePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:id"
              element={
                <ProtectedRoute>
                  <WorkspaceDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/tasks/:taskId/agent"
              element={
                <ProtectedRoute>
                  <CoderAgentPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/polling-status"
              element={
                <ProtectedRoute>
                  <PollingStatusPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/test-suites"
              element={
                <ProtectedRoute>
                  <TestSuitesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/test-suites/:suiteId"
              element={
                <ProtectedRoute>
                  <TestSuiteDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/test-runs/:runId"
              element={
                <ProtectedRoute>
                  <TestRunResultsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/ci/:ciRunId"
              element={
                <ProtectedRoute>
                  <CIRunDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/test-generation"
              element={
                <ProtectedRoute>
                  <TestGenerationTasksPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workspaces/:workspaceId/test-generation/:jobId"
              element={
                <ProtectedRoute>
                  <TestGenerationDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/github-setup"
              element={
                <ProtectedRoute>
                  <GitHubSetupPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
