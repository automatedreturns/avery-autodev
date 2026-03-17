import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { pollWorkspaceIssues } from '../api/issue_polling';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, ArrowLeft, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';

// TODO: Implement getPollingHistory API endpoint
interface PollingHistoryEntry {
  id: number;
  polled_at: string;
  triggered_by: string;
  success: string;
  issues_found: number;
  issues_linked: number;
  issues_skipped: number;
  linked_issue_numbers?: number[];
  error_message?: string;
}

const PollingHistoryPage = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();

  const [history, setHistory] = useState<PollingHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const loadHistory = async () => {
    if (!workspaceId) return;

    try {
      setLoading(true);
      // TODO: Implement getPollingHistory API endpoint
      // const response = await getPollingHistory(parseInt(workspaceId));
      // setHistory(response.history);
      setHistory([]); // Temporary: return empty history
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load polling history');
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
      // Reload history after polling
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger polling');
    } finally {
      setPolling(false);
    }
  };

  useEffect(() => {
    if (workspaceId) {
      loadHistory();
    }
  }, [workspaceId]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getTriggeredByLabel = (triggeredBy: string) => {
    if (triggeredBy === 'automatic') return 'Automatic';
    if (triggeredBy.startsWith('user_id:')) {
      const userId = triggeredBy.split(':')[1];
      return `Manual (User #${userId})`;
    }
    return triggeredBy;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading polling history...</p>
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
              <h1 className="text-4xl font-bold text-foreground">Polling History</h1>
              <p className="text-muted-foreground mt-2">
                Track automatic issue detection and linking
              </p>
            </div>
            <Button
              onClick={handleManualPoll}
              disabled={polling}
            >
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

        {/* Error Message */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* History List */}
        {history.length === 0 ? (
          <Card className="text-center py-20">
            <CardContent className="pt-6">
              <Clock className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-foreground mb-2">No Polling History Yet</h3>
              <p className="text-muted-foreground mb-6">
                Polling happens automatically every 5 minutes, or you can trigger it manually.
              </p>
              <Button
                onClick={handleManualPoll}
                disabled={polling}
              >
                Poll Now
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {history.map((entry) => (
              <Card
                key={entry.id}
                className={`border-l-4 ${
                  entry.success === 'success'
                    ? 'border-l-green-500'
                    : 'border-l-destructive'
                }`}
              >
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      {/* Header */}
                      <div className="flex items-center gap-3 mb-3">
                        {entry.success === 'success' ? (
                          <div className="flex-shrink-0 w-8 h-8 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                            <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                          </div>
                        ) : (
                          <div className="flex-shrink-0 w-8 h-8 bg-destructive/10 rounded-full flex items-center justify-center">
                            <XCircle className="w-5 h-5 text-destructive" />
                          </div>
                        )}
                        <div>
                          <h3 className="text-lg font-semibold text-foreground">
                            {entry.success === 'success' ? 'Poll Successful' : 'Poll Failed'}
                          </h3>
                          <p className="text-sm text-muted-foreground">
                            {formatDate(entry.polled_at)} • {getTriggeredByLabel(entry.triggered_by)}
                          </p>
                        </div>
                      </div>

                      {/* Stats */}
                      {entry.success === 'success' && (
                        <div className="grid grid-cols-3 gap-4 mb-4">
                          <div className="bg-blue-50 dark:bg-blue-950/20 rounded-lg p-3 border border-blue-200 dark:border-blue-800">
                            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                              {entry.issues_found}
                            </div>
                            <div className="text-sm text-blue-900 dark:text-blue-300">Found</div>
                          </div>
                          <div className="bg-green-50 dark:bg-green-950/20 rounded-lg p-3 border border-green-200 dark:border-green-800">
                            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                              {entry.issues_linked}
                            </div>
                            <div className="text-sm text-green-900 dark:text-green-300">Linked</div>
                          </div>
                          <div className="bg-muted rounded-lg p-3 border border-border">
                            <div className="text-2xl font-bold text-muted-foreground">
                              {entry.issues_skipped}
                            </div>
                            <div className="text-sm text-foreground">Skipped</div>
                          </div>
                        </div>
                      )}

                      {/* Linked Issues */}
                      {entry.linked_issue_numbers && entry.linked_issue_numbers.length > 0 && (
                        <div className="bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                          <h4 className="font-semibold text-green-900 dark:text-green-200 mb-2">
                            New Issues Linked:
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {entry.linked_issue_numbers.map((issueNum: number) => (
                              <Link
                                key={issueNum}
                                to={`/workspaces/${workspaceId}`}
                                className="inline-flex items-center px-3 py-1 bg-background border border-green-300 dark:border-green-700 rounded-full text-sm font-medium text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors"
                              >
                                #{issueNum}
                              </Link>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Error Message */}
                      {entry.error_message && (
                        <Alert variant="destructive">
                          <AlertCircle className="h-4 w-4" />
                          <AlertDescription>
                            <div className="font-semibold mb-1">Error:</div>
                            <p className="text-sm font-mono">
                              {entry.error_message}
                            </p>
                          </AlertDescription>
                        </Alert>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PollingHistoryPage;
