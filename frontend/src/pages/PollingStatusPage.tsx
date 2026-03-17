import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getPollingStatus,
  pollWorkspaceIssues,
  type PollingStatus,
} from "../api/issue_polling";
import { togglePollingEnabled, getWorkspace } from "../api/workspaces";
import type { WorkspaceDetail } from "../types/workspace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertCircle,
  ArrowLeft,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
} from "lucide-react";

const PollingStatusPage = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();

  const [status, setStatus] = useState<PollingStatus | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const loadStatus = async () => {
    if (!workspaceId) return;

    try {
      setLoading(true);
      const [statusResponse, workspaceResponse] = await Promise.all([
        getPollingStatus(parseInt(workspaceId)),
        getWorkspace(parseInt(workspaceId)),
      ]);
      setStatus(statusResponse);
      setWorkspace(workspaceResponse);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load polling status"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleManualPoll = async () => {
    if (!workspaceId || polling) return;

    try {
      setPolling(true);
      setError(null);
      await pollWorkspaceIssues(parseInt(workspaceId));
      // Reload status after polling
      await loadStatus();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to trigger polling"
      );
    } finally {
      setPolling(false);
    }
  };

  const handleTogglePolling = async () => {
    if (!workspace || !workspaceId) return;

    try {
      const newEnabled = !workspace.polling_enabled;
      await togglePollingEnabled(parseInt(workspaceId), newEnabled);

      // Update local state
      setWorkspace({
        ...workspace,
        polling_enabled: newEnabled,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle polling");
    }
  };

  useEffect(() => {
    if (workspaceId) {
      loadStatus();
    }
  }, [workspaceId]);

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";

    const utcDate = new Date(`${dateString}Z`);
    const year = utcDate.getFullYear();
    const month = utcDate.toLocaleString("default", { month: "short" });
    const day = utcDate.getDate();
    const hours = utcDate.getHours();
    const minutes = utcDate.getMinutes().toString().padStart(2, "0");
    const seconds = utcDate.getSeconds().toString().padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    const displayHours = hours % 12 || 12;

    const offset = -utcDate.getTimezoneOffset();
    const offsetHours = Math.floor(Math.abs(offset) / 60);
    const offsetMinutes = Math.abs(offset) % 60;
    const offsetSign = offset >= 0 ? "+" : "-";
    const timezone = `GMT${offsetSign}${offsetHours}:${offsetMinutes
      .toString()
      .padStart(2, "0")}`;

    return `${day} ${month} ${year}, ${displayHours}:${minutes}:${seconds} ${ampm} (${timezone})`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "success":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200">
            <CheckCircle className="w-4 h-4 mr-1.5" />
            Success
          </span>
        );
      case "error":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-destructive/10 text-destructive">
            <XCircle className="w-4 h-4 mr-1.5" />
            Error
          </span>
        );
      case "never":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-muted text-muted-foreground">
            <Clock className="w-4 h-4 mr-1.5" />
            Never Polled
          </span>
        );
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">
            Loading polling status...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <Link
            to={`/workspaces/${workspaceId}`}
            className="text-primary hover:underline mb-4 inline-flex items-center"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Workspace
          </Link>
          <div className="flex items-center justify-between mt-4">
            <div>
              <h1 className="text-4xl font-bold text-foreground">
                Polling Status
              </h1>
              <p className="text-muted-foreground mt-2">
                Track automatic issue detection and PR conflict resolution
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* Auto-Poll Toggle */}
              {workspace &&
                (workspace.role === "owner" || workspace.role === "admin") && (
                  <div className="flex items-center gap-3 border border-border rounded-lg px-4 py-3">
                    <span className="text-sm font-medium text-foreground">
                      Auto-Poll
                    </span>
                    <button
                      onClick={handleTogglePolling}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        workspace.polling_enabled ? "bg-primary" : "bg-muted"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-background transition-transform ${
                          workspace.polling_enabled
                            ? "translate-x-6"
                            : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                )}

              {/* Poll Now Button */}
              <Button onClick={handleManualPoll} disabled={polling}>
                {polling ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Polling...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Poll Now
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Status Display */}
        {status && (
          <div className="space-y-6">
            {/* Overview Card */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Current Status</CardTitle>
                  {getStatusBadge(status.last_poll_status)}
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-1">
                      Last Poll Time
                    </div>
                    <div className="text-lg font-semibold text-foreground">
                      {formatDate(status.last_poll_time)}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-1">
                      Total Issues Imported
                    </div>
                    <div className="text-3xl font-bold text-primary">
                      {status.total_issues_imported}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-medium text-muted-foreground mb-1">
                      Total PR Tasks Created
                    </div>
                    <div className="text-3xl font-bold text-primary">
                      {status.total_pr_tasks_created || 0}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Last Poll Results */}
            {status.last_poll_status !== "never" && (
              <Card>
                <CardHeader>
                  <CardTitle>Last Poll Results</CardTitle>
                </CardHeader>
                <CardContent>
                  {status.last_poll_status === "success" ? (
                    <div className="space-y-6">
                      {/* Issue Results */}
                      <div>
                        <h3 className="text-sm font-semibold text-muted-foreground mb-3">
                          GitHub Issues
                        </h3>
                        <div className="grid grid-cols-3 gap-4">
                          <div className="bg-primary/10 rounded-lg p-4 border border-primary/20">
                            <div className="text-3xl font-bold text-primary">
                              {status.last_poll_issues_found}
                            </div>
                            <div className="text-sm font-medium text-primary/90 mt-1">
                              Issues Found
                            </div>
                            <div className="text-xs text-primary/70 mt-1">
                              with 'avery-developer' label
                            </div>
                          </div>

                          <div className="bg-success/10 rounded-lg p-4 border border-success/20">
                            <div className="text-3xl font-bold text-success">
                              {status.last_poll_issues_linked}
                            </div>
                            <div className="text-sm font-medium text-success/90 mt-1">
                              Issues Linked
                            </div>
                            <div className="text-xs text-success/70 mt-1">
                              new tasks created
                            </div>
                          </div>

                          <div className="bg-muted rounded-lg p-4 border border-border">
                            <div className="text-3xl font-bold text-muted-foreground">
                              {status.last_poll_issues_skipped}
                            </div>
                            <div className="text-sm font-medium text-foreground mt-1">
                              Issues Skipped
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              already linked
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* PR Results */}
                      <div>
                        <h3 className="text-sm font-semibold text-muted-foreground mb-3">
                          Pull Requests
                        </h3>
                        <div className="grid grid-cols-3 gap-4">
                          <div className="bg-accent/10 rounded-lg p-4 border border-accent/20">
                            <div className="text-3xl font-bold text-accent">
                              {status.last_poll_prs_checked || 0}
                            </div>
                            <div className="text-sm font-medium text-accent/90 mt-1">
                              PRs Checked
                            </div>
                            <div className="text-xs text-accent/70 mt-1">
                              with 'avery-developer' label
                            </div>
                          </div>

                          <div className="bg-destructive/10 rounded-lg p-4 border border-destructive/20">
                            <div className="text-3xl font-bold text-destructive">
                              {status.last_poll_prs_with_conflicts || 0}
                            </div>
                            <div className="text-sm font-medium text-destructive/90 mt-1">
                              Conflicts Found
                            </div>
                            <div className="text-xs text-destructive/70 mt-1">
                              PRs with merge conflicts
                            </div>
                          </div>

                          <div className="bg-success/10 rounded-lg p-4 border border-success/20">
                            <div className="text-3xl font-bold text-success">
                              {status.total_pr_tasks_created || 0}
                            </div>
                            <div className="text-sm font-medium text-success/90 mt-1">
                              Tasks Created
                            </div>
                            <div className="text-xs text-success/70 mt-1">
                              conflict resolution tasks
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        <div className="font-semibold mb-1">
                          Last Poll Failed
                        </div>
                        <p className="text-sm font-mono">
                          {status.last_poll_error || "Unknown error occurred"}
                        </p>
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Info Card */}
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <div className="font-semibold mb-2">How It Works</div>
                <ul className="text-sm space-y-1">
                  <li>• Automatic polling runs every 5 minutes</li>
                  <li>
                    • Detects GitHub issues with the 'avery-developer' label and automatically creates tasks
                  </li>
                  <li>
                    • Detects pull requests with the 'avery-developer' label that have merge conflicts
                  </li>
                  <li>
                    • Automatically creates conflict resolution tasks for PRs with conflicts
                  </li>
                  <li>• Skips issues and PRs that are already linked to tasks</li>
                  <li>
                    • You can manually trigger polling anytime using the "Poll Now" button
                  </li>
                </ul>
              </AlertDescription>
            </Alert>
          </div>
        )}
      </div>
    </div>
  );
};

export default PollingStatusPage;
