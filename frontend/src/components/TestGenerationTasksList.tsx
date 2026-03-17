/**
 * Test Generation Tasks List Component
 * Displays test generation jobs for a workspace with status and progress
 */

import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { listTestGenerationJobs, retryTestGeneration } from "../api/test_generation";
import type { AgentTestGeneration, TestGenerationStatus } from "../types/test_generation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  FileCode,
  GitPullRequest,
  BarChart3,
  Wand2,
  ExternalLink,
} from "lucide-react";

interface TestGenerationTasksListProps {
  workspaceId: number;
  limit?: number;
}

export default function TestGenerationTasksList({
  workspaceId,
  limit = 10,
}: TestGenerationTasksListProps) {
  const [jobs, setJobs] = useState<AgentTestGeneration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    loadJobs();
    startPolling();
    return () => stopPolling();
  }, [workspaceId]);

  const loadJobs = async () => {
    try {
      setError("");
      const data = await listTestGenerationJobs(workspaceId, undefined, undefined, limit);
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
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">Loading tasks...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
        <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="text-center py-8 bg-muted/30 rounded-lg border border-dashed">
        <Wand2 className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
        <h3 className="text-sm font-medium mb-1">No test generation tasks</h3>
        <p className="text-sm text-muted-foreground">
          Tasks will appear here when you generate tests.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header with refresh and view all */}
      <div className="flex items-center justify-between mb-2">
        <Button variant="ghost" size="sm" onClick={loadJobs}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
        <Link
          to={`/workspaces/${workspaceId}/test-generation`}
          className="text-sm text-primary hover:underline inline-flex items-center gap-1"
        >
          View all tasks
          <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

      {/* Jobs List */}
      {jobs.map((job) => (
        <Link key={job.id} to={`/workspaces/${workspaceId}/test-generation/${job.id}`}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardContent className="p-3">
              <div className="flex items-start justify-between gap-3">
                {/* Left: Job Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    {getStatusBadge(job.status)}
                    {getTriggerTypeBadge(job.trigger_type)}
                    <span className="text-xs text-muted-foreground">#{job.id}</span>
                  </div>

                {/* Source Files */}
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
                  <FileCode className="h-3 w-3 flex-shrink-0" />
                  <span className="truncate">
                    {job.source_files.length > 0
                      ? job.source_files[0].split("/").pop()
                      : "No files"}
                    {job.source_files.length > 1 && ` +${job.source_files.length - 1}`}
                  </span>
                </div>

                {/* Stats Row */}
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1">
                    <BarChart3 className="h-3 w-3 text-muted-foreground" />
                    <span>{job.tests_generated_count} tests</span>
                  </div>

                  {job.test_quality_score !== undefined && job.test_quality_score !== null && (
                    <span className={job.test_quality_score >= 70 ? "text-green-600" : job.test_quality_score >= 50 ? "text-yellow-600" : "text-red-600"}>
                      {job.test_quality_score}% quality
                    </span>
                  )}

                  {job.agent_run_metadata?.pr_number && (
                    <div className="flex items-center gap-1">
                      <GitPullRequest className="h-3 w-3" />
                      <span>#{job.agent_run_metadata.pr_number}</span>
                    </div>
                  )}

                  <span className="text-muted-foreground">{formatDate(job.created_at)}</span>
                </div>

                {/* Error Message */}
                {job.error_message && (
                  <p className="mt-1.5 text-xs text-red-600 dark:text-red-400 truncate" title={job.error_message}>
                    {job.error_message}
                  </p>
                )}
              </div>

              {/* Right: Actions */}
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
                  className="flex-shrink-0"
                >
                  {retryingJobId === job.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3" />
                  )}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
        </Link>
      ))}
    </div>
  );
}
