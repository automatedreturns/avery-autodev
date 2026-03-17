/**
 * Test Generation Detail Page
 * Displays full details of a test generation job including progress, results, and PR creation
 */

import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getTestGenerationJob, retryTestGeneration } from "../api/test_generation";
import type { AgentTestGeneration } from "../types/test_generation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  ExternalLink,
  Copy,
  GitBranch,
  Timer,
  Zap,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

export default function TestGenerationDetailPage() {
  const { workspaceId, jobId } = useParams<{ workspaceId: string; jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<AgentTestGeneration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [copied, setCopied] = useState(false);
  const pollingIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (jobId) {
      loadJob();
      startPolling();
    }
    return () => stopPolling();
  }, [jobId]);

  const loadJob = async () => {
    try {
      setError("");
      const data = await getTestGenerationJob(parseInt(jobId!));
      setJob(data);

      // Stop polling if job is complete
      if (data.status === "completed" || data.status === "failed") {
        stopPolling();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load test generation job");
    } finally {
      setLoading(false);
    }
  };

  const startPolling = () => {
    stopPolling();
    pollingIntervalRef.current = window.setInterval(async () => {
      if (job && (job.status === "pending" || job.status === "generating" || job.status === "validating")) {
        await loadJob();
      }
    }, 2000);
  };

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  const handleRetry = async () => {
    if (!job) return;
    try {
      setRetrying(true);
      await retryTestGeneration(job.id);
      await loadJob();
      startPolling();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retry job");
    } finally {
      setRetrying(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
            <Clock className="w-4 h-4 mr-1.5" />
            Pending
          </span>
        );
      case "generating":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
            Generating Tests
          </span>
        );
      case "validating":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
            Validating
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
            <CheckCircle className="w-4 h-4 mr-1.5" />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
            <XCircle className="w-4 h-4 mr-1.5" />
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
            {status}
          </span>
        );
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return "N/A";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <span className="ml-2 text-muted-foreground">Loading job details...</span>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error || "Job not found"}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Workspace
        </Button>
      </div>
    );
  }

  const branchName = job.agent_run_metadata?.branch_name;
  const prUrl = job.agent_run_metadata?.pr_url;
  const prNumber = job.agent_run_metadata?.pr_number;
  const prLink = job.agent_run_metadata?.pr_link;

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      {/* Breadcrumb */}
      <nav className="flex mb-6" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-2 text-sm">
          <li>
            <Link
              to="/workspaces"
              className="text-muted-foreground hover:text-foreground"
            >
              Workspaces
            </Link>
          </li>
          <li><span className="text-muted-foreground">/</span></li>
          <li>
            <Link
              to={`/workspaces/${workspaceId}`}
              className="text-muted-foreground hover:text-foreground"
            >
              Workspace
            </Link>
          </li>
          <li><span className="text-muted-foreground">/</span></li>
          <li>
            <Link
              to={`/workspaces/${workspaceId}/test-generation`}
              className="text-muted-foreground hover:text-foreground"
            >
              Test Generation
            </Link>
          </li>
          <li><span className="text-muted-foreground">/</span></li>
          <li>
            <span className="text-foreground font-medium">Job #{job.id}</span>
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Wand2 className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold">Test Generation Job #{job.id}</h1>
            {getStatusBadge(job.status)}
          </div>
          <p className="text-muted-foreground">
            Created {formatDate(job.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadJob}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          {job.status === "failed" && job.retry_count < job.max_retries && (
            <Button onClick={handleRetry} disabled={retrying}>
              {retrying ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Retry
            </Button>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {job.error_message && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{job.error_message}</AlertDescription>
        </Alert>
      )}

      {/* PR/Branch Section - Show for completed jobs */}
      {job.status === "completed" && (
        <Card className="mb-6 border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20">
          <CardHeader>
            <div className="flex items-center gap-3">
              <GitPullRequest className="w-6 h-6 text-green-600" />
              <CardTitle>
                {prNumber ? "Pull Request Created" : "Ready to Create Pull Request"}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {branchName && (
              <div className="flex items-center justify-between p-3 bg-background rounded-lg border">
                <div className="flex items-center gap-2">
                  <GitBranch className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Branch:</span>
                  <code className="font-mono text-sm">{branchName}</code>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(branchName)}
                >
                  {copied ? <CheckCircle2 className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            )}

            {prUrl && !prNumber && (
              <Button asChild className="w-full" size="lg">
                <a href={prUrl} target="_blank" rel="noopener noreferrer">
                  <GitPullRequest className="h-5 w-5 mr-2" />
                  Create Pull Request
                  <ExternalLink className="h-4 w-4 ml-2" />
                </a>
              </Button>
            )}

            {prNumber && (
              <div className="flex items-center justify-between p-3 bg-background rounded-lg border">
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  Pull Request #{prNumber} created
                </div>
                {prLink && (
                  <Button asChild variant="outline" size="sm">
                    <a href={prLink} target="_blank" rel="noopener noreferrer">
                      View PR
                      <ExternalLink className="h-3 w-3 ml-1" />
                    </a>
                  </Button>
                )}
              </div>
            )}

            {!branchName && !prUrl && !prNumber && (
              <p className="text-sm text-muted-foreground">
                Tests were generated successfully. Branch information is not available for this job.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <BarChart3 className="h-4 w-4" />
              Tests Generated
            </div>
            <div className="text-2xl font-bold">{job.tests_generated_count}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <CheckCircle className="h-4 w-4" />
              Tests Passed
            </div>
            <div className="text-2xl font-bold text-green-600">{job.tests_passed_count}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <XCircle className="h-4 w-4" />
              Tests Failed
            </div>
            <div className="text-2xl font-bold text-red-600">{job.tests_failed_count}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <Timer className="h-4 w-4" />
              Duration
            </div>
            <div className="text-2xl font-bold">{formatDuration(job.duration_seconds)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Quality & Coverage */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Quality Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            {job.test_quality_score !== undefined && job.test_quality_score !== null ? (
              <div className="space-y-3">
                <div className="flex items-end gap-2">
                  <span className={`text-4xl font-bold ${
                    job.test_quality_score >= 70 ? "text-green-600" :
                    job.test_quality_score >= 50 ? "text-yellow-600" : "text-red-600"
                  }`}>
                    {job.test_quality_score.toFixed(0)}
                  </span>
                  <span className="text-muted-foreground text-lg mb-1">/ 100</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      job.test_quality_score >= 70 ? "bg-green-500" :
                      job.test_quality_score >= 50 ? "bg-yellow-500" : "bg-red-500"
                    }`}
                    style={{ width: `${job.test_quality_score}%` }}
                  />
                </div>
                <div className="flex items-center gap-2 text-sm">
                  {job.validation_passed ? (
                    <span className="flex items-center gap-1 text-green-600">
                      <CheckCircle className="h-4 w-4" /> Validation passed
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-yellow-600">
                      <AlertTriangle className="h-4 w-4" /> Validation pending
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground">Not available yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Coverage Impact
            </CardTitle>
          </CardHeader>
          <CardContent>
            {job.coverage_delta !== undefined && job.coverage_delta !== null ? (
              <div className="space-y-3">
                <div className="flex items-end gap-2">
                  <span className={`text-4xl font-bold ${
                    job.coverage_delta > 0 ? "text-green-600" :
                    job.coverage_delta < 0 ? "text-red-600" : "text-gray-600"
                  }`}>
                    {job.coverage_delta > 0 ? "+" : ""}{job.coverage_delta.toFixed(1)}%
                  </span>
                </div>
                {(job.coverage_before !== undefined || job.coverage_after !== undefined) && (
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    {job.coverage_before !== undefined && (
                      <span>Before: {job.coverage_before.toFixed(1)}%</span>
                    )}
                    {job.coverage_after !== undefined && (
                      <span>After: {job.coverage_after.toFixed(1)}%</span>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">Not available yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Source Files */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <FileCode className="h-5 w-5" />
            Source Files ({job.source_files.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {job.source_files.length > 0 ? (
            <div className="space-y-2">
              {job.source_files.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 bg-muted rounded-lg font-mono text-sm"
                >
                  <FileCode className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <span className="truncate">{file}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No source files specified</p>
          )}
        </CardContent>
      </Card>

      {/* Generated Test Files */}
      {job.generated_test_files.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              Generated Test Files ({job.generated_test_files.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {job.generated_test_files.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 bg-green-50 dark:bg-green-900/20 rounded-lg font-mono text-sm"
                >
                  <FileCode className="h-4 w-4 text-green-600 flex-shrink-0" />
                  <span className="truncate text-green-700 dark:text-green-300">{file}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Validation Errors */}
      {job.validation_errors && job.validation_errors.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2 text-yellow-600">
              <AlertTriangle className="h-5 w-5" />
              Validation Errors ({job.validation_errors.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {job.validation_errors.map((error, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-sm"
                >
                  <AlertCircle className="h-4 w-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <span className="text-yellow-700 dark:text-yellow-300">{error}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Job Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Job Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Trigger Type</dt>
              <dd className="font-medium capitalize">{job.trigger_type.replace("_", " ")}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Generation Method</dt>
              <dd className="font-medium capitalize">{job.generation_method || "N/A"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Retry Count</dt>
              <dd className="font-medium">{job.retry_count} / {job.max_retries}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Tokens Used</dt>
              <dd className="font-medium">
                {job.prompt_tokens_used + job.completion_tokens_used > 0
                  ? `${(job.prompt_tokens_used + job.completion_tokens_used).toLocaleString()} tokens`
                  : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd className="font-medium">{formatDate(job.created_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed</dt>
              <dd className="font-medium">{formatDate(job.completed_at)}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
