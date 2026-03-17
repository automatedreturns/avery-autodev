import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { storeGitHubToken } from '../api/github';
import type { GitProvider } from '../types/github';

export default function GitHubSetupPage() {
  const [token, setToken] = useState('');
  const [gitlabUrl, setGitlabUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { checkAuth } = useAuth();

  // Get redirect info and provider from navigation state
  const state = location.state as { from?: string; message?: string; provider?: GitProvider } | null;
  const from = state?.from || '/workspaces';
  const redirectMessage = state?.message;
  const provider: GitProvider = state?.provider || 'github';

  const isGitLab = provider === 'gitlab';
  const providerLabel = isGitLab ? 'GitLab' : 'GitHub';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!token.trim()) {
      setError(`Please enter a ${providerLabel} token`);
      return;
    }

    try {
      setLoading(true);
      setError('');

      await storeGitHubToken({
        token: token.trim(),
        provider,
        ...(isGitLab && gitlabUrl.trim() ? { gitlab_url: gitlabUrl.trim() } : {}),
      });

      await checkAuth();
      setSuccess(true);
      setTimeout(() => {
        navigate(from);
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to connect ${providerLabel} account`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Connect {providerLabel} Account</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Connect your {providerLabel} account to manage workspaces with repository integration
        </p>
      </div>

      {/* Provider switcher tabs */}
      <div className="flex mb-6 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
        <button
          type="button"
          onClick={() => navigate('/github-setup', { state: { ...state, provider: 'github' }, replace: true })}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            !isGitLab
              ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          GitHub
        </button>
        <button
          type="button"
          onClick={() => navigate('/github-setup', { state: { ...state, provider: 'gitlab' }, replace: true })}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            isGitLab
              ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          GitLab
        </button>
      </div>

      {success ? (
        <div className="bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-lg p-6 text-center">
          <svg
            className="w-16 h-16 text-green-500 mx-auto mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h2 className="text-2xl font-bold text-green-900 dark:text-green-100 mb-2">Connected Successfully!</h2>
          <p className="text-green-700 dark:text-green-300">Redirecting to workspaces...</p>
        </div>
      ) : (
        <>
          {redirectMessage && (
            <div className="bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-200 px-4 py-3 rounded-lg mb-6">
              <div className="flex items-center">
                <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {redirectMessage}
              </div>
            </div>
          )}

          {/* Instructions */}
          {isGitLab ? (
            <div className="bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-800 rounded-lg p-6 mb-6">
              <h3 className="font-semibold text-orange-900 dark:text-orange-100 mb-2">How to create a GitLab Personal Access Token:</h3>
              <ol className="list-decimal list-inside space-y-2 text-orange-800 dark:text-orange-200 text-sm">
                <li>
                  Go to your GitLab instance &rarr; <strong>Preferences</strong> &rarr; <strong>Access Tokens</strong>
                </li>
                <li>Click "Add new token"</li>
                <li>Give it a descriptive name (e.g., "Avery Workspace Manager")</li>
                <li>
                  <strong>Required scopes:</strong>
                  <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                    <li>
                      <code className="bg-orange-100 dark:bg-orange-900/40 px-1 rounded">api</code> - Full API access (read/write repositories, issues, merge requests)
                    </li>
                    <li>
                      <code className="bg-orange-100 dark:bg-orange-900/40 px-1 rounded">read_repository</code> - Read repository contents
                    </li>
                  </ul>
                </li>
                <li>Set an expiration date</li>
                <li>Click "Create personal access token"</li>
                <li>Copy the token and paste it below</li>
              </ol>
            </div>
          ) : (
            <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6 mb-6">
              <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">How to create a GitHub Personal Access Token:</h3>
              <ol className="list-decimal list-inside space-y-2 text-blue-800 dark:text-blue-200 text-sm">
                <li>
                  Go to{' '}
                  <a
                    href="https://github.com/settings/tokens/new"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-blue-600 dark:hover:text-blue-400"
                  >
                    GitHub Settings &rarr; Developer settings &rarr; Personal access tokens
                  </a>
                </li>
                <li>Click "Generate new token" (classic)</li>
                <li>Give it a descriptive name (e.g., "Avery Workspace Manager")</li>
                <li>
                  <strong>Required permissions:</strong>
                  <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                    <li>
                      <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">repo</code> - Full control of private repositories
                    </li>
                    <li>
                      <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">workflow</code> - Update GitHub Action workflows (optional)
                    </li>
                  </ul>
                </li>
                <li>Set an expiration date (recommended: 90 days)</li>
                <li>Click "Generate token" and copy the token</li>
                <li>Paste the token in the field below</li>
              </ol>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="bg-white dark:bg-card rounded-lg shadow-md border border-border p-6">
            {isGitLab && (
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  GitLab URL
                </label>
                <input
                  type="url"
                  value={gitlabUrl}
                  onChange={(e) => setGitlabUrl(e.target.value)}
                  placeholder="https://gitlab.com"
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm bg-white dark:bg-gray-800 text-foreground"
                />
                <p className="text-gray-500 dark:text-gray-400 text-xs mt-2">
                  Leave blank for gitlab.com, or enter your self-hosted GitLab URL (e.g., https://gitlab.mycompany.com)
                </p>
              </div>
            )}

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {providerLabel} Personal Access Token *
              </label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={isGitLab ? 'glpat-xxxxxxxxxxxxxxxxxxxx' : 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm bg-white dark:bg-gray-800 text-foreground"
              />
              <p className="text-gray-500 dark:text-gray-400 text-xs mt-2">
                Your token is encrypted and stored securely. It's never exposed in API responses.
              </p>
            </div>

            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => navigate('/workspaces')}
                className="flex-1 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 px-6 py-2 rounded-lg font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-medium transition-colors"
              >
                {loading ? 'Connecting...' : `Connect ${providerLabel}`}
              </button>
            </div>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Already connected?{' '}
              <button
                onClick={() => navigate('/workspaces')}
                className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
              >
                Go to Workspaces
              </button>
            </p>
          </div>
        </>
      )}
    </div>
  );
}
