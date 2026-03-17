import { useState, useEffect } from 'react';
import { listPullRequests, linkPullRequestToWorkspace, type PullRequest } from '../api/workspace_tasks';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertCircle,
  GitPullRequest,
  ExternalLink,
  CheckCircle,
  XCircle,
  AlertTriangle,
  GitBranch,
  Calendar,
  X,
} from 'lucide-react';

interface Props {
  workspaceId: number;
  onClose: () => void;
  onPRLinked: () => void;
}

export default function LinkPRModal({ workspaceId, onClose, onPRLinked }: Props) {
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPR, setSelectedPR] = useState<PullRequest | null>(null);
  const [linking, setLinking] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadPullRequests();
  }, [workspaceId]);

  const loadPullRequests = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await listPullRequests(workspaceId, 'open');

      if (response.error) {
        setError(response.error);
      } else {
        setPullRequests(response.pull_requests);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pull requests');
    } finally {
      setLoading(false);
    }
  };

  const handleLinkPR = async () => {
    if (!selectedPR) return;

    try {
      setLinking(true);
      setError('');
      await linkPullRequestToWorkspace(workspaceId, selectedPR.number);
      setSuccess(true);

      // Wait a moment to show success message, then close and refresh
      setTimeout(() => {
        onPRLinked();
        onClose();
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to link pull request');
    } finally {
      setLinking(false);
    }
  };

  const getMergeableStateIcon = (state: string) => {
    switch (state) {
      case 'clean':
        return <CheckCircle className="w-4 h-4 text-success" />;
      case 'dirty':
      case 'blocked':
        return <XCircle className="w-4 h-4 text-destructive" />;
      case 'unstable':
        return <AlertTriangle className="w-4 h-4 text-warning" />;
      default:
        return <AlertCircle className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const getMergeableStateText = (state: string) => {
    switch (state) {
      case 'clean':
        return 'Ready to merge';
      case 'dirty':
        return 'Has conflicts';
      case 'blocked':
        return 'Blocked';
      case 'unstable':
        return 'Checks failing';
      case 'unknown':
        return 'Status unknown';
      default:
        return state;
    }
  };

  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg shadow-lg border max-w-3xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
              <GitPullRequest className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-foreground">Link Pull Request</h2>
              <p className="text-sm text-muted-foreground">
                Select an open PR to work on with the agent
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            disabled={linking}
            className="h-8 w-8"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {success && (
            <Alert className="mb-4 border-success bg-success/10">
              <CheckCircle className="h-4 w-4 text-success" />
              <AlertDescription className="text-success">
                Pull request linked successfully! A new task has been created.
              </AlertDescription>
            </Alert>
          )}

          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-4 border-muted border-t-primary"></div>
              <p className="mt-4 text-sm text-muted-foreground">Loading pull requests...</p>
            </div>
          ) : pullRequests.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                <GitPullRequest className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">No open pull requests</h3>
              <p className="text-muted-foreground">
                There are no open pull requests in this repository.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {pullRequests.map((pr) => (
                <div
                  key={pr.number}
                  onClick={() => setSelectedPR(pr)}
                  className={`border rounded-lg p-4 cursor-pointer transition-all ${
                    selectedPR?.number === pr.number
                      ? 'border-primary bg-primary/5 shadow-md'
                      : 'border-border hover:border-primary/50 hover:bg-accent/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <a
                          href={pr.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1.5 text-primary hover:text-primary/90 font-bold text-base group"
                        >
                          <span className="font-mono">#{pr.number}</span>
                          <ExternalLink className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                        </a>
                        {pr.draft && (
                          <span className="px-2 py-0.5 bg-muted text-muted-foreground text-xs font-medium rounded border border-border">
                            Draft
                          </span>
                        )}
                        <div className="inline-flex items-center gap-1.5 text-xs">
                          {getMergeableStateIcon(pr.mergeable_state)}
                          <span className="text-muted-foreground">
                            {getMergeableStateText(pr.mergeable_state)}
                          </span>
                        </div>
                      </div>

                      <h3 className="text-base font-semibold text-foreground mb-2 line-clamp-2">
                        {pr.title}
                      </h3>

                      <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                        <div className="flex items-center gap-1 px-2 py-0.5 bg-muted rounded border border-border">
                          <GitBranch className="w-3 h-3" />
                          <span className="font-mono">{pr.head_branch}</span>
                          <span className="mx-1">→</span>
                          <span className="font-mono">{pr.base_branch}</span>
                        </div>
                        <span>•</span>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          <span>Updated {new Date(pr.updated_at).toLocaleDateString()}</span>
                        </div>
                      </div>

                      {pr.labels.length > 0 && (
                        <div className="flex items-center gap-1 mt-2 flex-wrap">
                          {pr.labels.slice(0, 3).map((label) => (
                            <span
                              key={label}
                              className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs rounded"
                            >
                              {label}
                            </span>
                          ))}
                          {pr.labels.length > 3 && (
                            <span className="text-xs text-muted-foreground">
                              +{pr.labels.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {selectedPR?.number === pr.number && (
                      <CheckCircle className="w-5 h-5 text-primary flex-shrink-0" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 p-6 border-t bg-muted/30">
          <div className="text-sm text-muted-foreground">
            {selectedPR ? (
              <>
                Selected: <span className="font-medium text-foreground">PR #{selectedPR.number}</span>
              </>
            ) : (
              'Select a pull request to continue'
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} disabled={linking}>
              Cancel
            </Button>
            <Button
              variant="gradient"
              onClick={handleLinkPR}
              disabled={!selectedPR || linking || success}
            >
              {linking ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-background/30 border-t-background mr-2"></div>
                  Linking...
                </>
              ) : (
                <>
                  <GitPullRequest className="w-4 h-4 mr-2" />
                  Link Pull Request
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
