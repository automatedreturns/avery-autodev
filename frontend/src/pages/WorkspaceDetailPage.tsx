/* eslint-disable @typescript-eslint/no-unused-vars */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getWorkspace,
  setupWorkflow,
  type WorkflowSetupResponse,
} from "../api/workspaces";
import type { WorkspaceDetail } from "../types/workspace";
import WorkspaceTaskList from "../components/WorkspaceTaskList";
import AddTaskModal from "../components/AddTaskModal";
import FeatureRequestModal from "../components/FeatureRequestModal";
import ShareWorkspaceModal from "../components/ShareWorkspaceModal";
import CIRunList from "../components/CIRunList";
import TestPolicySettings from "../components/TestPolicySettings";
import TestGenerationModal from "../components/TestGenerationModal";
import TestGenerationTasksList from "../components/TestGenerationTasksList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertCircle,
  ArrowLeft,
  Users as UsersIcon,
  ExternalLink,
  Clock,
  BarChart3,
  CheckSquare,
  Github,
  GitBranch,
  Star,
  User,
  FileCode,
  Activity,
  Shield,
  Wand2,
  Play,
  CheckCircle,
  Copy,
  X,
  TestTube2,
} from "lucide-react";

export default function WorkspaceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<
    "overview" | "tasks" | "members" | "ci" | "tests"
  >("tasks");
  const [testsSubTab, setTestsSubTab] = useState<"policy" | "generation">("policy");
  const [showAddTaskModal, setShowAddTaskModal] = useState(false);
  const [showFeatureRequestModal, setShowFeatureRequestModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [showTestGenerationModal, setShowTestGenerationModal] = useState(false);
  const [taskRefreshTrigger, setTaskRefreshTrigger] = useState(0);
  const [workflowSetupLoading, setWorkflowSetupLoading] = useState(false);
  const [workflowSetupResult, setWorkflowSetupResult] =
    useState<WorkflowSetupResponse | null>(null);
  const [showWorkflowInstructions, setShowWorkflowInstructions] =
    useState(false);

  useEffect(() => {
    if (id) {
      loadWorkspace(parseInt(id));
    }
  }, [id]);

  const loadWorkspace = async (workspaceId: number) => {
    try {
      setLoading(true);
      setError("");
      const data = await getWorkspace(workspaceId);
      setWorkspace(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workspace");
    } finally {
      setLoading(false);
    }
  };

  const handleTaskAdded = () => {
    setTaskRefreshTrigger((prev) => prev + 1);
  };

  const handleMemberAdded = async () => {
    if (id) {
      await loadWorkspace(parseInt(id));
    }
  };

  const handleWorkflowSetup = async () => {
    if (!workspace) return;

    setWorkflowSetupLoading(true);
    setError("");

    try {
      const result = await setupWorkflow(workspace.id, true); // Always force update
      setWorkflowSetupResult(result);
      setShowWorkflowInstructions(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to setup workflow");
    } finally {
      setWorkflowSetupLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading workspace...</p>
        </div>
      </div>
    );
  }

  if (error || !workspace) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-8 max-w-4xl">
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {error || "Workspace not found"}
            </AlertDescription>
          </Alert>
          <Button variant="outline" onClick={() => navigate("/workspaces")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Workspaces
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background pt-4">
      <div className="container mx-auto px-4 py-4 max-w-7xl">
        {/* Compact Header - Single Row */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-5">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/workspaces")}
              className="text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back to Workspaces
            </Button>
            {workspace &&
              (workspace.role === "owner" || workspace.role === "admin") && (
                <Button
                  variant="gradient"
                  size="sm"
                  onClick={() => setShowShareModal(true)}
                >
                  <UsersIcon className="w-4 h-4 mr-2" />
                  Share
                </Button>
              )}
          </div>

          {/* Compact Header with Tabs */}
          <Card>
            <CardContent className="p-3 sm:p-4">
              {/* Mobile: Stacked layout, Desktop: Side-by-side */}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 mb-4">
                {/* Left: Title and Repo */}
                <div className="flex-1 min-w-0 overflow-hidden">
                  {/* Title row */}
                  <div className="flex items-start sm:items-center gap-2 sm:gap-3 mb-2 flex-wrap">
                    <h1 className="text-xl sm:text-2xl font-bold text-foreground truncate max-w-full sm:max-w-none">
                      {workspace.name}
                    </h1>
                    {/* Status Badges - wrap on mobile */}
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 sm:py-1 rounded-md text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                        {workspace.role}
                      </span>
                      {workspace.is_default && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 sm:py-1 rounded-md text-xs font-medium bg-success/10 text-success border border-success/20">
                          <Star className="w-3 h-3" />
                          <span className="hidden xs:inline">Default</span>
                        </span>
                      )}
                      <span
                        className={`inline-flex items-center px-2 py-0.5 sm:py-1 rounded-md text-xs font-medium ${
                          workspace.is_active
                            ? "bg-success/10 text-success border border-success/20"
                            : "bg-muted text-muted-foreground border border-border"
                        }`}
                      >
                        {workspace.is_active ? "●" : "○"}
                        <span className="hidden xs:inline ml-1">
                          {workspace.is_active ? "Active" : "Inactive"}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Repository link */}
                  <div className="flex items-center gap-2 sm:gap-4 text-sm overflow-hidden">
                    <a
                      href={workspace.git_provider === 'gitlab' ? `${workspace.gitlab_url || 'https://gitlab.com'}/${workspace.github_repository}` : `https://github.com/${workspace.github_repository}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors min-w-0"
                    >
                      <Github className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="font-mono text-xs truncate">
                        {workspace.github_repository}
                      </span>
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    </a>

                    {workspace.description && (
                      <>
                        <span className="text-muted-foreground hidden sm:inline">
                          •
                        </span>
                        <p className="text-muted-foreground text-xs truncate hidden sm:block">
                          {workspace.description}
                        </p>
                      </>
                    )}
                  </div>
                </div>

                {/* Right: Action Buttons - icons only on mobile */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      navigate(`/workspaces/${workspace.id}/polling-status`)
                    }
                    className="min-h-[44px] px-2 sm:px-3"
                  >
                    <Clock className="w-4 h-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">Polling Status</span>
                  </Button>
                </div>
              </div>

              {/* Integrated Tabs - horizontal scroll on mobile */}
              <div className="overflow-x-auto -mx-3 sm:-mx-4 px-3 sm:px-4 border-t pt-3">
                <div className="flex gap-1 min-w-max sm:min-w-0">
                  <Button
                    variant={activeTab === "overview" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("overview")}
                    className="flex-1 min-w-[80px] sm:min-w-0 min-h-[44px] px-2 sm:px-3"
                  >
                    <BarChart3 className="w-4 h-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">Overview</span>
                  </Button>
                  <Button
                    variant={activeTab === "tasks" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("tasks")}
                    className="flex-1 min-w-[80px] sm:min-w-0 min-h-[44px] px-2 sm:px-3"
                  >
                    <CheckSquare className="w-4 h-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">Tasks</span>
                  </Button>
                  <Button
                    variant={activeTab === "ci" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("ci")}
                    className="flex-1 min-w-[80px] sm:min-w-0 min-h-[44px] px-2 sm:px-3"
                  >
                    <Activity className="w-4 h-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">CI Runs</span>
                  </Button>
                  <Button
                    variant={activeTab === "tests" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("tests")}
                    className="flex-1 min-w-[80px] sm:min-w-0 min-h-[44px] px-2 sm:px-3"
                  >
                    <TestTube2 className="w-4 h-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">Tests</span>
                  </Button>
                  <Button
                    variant={activeTab === "members" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("members")}
                    className="flex-1 min-w-[80px] sm:min-w-0 min-h-[44px] px-2 sm:px-3"
                  >
                    <UsersIcon className="w-4 h-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">Members</span>
                    <span className="ml-1 sm:ml-1.5 px-1.5 py-0.5 bg-background rounded-full text-xs">
                      {workspace.member_count}
                    </span>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === "overview" && (
            <Card>
              <CardContent className="p-8">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                          <Github className="w-5 h-5 text-primary" />
                        </div>
                        <CardTitle className="text-sm uppercase tracking-wide">
                          Repository
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <a
                        href={workspace.git_provider === 'gitlab' ? `${workspace.gitlab_url || 'https://gitlab.com'}/${workspace.github_repository}` : `https://github.com/${workspace.github_repository}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:text-primary/90 font-mono text-sm flex items-center gap-2 group"
                      >
                        <span>{workspace.github_repository}</span>
                        <ExternalLink className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                      </a>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-success/10 rounded-lg">
                          <GitBranch className="w-5 h-5 text-success" />
                        </div>
                        <CardTitle className="text-sm uppercase tracking-wide">
                          Development Branch
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="font-mono text-sm bg-muted px-3 py-2 rounded-lg">
                        {workspace.github_dev_branch}
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                          <GitBranch className="w-5 h-5 text-primary" />
                        </div>
                        <CardTitle className="text-sm uppercase tracking-wide">
                          Main Branch
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="font-mono text-sm bg-muted px-3 py-2 rounded-lg">
                        {workspace.github_main_branch}
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-accent rounded-lg">
                          <User className="w-5 h-5 text-accent-foreground" />
                        </div>
                        <CardTitle className="text-sm uppercase tracking-wide">
                          Owner
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="font-medium text-sm text-foreground">
                        {workspace.owner.username}
                      </p>
                      <p className="text-muted-foreground text-xs mt-1">
                        {workspace.owner.email}
                      </p>
                    </CardContent>
                  </Card>

                  <Card className="md:col-span-2">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-blue-500/10 rounded-lg">
                            <Play className="w-5 h-5 text-blue-500" />
                          </div>
                          <div>
                            <CardTitle className="text-sm uppercase tracking-wide">
                              CI Integration
                            </CardTitle>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              Automated testing and coverage tracking
                            </p>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={handleWorkflowSetup}
                          disabled={workflowSetupLoading}
                        >
                          {workflowSetupLoading ? (
                            <>
                              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                              Setting up...
                            </>
                          ) : (
                            <>
                              <FileCode className="w-4 h-4 mr-2" />
                              Setup Workflow
                            </>
                          )}
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-start gap-3 text-sm">
                        <div className="flex-1">
                          <p className="text-muted-foreground">
                            The Avery CI workflow runs automatically on pull
                            requests and pushes to track test coverage and
                            enforce policies.
                          </p>
                          <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                            <p>• Runs tests with coverage on every PR</p>
                            <p>• Sends coverage data to Avery for analysis</p>
                            <p>• Enforces test quality policies</p>
                            <p>• Auto-generates tests for uncovered code</p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "tasks" && (
            <Card>
              <CardContent className="p-3 sm:p-6">
                <WorkspaceTaskList
                  workspaceId={workspace.id}
                  repository={workspace.github_repository}
                  defaultBranch={workspace.github_dev_branch}
                  onAddTask={() => setShowAddTaskModal(true)}
                  onRequestFeature={() => setShowFeatureRequestModal(true)}
                  refreshTrigger={taskRefreshTrigger}
                />
              </CardContent>
            </Card>
          )}

          {activeTab === "ci" && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Activity className="w-6 h-6 text-primary" />
                    <CardTitle className="text-2xl">CI Runs</CardTitle>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    GitHub Actions CI/CD runs for this workspace
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                <CIRunList workspaceId={workspace.id} limit={20} />
              </CardContent>
            </Card>
          )}

          {activeTab === "tests" && (
            <div className="space-y-6">
              {/* Sub-tabs for Tests section */}
              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  <Button
                    variant={testsSubTab === "policy" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setTestsSubTab("policy")}
                  >
                    <Shield className="w-4 h-4 mr-2" />
                    Test Policy
                  </Button>
                  <Button
                    variant={testsSubTab === "generation" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setTestsSubTab("generation")}
                  >
                    <Wand2 className="w-4 h-4 mr-2" />
                    Test Generation
                  </Button>
                </div>
                <Button onClick={() => setShowTestGenerationModal(true)}>
                  <Wand2 className="w-4 h-4 mr-2" />
                  Generate Tests
                </Button>
              </div>

              {/* Test Policy Sub-tab */}
              {testsSubTab === "policy" && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <Shield className="w-6 h-6 text-primary" />
                      <CardTitle className="text-2xl">Test Policy</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <TestPolicySettings workspaceId={workspace.id} />
                  </CardContent>
                </Card>
              )}

              {/* Test Generation Sub-tab */}
              {testsSubTab === "generation" && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <Wand2 className="w-6 h-6 text-primary" />
                      <CardTitle className="text-2xl">Test Generation Tasks</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <TestGenerationTasksList workspaceId={workspace.id} limit={20} />
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {activeTab === "members" && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <UsersIcon className="w-6 h-6 text-primary" />
                  <CardTitle className="text-2xl">Team Members</CardTitle>
                  <span className="text-lg font-normal text-muted-foreground">
                    ({workspace.member_count})
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {workspace.members.map((member) => (
                    <Card
                      key={member.id}
                      className="hover:shadow-md transition-all duration-200 group"
                    >
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 bg-gradient-to-br from-primary/60 to-primary rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-md">
                              {member.username.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-semibold text-foreground group-hover:text-primary transition-colors">
                                {member.username}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {member.email}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="px-4 py-2 rounded-lg text-sm font-semibold bg-muted text-foreground border border-border">
                              {member.role}
                            </span>
                            {member.user_id === workspace.owner_id && (
                              <span className="px-4 py-2 rounded-lg text-sm font-semibold bg-primary/10 text-primary border border-primary/20">
                                Owner
                              </span>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Add Task Modal */}
      {showAddTaskModal && (
        <AddTaskModal
          workspaceId={workspace.id}
          onClose={() => setShowAddTaskModal(false)}
          onTaskAdded={handleTaskAdded}
        />
      )}

      {/* Feature Request Modal */}
      {showFeatureRequestModal && (
        <FeatureRequestModal
          workspaceId={workspace.id}
          onClose={() => setShowFeatureRequestModal(false)}
          onFeatureRequestCreated={handleTaskAdded}
        />
      )}

      {/* Share Workspace Modal */}
      {showShareModal && (
        <ShareWorkspaceModal
          workspaceId={workspace.id}
          workspaceName={workspace.name}
          onClose={() => setShowShareModal(false)}
          onSuccess={handleMemberAdded}
        />
      )}

      {/* Test Generation Modal */}
      {showTestGenerationModal && (
        <TestGenerationModal
          workspaceId={workspace.id}
          onClose={() => setShowTestGenerationModal(false)}
          onSuccess={(jobId) => {
            console.log("Test generation job created:", jobId);
            setShowTestGenerationModal(false);
          }}
        />
      )}

      {/* Workflow Setup Instructions Modal */}
      {showWorkflowInstructions && workflowSetupResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-success/10 rounded-lg">
                  <CheckCircle className="w-6 h-6 text-success" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold">
                    Workflow Setup Complete!
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {workflowSetupResult.workflow.message}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowWorkflowInstructions(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Workflow File Info */}
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <FileCode className="w-5 h-5 text-primary mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium">Workflow File</p>
                    <p className="text-sm text-muted-foreground font-mono mt-1">
                      {workflowSetupResult.instructions.workflow_path}
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      The workflow file has been added to your repository and
                      will run automatically on pull requests.
                    </p>
                  </div>
                </div>
              </div>

              {/* Next Steps */}
              <div>
                <h3 className="font-semibold mb-3">Next Steps</h3>
                <div className="space-y-3">
                  {workflowSetupResult.instructions.instructions.map(
                    (instruction, index) => (
                      <div key={index} className="flex items-start gap-3">
                        <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <span className="text-xs font-medium text-primary">
                            {index + 1}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground flex-1">
                          {instruction}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              </div>

              {/* Secrets to Add */}
              {workflowSetupResult.instructions.secrets_to_add.map((secret) => (
                <div key={secret.name} className="bg-muted/50 rounded-lg p-4">
                  <div className="space-y-3">
                    <div>
                      <p className="font-medium text-sm">Secret Name</p>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 bg-background px-3 py-2 rounded text-sm font-mono">
                          {secret.name}
                        </code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(secret.name);
                          }}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    <div>
                      <p className="font-medium text-sm">Secret Value</p>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 bg-background px-3 py-2 rounded text-sm font-mono break-all">
                          {secret.value}
                        </code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(secret.value);
                          }}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {secret.description}
                    </p>
                  </div>
                </div>
              ))}

              {/* Repository Settings Link */}
              <div className="bg-blue-500/10 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <Github className="w-5 h-5 text-blue-500 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium text-sm">Add Secret to GitHub</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Go to your repository settings → Secrets and variables →
                      Actions → New repository secret
                    </p>
                    <a
                      href={workspace.git_provider === 'gitlab' ? `${workspace.gitlab_url || 'https://gitlab.com'}/${workspace.github_repository}/-/settings/ci_cd` : `https://github.com/${workspace.github_repository}/settings/secrets/actions`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm text-blue-500 hover:underline mt-2"
                    >
                      Open Repository Settings
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-6 border-t bg-muted/30">
              <Button onClick={() => setShowWorkflowInstructions(false)}>
                Done
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
