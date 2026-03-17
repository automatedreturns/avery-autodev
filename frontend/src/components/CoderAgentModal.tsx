import { useEffect, useState } from 'react';
import { executeCoderAgent, getCoderAgentStatus } from '../api/coder_agent';
import { listBranches } from '../api/github';
import type { WorkspaceTask } from '../types/workspace_task';

interface Props {
  workspaceId: number;
  task: WorkspaceTask;
  repository: string;
  defaultBranch: string;
  onClose: () => void;
  onComplete: () => void;
}

export default function CoderAgentModal({
  workspaceId,
  task,
  repository,
  defaultBranch,
  onClose,
  onComplete,
}: Props) {
  const [additionalContext, setAdditionalContext] = useState('');
  const [targetBranch, setTargetBranch] = useState(defaultBranch);
  const [filesToModify, setFilesToModify] = useState('');
  const [branches, setBranches] = useState<string[]>([]);
  const [loadingBranches, setLoadingBranches] = useState(false);

  const [executing, setExecuting] = useState(false);
  const [agentStatus, setAgentStatus] = useState(task.agent_status);
  const [agentPrUrl, setAgentPrUrl] = useState(task.agent_pr_url);
  const [agentError, setAgentError] = useState(task.agent_error);
  const [error, setError] = useState('');

  // Load branches on mount
  useEffect(() => {
    loadBranches();
  }, [repository]);

  // Poll agent status if already running
  useEffect(() => {
    if (agentStatus === 'running') {
      const interval = setInterval(() => {
        pollAgentStatus();
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [agentStatus]);

  const loadBranches = async () => {
    try {
      setLoadingBranches(true);
      const response = await listBranches(repository);
      setBranches(response.branches);
    } catch (err) {
      console.error('Failed to load branches:', err);
    } finally {
      setLoadingBranches(false);
    }
  };

  const pollAgentStatus = async () => {
    try {
      const status = await getCoderAgentStatus(workspaceId, task.id);
      setAgentStatus(status.status);
      setAgentPrUrl(status.pr_url);
      setAgentError(status.error);

      if (status.status === 'completed' || status.status === 'failed') {
        onComplete();
      }
    } catch (err) {
      console.error('Failed to poll agent status:', err);
    }
  };

  const handleExecute = async () => {
    try {
      setExecuting(true);
      setError('');

      const filesArray = filesToModify
        .split(',')
        .map((f) => f.trim())
        .filter((f) => f.length > 0);

      await executeCoderAgent(workspaceId, task.id, {
        additional_context: additionalContext,
        target_branch: targetBranch,
        files_to_modify: filesArray.length > 0 ? filesArray : undefined,
      });

      setAgentStatus('running');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute agent');
    } finally {
      setExecuting(false);
    }
  };

  const handleRetry = () => {
    setAgentStatus('idle');
    setAgentError(null);
    setError('');
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">
            Execute Coder Agent
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            disabled={agentStatus === 'running'}
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Issue Info */}
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-sm font-medium text-gray-700 mb-1">
              GitHub Issue #{task.github_issue_number}
            </h3>
            <a
              href={task.issue_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 text-sm flex items-center"
            >
              View on GitHub
              <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </div>

          {/* Status Display */}
          {agentStatus === 'running' && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500 mr-3"></div>
                <div>
                  <p className="text-sm font-medium text-blue-900">
                    Agent is working...
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    This may take a few minutes. The agent is analyzing the issue,
                    generating code, and creating a pull request.
                  </p>
                </div>
              </div>
            </div>
          )}

          {agentStatus === 'completed' && agentPrUrl && (
            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-medium text-green-900">
                    Pull Request Created!
                  </p>
                  <a
                    href={agentPrUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-green-700 hover:text-green-800 flex items-center mt-1"
                  >
                    View Pull Request
                    <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                </div>
              </div>
            </div>
          )}

          {agentStatus === 'failed' && agentError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-red-500 mr-3 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-900">Agent Failed</p>
                  <p className="text-xs text-red-700 mt-1">{agentError}</p>
                  <button
                    onClick={handleRetry}
                    className="mt-2 text-sm text-red-700 hover:text-red-800 font-medium"
                  >
                    Retry
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Form - only show when idle or failed */}
          {(agentStatus === 'idle' || agentStatus === 'failed') && (
            <>
              {/* Target Branch */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Branch
                </label>
                <select
                  value={targetBranch}
                  onChange={(e) => setTargetBranch(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  disabled={loadingBranches}
                >
                  {loadingBranches ? (
                    <option>Loading branches...</option>
                  ) : (
                    branches.map((branch) => (
                      <option key={branch} value={branch}>
                        {branch}
                      </option>
                    ))
                  )}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  The agent will create a new branch from this base branch
                </p>
              </div>

              {/* Additional Context */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Additional Context (Optional)
                </label>
                <textarea
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Provide any additional instructions or context for the agent..."
                />
              </div>

              {/* Files to Modify */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Files to Modify (Optional)
                </label>
                <input
                  type="text"
                  value={filesToModify}
                  onChange={(e) => setFilesToModify(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., src/app.py, src/utils.py"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Comma-separated list of files. Leave empty to let the agent decide.
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  {error}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {(agentStatus === 'idle' || agentStatus === 'failed') && (
          <div className="flex justify-end gap-3 p-6 border-t">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:text-gray-900 font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={executing}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
            >
              {executing ? 'Starting...' : 'Execute Agent'}
            </button>
          </div>
        )}

        {agentStatus === 'running' && (
          <div className="flex justify-end gap-3 p-6 border-t">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:text-gray-900 font-medium"
            >
              Close
            </button>
          </div>
        )}

        {agentStatus === 'completed' && (
          <div className="flex justify-end gap-3 p-6 border-t">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
