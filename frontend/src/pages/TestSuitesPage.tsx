import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { listTestSuites, createTestSuite, deleteTestSuite, runTestSuite } from "../api/test_suites";
import type { TestSuite, TestSuiteCreate, TestRunCreate } from "../types/test_suite";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
  Plus,
  Play,
  FileCode,
  Trash2,
  CheckCircle,
} from "lucide-react";

export default function TestSuitesPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const [testSuites, setTestSuites] = useState<TestSuite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [suiteToDelete, setSuiteToDelete] = useState<number | null>(null);

  useEffect(() => {
    if (workspaceId) {
      loadTestSuites();
    }
  }, [workspaceId]);

  const loadTestSuites = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await listTestSuites(parseInt(workspaceId!));
      setTestSuites(data.test_suites);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load test suites");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTestSuite = async (data: TestSuiteCreate) => {
    try {
      setCreating(true);
      await createTestSuite(parseInt(workspaceId!), data);
      setShowCreateModal(false);
      loadTestSuites();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create test suite");
    } finally {
      setCreating(false);
    }
  };

  const handleRunTests = async (suiteId: number, branchName: string) => {
    try {
      const runData: TestRunCreate = {
        branch_name: branchName,
        trigger_type: "manual",
      };
      await runTestSuite(parseInt(workspaceId!), suiteId, runData);
      setSuccessMessage("Test run started! Check the test run history for results.");
      setShowSuccessModal(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start test run");
    }
  };

  const handleDelete = (suiteId: number) => {
    setSuiteToDelete(suiteId);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!suiteToDelete) return;

    try {
      await deleteTestSuite(parseInt(workspaceId!), suiteToDelete);
      setShowDeleteConfirm(false);
      setSuiteToDelete(null);
      loadTestSuites();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete test suite");
    }
  };

  // TODO: Use this function if needed
  // const getCoverageColor = (coverage: number | null) => {
  //   if (!coverage) return "text-gray-400";
  //   if (coverage >= 80) return "text-green-600";
  //   if (coverage >= 50) return "text-yellow-600";
  //   return "text-red-600";
  // };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">Loading test suites...</div>
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
            onClick={() => navigate(`/workspaces/${workspaceId}`)}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workspace
          </Button>
          <h1 className="text-3xl font-bold">Test Suites</h1>
        </div>
        <Button variant="gradient" onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Test Suite
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {testSuites.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileCode className="h-12 w-12 mx-auto mb-4 text-gray-400" />
            <h3 className="text-lg font-semibold mb-2">No test suites yet</h3>
            <p className="text-gray-600 mb-4">
              Create your first test suite to start testing your code
            </p>
            <Button variant="gradient" onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Test Suite
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {testSuites.map((suite) => (
            <Card
              key={suite.id}
              className="hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => navigate(`/workspaces/${workspaceId}/test-suites/${suite.id}`)}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{suite.name}</CardTitle>
                    <p className="text-sm text-gray-600 mt-1">
                      {suite.test_framework} • {suite.test_directory}
                    </p>
                  </div>
                  {!suite.is_active && (
                    <span className="text-xs bg-gray-200 px-2 py-1 rounded">
                      Inactive
                    </span>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {suite.description && (
                  <p className="text-sm text-gray-600 mb-4">{suite.description}</p>
                )}

                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Test Cases:</span>
                    <span className="font-semibold">{suite.test_case_count}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Coverage Threshold:</span>
                    <span className="font-semibold">{suite.coverage_threshold}%</span>
                  </div>

                  {suite.last_run && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">Last Run:</span>
                      <span className="text-xs">
                        {new Date(suite.last_run).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 mt-4" onClick={(e) => e.stopPropagation()}>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => handleRunTests(suite.id, "main")}
                  >
                    <Play className="h-3 w-3 mr-1" />
                    Run Tests
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(suite.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Test Suite Modal - Simplified for now */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Create Test Suite</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.currentTarget);
                  handleCreateTestSuite({
                    name: formData.get("name") as string,
                    description: formData.get("description") as string,
                    test_framework: formData.get("framework") as string,
                    test_directory: formData.get("directory") as string,
                    coverage_threshold: parseFloat(formData.get("threshold") as string),
                  });
                }}
              >
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Name</label>
                    <input
                      name="name"
                      className="w-full border rounded px-3 py-2"
                      required
                      placeholder="Unit Tests"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Description</label>
                    <textarea
                      name="description"
                      className="w-full border rounded px-3 py-2"
                      rows={2}
                      placeholder="Optional description"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Framework</label>
                    <select name="framework" className="w-full border rounded px-3 py-2" required>
                      <option value="pytest">pytest (Python)</option>
                      <option value="jest">Jest (JavaScript)</option>
                      <option value="mocha">Mocha (JavaScript)</option>
                      <option value="junit">JUnit (Java)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Test Directory</label>
                    <input
                      name="directory"
                      className="w-full border rounded px-3 py-2"
                      required
                      placeholder="tests"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Coverage Threshold (%)
                    </label>
                    <input
                      name="threshold"
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      defaultValue="80"
                      className="w-full border rounded px-3 py-2"
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button type="submit" variant="gradient" disabled={creating} className="flex-1">
                      {creating ? "Creating..." : "Create"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowCreateModal(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

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

      {/* Delete Confirmation Modal */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Test Suite?</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this test suite? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowDeleteConfirm(false);
                setSuiteToDelete(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
