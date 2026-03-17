import { useState, useEffect } from 'react';
import { searchUsers, type User } from '../api/users';
import { addWorkspaceMember } from '../api/workspaces';

interface ShareWorkspaceModalProps {
  workspaceId: number;
  workspaceName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ShareWorkspaceModal({
  workspaceId,
  workspaceName,
  onClose,
  onSuccess,
}: ShareWorkspaceModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRole, setSelectedRole] = useState<'admin' | 'member'>('member');
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced search
  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setSearching(true);
        setError(null);
        const results = await searchUsers(searchQuery);
        setSearchResults(results);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to search users');
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleAddMember = async () => {
    if (!selectedUser) return;

    try {
      setAdding(true);
      setError(null);
      await addWorkspaceMember(workspaceId, {
        user_id: selectedUser.id,
        role: selectedRole,
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add member');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-card rounded-2xl shadow-2xl max-w-md w-full max-h-[80vh] overflow-hidden flex flex-col border border-border">
        {/* Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-foreground">Share Workspace</h2>
              <p className="text-sm text-muted-foreground mt-1">{workspaceName}</p>
            </div>
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 flex-1 overflow-y-auto">
          {/* Search Input */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-foreground mb-2">
              Search by username or email
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter username or email..."
              className="w-full px-4 py-2 border border-input rounded-lg bg-background text-foreground placeholder-muted-foreground focus:ring-2 focus:ring-ring focus:border-transparent"
            />
          </div>

          {/* Search Results */}
          {searching && (
            <div className="text-center py-4">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent mx-auto"></div>
            </div>
          )}

          {searchResults.length > 0 && !selectedUser && (
            <div className="space-y-2 mb-4">
              <p className="text-sm font-medium text-foreground">Select a user:</p>
              {searchResults.map((user) => (
                <button
                  key={user.id}
                  onClick={() => {
                    setSelectedUser(user);
                    setSearchResults([]);
                    setSearchQuery('');
                  }}
                  className="w-full text-left px-4 py-3 border border-border rounded-lg hover:bg-muted transition-colors"
                >
                  <div className="font-medium text-foreground">{user.username}</div>
                  <div className="text-sm text-muted-foreground">{user.email}</div>
                </button>
              ))}
            </div>
          )}

          {/* Selected User */}
          {selectedUser && (
            <div className="mb-4">
              <p className="text-sm font-medium text-foreground mb-2">Selected user:</p>
              <div className="flex items-center justify-between px-4 py-3 bg-accent/10 border border-accent/30 rounded-lg">
                <div>
                  <div className="font-medium text-foreground">{selectedUser.username}</div>
                  <div className="text-sm text-muted-foreground">{selectedUser.email}</div>
                </div>
                <button
                  onClick={() => setSelectedUser(null)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Role Selection */}
          {selectedUser && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-foreground mb-2">
                Select role
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setSelectedRole('member')}
                  className={`px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedRole === 'member'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <div className="font-semibold">Member</div>
                  <div className="text-xs text-muted-foreground mt-1">Can view and work on tasks</div>
                </button>
                <button
                  onClick={() => setSelectedRole('admin')}
                  className={`px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedRole === 'admin'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <div className="font-semibold">Admin</div>
                  <div className="text-xs text-muted-foreground mt-1">Can manage workspace</div>
                </button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-lg">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-border rounded-lg text-foreground hover:bg-muted transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleAddMember}
            disabled={!selectedUser || adding}
            className="flex-1 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {adding ? 'Adding...' : 'Add Member'}
          </button>
        </div>
      </div>
    </div>
  );
}
