import { useState, useEffect } from "react";
import {
  createFeatureRequest,
  searchSimilarIssues,
} from "../api/workspace_tasks";
import type { GitHubIssuePreview } from "../types/workspace_task";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  Lightbulb,
  ExternalLink,
  Search,
} from "lucide-react";

interface Props {
  workspaceId: number;
  onClose: () => void;
  onFeatureRequestCreated: () => void;
}

export default function FeatureRequestModal({
  workspaceId,
  onClose,
  onFeatureRequestCreated,
}: Props) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [linkAsTask, setLinkAsTask] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [issueUrl, setIssueUrl] = useState("");

  // Similar issues search
  const [similarIssues, setSimilarIssues] = useState<GitHubIssuePreview[]>([]);
  const [searchingSimilar, setSearchingSimilar] = useState(false);
  const [showSimilar, setShowSimilar] = useState(false);

  // Debounced search for similar issues
  useEffect(() => {
    if (title.length < 3) {
      setSimilarIssues([]);
      setShowSimilar(false);
      return;
    }

    const timer = setTimeout(() => {
      searchForSimilar();
    }, 500);

    return () => clearTimeout(timer);
  }, [title]);

  const searchForSimilar = async () => {
    if (title.length < 3) return;

    try {
      setSearchingSimilar(true);
      const response = await searchSimilarIssues(workspaceId, {
        query: title,
        state: "open",
        max_results: 5,
      });

      if (!response.error && response.issues.length > 0) {
        setSimilarIssues(response.issues);
        setShowSimilar(true);
      } else {
        setSimilarIssues([]);
        setShowSimilar(false);
      }
    } catch (err) {
      // Silent fail for similar search
      setSimilarIssues([]);
    } finally {
      setSearchingSimilar(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      setError("Please enter a title for the feature request");
      return;
    }

    if (!description.trim()) {
      setError("Please enter a description for the feature request");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await createFeatureRequest(workspaceId, {
        title: title.trim(),
        description: description.trim(),
        acceptance_criteria: acceptanceCriteria.trim() || undefined,
        labels: ["enhancement"],
        link_as_task: linkAsTask,
      });

      if (response.success && response.issue_url) {
        setSuccess(true);
        setIssueUrl(response.issue_url);
        onFeatureRequestCreated();

        // Auto-close after 3 seconds
        setTimeout(() => {
          onClose();
        }, 3000);
      } else {
        setError(response.error || "Failed to create feature request");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create feature request"
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <Dialog open onOpenChange={onClose}>
        <DialogContent className="sm:max-w-lg">
          <div className="text-center py-6">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-green-900 mb-2">
              Feature Request Created!
            </h2>
            <p className="text-gray-600 mb-4">
              Your feature request has been created successfully.
            </p>
            {issueUrl && (
              <a
                href={issueUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-blue-600 hover:text-blue-700"
              >
                View on GitHub
                <ExternalLink className="w-4 h-4 ml-1" />
              </a>
            )}
            {linkAsTask && (
              <p className="text-sm text-gray-500 mt-2">
                The issue has been linked as a task and agent is analyzing it...
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center text-xl">
            <Lightbulb className="w-6 h-6 mr-2 text-yellow-500" />
            Submit Feature Request
          </DialogTitle>
          <DialogDescription>
            Create a new feature request that will be added as a GitHub issue
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          {/* Title Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Feature Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Add dark mode support"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
              disabled={loading}
            />
            {searchingSimilar && (
              <div className="flex items-center text-sm text-gray-500 mt-1">
                <Search className="w-3 h-3 mr-1 animate-pulse" />
                Searching for similar issues...
              </div>
            )}
          </div>

          {/* Similar Issues Alert */}
          {showSimilar && similarIssues.length > 0 && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <div className="font-semibold mb-2">Similar issues found:</div>
                <div className="space-y-2">
                  {similarIssues.map((issue) => (
                    <Card key={issue.number} className="p-3 bg-gray-50">
                      <a
                        href={issue.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-blue-600 hover:text-blue-700 flex items-center"
                      >
                        #{issue.number}: {issue.title}
                        <ExternalLink className="w-3 h-3 ml-1" />
                      </a>
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className={`text-xs px-2 py-0.5 rounded ${
                            issue.state === "open"
                              ? "bg-green-100 text-green-700"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {issue.state}
                        </span>
                      </div>
                    </Card>
                  ))}
                </div>
                <p className="text-xs text-gray-600 mt-2">
                  Check if one of these matches your request before creating a
                  new one.
                </p>
              </AlertDescription>
            </Alert>
          )}

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description *
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the feature you'd like to see..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[120px]"
              required
              disabled={loading}
            />
            <p className="text-xs text-gray-500 mt-1">
              Provide a detailed description of the feature and why it would be
              useful
            </p>
          </div>

          {/* Acceptance Criteria */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Acceptance Criteria (Optional)
            </label>
            <textarea
              value={acceptanceCriteria}
              onChange={(e) => setAcceptanceCriteria(e.target.value)}
              placeholder="- The feature should...&#10;- Users can...&#10;- The system must..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[100px]"
              disabled={loading}
            />
            <p className="text-xs text-gray-500 mt-1">
              Define what "done" looks like for this feature
            </p>
          </div>

          {/* Link as Task Checkbox */}
          {false && (
            <div className="flex items-start">
              <input
                type="checkbox"
                id="linkAsTask"
                checked={linkAsTask}
                onChange={(e) => setLinkAsTask(e.target.checked)}
                className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                disabled={loading}
              />
              <label htmlFor="linkAsTask" className="ml-2 block">
                <span className="text-sm font-medium text-gray-700">
                  Link as workspace task
                </span>
                <p className="text-xs text-gray-500">
                  Automatically create a task and trigger agent analysis
                </p>
              </label>
            </div>
          )}

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" variant="gradient" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Feature Request"
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
