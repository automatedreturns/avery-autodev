import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { removeGitHubToken } from '../api/github';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, CheckCircle, AlertTriangle } from 'lucide-react';
import AlertModal from '../components/AlertModal';
import type { GitProvider } from '../types/github';

const ProfilePage = () => {
  const { user, logout, checkAuth } = useAuth();
  const navigate = useNavigate();
  const [disconnecting, setDisconnecting] = useState<GitProvider | null>(null);
  const [error, setError] = useState('');
  const [showDisconnectModal, setShowDisconnectModal] = useState<GitProvider | null>(null);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const handleDisconnect = async (provider: GitProvider) => {
    setShowDisconnectModal(null);
    try {
      setDisconnecting(provider);
      setError('');
      await removeGitHubToken(provider);
      await checkAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to disconnect ${provider === 'gitlab' ? 'GitLab' : 'GitHub'}`);
    } finally {
      setDisconnecting(null);
    }
  };

  if (!user) {
    return null;
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const isGitHubConnected = !!user.github_username;
  const isGitLabConnected = !!user.gitlab_username;

  const renderProviderSection = (
    provider: GitProvider,
    label: string,
    isConnected: boolean,
    username?: string,
  ) => (
    <div className="sm:col-span-2 pt-4 border-t border-border">
      <dt className="text-sm font-medium text-card-foreground mb-3">{label} Integration</dt>
      <dd>
        {isConnected ? (
          <div className="flex items-center justify-between bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
            <div className="flex items-center">
              <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400 mr-3" />
              <div>
                <p className="text-sm font-medium text-green-900 dark:text-green-100">Connected as @{username}</p>
                <p className="text-xs text-green-700 dark:text-green-300">Your {label} account is connected and ready to use</p>
              </div>
            </div>
            <Button
              onClick={() => setShowDisconnectModal(provider)}
              disabled={disconnecting === provider}
              variant="destructive"
              size="sm"
            >
              {disconnecting === provider ? 'Disconnecting...' : 'Disconnect'}
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <div className="flex items-center">
              <AlertTriangle className="w-8 h-8 text-yellow-600 dark:text-yellow-400 mr-3" />
              <div>
                <p className="text-sm font-medium text-yellow-900 dark:text-yellow-100">{label} not connected</p>
                <p className="text-xs text-yellow-700 dark:text-yellow-300">Connect your {label} account to create and manage workspaces</p>
              </div>
            </div>
            <Button
              variant="gradient"
              onClick={() => navigate('/github-setup', { state: { provider } })}
              size="sm"
            >
              Connect {label}
            </Button>
          </div>
        )}
      </dd>
    </div>
  );

  return (
    <div className="min-h-screen bg-background py-12">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Card>
          {/* Header */}
          <CardHeader className="bg-primary text-primary-foreground rounded-t-lg">
            <CardTitle className="text-2xl">Profile</CardTitle>
            <CardDescription className="text-primary-foreground/90">
              Manage your account information
            </CardDescription>
          </CardHeader>

          {/* Content */}
          <CardContent className="pt-6">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
              <div className="sm:col-span-1">
                <dt className="text-sm font-medium text-muted-foreground">Username</dt>
                <dd className="mt-1 text-sm text-foreground font-semibold">{user.username}</dd>
              </div>

              <div className="sm:col-span-1">
                <dt className="text-sm font-medium text-muted-foreground">Email address</dt>
                <dd className="mt-1 text-sm text-foreground">{user.email}</dd>
              </div>

              <div className="sm:col-span-1">
                <dt className="text-sm font-medium text-muted-foreground">User ID</dt>
                <dd className="mt-1 text-sm text-foreground">{user.id}</dd>
              </div>

              <div className="sm:col-span-1">
                <dt className="text-sm font-medium text-muted-foreground">Account Status</dt>
                <dd className="mt-1">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      user.is_active
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-destructive/10 text-destructive'
                    }`}
                  >
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </dd>
              </div>

              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-muted-foreground">Member since</dt>
                <dd className="mt-1 text-sm text-foreground">{formatDate(user.created_at)}</dd>
              </div>

              {/* Git Provider Integrations */}
              {renderProviderSection('github', 'GitHub', isGitHubConnected, user.github_username)}
              {renderProviderSection('gitlab', 'GitLab', isGitLabConnected, user.gitlab_username)}
            </dl>
          </CardContent>

          {/* Actions */}
          <div className="px-6 py-4 bg-muted/50 rounded-b-lg flex justify-end items-center gap-3">
            <Button
              onClick={handleLogout}
              variant="destructive"
            >
              Logout
            </Button>
          </div>
        </Card>

        {/* Disconnect Confirmation Modal */}
        <AlertModal
          isOpen={showDisconnectModal !== null}
          title={`Disconnect ${showDisconnectModal === 'gitlab' ? 'GitLab' : 'GitHub'} Account`}
          message={`Are you sure you want to disconnect your ${showDisconnectModal === 'gitlab' ? 'GitLab' : 'GitHub'} account? You will need to reconnect to create or manage workspaces using this provider.`}
          type="warning"
          confirmText="Disconnect"
          cancelText="Cancel"
          showCancel={true}
          onConfirm={() => showDisconnectModal && handleDisconnect(showDisconnectModal)}
          onCancel={() => setShowDisconnectModal(null)}
        />
      </div>
    </div>
  );
};

export default ProfilePage;
