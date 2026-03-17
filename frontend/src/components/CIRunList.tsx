/**
 * CI Run List Component
 * Displays a list of CI runs for a workspace with status indicators
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { listCIRuns } from "../api/ci_runs";
import type { CIRunSummary, CIRunListParams } from "../types/ci_run";
import LoadingSpinner from "./LoadingSpinner";

interface CIRunListProps {
  workspaceId: number;
  filters?: CIRunListParams;
  limit?: number;
}

export default function CIRunList({
  workspaceId,
  filters,
  limit = 20,
}: CIRunListProps) {
  const [ciRuns, setCIRuns] = useState<CIRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCIRuns();
  }, [workspaceId, filters]);

  const loadCIRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listCIRuns(workspaceId, { ...filters, limit });
      setCIRuns(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load CI runs");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string, conclusion: string | null) => {
    if (status === "in_progress" || status === "queued") {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          <span className="animate-pulse mr-1.5 h-2 w-2 rounded-full bg-blue-600 dark:bg-blue-400"></span>
          {status === "queued" ? "Queued" : "Running"}
        </span>
      );
    }

    if (conclusion === "success") {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          ✓ Success
        </span>
      );
    }

    if (conclusion === "failure") {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          ✗ Failed
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
        {conclusion || status}
      </span>
    );
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "N/A";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(`${dateString}Z`);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
        <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
      </div>
    );
  }

  if (ciRuns.length === 0) {
    return (
      <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
          No CI runs
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          CI runs will appear here when PRs are created.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                PR
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Job
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Tests
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Coverage Δ
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Duration
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Time
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {ciRuns.map((run) => (
              <tr
                key={run.id}
                className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <Link
                    to={`/workspaces/${workspaceId}/ci/${run.id}`}
                    className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    #{run.pr_number}
                  </Link>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-gray-900 dark:text-gray-100">
                    {run.job_name}
                  </span>
                  {run.self_fix_attempted && (
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                      🤖 Self-Fix
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(run.status, run.conclusion)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                  {run.tests_passed !== null && run.tests_failed !== null ? (
                    <span>
                      <span className="text-green-600 dark:text-green-400">
                        {run.tests_passed}
                      </span>
                      {" / "}
                      <span className="text-red-600 dark:text-red-400">
                        {run.tests_failed}
                      </span>
                    </span>
                  ) : (
                    "N/A"
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {run.coverage_delta !== null ? (
                    <span
                      className={
                        run.coverage_delta > 0
                          ? "text-green-600 dark:text-green-400"
                          : run.coverage_delta < 0
                            ? "text-red-600 dark:text-red-400"
                            : "text-gray-600 dark:text-gray-400"
                      }
                    >
                      {run.coverage_delta > 0 ? "+" : ""}
                      {run.coverage_delta.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-gray-400 dark:text-gray-500">
                      N/A
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {formatDuration(run.duration_seconds)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {formatDate(run.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
