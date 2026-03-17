import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listWorkspaces } from '../api/workspaces';
import type { Workspace } from '../types/workspace';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Plus, Github, Gitlab, GitBranch, Star, ArrowRight, Layers, Sparkles } from 'lucide-react';

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    loadWorkspaces();
  }, []);

  const loadWorkspaces = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await listWorkspaces();
      setWorkspaces(response.workspaces);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 animate-pulse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <Layers className="w-8 h-8 text-primary animate-spin" style={{ animationDuration: '3s' }} />
            </div>
          </div>
          <p className="mt-6 text-sm font-medium text-muted-foreground tracking-wide">Loading workspaces...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Subtle gradient background */}
      <div className="fixed inset-0 bg-gradient-to-br from-primary/[0.02] via-transparent to-accent/[0.02] pointer-events-none" />

      <div className="relative container mx-auto px-6 py-12 pb-20 max-w-6xl">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:justify-between md:items-end gap-6 mb-12">
          <div className="space-y-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary to-primary/80 shadow-lg shadow-primary/25">
                <Layers className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">Workspaces</span>
            </div>
            <h1 className="text-4xl md:text-4xl font-bold text-foreground tracking-tight">
              Your Workspaces
            </h1>
            <p className="text-muted-foreground text-md font-light max-w-md">
              Manage and organize your development environments
            </p>
          </div>

          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/profile')}
              variant="outline"
              className="h-11 px-5 rounded-xl border-border/50 hover:bg-muted/50 hover:border-border transition-all duration-300"
            >
              <GitBranch className="w-4 h-4 mr-2" />
              <span className="font-medium">Git Setup</span>
            </Button>
            <Button
              onClick={() => navigate('/workspaces/new')}
              variant={'gradient'}
              className="h-11 px-5 rounded-xl bg-gradient-to-r from-primary to-primary/90 hover:from-primary/90 hover:to-primary/80 shadow-lg shadow-primary/25 hover:shadow-xl hover:shadow-primary/30 transition-all duration-300"
            >
              <Plus className="w-4 h-4 mr-2" />
              <span className="font-medium">New Workspace</span>
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-8 rounded-xl border-destructive/20 bg-destructive/5">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="font-medium">{error}</AlertDescription>
          </Alert>
        )}

        {workspaces.length === 0 ? (
          /* Empty State */
          <div className="relative overflow-hidden rounded-3xl border border-border/50 bg-gradient-to-br from-card to-card/50 p-12 md:p-16">
            <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-primary/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-gradient-to-tr from-accent/10 to-transparent rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />

            <div className="relative text-center max-w-lg mx-auto">
              <div className="inline-flex p-4 rounded-2xl bg-gradient-to-br from-primary/10 to-accent/10 mb-8">
                <div className="p-3 rounded-xl bg-gradient-to-br from-primary to-primary/80 shadow-lg shadow-primary/25">
                  <Sparkles className="w-8 h-8 text-primary-foreground" />
                </div>
              </div>

              <h2 className="text-3xl font-bold text-foreground mb-4 tracking-tight">
                Create your first workspace
              </h2>
              <p className="text-muted-foreground text-lg font-light mb-10 leading-relaxed">
                Workspaces help you organize your projects and keep your development environments clean and focused.
              </p>

              <Button
                onClick={() => navigate('/workspaces/new')}
                size="lg"
                variant="gradient"
                className="h-12 px-8 rounded-xl group"
              >
                <Plus className="w-5 h-5 mr-2" />
                <span className="font-semibold">Create Workspace</span>
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
              </Button>
            </div>
          </div>
        ) : (
          /* Workspace Grid */
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {workspaces.map((workspace) => (
              <div
                key={workspace.id}
                onClick={() => navigate(`/workspaces/${workspace.id}`)}
                className="group relative cursor-pointer rounded-xl border border-border/50 bg-card p-5 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 transition-all duration-200"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <h3 className="text-base font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                    {workspace.name}
                  </h3>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {workspace.is_default && (
                      <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
                    )}
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>

                {/* Repository */}
                <div className="flex items-center gap-2 text-muted-foreground mb-3">
                  {workspace.git_provider === 'gitlab' ? (
                    <Gitlab className="w-3.5 h-3.5 shrink-0" />
                  ) : (
                    <Github className="w-3.5 h-3.5 shrink-0" />
                  )}
                  <span className="font-mono text-xs truncate">{workspace.github_repository}</span>
                </div>

                {/* Branch info */}
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <GitBranch className="w-3 h-3" />
                    <span className="font-mono">{workspace.github_dev_branch}</span>
                  </div>
                  <span className="text-border">•</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide ${
                    workspace.is_active
                      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                      : 'bg-muted text-muted-foreground'
                  }`}>
                    {workspace.role}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
