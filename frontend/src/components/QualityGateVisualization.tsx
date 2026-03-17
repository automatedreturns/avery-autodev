/**
 * Quality Gate Visualization Component
 * Displays quality gate checks and recommendation
 */

import type { QualityGateResult } from '../types/ci_run';

interface QualityGateVisualizationProps {
  qualityGate: QualityGateResult;
}

export default function QualityGateVisualization({ qualityGate }: QualityGateVisualizationProps) {
  const getRecommendationBadge = (recommendation: string) => {
    const badges = {
      approve: (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          ✓ Approve
        </span>
      ),
      needs_review: (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          👀 Needs Review
        </span>
      ),
      request_changes: (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          ✗ Request Changes
        </span>
      ),
    };
    return badges[recommendation as keyof typeof badges] || null;
  };

  return (
    <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Quality Gate</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Automated quality checks and recommendation
          </p>
        </div>
        {getRecommendationBadge(qualityGate.recommendation)}
      </div>

      {/* Overall Status */}
      <div className="mb-6">
        {qualityGate.passed ? (
          <div className="flex items-center text-green-600 dark:text-green-400">
            <svg className="h-6 w-6 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">All quality gates passed</span>
          </div>
        ) : (
          <div className="flex items-center text-red-600 dark:text-red-400">
            <svg className="h-6 w-6 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">Quality gates failed</span>
          </div>
        )}
      </div>

      {/* Individual Checks */}
      <div className="space-y-3">
        {Object.entries(qualityGate.checks).map(([checkName, passed]) => (
          <div key={checkName} className="flex items-center justify-between">
            <div className="flex items-center">
              {passed ? (
                <svg
                  className="h-5 w-5 text-green-500 dark:text-green-400 mr-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg
                  className="h-5 w-5 text-red-500 dark:text-red-400 mr-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {checkName.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              </span>
            </div>
            <span
              className={`text-xs font-medium ${
                passed
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-red-600 dark:text-red-400'
              }`}
            >
              {passed ? 'PASS' : 'FAIL'}
            </span>
          </div>
        ))}
      </div>

      {/* Violations */}
      {qualityGate.violations.length > 0 && (
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-md">
          <h4 className="text-sm font-medium text-red-800 dark:text-red-200 mb-2">
            Violations ({qualityGate.violations.length})
          </h4>
          <ul className="list-disc list-inside space-y-1">
            {qualityGate.violations.map((violation, index) => (
              <li key={index} className="text-sm text-red-700 dark:text-red-300">
                {violation}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Coverage Delta */}
      {qualityGate.coverage_delta !== null && (
        <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Coverage Change
            </span>
            <span
              className={`text-sm font-semibold ${
                qualityGate.coverage_delta > 0
                  ? 'text-green-600 dark:text-green-400'
                  : qualityGate.coverage_delta < 0
                  ? 'text-red-600 dark:text-red-400'
                  : 'text-gray-600 dark:text-gray-400'
              }`}
            >
              {qualityGate.coverage_delta > 0 ? '+' : ''}
              {qualityGate.coverage_delta.toFixed(2)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
