/**
 * TypeScript types for coder agent
 */

export interface CoderAgentExecuteRequest {
  additional_context?: string;
  target_branch?: string;
  files_to_modify?: string[];
}

export interface CoderAgentExecuteResponse {
  status: string;
  message: string;
  task_id: number;
}

export interface CoderAgentStatusResponse {
  status: "idle" | "running" | "completed" | "failed";
  branch_name: string | null;
  pr_number: number | null;
  pr_url: string | null;
  error: string | null;
  executed_at: string | null;
}
