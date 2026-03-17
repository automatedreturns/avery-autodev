/**
 * TypeScript types for Git provider integration (GitHub & GitLab)
 */

export type GitProvider = "github" | "gitlab";

export interface GitHubTokenData {
  token: string;
  github_username?: string;
  provider?: GitProvider;
  gitlab_url?: string;
}

export interface GitHubTokenResponse {
  status: "connected" | "not_connected";
  github_username?: string;
  provider?: GitProvider;
}

export interface GitHubRepoValidation {
  valid: boolean;
  repository: string;
  description?: string;
  default_branch?: string;
  error?: string;
}

export interface GitHubBranchList {
  repository: string;
  branches: string[];
  error?: string;
}
