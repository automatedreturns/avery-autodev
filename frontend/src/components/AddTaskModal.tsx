import { useEffect, useState } from 'react';
import { addWorkspaceTask, listAvailableIssues } from '../api/workspace_tasks';
import type { GitHubIssuePreview } from '../types/workspace_task';
import AlertModal from './AlertModal';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Search,
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  GitPullRequest,
} from 'lucide-react';

interface Props {
  workspaceId: number;
  onClose: () => void;
  onTaskAdded: () => void;
}

export default function AddTaskModal({ workspaceId, onClose, onTaskAdded }: Props) {
  const [issues, setIssues] = useState<GitHubIssuePreview[]>([]);
  const [alreadyLinked, setAlreadyLinked] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [stateFilter, setStateFilter] = useState<'open' | 'closed' | 'all'>('open');
  const [searchQuery, setSearchQuery] = useState('');
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: 'info' | 'error' | 'warning' | 'success';
  }>({
    isOpen: false,
    title: '',
    message: '',
    type: 'info',
  });

  useEffect(() => {
    loadIssues();
  }, [workspaceId, stateFilter]);

  const loadIssues = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await listAvailableIssues(workspaceId, stateFilter);
      setIssues(response.issues);
      setAlreadyLinked(response.already_linked);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load issues');
    } finally {
      setLoading(false);
    }
  };

  const handleAddTask = async (issueNumber: number) => {
    try {
      setAdding(true);
      await addWorkspaceTask(workspaceId, { github_issue_number: issueNumber });
      onTaskAdded();
      onClose();
    } catch (err) {
      setAlertModal({
        isOpen: true,
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to add task',
        type: 'error',
      });
    } finally {
      setAdding(false);
    }
  };

  // Filter issues based on search query
  const filteredIssues = issues.filter((issue) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      issue.number.toString().includes(query) ||
      issue.title.toLowerCase().includes(query)
    );
  });

  return (
    <>
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col p-0">
          <DialogHeader className="p-6 border-b border-border">
            <DialogTitle className="text-xl font-semibold flex items-center gap-2">
              <GitPullRequest className="w-5 h-5 text-primary" />
              Link Issue
            </DialogTitle>
          </DialogHeader>

          {/* Filter */}
          <div className="p-6 border-b border-border space-y-4">
            {/* Search Input */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-muted-foreground" />
              </div>
              <input
                type="text"
                placeholder="Search by issue number or title..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="block w-full pl-10 pr-10 py-2 bg-background border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary text-sm text-foreground placeholder-muted-foreground"
              />
              {searchQuery && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSearchQuery('')}
                  className="absolute inset-y-0 right-0 h-full w-10"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>

            {/* State Filter Buttons */}
            <div className="flex gap-2">
              <Button
                variant={stateFilter === 'open' ? 'default' : 'outline'}
                onClick={() => setStateFilter('open')}
                className="flex-1"
              >
                Open
              </Button>
              <Button
                variant={stateFilter === 'closed' ? 'default' : 'outline'}
                onClick={() => setStateFilter('closed')}
                className="flex-1"
              >
                Closed
              </Button>
              <Button
                variant={stateFilter === 'all' ? 'default' : 'outline'}
                onClick={() => setStateFilter('all')}
                className="flex-1"
              >
                All
              </Button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="mt-2 text-sm text-muted-foreground">Loading issues...</p>
              </div>
            ) : error ? (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : issues.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No {stateFilter !== 'all' ? stateFilter : ''} issues found
              </div>
            ) : filteredIssues.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No issues match your search "{searchQuery}"
              </div>
            ) : (
              <div className="space-y-2">
                {filteredIssues.map((issue) => {
                  const isLinked = alreadyLinked.includes(issue.number);
                  return (
                    <Card
                      key={issue.number}
                      className={`p-4 ${
                        isLinked
                          ? 'bg-muted/50 opacity-60'
                          : 'hover:border-primary cursor-pointer transition-colors'
                      }`}
                    >
                      <div className="flex justify-between items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-mono text-muted-foreground">
                              #{issue.number}
                            </span>
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                issue.state === 'open'
                                  ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                                  : 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300'
                              }`}
                            >
                              {issue.state}
                            </span>
                          </div>
                          <p className="text-sm text-foreground mt-2 font-medium">{issue.title}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Updated {new Date(issue.updated_at).toLocaleDateString()}
                          </p>
                        </div>
                        {isLinked ? (
                          <div className="flex items-center gap-2 text-xs text-muted-foreground ml-4">
                            <CheckCircle2 className="w-4 h-4" />
                            Already linked
                          </div>
                        ) : (
                          <Button
                            variant="gradient"
                            onClick={() => handleAddTask(issue.number)}
                            disabled={adding}
                            size="sm"
                            className="ml-4 flex-shrink-0"
                          >
                            {adding ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Linking...
                              </>
                            ) : (
                              'Link Issue'
                            )}
                          </Button>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Alert Modal */}
      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        type={alertModal.type}
        onConfirm={() => setAlertModal({ ...alertModal, isOpen: false })}
      />
    </>
  );
}
