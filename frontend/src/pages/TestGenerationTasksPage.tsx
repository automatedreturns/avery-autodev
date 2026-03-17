/**
 * Test Generation Tasks Page
 * Displays all test generation jobs for a workspace with status and progress
 */

import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { listTestGenerationJobs, retryTestGeneration } from "../api/test_generation";
import type { AgentTestGeneration, TestGenerationStatus } from "../types/test_generation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertCircle,
  ArrowLeft,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  FileCode,
  GitPullRequest,
  BarChart3,
  Wand2,
} from "lucide-react";

export default function TestGenerationTasksPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<AgentTestGeneration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<TestGenerationStatus | "all">("all");
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (workspaceId) {
      loadJobs();
      startPolling();
    }
    return () => stopPolling();
  }, [workspaceId, filter]);

  const loadJobs = async () => {
    try {
      setError("");
      const statusFilter = filter === "all" ? undefined : filter;
      const data = await listTestGenerationJobs(parseInt(workspaceId!), statusFilter);
      setJobs(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load test generation jobs");
    } finally {
      setLoading(false);
    }
  };

  const startPolling = () => {
    stopPolling();
    pollingIntervalRef.current = window.setInterval(async () => {
      // Only poll if there are active jobs
      const hasActiveJobs = jobs.some(
        (job) => job.status === "pending" || job.status === "generating" || job.status === "validating"
      );
      if (hasActiveJobs) {
        await loadJobs();
      }
    }, 3000);
  };

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  const handleRetry = async (jobId: number) => {
    try {
      setRetryingJobId(jobId);
      await retryTestGeneration(jobId);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retry job");
    } finally {
      setRetryingJobId(null);
    }
  };

  const getStatusBadge = (status: TestGenerationStatus) => {
    switch (status) {
      case "pending":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
            <Clock className="w-3 h-3 mr-1" />
            Pending
          </span>
        );
      case "generating":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            Generating
          </span>
        );
      case "validating":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            Validating
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
            <CheckCircle className="w-3 h-3 mr-1" />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
            <XCircle className="w-3 h-3 mr-1" />
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            {status}
          </span>
        );
    }
  };

  const getTriggerTypeBadge = (triggerType: string) => {
    const colors: Record<string, string> = {
      feature: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
      bug_fix: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
      manual: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      regression: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
      refactor: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200",
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[triggerType] || "bg-gray-100 text-gray-800"}`}>
        {triggerType.replace("_", " ")}
      </span>
    );
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <span className="ml-2 text-muted-foreground">Loading test generation tasks...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/workspaces/${workspaceId}`)}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workspace
          </Button>
          <div className="flex items-center gap-2">
            <Wand2 className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">Test Generation Tasks</h1>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadJobs}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {(["all", "pending", "generating", "validating", "completed", "failed"] as const).map((status) => (
          <Button
            key={status}
            variant={filter === status ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(status)}
          >
            {status === "all" ? "All" : status.charAt(0).toUpperCase() + status.slice(1)}
          </Button>
        ))}
      </div>

      {/* Jobs List */}
      {jobs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Wand2 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
            <h3 className="text-lg font-semibold mb-2">No test generation tasks</h3>
            <p className="text-gray-600 mb-4">
              Test generation tasks will appear here when you generate tests.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <Link key={job.id} to={`/workspaces/${workspaceId}/test-generation/${job.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    {/* Left: Job Info */}
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusBadge(job.status)}
                        {getTriggerTypeBadge(job.trigger_type)}
                        <span className="text-sm text-muted-foreground">
                          Job #{job.id}
                        </span>
                      </div>

                    {/* Source Files */}
                    <div className="mb-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                        <FileCode className="h-4 w-4" />
                        <span>Source Files:</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {job.source_files.slice(0, 3).map((file, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center px-2 py-1 rounded bg-muted text-xs font-mono truncate max-w-[200px]"
                            title={file}
                          >
                            {file.split("/").pop()}
                          </span>
                        ))}
                        {job.source_files.length > 3 && (
                          <span className="text-xs text-muted-foreground">
                            +{job.source_files.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Stats Row */}
                    <div className="flex items-center gap-6 text-sm">
                      <div className="flex items-center gap-1">
                        <BarChart3 className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Tests:</span>
                        <span className="font-medium">{job.tests_generated_count}</span>
                      </div>

                      {job.test_quality_score !== undefined && job.test_quality_score !== null && (
                        <div className="flex items-center gap-1">
                          <span className="text-muted-foreground">Quality:</span>
                          <span className={`font-medium ${job.test_quality_score >= 70 ? "text-green-600" : job.test_quality_score >= 50 ? "text-yellow-600" : "text-red-600"}`}>
                            {job.test_quality_score}%
                          </span>
                        </div>
                      )}

                      {job.coverage_delta !== undefined && job.coverage_delta !== null && (
                        <div className="flex items-center gap-1">
                          <span className="text-muted-foreground">Coverage:</span>
                          <span className={`font-medium ${job.coverage_delta > 0 ? "text-green-600" : job.coverage_delta < 0 ? "text-red-600" : "text-gray-600"}`}>
                            {job.coverage_delta > 0 ? "+" : ""}{job.coverage_delta.toFixed(1)}%
                          </span>
                        </div>
                      )}

                      {job.agent_run_metadata?.pr_number && (
                        <div className="flex items-center gap-1">
                          <GitPullRequest className="h-4 w-4 text-muted-foreground" />
                          <span className="text-muted-foreground">PR:</span>
                          <span className="font-medium">#{job.agent_run_metadata.pr_number}</span>
                        </div>
                      )}

                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        {formatDate(job.created_at)}
                      </div>
                    </div>

                    {/* Error Message */}
                    {job.error_message && (
                      <div className="mt-3 p-2 bg-red-50 dark:bg-red-900/20 rounded text-sm text-red-700 dark:text-red-300">
                        {job.error_message}
                      </div>
                    )}

                    {/* Generated Files */}
                    {job.generated_test_files.length > 0 && (
                      <div className="mt-3">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                          <CheckCircle className="h-4 w-4 text-green-500" />
                          <span>Generated Files:</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {job.generated_test_files.slice(0, 3).map((file, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center px-2 py-1 rounded bg-green-50 dark:bg-green-900/20 text-xs font-mono text-green-700 dark:text-green-300 truncate max-w-[200px]"
                              title={file}
                            >
                              {file.split("/").pop()}
                            </span>
                          ))}
                          {job.generated_test_files.length > 3 && (
                            <span className="text-xs text-muted-foreground">
                              +{job.generated_test_files.length - 3} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-2 ml-4">
                      {job.status === "failed" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            handleRetry(job.id);
                          }}
                          disabled={retryingJobId === job.id}
                        >
                          {retryingJobId === job.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <RefreshCw className="h-4 w-4 mr-1" />
                              Retry
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
