/**
 * TypeScript types for agent chat messages
 */

export interface FileAttachment {
  filename: string;
  file_path: string;
  file_size: number;
  content_type: string;
}

export interface AgentMessage {
  id: number;
  workspace_task_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  attachments?: FileAttachment[] | null;
  created_at: string;
  user_id: number | null;
  username: string | null;
}

export interface AgentMessageCreate {
  content: string;
}

export interface AgentMessageListResponse {
  messages: AgentMessage[];
  total: number;
}
