/**
 * TypeScript types for workspace task management
 */

export interface WorkspaceTask {
  id: number;
  workspace_id: number;
  github_issue_number: number;
  github_issue_title: string | null;
  issue_url: string;
  added_by_user_id: number;
  added_by_username: string;
  added_at: string;

  // Coder Agent fields
  agent_status: "idle" | "running" | "completed" | "failed";
  agent_branch_name: string | null;
  agent_pr_number: number | null;
  agent_pr_url: string | null;
  agent_error: string | null;
  agent_executed_at: string | null;
}

export interface WorkspaceTaskListResponse {
  tasks: WorkspaceTask[];
  total: number;
}

export interface WorkspaceTaskCreate {
  github_issue_number: number;
}

export interface GitHubIssuePreview {
  number: number;
  title: string;
  state: "open" | "closed";
  html_url: string;
  created_at: string;
  updated_at: string;
}

export interface AvailableIssuesResponse {
  repository: string;
  issues: GitHubIssuePreview[];
  total_count: number;
  has_next: boolean;
  already_linked: number[];
}

export interface FeatureRequestCreate {
  title: string;
  description: string;
  acceptance_criteria?: string;
  labels?: string[];
  link_as_task?: boolean;
}

export interface FeatureRequestResponse {
  success: boolean;
  issue_number?: number;
  issue_url?: string;
  task_id?: number;
  error?: string;
}

export interface SimilarIssuesSearch {
  query: string;
  state?: "open" | "closed" | "all";
  max_results?: number;
}

export interface SimilarIssuesResponse {
  repository: string;
  issues: GitHubIssuePreview[];
  total_count: number;
  error?: string;
}
