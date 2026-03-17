import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getTestRun, getTestResults } from "../api/test_suites";
import type { TestRun, TestResult } from "../types/test_suite";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle,
  XCircle,
  Clock,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";

export default function TestRunResultsPage() {
  const { workspaceId, runId } = useParams<{ workspaceId: string; runId: string }>();
  const navigate = useNavigate();

  const [testRun, setTestRun] = useState<TestRun | null>(null);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "passed" | "failed" | "skipped">("all");

  useEffect(() => {
    if (workspaceId && runId) {
      loadTestRunData();
    }
  }, [workspaceId, runId]);

  const loadTestRunData = async () => {
    try {
      setLoading(true);
      setError("");

      const [run, resultsData] = await Promise.all([
        getTestRun(parseInt(workspaceId!), parseInt(runId!)),
        getTestResults(parseInt(workspaceId!), parseInt(runId!)),
      ]);

      setTestRun(run);
      setTestResults(resultsData.test_results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load test run data");
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "passed":
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case "failed":
        return <XCircle className="h-5 w-5 text-red-600" />;
      case "skipped":
        return <AlertTriangle className="h-5 w-5 text-yellow-600" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-green-600 bg-green-50 border-green-200";
      case "failed":
        return "text-red-600 bg-red-50 border-red-200";
      case "running":
        return "text-blue-600 bg-blue-50 border-blue-200";
      default:
        return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  const filteredResults = testResults.filter((result) => {
    if (filter === "all") return true;
    return result.status === filter;
  });

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">Loading test run results...</div>
      </div>
    );
  }

  if (!testRun) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Test run not found</AlertDescription>
        </Alert>
      </div>
    );
  }

  const successRate =
    testRun.total_tests > 0
      ? ((testRun.passed_tests / testRun.total_tests) * 100).toFixed(1)
      : "0";

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center gap-4 mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/workspaces/${workspaceId}/test-suites/${testRun.test_suite_id}`)}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Test Suite
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Test Run #{testRun.id}</h1>
          <p className="text-gray-600 mt-1">
            Branch: {testRun.branch_name} • Triggered: {testRun.trigger_type}
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className={`mb-6 border-2 ${getStatusColor(testRun.status)}`}>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {getStatusIcon(testRun.status)}
              <div>
                <div className="text-lg font-semibold capitalize">{testRun.status}</div>
                <div className="text-sm text-gray-600">
                  {testRun.started_at && (
                    <span>Started: {new Date(testRun.started_at).toLocaleString()}</span>
                  )}
                  {testRun.completed_at && (
                    <span className="ml-4">
                      Completed: {new Date(testRun.completed_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            </div>
            {testRun.duration_seconds !== null && (
              <div className="text-right">
                <div className="text-2xl font-bold">
                  {testRun.duration_seconds.toFixed(1)}s
                </div>
                <div className="text-sm text-gray-600">Duration</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {testRun.error_message && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <div className="font-semibold mb-1">Error</div>
            <div className="text-sm">{testRun.error_message}</div>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-5 mb-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total Tests
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{testRun.total_tests}</div>
          </CardContent>
        </Card>

        <Card className="border-green-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-green-600">
              Passed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {testRun.passed_tests}
            </div>
          </CardContent>
        </Card>

        <Card className="border-red-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-red-600">
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {testRun.failed_tests}
            </div>
          </CardContent>
        </Card>

        <Card className="border-yellow-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-yellow-600">
              Skipped
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {testRun.skipped_tests}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Success Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-blue-600" />
              <div className="text-2xl font-bold">{successRate}%</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {testRun.coverage_percentage !== null && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Code Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-blue-600 h-4 rounded-full transition-all"
                    style={{ width: `${testRun.coverage_percentage}%` }}
                  />
                </div>
              </div>
              <div className="text-2xl font-bold">
                {testRun.coverage_percentage.toFixed(1)}%
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Test Results ({filteredResults.length})</CardTitle>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={filter === "all" ? "default" : "outline"}
                onClick={() => setFilter("all")}
              >
                All
              </Button>
              <Button
                size="sm"
                variant={filter === "passed" ? "default" : "outline"}
                onClick={() => setFilter("passed")}
              >
                Passed
              </Button>
              <Button
                size="sm"
                variant={filter === "failed" ? "default" : "outline"}
                onClick={() => setFilter("failed")}
              >
                Failed
              </Button>
              <Button
                size="sm"
                variant={filter === "skipped" ? "default" : "outline"}
                onClick={() => setFilter("skipped")}
              >
                Skipped
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {filteredResults.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No test results found for this filter
            </div>
          ) : (
            <div className="space-y-3">
              {filteredResults.map((result) => (
                <div
                  key={result.id}
                  className={`p-4 border rounded ${
                    result.status === "failed" ? "border-red-200 bg-red-50" : ""
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      {getStatusIcon(result.status)}
                      <div className="flex-1">
                        <div className="font-medium">{result.test_name}</div>
                        <div className="text-sm text-gray-600 mt-1">
                          {result.file_path}
                        </div>

                        {result.error_message && (
                          <Alert variant="destructive" className="mt-3">
                            <AlertDescription>
                              <div className="font-semibold mb-1">Error Message</div>
                              <pre className="text-xs whitespace-pre-wrap font-mono">
                                {result.error_message}
                              </pre>
                            </AlertDescription>
                          </Alert>
                        )}

                        {result.stack_trace && (
                          <details className="mt-3">
                            <summary className="cursor-pointer text-sm font-semibold text-gray-700">
                              Stack Trace
                            </summary>
                            <pre className="mt-2 text-xs whitespace-pre-wrap font-mono bg-gray-100 p-3 rounded">
                              {result.stack_trace}
                            </pre>
                          </details>
                        )}

                        {result.output && (
                          <details className="mt-3">
                            <summary className="cursor-pointer text-sm font-semibold text-gray-700">
                              Output
                            </summary>
                            <pre className="mt-2 text-xs whitespace-pre-wrap font-mono bg-gray-100 p-3 rounded">
                              {result.output}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>

                    {result.duration_seconds !== null && (
                      <div className="text-sm text-gray-500 ml-4">
                        {result.duration_seconds.toFixed(3)}s
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
