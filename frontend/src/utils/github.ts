/**
 * Git provider utility functions (GitHub & GitLab)
 */

import type { GitProvider } from '../types/github';

/**
 * Normalize GitHub repository input to owner/repo format.
 */
export function normalizeGitHubRepository(input: string): string | null {
  if (!input) return null;

  const trimmed = input.trim();

  // Short format: owner/repo
  const shortFormatMatch = /^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)$/.test(trimmed);
  if (shortFormatMatch) {
    return trimmed;
  }

  // HTTPS URL: https://github.com/owner/repo or https://github.com/owner/repo.git
  const httpsMatch = trimmed.match(/^https?:\/\/github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+?)(\.git)?$/);
  if (httpsMatch) {
    return `${httpsMatch[1]}/${httpsMatch[2]}`;
  }

  // SSH URL: git@github.com:owner/repo.git
  const sshMatch = trimmed.match(/^git@github\.com:([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+?)(\.git)?$/);
  if (sshMatch) {
    return `${sshMatch[1]}/${sshMatch[2]}`;
  }

  return null;
}

/**
 * Normalize GitLab repository input to namespace/project format.
 */
export function normalizeGitLabRepository(input: string, gitlabUrl: string = 'https://gitlab.com'): string | null {
  if (!input) return null;

  const trimmed = input.trim();

  // Short format: namespace/project (can include nested groups)
  if (/^[a-zA-Z0-9_.-]+(\/[a-zA-Z0-9_.-]+)+$/.test(trimmed) && !trimmed.includes('://') && !trimmed.includes('@')) {
    return trimmed;
  }

  // Extract host from gitlabUrl for pattern matching
  const host = gitlabUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
  const escapedHost = host.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  // HTTPS URL
  const httpsMatch = trimmed.match(new RegExp(`^https?://${escapedHost}/(.+?)(?:\\.git)?$`));
  if (httpsMatch) {
    const path = httpsMatch[1].replace(/\/-\/.*$/, '').replace(/\/$/, '');
    return path;
  }

  // SSH URL
  const sshMatch = trimmed.match(new RegExp(`^git@${escapedHost}:(.+?)(?:\\.git)?$`));
  if (sshMatch) {
    return sshMatch[1];
  }

  return null;
}

/**
 * Normalize a repository input based on the provider type.
 */
export function normalizeRepository(input: string, provider: GitProvider = 'github', gitlabUrl?: string): string | null {
  if (provider === 'gitlab') {
    return normalizeGitLabRepository(input, gitlabUrl);
  }
  return normalizeGitHubRepository(input);
}

/**
 * Validate if a string is a valid repository format for the given provider.
 */
export function isValidRepository(input: string, provider: GitProvider = 'github', gitlabUrl?: string): boolean {
  return normalizeRepository(input, provider, gitlabUrl) !== null;
}

/**
 * Validate if a string is a valid GitHub repository format.
 */
export function isValidGitHubRepository(input: string): boolean {
  return normalizeGitHubRepository(input) !== null;
}

/**
 * Get repository display name from normalized format.
 */
export function getRepositoryName(repo: string): string {
  const parts = repo.split('/');
  return parts.length >= 2 ? parts[parts.length - 1] : repo;
}

/**
 * Get repository owner/namespace from normalized format.
 */
export function getRepositoryOwner(repo: string): string {
  const parts = repo.split('/');
  if (parts.length >= 2) {
    return parts.slice(0, -1).join('/');
  }
  return '';
}
