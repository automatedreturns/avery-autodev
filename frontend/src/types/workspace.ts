/**
 * TypeScript types for workspace management
 */

export type WorkspaceMemberRole = "owner" | "admin" | "member";

export interface WorkspaceMember {
  id: number;
  user_id: number;
  username: string;
  email: string;
  role: WorkspaceMemberRole;
  joined_at: string;
}

export interface Workspace {
  id: number;
  name: string;
  description?: string;
  git_provider: "github" | "gitlab";
  gitlab_url?: string;
  github_repository: string;
  github_dev_branch: string;
  github_main_branch: string;
  is_active: boolean;
  owner_id: number;
  created_at: string;
  updated_at: string;
  role: WorkspaceMemberRole;
  is_default: boolean;
}

export interface WorkspaceDetail extends Workspace {
  owner: {
    id: number;
    username: string;
    email: string;
  };
  members: WorkspaceMember[];
  member_count: number;
  polling_enabled: boolean;
}

export interface WorkspaceCreateData {
  name: string;
  description?: string;
  git_provider?: "github" | "gitlab";
  gitlab_url?: string;
  github_repository: string;
  github_dev_branch: string;
  github_main_branch: string;
}

export interface WorkspaceUpdateData {
  name?: string;
  description?: string;
  github_dev_branch?: string;
  github_main_branch?: string;
  is_active?: boolean;
}

export interface AddMemberData {
  user_id: number;
  role: "admin" | "member";
}

export interface WorkspaceListResponse {
  workspaces: Workspace[];
  total: number;
}
