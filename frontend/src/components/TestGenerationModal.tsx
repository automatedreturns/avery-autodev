/**
 * Test Generation Modal
 *
 * Allows users to manually trigger AI-powered test generation
 * for files with low or no test coverage.
 */

import { useState, useEffect } from "react";
import { X, Wand2, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { createTestGenerationJob } from "../api/test_generation";
import { getWorkspaceUncoveredFiles } from "../api/coverage";

interface TestGenerationModalProps {
  workspaceId: number;
  onClose: () => void;
  onSuccess?: (jobId: number) => void;
}

interface UncoveredFile {
  path: string;
  coverage: number;
  uncoveredLines: number;
}

export default function TestGenerationModal({
  workspaceId,
  onClose,
  onSuccess,
}: TestGenerationModalProps) {
  const [uncoveredFiles, setUncoveredFiles] = useState<UncoveredFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [generationType, setGenerationType] = useState<"unit" | "integration" | "regression">("unit");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadUncoveredFiles();
  }, [workspaceId]);

  const loadUncoveredFiles = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await getWorkspaceUncoveredFiles(workspaceId, 20);

      // Transform API response to component format
      const files: UncoveredFile[] = response.priority_files.map((file) => ({
        path: file.path,
        coverage: file.coverage,
        uncoveredLines: file.uncovered_count,
      }));

      setUncoveredFiles(files);
    } catch (err) {
      // Check if error is due to no coverage data
      const errorMessage = err instanceof Error ? err.message : "Failed to load files";
      if (errorMessage.includes("No coverage data")) {
        setError("No coverage data found. Please run tests with coverage enabled first.");
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileToggle = (filePath: string) => {
    setSelectedFiles((prev) =>
      prev.includes(filePath)
        ? prev.filter((f) => f !== filePath)
        : [...prev, filePath]
    );
  };

  const handleSelectAll = () => {
    if (selectedFiles.length === uncoveredFiles.length) {
      setSelectedFiles([]);
    } else {
      setSelectedFiles(uncoveredFiles.map((f) => f.path));
    }
  };

  const handleGenerate = async () => {
    if (selectedFiles.length === 0) {
      setError("Please select at least one file");
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      const job = await createTestGenerationJob({
        workspace_id: workspaceId,
        files: selectedFiles,
        trigger_type: "manual",
        generation_type: generationType,
        context: `Manual test generation for ${selectedFiles.length} files`,
      });

      setSuccess(true);
      setTimeout(() => {
        if (onSuccess) {
          onSuccess(job.id);
        }
        onClose();
      }, 1500);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start test generation"
      );
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Wand2 className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Generate Tests</h2>
              <p className="text-sm text-muted-foreground">
                AI-powered test generation for uncovered code
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Success Message */}
          {success && (
            <Alert variant="success">
              <CheckCircle className="h-4 w-4" />
              <AlertTitle>Test generation started!</AlertTitle>
              <AlertDescription>
                You'll be redirected to track progress...
              </AlertDescription>
            </Alert>
          )}

          {/* Error Message */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Generation Type */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Test Type
            </label>
            <div className="flex gap-2">
              {(["unit", "integration", "regression"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setGenerationType(type)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    generationType === type
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* File Selection */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="block text-sm font-medium">
                Select Files ({selectedFiles.length}/{uncoveredFiles.length} selected)
              </label>
              <button
                onClick={handleSelectAll}
                className="text-sm text-primary hover:underline"
              >
                {selectedFiles.length === uncoveredFiles.length
                  ? "Deselect All"
                  : "Select All"}
              </button>
            </div>

            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                Loading files...
              </div>
            ) : uncoveredFiles.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No uncovered files found.</p>
                <p className="text-sm mt-1">All files have sufficient coverage!</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {uncoveredFiles.map((file) => (
                  <label
                    key={file.path}
                    className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedFiles.includes(file.path)}
                      onChange={() => handleFileToggle(file.path)}
                      className="w-4 h-4"
                    />
                    <div className="flex-1">
                      <p className="font-mono text-sm text-foreground">{file.path}</p>
                      <div className="flex items-center gap-4 mt-1">
                        <span
                          className={`text-xs font-medium ${
                            file.coverage < 50
                              ? "text-destructive"
                              : file.coverage < 70
                              ? "text-yellow-600 dark:text-yellow-500"
                              : "text-success"
                          }`}
                        >
                          {file.coverage.toFixed(1)}% coverage
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {file.uncoveredLines} uncovered lines
                        </span>
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t bg-muted/30">
          <Button variant="outline" onClick={onClose} disabled={generating}>
            Cancel
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={generating || selectedFiles.length === 0 || loading}
          >
            {generating ? (
              <>
                <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin mr-2" />
                Generating...
              </>
            ) : (
              <>
                <Wand2 className="w-4 h-4 mr-2" />
                Generate Tests
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
