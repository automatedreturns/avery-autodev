/**
 * CI Run Detail Page
 * Full page view of a specific CI run
 */

import { useParams, Link } from 'react-router-dom';
import CIRunDetail from '../components/CIRunDetail';

export default function CIRunDetailPage() {
  const { workspaceId, ciRunId } = useParams<{ workspaceId: string; ciRunId: string }>();

  if (!workspaceId || !ciRunId) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">Invalid workspace or CI run ID</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="flex mb-6" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-2 text-sm">
          <li>
            <Link
              to="/workspaces"
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Workspaces
            </Link>
          </li>
          <li>
            <span className="text-gray-400 dark:text-gray-600">/</span>
          </li>
          <li>
            <Link
              to={`/workspaces/${workspaceId}`}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Workspace
            </Link>
          </li>
          <li>
            <span className="text-gray-400 dark:text-gray-600">/</span>
          </li>
          <li>
            <span className="text-gray-900 dark:text-gray-100 font-medium">CI Run #{ciRunId}</span>
          </li>
        </ol>
      </nav>

      {/* CI Run Detail */}
      <CIRunDetail ciRunId={parseInt(ciRunId)} workspaceId={parseInt(workspaceId)} />
    </div>
  );
}
