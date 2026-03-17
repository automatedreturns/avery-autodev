import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listWorkspaceTasks,
  removeWorkspaceTask,
} from "../api/workspace_tasks";
import type { WorkspaceTask } from "../types/workspace_task";
import AlertModal from "./AlertModal";
import LinkPRModal from "./LinkPRModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertCircle,
  Plus,
  ExternalLink,
  User,
  Calendar,
  GitBranch,
  GitPullRequest,
  Code,
  Trash2,
  CheckCircle,
  XCircle,
  Circle,
  Lightbulb,
  AlertTriangle,
  GitMerge,
  FileText,
} from "lucide-react";

interface Props {
  workspaceId: number;
  repository: string;
  defaultBranch: string;
  onAddTask: () => void;
  onRequestFeature?: () => void;
  refreshTrigger?: number; // External trigger to refresh list
}

export default function WorkspaceTaskList({
  workspaceId,
  onAddTask,
  onRequestFeature,
  refreshTrigger,
}: Props) {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<WorkspaceTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [removingTaskId, setRemovingTaskId] = useState<number | null>(null);
  const [showLinkPRModal, setShowLinkPRModal] = useState(false);
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: "info" | "error" | "warning" | "success";
    showCancel?: boolean;
    onConfirm?: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    type: "info",
  });

  useEffect(() => {
    loadTasks();
  }, [workspaceId, refreshTrigger]);

  const loadTasks = async () => {
    try {
      setLoading(true);
      setError("");
      const response = await listWorkspaceTasks(workspaceId);
      setTasks(response.tasks);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveTask = (taskId: number) => {
    setAlertModal({
      isOpen: true,
      title: "Remove Task",
      message: "Remove this task from the workspace?",
      type: "warning",
      showCancel: true,
      onConfirm: async () => {
        setAlertModal({ ...alertModal, isOpen: false });
        try {
          setRemovingTaskId(taskId);
          await removeWorkspaceTask(workspaceId, taskId);
          setTasks(tasks.filter((t) => t.id !== taskId));
        } catch (err) {
          setAlertModal({
            isOpen: true,
            title: "Error",
            message:
              err instanceof Error ? err.message : "Failed to remove task",
            type: "error",
          });
        } finally {
          setRemovingTaskId(null);
        }
      },
    });
  };

  const handleExecuteAgent = (task: WorkspaceTask) => {
    navigate(`/workspaces/${workspaceId}/tasks/${task.id}/agent`);
  };

  const isPRTask = (task: WorkspaceTask): boolean => {
    return task.agent_pr_number !== null;
  };

  const getTaskTypeBadge = (task: WorkspaceTask) => {
    if (isPRTask(task)) {
      // Check if it's a conflict resolution task based on title
      const isConflictTask = task.github_issue_title?.toLowerCase().includes("resolve merge conflicts");

      if (isConflictTask) {
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-destructive/10 text-destructive border border-destructive/20">
            <AlertTriangle className="w-3 h-3" />
            PR Conflict
          </span>
        );
      }

      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-accent/10 text-accent border border-accent/20">
          <GitMerge className="w-3 h-3" />
          Pull Request
        </span>
      );
    }

    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
        <FileText className="w-3 h-3" />
        Issue
      </span>
    );
  };

  const getAgentStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return (
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
            <div className="w-2 h-2 bg-primary rounded-full animate-pulse"></div>
            Active
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
            <div className="animate-spin rounded-full h-3 w-3 border-2 border-primary/30 border-t-primary"></div>
            Running
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-success text-success-foreground shadow-sm">
            <CheckCircle className="w-3 h-3" />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-destructive/10 text-destructive border border-destructive/20">
            <XCircle className="w-3 h-3" />
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-muted text-muted-foreground border border-border">
            <Circle className="w-2 h-2 fill-current" />
            Idle
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-muted border-t-primary"></div>
        <p className="mt-4 text-sm text-muted-foreground">Loading tasks...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h3 className="text-lg sm:text-xl font-bold text-foreground flex items-center gap-2 sm:gap-3">
          <Code className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
          Tasks
          <span className="text-sm sm:text-base font-normal text-muted-foreground">
            ({tasks.length})
          </span>
        </h3>
        <div className="flex gap-2 w-full sm:w-auto">
          {onRequestFeature && (
            <Button onClick={onRequestFeature} variant="outline" className="flex-1 sm:flex-none min-h-[44px] px-2 sm:px-4">
              <Lightbulb className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Feature</span>
            </Button>
          )}
          <Button onClick={() => setShowLinkPRModal(true)} variant="outline" className="flex-1 sm:flex-none min-h-[44px] px-2 sm:px-4">
            <GitPullRequest className="w-4 h-4 sm:mr-2" />
            <span className="hidden sm:inline">Link PR</span>
          </Button>
          <Button variant="gradient" onClick={onAddTask} className="flex-1 sm:flex-none min-h-[44px] px-2 sm:px-4">
            <Plus className="w-5 h-5 sm:mr-2" />
            <span className="hidden sm:inline">Link Issue</span>
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {tasks.length === 0 ? (
        <Card className="text-center py-8 sm:py-16 border-2 border-dashed">
          <CardContent className="pt-4 sm:pt-6 px-4">
            <div className="w-16 h-16 sm:w-20 sm:h-20 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Code className="w-8 h-8 sm:w-10 sm:h-10 text-primary" />
            </div>
            <h4 className="text-base sm:text-lg font-bold text-foreground mb-2">
              No tasks linked yet
            </h4>
            <p className="text-sm sm:text-base text-muted-foreground mb-6 max-w-md mx-auto">
              Get started by linking a GitHub issue, pull request, or requesting a new feature
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-3">
              {onRequestFeature && (
                <Button onClick={onRequestFeature} size="lg" variant="outline" className="w-full sm:w-auto min-h-[48px]">
                  <Lightbulb className="w-5 h-5 mr-2" />
                  Request Feature
                </Button>
              )}
              <Button onClick={() => setShowLinkPRModal(true)} size="lg" variant="outline" className="w-full sm:w-auto min-h-[48px]">
                <GitPullRequest className="w-5 h-5 mr-2" />
                Link Pull Request
              </Button>
              <Button variant="gradient" onClick={onAddTask} size="lg" className="w-full sm:w-auto min-h-[48px]">
                <Plus className="w-5 h-5 mr-2" />
                Link Issue
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {tasks.map((task) => {
            const isConflictTask = isPRTask(task) && task.github_issue_title?.toLowerCase().includes("resolve merge conflicts");
            const cardBorderClass = isConflictTask
              ? "border-l-4 border-l-destructive"
              : isPRTask(task)
              ? "border-l-4 border-l-accent"
              : "border-l-4 border-l-primary";

            return (
            <Card
              key={task.id}
              onClick={() => handleExecuteAgent(task)}
              className={`group cursor-pointer hover:shadow-md transition-all duration-200 hover:border-primary overflow-hidden ${cardBorderClass}`}
            >
              <CardContent className="p-3 sm:p-4">
                {/* Mobile: stacked layout, Desktop: side-by-side */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-3">
                  <div className="flex-1 min-w-0 overflow-hidden">
                    {/* Header row with issue number, badges, and mobile action buttons */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
                        <a
                          href={task.issue_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1.5 text-primary hover:text-primary/90 font-bold text-sm sm:text-base group/link"
                        >
                          <span className="font-mono">
                            #{task.github_issue_number}
                          </span>
                          <ExternalLink className="w-3.5 h-3.5 group-hover/link:translate-x-1 transition-transform" />
                        </a>
                        {getTaskTypeBadge(task)}
                        {getAgentStatusBadge(task.agent_status)}
                      </div>
                      {/* Mobile action buttons - inline with header */}
                      <div className="flex items-center gap-1 flex-shrink-0 sm:hidden">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleExecuteAgent(task);
                          }}
                          disabled={task.agent_status === "running"}
                          title="Open Agent Chat"
                          className="h-9 w-9 min-h-[44px] min-w-[44px]"
                        >
                          <Code className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveTask(task.id);
                          }}
                          disabled={removingTaskId === task.id}
                          title="Remove task"
                          className="h-9 w-9 min-h-[44px] min-w-[44px] text-destructive hover:text-destructive"
                        >
                          {removingTaskId === task.id ? (
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-muted border-t-destructive"></div>
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>

                    {task.github_issue_title && (
                      <h3 className="text-sm sm:text-base font-semibold text-foreground mb-2 line-clamp-2 sm:line-clamp-1">
                        {task.github_issue_title}
                      </h3>
                    )}

                    {/* Metadata row */}
                    <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                      <div className="flex items-center gap-1">
                        <User className="w-3 h-3 flex-shrink-0" />
                        <span className="font-medium text-foreground">
                          {task.added_by_username}
                        </span>
                      </div>
                      <span>•</span>
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 flex-shrink-0" />
                        <span>
                          {new Date(task.added_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    {/* Branch name and PR link */}
                    {(task.agent_branch_name || (task.agent_status === "completed" && task.agent_pr_url)) && (
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
                        {task.agent_branch_name && (
                          <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-muted rounded border border-border max-w-[calc(100%-70px)] sm:max-w-xs">
                            <GitBranch className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                            <span className="font-mono text-foreground truncate text-xs">
                              {task.agent_branch_name}
                            </span>
                          </div>
                        )}
                        {task.agent_status === "completed" && task.agent_pr_url && (
                          <a
                            href={task.agent_pr_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-success/10 text-success hover:bg-success/20 font-semibold border border-success/20 transition-colors group/pr text-xs flex-shrink-0"
                          >
                            <CheckCircle className="w-3 h-3" />
                            PR
                            <ExternalLink className="w-3 h-3 group-hover/pr:translate-x-0.5 transition-transform" />
                          </a>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Desktop action buttons */}
                  <div className="hidden sm:flex items-center gap-1 flex-shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExecuteAgent(task);
                      }}
                      disabled={task.agent_status === "running"}
                      title="Open Agent Chat"
                      className="h-10 w-10 min-h-[44px] min-w-[44px]"
                    >
                      <Code className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveTask(task.id);
                      }}
                      disabled={removingTaskId === task.id}
                      title="Remove task"
                      className="h-10 w-10 min-h-[44px] min-w-[44px] text-destructive hover:text-destructive"
                    >
                      {removingTaskId === task.id ? (
                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-muted border-t-destructive"></div>
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            );
          })}
        </div>
      )}

      {/* Alert Modal */}
      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        type={alertModal.type}
        showCancel={alertModal.showCancel}
        onConfirm={() => {
          if (alertModal.onConfirm) {
            alertModal.onConfirm();
          } else {
            setAlertModal({ ...alertModal, isOpen: false });
          }
        }}
        onCancel={() => setAlertModal({ ...alertModal, isOpen: false })}
      />

      {/* Link PR Modal */}
      {showLinkPRModal && (
        <LinkPRModal
          workspaceId={workspaceId}
          onClose={() => setShowLinkPRModal(false)}
          onPRLinked={loadTasks}
        />
      )}
    </div>
  );
}
