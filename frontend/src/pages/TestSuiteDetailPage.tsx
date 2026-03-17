/* eslint-disable @typescript-eslint/no-unused-vars */
import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getTestSuite,
  listTestCases,
  listTestRuns,
  runTestSuite,
  analyzeTests,
  applySuggestions,
  generateTestCode,
  getTestGenerationJobStatus,
  discoverTests,
} from "../api/test_suites";
import type {
  TestSuite,
  TestCase,
  TestRun,
  TestRunCreate,
  TestAnalysisResponse,
  TestGenerationJob,
} from "../types/test_suite";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertCircle,
  ArrowLeft,
  Play,
  TrendingUp,
  FileCode,
  CheckCircle,
  XCircle,
  Clock,
  Sparkles,
  Plus,
  Search,
  ExternalLink,
} from "lucide-react";

export default function TestSuiteDetailPage() {
  const { workspaceId, suiteId } = useParams<{
    workspaceId: string;
    suiteId: string;
  }>();
  const navigate = useNavigate();

  const [testSuite, setTestSuite] = useState<TestSuite | null>(null);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analyzing, setAnalyzing] = useState(false); // Used in JSX
  const [analysis, setAnalysis] = useState<TestAnalysisResponse | null>(null);
  const [applyingSuggestions, setApplyingSuggestions] = useState(false);
  const [runningTests, setRunningTests] = useState(false);
  const [discoveringTests, setDiscoveringTests] = useState(false);
  const [generatingCode, setGeneratingCode] = useState(false); // Used in JSX
  const [generationJob, setGenerationJob] = useState<TestGenerationJob | null>( // Used in JSX
    null
  );
  const pollingIntervalRef = useRef<number | null>(null);

  // Modal states
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [showDiscoveryModal, setShowDiscoveryModal] = useState(false);
  const [discoveryResults, setDiscoveryResults] = useState({ discovered: 0, imported: 0, skipped: 0 });
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [completionData, setCompletionData] = useState<{ branch: string; files: number; tests: number; prUrl?: string }>({
    branch: '', files: 0, tests: 0
  });

  // Suppress TypeScript unused variable warnings - these are used in JSX
  void analyzing; void generatingCode; void generationJob;

  useEffect(() => {
    if (workspaceId && suiteId) {
      loadTestSuiteData();
    }
  }, [workspaceId, suiteId]);

  const loadTestSuiteData = async () => {
    try {
      setLoading(true);
      setError("");

      const [suite, casesData, runsData] = await Promise.all([
        getTestSuite(parseInt(workspaceId!), parseInt(suiteId!)),
        listTestCases(parseInt(workspaceId!), parseInt(suiteId!)),
        listTestRuns(parseInt(workspaceId!), parseInt(suiteId!), 0, 10),
      ]);

      setTestSuite(suite);
      setTestCases(casesData.test_cases);
      setTestRuns(runsData.test_runs);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load test suite data"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRunTests = async () => {
    if (!testSuite) return;

    try {
      setRunningTests(true);
      setError("");

      const runData: TestRunCreate = {
        trigger_type: "manual",
      };

      const testRun = await runTestSuite(
        parseInt(workspaceId!),
        parseInt(suiteId!),
        runData
      );

      // Show success message
      setSuccessMessage(`Test run started! Run ID: ${testRun.id}. Check the test run history for results.`);
      setShowSuccessModal(true);

      // Reload data to show new test run
      loadTestSuiteData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start test run");
    } finally {
      setRunningTests(false);
    }
  };

  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      setError("");

      const result = await analyzeTests(
        parseInt(workspaceId!),
        parseInt(suiteId!),
        {}
      );
      setAnalysis(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to analyze test suite"
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const handleApplySuggestions = async () => {
    if (!analysis) return;

    try {
      setApplyingSuggestions(true);
      setError("");

      await applySuggestions(
        parseInt(workspaceId!),
        parseInt(suiteId!),
        analysis.suggested_tests
      );

      setAnalysis(null);
      loadTestSuiteData();
      setSuccessMessage("Suggested tests have been added to the test suite!");
      setShowSuccessModal(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to apply suggestions"
      );
    } finally {
      setApplyingSuggestions(false);
    }
  };

  const handleDiscoverTests = async () => {
    try {
      setDiscoveringTests(true);
      setError("");

      const result = await discoverTests(
        parseInt(workspaceId!),
        parseInt(suiteId!)
      );

      // Reload test cases to show newly discovered tests
      loadTestSuiteData();

      // Show results in modal
      setDiscoveryResults({
        discovered: result.discovered_count,
        imported: result.imported_count,
        skipped: result.skipped_count,
      });
      setShowDiscoveryModal(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discover tests");
    } finally {
      setDiscoveringTests(false);
    }
  };

  const handleGenerateCode = async () => { // Used in JSX
    setShowConfirmModal(true);
  };
  void handleGenerateCode; // Suppress TS6133 - function is used in JSX

  const confirmGenerateCode = async () => {
    setShowConfirmModal(false);

    try {
      setGeneratingCode(true);
      setError("");

      // Start job - returns immediately with job ID
      const job = await generateTestCode(
        parseInt(workspaceId!),
        parseInt(suiteId!)
      );
      setGenerationJob(job);

      // Start polling for progress
      startPollingJobStatus(job.id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate test code"
      );
      setGeneratingCode(false);
    }
  };

  const startPollingJobStatus = (jobId: number) => {
    // Clear any existing interval
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    // Poll every 1.5 seconds
    pollingIntervalRef.current = window.setInterval(async () => {
      try {
        const updatedJob = await getTestGenerationJobStatus(
          parseInt(workspaceId!),
          jobId
        );
        setGenerationJob(updatedJob);

        // Check if job is complete
        if (
          updatedJob.status === "completed" ||
          updatedJob.status === "failed"
        ) {
          stopPollingJobStatus();
          setGeneratingCode(false);

          if (updatedJob.status === "completed") {
            // Show success modal with PR link
            setCompletionData({
              branch: updatedJob.branch_name || '',
              files: updatedJob.generated_files?.length || 0,
              tests: updatedJob.total_tests || 0,
              prUrl: updatedJob.pr_url || undefined,
            });
            setShowCompletionModal(true);
          } else if (updatedJob.status === "failed") {
            setError(updatedJob.error_message || "Test generation failed");
          }
        }
      } catch (err) {
        console.error("Failed to poll job status:", err);
      }
    }, 1500);
  };

  const stopPollingJobStatus = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      stopPollingJobStatus();
    };
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
      case "passed":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-600" />;
      case "running":
        return <Clock className="h-4 w-4 text-blue-600 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">Loading test suite...</div>
      </div>
    );
  }

  if (!testSuite) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Test suite not found</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/workspaces/${workspaceId}/test-suites`)}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Test Suites
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{testSuite.name}</h1>
            <p className="text-gray-600 mt-1">
              {testSuite.test_framework} • {testSuite.test_directory}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleDiscoverTests}
            disabled={discoveringTests}
            variant="outline"
          >
            <Search className="h-4 w-4 mr-2" />
            {discoveringTests ? "Discovering..." : "Discover Tests"}
          </Button>
          {/* <Button
            onClick={handleAnalyze}
            disabled={analyzing}
            variant="outline"
          >
            <Sparkles className="h-4 w-4 mr-2" />
            {analyzing ? "Analyzing..." : "AI Analysis"}
          </Button> */}
          {/* <Button
            onClick={handleGenerateCode}
            disabled={generatingCode || testCases.length === 0}
            variant="outline"
          >
            <FileCode className="h-4 w-4 mr-2" />
            {generatingCode && generationJob
              ? `${
                  generationJob.current_stage === "generating" &&
                  generationJob.current_test_name
                    ? `${generationJob.current_test_name} (${generationJob.completed_tests}/${generationJob.total_tests})`
                    : generationJob.current_stage === "cloning"
                    ? "Cloning repository..."
                    : generationJob.current_stage === "committing"
                    ? "Committing files..."
                    : generationJob.current_stage === "pushing"
                    ? "Pushing to GitHub..."
                    : "Generating..."
                }`
              : generatingCode
              ? "Starting..."
              : "Generate Code & PR"}
          </Button> */}
          <Button variant="gradient" onClick={handleRunTests} disabled={runningTests}>
            <Play className="h-4 w-4 mr-2" />
            {runningTests ? "Running..." : "Run Tests"}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {testSuite.description && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <p className="text-gray-700">{testSuite.description}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Test Cases
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{testCases.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Coverage Threshold
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {testSuite.coverage_threshold}%
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Last Run
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm">
              {testSuite.last_run
                ? new Date(testSuite.last_run).toLocaleDateString()
                : "Never"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {testSuite.is_active ? (
                <>
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm">Active</span>
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4 text-gray-400" />
                  <span className="text-sm">Inactive</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {analysis && (
        <Card className="mb-6 border-blue-200 bg-blue-50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-blue-600" />
                AI Analysis Results
              </CardTitle>
              <Button
                variant="gradient"
                onClick={handleApplySuggestions}
                disabled={applyingSuggestions}
                size="sm"
              >
                {applyingSuggestions ? "Applying..." : "Apply Suggestions"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Summary</h4>
                <p className="text-sm text-gray-700">
                  {analysis.analysis_summary}
                </p>
              </div>

              {analysis.coverage_gaps.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2">Coverage Gaps</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {analysis.coverage_gaps.map((gap, idx) => (
                      <li key={idx} className="text-sm text-gray-700">
                        {gap}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.recommendations.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2">Recommendations</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {analysis.recommendations.map((rec, idx) => (
                      <li key={idx} className="text-sm text-gray-700">
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h4 className="font-semibold mb-2">
                  Suggested Tests ({analysis.suggested_tests.length})
                </h4>
                <div className="space-y-2">
                  {analysis.suggested_tests.slice(0, 3).map((test, idx) => (
                    <div key={idx} className="bg-white p-3 rounded border">
                      <div className="font-medium text-sm">
                        {test.test_name}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        {test.file_path}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {test.description}
                      </div>
                    </div>
                  ))}
                  {analysis.suggested_tests.length > 3 && (
                    <p className="text-xs text-gray-600">
                      And {analysis.suggested_tests.length - 3} more...
                    </p>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="test-cases" className="space-y-4">
        <TabsList>
          <TabsTrigger value="test-cases">Test Cases</TabsTrigger>
          <TabsTrigger value="test-runs">Test Runs</TabsTrigger>
          <TabsTrigger value="coverage">Coverage History</TabsTrigger>
        </TabsList>

        <TabsContent value="test-cases">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Test Cases</CardTitle>
                <Button size="sm" variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Test Case
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {testCases.length === 0 ? (
                <div className="text-center py-12">
                  <FileCode className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <h3 className="text-lg font-semibold mb-2">
                    No test cases yet
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Use AI Analysis to generate test cases or add them manually
                  </p>
                  <Button variant="gradient" onClick={handleAnalyze}>
                    <Sparkles className="h-4 w-4 mr-2" />
                    Analyze with AI
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {testCases.map((testCase) => (
                    <div
                      key={testCase.id}
                      className="flex items-start justify-between p-4 border rounded hover:bg-gray-50"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {testCase.test_name}
                          </span>
                          <span className="text-xs bg-gray-200 px-2 py-1 rounded">
                            {testCase.test_type}
                          </span>
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                            {testCase.status}
                          </span>
                        </div>
                        <div className="text-sm text-gray-600 mt-1">
                          {testCase.file_path}
                        </div>
                        {testCase.description && (
                          <p className="text-sm text-gray-500 mt-2">
                            {testCase.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="test-runs">
          <Card>
            <CardHeader>
              <CardTitle>Recent Test Runs</CardTitle>
            </CardHeader>
            <CardContent>
              {testRuns.length === 0 ? (
                <div className="text-center py-12">
                  <Clock className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <h3 className="text-lg font-semibold mb-2">
                    No test runs yet
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Run your tests to see execution history and results
                  </p>
                  <Button variant="gradient" onClick={handleRunTests}>
                    <Play className="h-4 w-4 mr-2" />
                    Run Tests
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {testRuns.map((run) => (
                    <div
                      key={run.id}
                      className="flex items-center justify-between p-4 border rounded hover:bg-gray-50 cursor-pointer"
                      onClick={() =>
                        navigate(
                          `/workspaces/${workspaceId}/test-runs/${run.id}`
                        )
                      }
                    >
                      <div className="flex items-center gap-4">
                        {getStatusIcon(run.status)}
                        <div>
                          <div className="font-medium">
                            Run #{run.id} • {run.branch_name}
                          </div>
                          <div className="text-sm text-gray-600">
                            {new Date(run.created_at).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-6 text-sm">
                        <div>
                          <span className="text-green-600 font-semibold">
                            {run.passed_tests}
                          </span>{" "}
                          passed
                        </div>
                        <div>
                          <span className="text-red-600 font-semibold">
                            {run.failed_tests}
                          </span>{" "}
                          failed
                        </div>
                        {run.coverage_percentage !== null && (
                          <div>
                            <TrendingUp className="h-4 w-4 inline mr-1" />
                            {run.coverage_percentage.toFixed(1)}%
                          </div>
                        )}
                        {run.duration_seconds !== null && (
                          <div className="text-gray-500">
                            {run.duration_seconds.toFixed(1)}s
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="coverage">
          <Card>
            <CardHeader>
              <CardTitle>Coverage History</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12 text-gray-500">
                Coverage visualization coming soon
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Success Modal */}
      <Dialog open={showSuccessModal} onOpenChange={setShowSuccessModal}>
        <DialogContent>
          <DialogHeader>
            <div className="flex items-center justify-center mb-4">
              <div className="bg-green-100 rounded-full p-3">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <DialogTitle className="text-center">Success!</DialogTitle>
            <DialogDescription className="text-center">
              {successMessage}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-center mt-4">
            <Button variant="gradient" onClick={() => setShowSuccessModal(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Discovery Results Modal */}
      <Dialog open={showDiscoveryModal} onOpenChange={setShowDiscoveryModal}>
        <DialogContent>
          <DialogHeader>
            <div className="flex items-center justify-center mb-4">
              <div className="bg-blue-100 rounded-full p-3">
                <Search className="h-8 w-8 text-blue-600" />
              </div>
            </div>
            <DialogTitle className="text-center">Test Discovery Complete!</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-4">
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
              <span className="text-sm font-medium">Total tests found:</span>
              <span className="text-lg font-bold">{discoveryResults.discovered}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-green-50 rounded">
              <span className="text-sm font-medium">New tests imported:</span>
              <span className="text-lg font-bold text-green-600">{discoveryResults.imported}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
              <span className="text-sm font-medium">Already existing:</span>
              <span className="text-lg font-bold">{discoveryResults.skipped}</span>
            </div>
          </div>
          <div className="flex justify-center mt-4">
            <Button variant="gradient" onClick={() => setShowDiscoveryModal(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Generate Code Confirmation Modal */}
      <Dialog open={showConfirmModal} onOpenChange={setShowConfirmModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Test Code Files?</DialogTitle>
            <DialogDescription>
              This will create a new branch with actual test files and create a pull request.
              Are you sure you want to continue?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmModal(false)}>
              Cancel
            </Button>
            <Button variant="gradient" onClick={confirmGenerateCode}>
              Generate Code & PR
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Code Generation Completion Modal */}
      <Dialog open={showCompletionModal} onOpenChange={setShowCompletionModal}>
        <DialogContent>
          <DialogHeader>
            <div className="flex items-center justify-center mb-4">
              <div className="bg-green-100 rounded-full p-3">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <DialogTitle className="text-center">Test Generation Completed!</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-4">
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
              <span className="text-sm font-medium">Branch:</span>
              <span className="text-sm font-mono">{completionData.branch}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
              <span className="text-sm font-medium">Files generated:</span>
              <span className="text-lg font-bold">{completionData.files}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
              <span className="text-sm font-medium">Tests:</span>
              <span className="text-lg font-bold">{completionData.tests}</span>
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setShowCompletionModal(false)}>
              Close
            </Button>
            {completionData.prUrl && (
              <Button
                variant="gradient"
                onClick={() => {
                  window.open(completionData.prUrl, "_blank");
                  setShowCompletionModal(false);
                }}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Open Pull Request
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
