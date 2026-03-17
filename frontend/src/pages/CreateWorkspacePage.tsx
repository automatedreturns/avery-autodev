import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { createWorkspace } from '../api/workspaces';
import { listBranches, validateRepository } from '../api/github';
import { normalizeRepository } from '../utils/github';
import { useAuth } from '../context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowLeft, CheckCircle2, AlertCircle } from 'lucide-react';
import type { GitProvider } from '../types/github';

// Zod schema for workspace creation
const workspaceSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name too long'),
  description: z.string().optional(),
  git_provider: z.enum(['github', 'gitlab']),
  gitlab_url: z.string().optional(),
  github_repository: z.string().min(1, 'Repository is required'),
  github_dev_branch: z.string().min(1, 'Dev branch is required'),
  github_main_branch: z.string().min(1, 'Main branch is required'),
});

type WorkspaceFormData = z.infer<typeof workspaceSchema>;

export default function CreateWorkspacePage() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [repoValidating, setRepoValidating] = useState(false);
  const [_repoValid, setRepoValid] = useState(false);
  const [branches, setBranches] = useState<string[]>([]);
  const navigate = useNavigate();
  const { user } = useAuth();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<WorkspaceFormData>({
    resolver: zodResolver(workspaceSchema),
    defaultValues: {
      git_provider: 'github',
      github_main_branch: 'main',
    },
  });

  const provider = watch('git_provider') as GitProvider;
  const repository = watch('github_repository');
  const gitlabUrl = watch('gitlab_url');

  // Check if the selected provider is configured, redirect to setup if not
  useEffect(() => {
    if (!user) return;
    if (provider === 'github' && !user.github_username) {
      navigate('/github-setup', {
        state: { from: '/workspaces/new', message: 'Please connect your GitHub account to create a workspace.', provider: 'github' }
      });
    }
    if (provider === 'gitlab' && !user.gitlab_username) {
      navigate('/github-setup', {
        state: { from: '/workspaces/new', message: 'Please connect your GitLab account to create a workspace.', provider: 'gitlab' }
      });
    }
  }, [user, provider, navigate]);

  const handleValidateRepository = async () => {
    if (!repository) {
      setError('Please enter a repository');
      return;
    }

    // Normalize the repository input based on provider
    const normalizedRepo = normalizeRepository(repository, provider, gitlabUrl);
    if (!normalizedRepo) {
      const example = provider === 'gitlab'
        ? 'e.g., namespace/project or https://gitlab.com/namespace/project'
        : 'e.g., owner/repo or https://github.com/owner/repo';
      setError(`Please enter a valid ${provider === 'gitlab' ? 'GitLab' : 'GitHub'} repository (${example})`);
      return;
    }

    // Update the form with normalized value
    setValue('github_repository', normalizedRepo);

    try {
      setRepoValidating(true);
      setError('');
      setRepoValid(false);

      // Validate repository via provider-aware API
      const validation = await validateRepository(normalizedRepo, provider, gitlabUrl);

      if (!validation.valid) {
        setError(validation.error || 'Repository validation failed');
        return;
      }

      // Get branches
      const branchData = await listBranches(normalizedRepo, true, provider, gitlabUrl);
      if (branchData.error) {
        setError(branchData.error);
        return;
      }

      setBranches(branchData.branches);
      setRepoValid(true);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate repository');
    } finally {
      setRepoValidating(false);
    }
  };

  const onSubmit = async (data: WorkspaceFormData) => {
    try {
      setLoading(true);
      setError('');

      const normalizedRepo = normalizeRepository(data.github_repository, provider, data.gitlab_url);
      if (!normalizedRepo) {
        setError('Invalid repository format');
        return;
      }

      await createWorkspace({
        ...data,
        github_repository: normalizedRepo,
        git_provider: data.git_provider as 'github' | 'gitlab',
        gitlab_url: data.git_provider === 'gitlab' ? data.gitlab_url : undefined,
      });

      navigate('/workspaces');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create workspace');
    } finally {
      setLoading(false);
    }
  };

  const providerLabel = provider === 'gitlab' ? 'GitLab' : 'GitHub';
  const repoPlaceholder = provider === 'gitlab'
    ? 'namespace/project or https://gitlab.com/namespace/project'
    : 'owner/repo or https://github.com/owner/repo';

  return (
    <div className="min-h-screen bg-background">
      <div className="fixed inset-0 bg-gradient-to-br from-primary/[0.02] via-transparent to-accent/[0.02] pointer-events-none" />

      <div className="relative container mx-auto px-6 py-12 max-w-2xl">
        <div className="mb-8">
          <Button
            onClick={() => navigate('/workspaces')}
            variant="ghost"
            className="mb-4 -ml-2 text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Workspaces
          </Button>
          <h1 className="text-4xl font-bold text-foreground tracking-tight">Create Workspace</h1>
          <p className="text-muted-foreground mt-2 text-md font-light">Set up a new development workspace</p>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-center">
            <div className={`flex items-center transition-colors ${step >= 1 ? 'text-primary' : 'text-muted-foreground'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-medium transition-colors ${step >= 1 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                1
              </div>
              <span className="ml-2 font-medium">Basic Info</span>
            </div>
            <div className={`w-16 h-1 mx-4 rounded transition-colors ${step >= 2 ? 'bg-primary' : 'bg-muted'}`}></div>
            <div className={`flex items-center transition-colors ${step >= 2 ? 'text-primary' : 'text-muted-foreground'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-medium transition-colors ${step >= 2 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                2
              </div>
              <span className="ml-2 font-medium">Branch Setup</span>
            </div>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6 rounded-xl">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="bg-card rounded-xl border border-border/50 shadow-lg p-6">
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <Label className="mb-2 block">
                  Workspace Name *
                </Label>
                <Input
                  {...register('name')}
                  type="text"
                  placeholder="My Awesome Project"
                />
                {errors.name && (
                  <p className="text-destructive text-sm mt-1">{errors.name.message}</p>
                )}
              </div>

              <div>
                <Label className="mb-2 block">
                  Description (optional)
                </Label>
                <Textarea
                  {...register('description')}
                  rows={3}
                  placeholder="What is this workspace for?"
                />
              </div>

              {/* Git Provider Selection */}
              <div>
                <Label className="mb-2 block">
                  Git Provider *
                </Label>
                <Select
                  value={provider}
                  onValueChange={(value: string) => {
                    setValue('git_provider', value as 'github' | 'gitlab');
                    // Reset repo validation when provider changes
                    setRepoValid(false);
                    setBranches([]);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="github">GitHub</SelectItem>
                    <SelectItem value="gitlab">GitLab</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* GitLab URL (only shown when GitLab is selected) */}
              {provider === 'gitlab' && (
                <div>
                  <Label className="mb-2 block">
                    GitLab URL (optional)
                  </Label>
                  <Input
                    {...register('gitlab_url')}
                    type="url"
                    placeholder="https://gitlab.com"
                  />
                  <p className="text-muted-foreground text-sm mt-1">
                    Leave blank for gitlab.com, or enter your self-hosted GitLab URL
                  </p>
                </div>
              )}

              <div>
                <Label className="mb-2 block">
                  {providerLabel} Repository *
                </Label>
                <div className="flex gap-2">
                  <Input
                    {...register('github_repository')}
                    type="text"
                    placeholder={repoPlaceholder}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    onClick={handleValidateRepository}
                    disabled={repoValidating || !repository}
                    className="px-6"
                  >
                    {repoValidating ? 'Validating...' : 'Validate'}
                  </Button>
                </div>
                {errors.github_repository && (
                  <p className="text-destructive text-sm mt-1">{errors.github_repository.message}</p>
                )}
                <p className="text-muted-foreground text-sm mt-1">
                  {provider === 'gitlab'
                    ? 'Accepts: namespace/project (e.g., mygroup/myproject) or full GitLab URL'
                    : 'Accepts: owner/repo (e.g., facebook/react) or full GitHub URL'
                  }
                </p>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <Alert variant="success" className="mb-4 rounded-xl border-success/20 bg-success/5">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <AlertDescription className="font-medium text-success">
                  Repository validated successfully
                </AlertDescription>
              </Alert>

              <div>
                <Label className="mb-2 block">
                  Development Branch *
                </Label>
                <Select
                  value={watch('github_dev_branch')}
                  onValueChange={(value: string) => setValue('github_dev_branch', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a branch" />
                  </SelectTrigger>
                  <SelectContent>
                    {branches.map((branch) => (
                      <SelectItem key={branch} value={branch}>
                        {branch}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.github_dev_branch && (
                  <p className="text-destructive text-sm mt-1">{errors.github_dev_branch.message}</p>
                )}
                <p className="text-muted-foreground text-sm mt-1">
                  The branch where active development happens
                </p>
              </div>

              <div>
                <Label className="mb-2 block">
                  Main/Production Branch *
                </Label>
                <Select
                  value={watch('github_main_branch')}
                  onValueChange={(value: string) => setValue('github_main_branch', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a branch" />
                  </SelectTrigger>
                  <SelectContent>
                    {branches.map((branch) => (
                      <SelectItem key={branch} value={branch}>
                        {branch}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.github_main_branch && (
                  <p className="text-destructive text-sm mt-1">{errors.github_main_branch.message}</p>
                )}
                <p className="text-muted-foreground text-sm mt-1">
                  The stable production branch (usually 'main' or 'master')
                </p>
              </div>

              <div className="flex gap-4 pt-4">
                <Button
                  type="button"
                  onClick={() => setStep(1)}
                  variant="outline"
                  className="flex-1"
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  disabled={loading}
                  className="flex-1"
                >
                  {loading ? 'Creating...' : 'Create Workspace'}
                </Button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
