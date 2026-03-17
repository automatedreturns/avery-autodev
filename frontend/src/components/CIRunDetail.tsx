/**
 * CI Run Detail Component
 * Displays detailed information about a specific CI run
 */

import { useState, useEffect } from 'react';
import { getCIRun, getQualityGate, getIssuePreview, createGitHubIssue, triggerSelfFix } from '../api/ci_runs';
import type { CIRun, QualityGateResult, IssuePreview } from '../types/ci_run';
import LoadingSpinner from './LoadingSpinner';
import QualityGateVisualization from './QualityGateVisualization';
import SelfFixStatus from './SelfFixStatus';

interface CIRunDetailProps {
  ciRunId: number;
  workspaceId: number;
}

export default function CIRunDetail({ ciRunId, workspaceId: _workspaceId }: CIRunDetailProps) {
  const [ciRun, setCIRun] = useState<CIRun | null>(null);
  const [qualityGate, setQualityGate] = useState<QualityGateResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggeringFix, setTriggeringFix] = useState(false);
  const [triggeringSelfFix, setTriggeringSelfFix] = useState(false);
  const [showIssueModal, setShowIssueModal] = useState(false);
  const [issuePreview, setIssuePreview] = useState<IssuePreview | null>(null);
  const [editedTitle, setEditedTitle] = useState('');
  const [editedBody, setEditedBody] = useState('');

  useEffect(() => {
    loadData();
  }, [ciRunId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [runData, gateData] = await Promise.all([
        getCIRun(ciRunId),
        getQualityGate(ciRunId).catch(() => null), // Quality gate might not be available
      ]);
      setCIRun(runData);
      setQualityGate(gateData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load CI run');
    } finally {
      setLoading(false);
    }
  };

  const handleFixCI = async () => {
    if (!ciRun) return;

    try {
      setTriggeringSelfFix(true);
      const result = await triggerSelfFix(ciRunId, { ci_run_id: ciRunId });

      if (result.success) {
        alert(result.message);
        // Reload data to see updated status
        await loadData();
      } else {
        alert('Failed to trigger self-fix');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to trigger self-fix');
    } finally {
      setTriggeringSelfFix(false);
    }
  };

  const handleCreateIssue = async () => {
    if (!ciRun) return;

    try {
      setTriggeringFix(true);
      // Fetch issue preview
      const preview = await getIssuePreview(ciRunId);
      setIssuePreview(preview);
      setEditedTitle(preview.title);
      setEditedBody(preview.body);
      setShowIssueModal(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to load issue preview');
    } finally {
      setTriggeringFix(false);
    }
  };

  const handleConfirmCreateIssue = async () => {
    if (!ciRun || !issuePreview) return;

    try {
      setTriggeringFix(true);
      const result = await createGitHubIssue(ciRunId, {
        title: editedTitle,
        body: editedBody,
        labels: issuePreview.labels,
      });

      setShowIssueModal(false);

      // Reload data to see updated status
      await loadData();

      if (result.issue_url) {
        // Show success message with link to issue
        const openIssue = confirm(
          `GitHub issue #${result.issue_number} created successfully! Would you like to open it?`
        );
        if (openIssue) {
          window.open(result.issue_url, '_blank');
        }
      } else {
        alert('GitHub issue created successfully!');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create GitHub issue');
    } finally {
      setTriggeringFix(false);
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !ciRun) {
    return (
      <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
        <p className="text-sm text-red-800 dark:text-red-200">{error || 'CI run not found'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              CI Run #{ciRun.id}
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              PR #{ciRun.pr_number} • {ciRun.job_name}
            </p>
          </div>
          {ciRun.conclusion === 'failure' && (
            <div className="flex gap-2">
              {ciRun.retry_count < ciRun.max_retries && (
                <button
                  onClick={handleFixCI}
                  disabled={triggeringSelfFix}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {triggeringSelfFix ? 'Fixing...' : 'FIX CI'}
                </button>
              )}
              <button
                onClick={handleCreateIssue}
                disabled={triggeringFix}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50"
              >
                {triggeringFix ? 'Creating Issue...' : 'Create Issue'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Status and Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Status</dt>
          <dd className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
            {ciRun.status === 'completed' ? ciRun.conclusion || 'Unknown' : ciRun.status}
          </dd>
        </div>

        <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Duration</dt>
          <dd className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
            {formatDuration(ciRun.duration_seconds)}
          </dd>
        </div>

        <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Tests</dt>
          <dd className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
            {ciRun.tests_passed !== null && ciRun.tests_failed !== null ? (
              <>
                <span className="text-green-600 dark:text-green-400">{ciRun.tests_passed}</span>
                {' / '}
                <span className="text-red-600 dark:text-red-400">{ciRun.tests_failed}</span>
                {' failed'}
              </>
            ) : (
              'N/A'
            )}
          </dd>
        </div>

        <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Coverage Δ</dt>
          <dd className="mt-1 text-lg font-semibold">
            {ciRun.coverage_delta !== null ? (
              <span
                className={
                  ciRun.coverage_delta > 0
                    ? 'text-green-600 dark:text-green-400'
                    : ciRun.coverage_delta < 0
                    ? 'text-red-600 dark:text-red-400'
                    : 'text-gray-900 dark:text-gray-100'
                }
              >
                {ciRun.coverage_delta > 0 ? '+' : ''}
                {ciRun.coverage_delta.toFixed(2)}%
              </span>
            ) : (
              <span className="text-gray-400 dark:text-gray-500">N/A</span>
            )}
          </dd>
        </div>
      </div>

      {/* Self-Fix Status */}
      {(ciRun.self_fix_attempted || ciRun.retry_count > 0) && (
        <SelfFixStatus ciRun={ciRun} />
      )}

      {/* Quality Gate */}
      {qualityGate && (
        <QualityGateVisualization qualityGate={qualityGate} />
      )}

      {/* Details */}
      <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Details</h3>
        <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Repository</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">{ciRun.repository}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Branch</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">{ciRun.branch_name}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Commit SHA</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100 font-mono">
              {ciRun.commit_sha.substring(0, 7)}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Workflow</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">{ciRun.workflow_name}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Started At</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">
              {formatDate(ciRun.started_at)}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">Completed At</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">
              {formatDate(ciRun.completed_at)}
            </dd>
          </div>
        </dl>

        {ciRun.logs_url && (
          <div className="mt-4">
            <a
              href={ciRun.logs_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              View Logs →
            </a>
          </div>
        )}
      </div>

      {/* Check Results */}
      {ciRun.check_results && Object.keys(ciRun.check_results).length > 0 && (
        <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
            Check Results
          </h3>
          <div className="space-y-2">
            {Object.entries(ciRun.check_results).map(([checkName, outcome]) => (
              <div key={checkName} className="flex items-center justify-between">
                <span className="text-sm text-gray-700 dark:text-gray-300">{checkName}</span>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    outcome === 'success'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                  }`}
                >
                  {outcome}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Summary */}
      {ciRun.error_summary && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
          <h3 className="text-lg font-medium text-red-900 dark:text-red-200 mb-2">
            Error Summary
          </h3>
          <pre className="text-sm text-red-800 dark:text-red-300 whitespace-pre-wrap font-mono">
            {ciRun.error_summary}
          </pre>
        </div>
      )}

      {/* Issue Preview Modal */}
      {showIssueModal && issuePreview && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50" onClick={() => setShowIssueModal(false)}>
          <div className="relative top-20 mx-auto p-5 border w-11/12 max-w-4xl shadow-lg rounded-md bg-white dark:bg-gray-800" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
                Review GitHub Issue
              </h3>
              <button
                onClick={() => setShowIssueModal(false)}
                className="text-gray-400 hover:text-gray-500"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              {/* Title Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Title
                </label>
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500 dark:bg-gray-700 dark:text-gray-100"
                />
              </div>

              {/* Body Textarea */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Description
                </label>
                <textarea
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  rows={20}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500 font-mono text-sm dark:bg-gray-700 dark:text-gray-100"
                />
              </div>

              {/* Labels */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Labels
                </label>
                <div className="flex gap-2">
                  {issuePreview.labels.map((label) => (
                    <span
                      key={label}
                      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowIssueModal(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmCreateIssue}
                disabled={triggeringFix}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50"
              >
                {triggeringFix ? 'Creating...' : 'Create Issue'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
