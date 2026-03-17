/**
 * Self-Fix Status Component
 * Displays agent self-fix attempt status and details
 */

import type { CIRun } from '../types/ci_run';

interface SelfFixStatusProps {
  ciRun: CIRun;
}

export default function SelfFixStatus({ ciRun }: SelfFixStatusProps) {
  const getStatusIcon = () => {
    if (!ciRun.self_fix_attempted) {
      return null;
    }

    if (ciRun.self_fix_successful === true) {
      return (
        <svg className="h-6 w-6 text-green-500 dark:text-green-400" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clipRule="evenodd"
          />
        </svg>
      );
    }

    if (ciRun.self_fix_successful === false) {
      return (
        <svg className="h-6 w-6 text-red-500 dark:text-red-400" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clipRule="evenodd"
          />
        </svg>
      );
    }

    // In progress
    return (
      <svg className="h-6 w-6 text-blue-500 dark:text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
    );
  };

  const getStatusText = () => {
    if (!ciRun.self_fix_attempted) {
      return 'No self-fix attempted';
    }

    if (ciRun.self_fix_successful === true) {
      return 'Self-fix successful';
    }

    if (ciRun.self_fix_successful === false) {
      return 'Self-fix failed';
    }

    return 'Self-fix in progress';
  };

  const getStatusColor = () => {
    if (!ciRun.self_fix_attempted) {
      return 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700';
    }

    if (ciRun.self_fix_successful === true) {
      return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
    }

    if (ciRun.self_fix_successful === false) {
      return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
    }

    return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800';
  };

  return (
    <div className={`rounded-lg border p-6 ${getStatusColor()}`}>
      <div className="flex items-start">
        <div className="flex-shrink-0">{getStatusIcon()}</div>
        <div className="ml-3 flex-1">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
              🤖 Agent Self-Fix
            </h3>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
              Retry {ciRun.retry_count} / {ciRun.max_retries}
            </span>
          </div>

          <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">{getStatusText()}</p>

          {ciRun.self_fix_attempted && (
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Attempts:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {ciRun.retry_count} / {ciRun.max_retries}
                </span>
              </div>

              {ciRun.self_fix_successful === true && (
                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-md">
                  <p className="text-sm text-green-800 dark:text-green-200">
                    ✓ The agent successfully analyzed the CI failure and applied fixes. A new commit
                    has been pushed to the PR branch.
                  </p>
                </div>
              )}

              {ciRun.self_fix_successful === false && (
                <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-md">
                  <p className="text-sm text-red-800 dark:text-red-200">
                    ✗ The agent attempted to fix the issues but was unsuccessful. Manual intervention
                    may be required.
                  </p>
                </div>
              )}

              {ciRun.self_fix_successful === null && ciRun.self_fix_attempted && (
                <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-md">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    ⏳ The agent is analyzing the failure and generating fixes...
                  </p>
                </div>
              )}

              {ciRun.retry_count >= ciRun.max_retries && ciRun.self_fix_successful !== true && (
                <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-md">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    ⚠️ Maximum retry attempts reached. Manual review required.
                  </p>
                </div>
              )}
            </div>
          )}

          {!ciRun.self_fix_attempted && ciRun.conclusion === 'failure' && (
            <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-800 rounded-md">
              <p className="text-sm text-gray-700 dark:text-gray-300">
                The CI run failed but self-fix has not been triggered yet. It may trigger
                automatically, or you can manually trigger it using the button above.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
