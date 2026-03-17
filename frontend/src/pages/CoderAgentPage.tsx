import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  vscDarkPlus,
  vs,
} from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  getWorkspaceTask,
  createPullRequestFromTask,
} from "../api/workspace_tasks";
import {
  listChatMessages,
  sendChatMessage,
  clearChatHistory,
  cancelAgentExecution,
  compactChatSession,
  getTaskDiff,
  type DiffData,
} from "../api/agent_chat";
import type { WorkspaceTask } from "../types/workspace_task";
import type { AgentMessage, FileAttachment } from "../types/agent_message";
import AlertModal from "../components/AlertModal";
import FileBrowser from "../components/FileBrowser";
import FileViewer from "../components/FileViewer";
import DiffViewer from "../components/DiffViewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ArrowLeft,
  Send,
  Paperclip,
  X,
  AlertCircle,
  GitBranch,
  Loader2,
  CheckCircle,
  FileText,
  Trash2,
  GitPullRequest,
  Clock,
  User,
  Bot,
  ChevronDown,
  Info,
  Copy,
  Check,
  Download,
  StopCircle,
  File,
  FileEdit,
  PanelLeftClose,
  PanelLeft,
  MoreVertical,
  RefreshCw,
} from "lucide-react";

// Code block component with syntax highlighting
function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    // Check if dark mode is enabled
    const checkDarkMode = () => {
      setIsDark(document.documentElement.classList.contains("dark"));
    };
    checkDarkMode();

    // Watch for theme changes
    const observer = new MutationObserver(checkDarkMode);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-3">
      <div className="absolute right-2 top-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleCopy}
          className="h-8 px-2 text-xs"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 mr-1" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="w-3 h-3 mr-1" />
              Copy
            </>
          )}
        </Button>
      </div>
      <div className="absolute left-3 top-2 text-xs text-muted-foreground font-mono opacity-70">
        {language}
      </div>
      <SyntaxHighlighter
        language={language}
        style={isDark ? vscDarkPlus : vs}
        customStyle={{
          margin: 0,
          borderRadius: "0.75rem",
          fontSize: "0.875rem",
          padding: "2.5rem 1rem 1rem 1rem",
        }}
        wrapLongLines={true}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

// Helper to group consecutive system messages
function groupMessages(
  messages: AgentMessage[],
): Array<AgentMessage | { type: "group"; messages: AgentMessage[] }> {
  const grouped: Array<
    AgentMessage | { type: "group"; messages: AgentMessage[] }
  > = [];
  let currentGroup: AgentMessage[] = [];

  for (const msg of messages) {
    // Check if this is a progress message (system message with emoji indicators)
    const isProgressMsg =
      msg.role === "system" && /^[🤖📖✍️💾☁️✅🔄❌📁]/.test(msg.content);

    if (isProgressMsg) {
      currentGroup.push(msg);
    } else {
      // Flush current group if exists
      if (currentGroup.length > 0) {
        grouped.push({ type: "group", messages: currentGroup });
        currentGroup = [];
      }
      grouped.push(msg);
    }
  }

  // Flush remaining group
  if (currentGroup.length > 0) {
    grouped.push({ type: "group", messages: currentGroup });
  }

  return grouped;
}

// Helper to format markdown-style text
function FileAttachmentsDisplay({
  attachments,
}: {
  attachments: FileAttachment[];
}) {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const getFileIcon = (contentType: string) => {
    if (contentType.startsWith("image/")) {
      return <FileText className="w-5 h-5" />;
    }
    return <FileText className="w-5 h-5" />;
  };

  return (
    <div className="mt-3 space-y-2">
      {attachments.map((attachment, index) => (
        <div
          key={index}
          className="flex items-center gap-3 px-4 py-3 bg-muted/50 border border-border rounded-xl"
        >
          <div className="flex-shrink-0 text-muted-foreground">
            {getFileIcon(attachment.content_type)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">
              {attachment.filename}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatFileSize(attachment.file_size)}
            </p>
          </div>
          <div className="flex-shrink-0">
            <Paperclip className="w-5 h-5 text-muted-foreground" />
          </div>
        </div>
      ))}
    </div>
  );
}

function FormattedMessage({
  content,
  className = "",
}: {
  content: string;
  className?: string;
}) {
  // Parse code blocks with language specification (```language\ncode\n```)
  const parseCodeBlocks = (text: string) => {
    const parts: Array<{
      type: "text" | "code";
      content: string;
      language?: string;
    }> = [];
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(text)) !== null) {
      // Add text before code block
      if (match.index > lastIndex) {
        parts.push({
          type: "text",
          content: text.slice(lastIndex, match.index),
        });
      }

      // Add code block
      parts.push({
        type: "code",
        content: match[2].trim(),
        language: match[1] || "plaintext",
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push({
        type: "text",
        content: text.slice(lastIndex),
      });
    }

    return parts.length > 0
      ? parts
      : [{ type: "text" as const, content: text }];
  };

  const renderTextContent = (text: string) => {
    return text.split("\n").map((line: string, idx: number) => {
      // Handle bold text (**text**) and inline code (`code`)
      const formattedLine = line
        .split(/(\*\*[^*]+\*\*|`[^`]+`)/)
        .map((part: string, i: number) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={i} className="font-bold">
                {part.slice(2, -2)}
              </strong>
            );
          }
          if (part.startsWith("`") && part.endsWith("`")) {
            return (
              <code
                key={i}
                className="px-1.5 py-0.5 bg-muted rounded text-sm font-mono"
              >
                {part.slice(1, -1)}
              </code>
            );
          }
          return part;
        });

      // Handle numbered list items (1. 2. 3.)
      const numberedMatch = line.trim().match(/^(\d+)\.\s+(.+)$/);
      if (numberedMatch) {
        const [, number, text] = numberedMatch;
        // Format the text part (without the number)
        const textWithFormatting = text
          .split(/(\*\*[^*]+\*\*|`[^`]+`)/)
          .map((part: string, i: number) => {
            if (part.startsWith("**") && part.endsWith("**")) {
              return (
                <strong key={i} className="font-bold">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            if (part.startsWith("`") && part.endsWith("`")) {
              return (
                <code
                  key={i}
                  className="px-1.5 py-0.5 bg-muted rounded text-sm font-mono"
                >
                  {part.slice(1, -1)}
                </code>
              );
            }
            return part;
          });

        return (
          <div key={idx} className="flex gap-2 ml-4 my-1">
            <span className="flex-shrink-0 font-semibold">{number}.</span>
            <span className="flex-1">{textWithFormatting}</span>
          </div>
        );
      }

      // Handle bullet list items (-)
      if (line.trim().startsWith("-")) {
        return (
          <div key={idx} className="flex gap-2 ml-4 my-1">
            <span className="flex-shrink-0">•</span>
            <span className="flex-1">{formattedLine}</span>
          </div>
        );
      }

      // Handle headings (## text)
      if (line.trim().startsWith("##")) {
        const headingText = line.trim().slice(2).trim();
        return (
          <h3 key={idx} className="text-base font-bold mt-3 mb-2">
            {headingText}
          </h3>
        );
      }

      // Regular line
      if (line.trim()) {
        return (
          <p key={idx} className="my-1">
            {formattedLine}
          </p>
        );
      }

      // Empty line
      return <div key={idx} className="h-2" />;
    });
  };

  const parts = parseCodeBlocks(content);

  return (
    <div className={`leading-relaxed ${className}`}>
      {parts.map((part, idx) => {
        if (part.type === "code") {
          return (
            <CodeBlock
              key={idx}
              code={part.content}
              language={part.language || "plaintext"}
            />
          );
        }
        return (
          <div key={idx} className="whitespace-pre-wrap">
            {renderTextContent(part.content)}
          </div>
        );
      })}
    </div>
  );
}

// Component for rendering interactive input requests
function InputRequestCard({
  message,
  onSubmit,
  allMessages,
}: {
  message: AgentMessage;
  onSubmit: (response: string) => void;
  allMessages: AgentMessage[];
}) {
  // Check if user already responded (next message after this input request)
  const messageIndex = allMessages.findIndex((m) => m.id === message.id);
  const nextMessage = messageIndex >= 0 ? allMessages[messageIndex + 1] : null;
  const existingResponse =
    nextMessage?.role === "user" ? nextMessage.content : null;

  const [textInput, setTextInput] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(!!existingResponse);
  const [selectedAnswer, setSelectedAnswer] = useState<string>(
    existingResponse || "",
  );

  const handleSubmit = (response: string) => {
    if (isSubmitted) return;
    setIsSubmitted(true);
    setSelectedAnswer(response);
    onSubmit(response);
  };

  try {
    const data = JSON.parse(message.content);
    if (data.type !== "input_request") return null;

    const { message: prompt, input_type, options = [] } = data;

    return (
      <div className="flex gap-4 animate-slide-up">
        {/* Avatar */}
        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-md">
          <AlertCircle className="w-6 h-6 text-primary-foreground" />
        </div>

        {/* Content */}
        <div className="flex-1 max-w-3xl">
          <Card className="border-2 border-primary/30 shadow-lg overflow-hidden">
            {/* Header */}
            <div className="px-5 py-4 bg-primary/10 border-b border-primary/20">
              <div className="flex items-center gap-2 mb-2">
                <Info className="w-5 h-5 text-primary" />
                <span className="font-semibold text-foreground">
                  Agent needs your input
                </span>
              </div>
              <FormattedMessage
                content={prompt}
                className="text-sm text-muted-foreground"
              />
            </div>

            {/* Input Area */}
            <CardContent className="p-5">
              {isSubmitted ? (
                /* Show selected answer after submission */
                <div className="bg-success/10 border-2 border-success/20 rounded-xl px-5 py-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-shrink-0 w-8 h-8 bg-success rounded-full flex items-center justify-center">
                      <CheckCircle className="w-5 h-5 text-success-foreground" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-foreground">
                        Your Response
                      </p>
                      <p className="text-base font-medium text-success mt-1">
                        {selectedAnswer}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 text-success">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      <span className="text-xs font-medium">Processing...</span>
                    </div>
                  </div>
                </div>
              ) : (
                /* Show input options before submission */
                <>
                  {input_type === "confirm" && (
                    <div className="flex gap-3">
                      <Button
                        onClick={() => handleSubmit("Yes")}
                        className="flex-1"
                        variant="default"
                      >
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Yes
                      </Button>
                      <Button
                        onClick={() => handleSubmit("No")}
                        className="flex-1"
                        variant="destructive"
                      >
                        <X className="w-4 h-4 mr-2" />
                        No
                      </Button>
                    </div>
                  )}

                  {input_type === "choice" && options.length > 0 && (
                    <div className="space-y-2">
                      {options.map((option: string, idx: number) => (
                        <Button
                          key={idx}
                          onClick={() => handleSubmit(option)}
                          className="w-full justify-start"
                          variant="outline"
                        >
                          <span className="flex-shrink-0 w-6 h-6 bg-primary/20 rounded-full flex items-center justify-center text-xs font-bold mr-3">
                            {idx + 1}
                          </span>
                          <span className="flex-1 text-left">{option}</span>
                        </Button>
                      ))}
                    </div>
                  )}

                  {input_type === "text" && (
                    <div className="space-y-3">
                      <textarea
                        value={textInput}
                        onChange={(e) => setTextInput(e.target.value)}
                        placeholder="Type your response..."
                        rows={3}
                        className="w-full px-4 py-3 bg-background border border-border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary text-foreground placeholder-muted-foreground"
                      />
                      <Button
                        variant="gradient"
                        onClick={() => {
                          if (textInput.trim()) {
                            handleSubmit(textInput.trim());
                            setTextInput("");
                          }
                        }}
                        disabled={!textInput.trim()}
                        className="w-full"
                      >
                        <Send className="w-4 h-4 mr-2" />
                        Submit Response
                      </Button>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  } catch (e) {
    // If parsing fails, don't render as input request
    return null;
  }
}

// Component for rendering grouped progress messages
function ProgressMessageGroup({
  messages,
  agentStatus,
}: {
  messages: AgentMessage[];
  agentStatus?: "idle" | "running" | "completed" | "failed";
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Get summary info
  const count = messages.length;
  const hasError = messages.some((m) => m.content.includes("❌"));
  // Use agent status if available, otherwise keep showing as processing
  const isComplete =
    agentStatus === "completed" ||
    agentStatus === "failed" ||
    agentStatus === "idle";

  return (
    <div className="flex gap-4 animate-slide-up">
      {/* Avatar */}
      <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-accent flex items-center justify-center shadow-md">
        {hasError ? (
          <AlertCircle className="w-5 h-5 text-accent-foreground" />
        ) : isComplete ? (
          <CheckCircle className="w-5 h-5 text-accent-foreground" />
        ) : (
          <Loader2 className="w-5 h-5 text-accent-foreground animate-spin" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 max-w-3xl">
        <Card className="border-accent/20 shadow-md overflow-hidden">
          {/* Header - Always visible */}
          <Button
            variant="ghost"
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-accent/10 h-auto"
          >
            <div className="flex items-center gap-3">
              {hasError ? (
                <AlertCircle className="w-5 h-5 text-destructive" />
              ) : isComplete ? (
                <CheckCircle className="w-5 h-5 text-success" />
              ) : (
                <div className="flex gap-1">
                  <div
                    className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  ></div>
                  <div
                    className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  ></div>
                  <div
                    className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  ></div>
                </div>
              )}
              <div className="text-left">
                <p className="text-sm font-semibold text-foreground">
                  {isComplete
                    ? "Processing Complete"
                    : hasError
                      ? "Processing with Errors"
                      : "Agent Processing"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {count} {count === 1 ? "step" : "steps"} • Click to{" "}
                  {isExpanded ? "collapse" : "expand"}
                </p>
              </div>
            </div>
            <ChevronDown
              className={`w-5 h-5 text-accent transition-transform ${
                isExpanded ? "rotate-180" : ""
              }`}
            />
          </Button>

          {/* Expanded Details */}
          {isExpanded && (
            <CardContent className="px-4 pb-3 space-y-1 border-t border-accent/20 bg-muted/30">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className="flex items-start gap-2 py-1.5 text-xs"
                >
                  <span className="text-accent mt-0.5">•</span>
                  <p className="flex-1 text-foreground leading-relaxed">
                    {msg.content}
                  </p>
                  <span className="text-muted-foreground text-[10px] whitespace-nowrap">
                    {new Date(`${msg.created_at}Z`).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </span>
                </div>
              ))}
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function CoderAgentPage() {
  const { workspaceId, taskId } = useParams<{
    workspaceId: string;
    taskId: string;
  }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<WorkspaceTask | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [agentProcessing, setAgentProcessing] = useState(false);
  const [error, setError] = useState("");
  const [creatingPR, setCreatingPR] = useState(false);
  const [compacting, setCompacting] = useState(false);
  const [prSuccess, setPrSuccess] = useState<string | null>(null);
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: "info" | "error" | "warning" | "success";
    showCancel?: boolean;
    onConfirm?: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    type: "info",
  });
  const [showDiffModal, setShowDiffModal] = useState(false);
  const [diffData, setDiffData] = useState<DiffData | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [selectedFileForViewing, setSelectedFileForViewing] = useState<
    string | null
  >(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const pollingStartTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (workspaceId && taskId) {
      loadTask();
      loadMessages();
    }
  }, [workspaceId, taskId]);

  // Update agentProcessing based on task status
  useEffect(() => {
    if (task) {
      setAgentProcessing(task.agent_status === "running");
    }
  }, [task]);

  useEffect(() => {
    // Only auto-scroll if user was already near the bottom
    if (shouldAutoScrollRef.current) {
      scrollToBottom();
    }
  }, [messages]);

  // Poll for new messages and task status while agent is processing
  useEffect(() => {
    if (!agentProcessing || !workspaceId || !taskId) {
      pollingStartTimeRef.current = null;
      return;
    }

    // Track when polling started
    if (pollingStartTimeRef.current === null) {
      pollingStartTimeRef.current = Date.now();
    }

    const pollInterval = setInterval(async () => {
      // Check if we've been polling for too long (5 minutes)
      const maxPollingTime = 5 * 60 * 1000; // 5 minutes
      if (
        pollingStartTimeRef.current &&
        Date.now() - pollingStartTimeRef.current > maxPollingTime
      ) {
        setAgentProcessing(false);
        pollingStartTimeRef.current = null;
        setError(
          "Agent seems to be taking longer than expected. Please check the task status or try refreshing the page.",
        );
        return;
      }

      // Reload both task status and messages
      await loadTask();
      await loadMessages();
    }, 1000); // Poll every second for real-time updates

    return () => clearInterval(pollInterval);
  }, [agentProcessing, workspaceId, taskId]);

  // Track scroll position to determine if we should auto-scroll
  const handleScroll = () => {
    if (!messagesContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } =
      messagesContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    // If user is within 100px of the bottom, enable auto-scroll
    shouldAutoScrollRef.current = distanceFromBottom < 100;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadTask = async () => {
    try {
      const data = await getWorkspaceTask(
        parseInt(workspaceId!),
        parseInt(taskId!),
      );
      setTask(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load task");
    }
  };

  const loadMessages = async () => {
    try {
      setLoading(true);
      const response = await listChatMessages(
        parseInt(workspaceId!),
        parseInt(taskId!),
      );
      // Always use server response as source of truth
      setMessages(response.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load messages");
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || sending) return;

    try {
      setSending(true);
      pollingStartTimeRef.current = Date.now(); // Reset polling timer
      const userMsg = inputMessage.trim();
      const filesToSend = [...selectedFiles];
      setInputMessage("");
      setSelectedFiles([]);

      // Enable auto-scroll when user sends a message
      shouldAutoScrollRef.current = true;

      // Send message to server
      await sendChatMessage(
        parseInt(workspaceId!),
        parseInt(taskId!),
        { content: userMsg },
        filesToSend.length > 0 ? filesToSend : undefined,
      );

      // Reload task and messages to show the saved user message
      await loadTask();
      await loadMessages();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setSelectedFiles((prev) => [...prev, ...files]);
    // Reset input value to allow selecting the same file again
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const handleExportChat = () => {
    if (messages.length === 0) {
      setAlertModal({
        isOpen: true,
        title: "No Messages",
        message: "There are no messages to export yet.",
        type: "info",
      });
      return;
    }

    // Generate markdown content
    let markdown = `# Agent Chat - Issue #${task?.github_issue_number}\n\n`;
    markdown += `**Workspace ID:** ${task?.workspace_id}\n`;
    markdown += `**Branch:** ${task?.agent_branch_name || "N/A"}\n`;
    markdown += `**Exported:** ${new Date().toLocaleString()}\n\n`;
    markdown += `---\n\n`;

    messages.forEach((msg) => {
      const timestamp = new Date(msg.created_at).toLocaleString();
      const roleLabel =
        msg.role === "user"
          ? "👤 User"
          : msg.role === "assistant"
            ? "🤖 Agent"
            : "⚙️ System";

      markdown += `## ${roleLabel} - ${timestamp}\n\n`;
      markdown += `${msg.content}\n\n`;

      if (msg.attachments && msg.attachments.length > 0) {
        markdown += `**Attachments:**\n`;
        msg.attachments.forEach((att) => {
          markdown += `- ${att.filename} (${(att.file_size / 1024).toFixed(
            2,
          )} KB)\n`;
        });
        markdown += `\n`;
      }

      markdown += `---\n\n`;
    });

    // Create and download file
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-chat-issue-${
      task?.github_issue_number || "unknown"
    }-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setAlertModal({
      isOpen: true,
      title: "Export Successful",
      message: "Chat history has been exported as markdown file.",
      type: "success",
    });
  };

  const handleStopAgent = () => {
    if (!agentProcessing) {
      return;
    }

    setAlertModal({
      isOpen: true,
      title: "Stop Agent Execution",
      message:
        "Are you sure you want to stop the agent? It will finish its current operation and then stop.",
      type: "warning",
      showCancel: true,
      onConfirm: async () => {
        setAlertModal({ ...alertModal, isOpen: false });
        try {
          await cancelAgentExecution(parseInt(workspaceId!), parseInt(taskId!));
          setAlertModal({
            isOpen: true,
            title: "Agent Stopped",
            message: "Agent execution has been stopped successfully.",
            type: "success",
          });
        } catch (err) {
          setAlertModal({
            isOpen: true,
            title: "Error",
            message:
              err instanceof Error ? err.message : "Failed to stop agent",
            type: "error",
          });
        }
      },
    });
  };

  const handleViewChanges = async () => {
    setLoadingDiff(true);
    setShowDiffModal(true);

    try {
      const diff = await getTaskDiff(parseInt(workspaceId!), parseInt(taskId!));
      setDiffData(diff);
    } catch (err) {
      setAlertModal({
        isOpen: true,
        title: "Error",
        message: err instanceof Error ? err.message : "Failed to load changes",
        type: "error",
      });
      setShowDiffModal(false);
    } finally {
      setLoadingDiff(false);
    }
  };

  const handleClearChat = () => {
    setAlertModal({
      isOpen: true,
      title: "Clear Chat History",
      message:
        "Are you sure you want to clear the entire conversation history?",
      type: "warning",
      showCancel: true,
      onConfirm: async () => {
        setAlertModal({ ...alertModal, isOpen: false });
        try {
          await clearChatHistory(parseInt(workspaceId!), parseInt(taskId!));
          setMessages([]);
          await loadTask(); // Reload to reset agent status
        } catch (err) {
          setAlertModal({
            isOpen: true,
            title: "Error",
            message:
              err instanceof Error ? err.message : "Failed to clear chat",
            type: "error",
          });
        }
      },
    });
  };

  const handleCompactSession = () => {
    setAlertModal({
      isOpen: true,
      title: "Compact Session",
      message:
        "This will summarize the conversation history and start a fresh session. " +
        "Use this when the context has grown too large. The summary will preserve key information about work done.",
      type: "info",
      showCancel: true,
      onConfirm: async () => {
        setAlertModal({ ...alertModal, isOpen: false });
        setCompacting(true);
        try {
          const result = await compactChatSession(
            parseInt(workspaceId!),
            parseInt(taskId!),
          );
          await loadMessages(); // Reload to show the compaction message
          await loadTask();
          setAlertModal({
            isOpen: true,
            title: "Session Compacted",
            message: `Session has been compacted successfully. Summary preview:\n\n${result.summary_preview}`,
            type: "success",
          });
        } catch (err) {
          setAlertModal({
            isOpen: true,
            title: "Error",
            message:
              err instanceof Error ? err.message : "Failed to compact session",
            type: "error",
          });
        } finally {
          setCompacting(false);
        }
      },
    });
  };

  const handleCreatePR = async () => {
    if (!task?.agent_branch_name) {
      setAlertModal({
        isOpen: true,
        title: "No Branch Available",
        message:
          "No agent branch available. Please ensure the agent has made changes first.",
        type: "warning",
      });
      return;
    }

    if (task.agent_pr_number) {
      setAlertModal({
        isOpen: true,
        title: "Pull Request Exists",
        message: `Pull request already exists: #${task.agent_pr_number}`,
        type: "info",
      });
      return;
    }

    setCreatingPR(true);
    setPrSuccess(null);
    setError("");

    try {
      const result = await createPullRequestFromTask(
        parseInt(workspaceId!),
        parseInt(taskId!),
        undefined, // No assignee for now
        true, // Create as draft
      );

      setPrSuccess(result.message);
      await loadTask(); // Reload to get PR info

      // Open PR in new tab
      if (result.pr_url) {
        window.open(result.pr_url, "_blank");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create pull request",
      );
    } finally {
      setCreatingPR(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter without Shift - send message
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      handleSendMessage();
    }
    // Ctrl+Enter or Cmd+Enter - send message (alternative)
    else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSendMessage();
    }
    // Escape - clear input
    else if (e.key === "Escape") {
      e.preventDefault();
      setInputMessage("");
      setSelectedFiles([]);
    }
  };

  if (loading && messages.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading agent chat...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 top-14 flex flex-col bg-background overflow-hidden">
      {/* Header */}
      <div className="bg-card border-b border-border shadow-sm flex-shrink-0">
        <div className="w-full px-3 sm:px-6 py-2 sm:py-3">
          <div className="flex items-center justify-between gap-2 sm:gap-4 min-h-[48px]">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-shrink-0">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate(`/workspaces/${workspaceId}`)}
                className="group flex-shrink-0 min-h-[44px] min-w-[44px]"
              >
                <ArrowLeft className="w-5 h-5 group-hover:-translate-x-1 transition-transform" />
              </Button>

              <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                <div className="w-8 h-8 sm:w-10 sm:h-10 bg-primary rounded-xl flex items-center justify-center shadow-sm flex-shrink-0">
                  <Bot className="w-4 h-4 sm:w-5 sm:h-5 text-primary-foreground" />
                </div>
                <div className="min-w-0 flex flex-col justify-center">
                  <h1 className="text-base sm:text-lg font-bold text-foreground truncate leading-tight">
                    Agent Chat
                  </h1>
                  {task && (
                    <p className="text-xs text-muted-foreground truncate leading-tight">
                      Issue #{task.github_issue_number}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Mobile action buttons */}
            <div className="flex items-center gap-1 sm:hidden">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowFileBrowser(!showFileBrowser)}
                className="min-h-[44px] min-w-[44px] text-muted-foreground"
              >
                {showFileBrowser ? (
                  <PanelLeftClose className="w-5 h-5" />
                ) : (
                  <PanelLeft className="w-5 h-5" />
                )}
              </Button>

              {task?.agent_pr_number ? (
                <Button
                  variant="outline"
                  size="icon"
                  className="min-h-[44px] min-w-[44px]"
                  asChild
                >
                  <a
                    href={task.agent_pr_url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <CheckCircle className="w-5 h-5 text-success" />
                  </a>
                </Button>
              ) : task?.agent_branch_name ? (
                <Button
                  variant="gradient"
                  size="icon"
                  onClick={handleCreatePR}
                  disabled={creatingPR}
                  className="min-h-[44px] min-w-[44px]"
                >
                  {creatingPR ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <GitPullRequest className="w-5 h-5" />
                  )}
                </Button>
              ) : null}

              {task?.agent_branch_name && (
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleViewChanges}
                  disabled={loadingDiff}
                  className="min-h-[44px] min-w-[44px]"
                >
                  {loadingDiff ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <FileEdit className="w-5 h-5" />
                  )}
                </Button>
              )}

              {agentProcessing && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleStopAgent}
                  className="min-h-[44px] min-w-[44px] text-destructive"
                >
                  <StopCircle className="w-5 h-5" />
                </Button>
              )}

              {/* More menu for less frequent actions */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="min-h-[44px] min-w-[44px]"
                  >
                    <MoreVertical className="w-5 h-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={handleExportChat}
                    disabled={messages.length === 0}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Export Chat
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={handleCompactSession}
                    disabled={
                      messages.length === 0 || compacting || agentProcessing
                    }
                  >
                    <RefreshCw
                      className={`w-4 h-4 mr-2 ${compacting ? "animate-spin" : ""}`}
                    />
                    Compact Session
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={handleClearChat}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Clear Chat
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Desktop action buttons */}
            <div className="hidden sm:flex items-center gap-2 flex-wrap justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFileBrowser(!showFileBrowser)}
                className="text-muted-foreground hover:text-foreground flex-shrink-0 min-h-[44px]"
              >
                {showFileBrowser ? (
                  <>
                    <PanelLeftClose className="w-4 h-4 mr-2" />
                    <span className="hidden md:inline">Hide Files</span>
                  </>
                ) : (
                  <>
                    <PanelLeft className="w-4 h-4 mr-2" />
                    <span className="hidden md:inline">Show Files</span>
                  </>
                )}
              </Button>

              {task?.agent_branch_name && (
                <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-muted rounded-lg border border-border flex-shrink-0">
                  <GitBranch className="w-4 h-4 text-muted-foreground" />
                  <span className="font-mono text-xs text-foreground truncate max-w-[150px]">
                    {task.agent_branch_name}
                  </span>
                </div>
              )}

              {task?.agent_pr_number ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-shrink-0 min-h-[44px]"
                  asChild
                >
                  <a
                    href={task.agent_pr_url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="no-underline"
                  >
                    <CheckCircle className="w-4 h-4 mr-2 text-success" />
                    <span className="hidden md:inline">
                      PR #{task.agent_pr_number}
                    </span>
                    <span className="md:hidden">#{task.agent_pr_number}</span>
                  </a>
                </Button>
              ) : task?.agent_branch_name ? (
                <Button
                  variant="gradient"
                  onClick={handleCreatePR}
                  disabled={creatingPR}
                  size="sm"
                  className="flex-shrink-0 min-h-[44px]"
                >
                  {creatingPR ? (
                    <>
                      <Loader2 className="w-4 h-4 md:mr-2 animate-spin" />
                      <span className="hidden md:inline">Creating...</span>
                    </>
                  ) : (
                    <>
                      <GitPullRequest className="w-4 h-4 md:mr-2" />
                      <span className="hidden md:inline">Create PR</span>
                    </>
                  )}
                </Button>
              ) : null}

              {task?.agent_branch_name && (
                <Button
                  variant="outline"
                  onClick={handleViewChanges}
                  size="sm"
                  disabled={loadingDiff}
                  className="flex-shrink-0 min-h-[44px]"
                >
                  {loadingDiff ? (
                    <>
                      <Loader2 className="w-4 h-4 md:mr-2 animate-spin" />
                      <span className="hidden md:inline">Loading...</span>
                    </>
                  ) : (
                    <>
                      <FileEdit className="w-4 h-4 md:mr-2" />
                      <span className="hidden md:inline">Changes</span>
                    </>
                  )}
                </Button>
              )}

              {agentProcessing && (
                <Button
                  variant="ghost"
                  onClick={handleStopAgent}
                  size="sm"
                  className="text-destructive hover:text-destructive/80 flex-shrink-0 min-h-[44px]"
                >
                  <StopCircle className="w-4 h-4 md:mr-2" />
                  <span className="hidden md:inline">Stop</span>
                </Button>
              )}

              <Button
                variant="ghost"
                onClick={handleExportChat}
                size="sm"
                disabled={messages.length === 0}
                className="flex-shrink-0 min-h-[44px]"
              >
                <Download className="w-4 h-4 md:mr-2" />
                <span className="hidden md:inline">Export</span>
              </Button>

              <Button
                variant="ghost"
                onClick={handleCompactSession}
                size="sm"
                disabled={
                  messages.length === 0 || compacting || agentProcessing
                }
                className="flex-shrink-0 min-h-[44px]"
                title="Compact conversation context when it grows too large"
              >
                <RefreshCw
                  className={`w-4 h-4 md:mr-2 ${compacting ? "animate-spin" : ""}`}
                />
                <span className="hidden md:inline">Compact</span>
              </Button>

              <Button
                variant="ghost"
                onClick={handleClearChat}
                size="sm"
                className="text-destructive hover:text-destructive flex-shrink-0 min-h-[44px]"
              >
                <Trash2 className="w-4 h-4 md:mr-2" />
                <span className="hidden md:inline">Clear</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area with File Browser */}
      <div className="flex-1 flex overflow-hidden min-h-0 relative">
        {/* File Browser - Mobile Overlay */}
        {showFileBrowser && (
          <>
            {/* Mobile backdrop */}
            <div
              className="fixed inset-0 bg-black/50 z-40 sm:hidden"
              onClick={() => setShowFileBrowser(false)}
            />
            {/* File browser sidebar - fixed on mobile, normal on desktop */}
            <div className="fixed inset-y-0 left-0 top-14 z-50 w-[85%] max-w-xs bg-card border-r border-border overflow-y-auto sm:relative sm:inset-auto sm:z-auto sm:w-80 sm:max-w-none sm:flex-shrink-0">
              <FileBrowser
                workspaceId={parseInt(workspaceId!)}
                taskId={parseInt(taskId!)}
                onFileSelect={(path) => {
                  setSelectedFileForViewing(path);
                  // Close file browser on mobile after selection
                  if (window.innerWidth < 640) {
                    setShowFileBrowser(false);
                  }
                }}
              />
            </div>
          </>
        )}

        {/* Chat Messages */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <div
            ref={messagesContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto min-h-0"
          >
            <div className="max-w-4xl mx-auto px-3 sm:px-6 py-4 sm:py-8">
              {error && (
                <Alert variant="destructive" className="mb-6">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {prSuccess && (
                <Alert className="mb-6 bg-success/10 border-success/20">
                  <div className="flex items-center justify-between gap-3 w-full">
                    <div className="flex items-center gap-3">
                      <CheckCircle className="h-4 w-4 text-success" />
                      <AlertDescription className="text-success">
                        {prSuccess}
                      </AlertDescription>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setPrSuccess(null)}
                      className="h-6 w-6 text-success hover:text-success/80"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </Alert>
              )}

              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 sm:py-20">
                  <div className="w-16 h-16 sm:w-24 sm:h-24 bg-primary/10 rounded-2xl sm:rounded-3xl flex items-center justify-center mb-4 sm:mb-6 shadow-xl">
                    <div className="flex gap-1">
                      <div
                        className="w-2 h-2 sm:w-3 sm:h-3 bg-primary rounded-full animate-bounce"
                        style={{ animationDelay: "0ms" }}
                      ></div>
                      <div
                        className="w-2 h-2 sm:w-3 sm:h-3 bg-primary rounded-full animate-bounce"
                        style={{ animationDelay: "150ms" }}
                      ></div>
                      <div
                        className="w-2 h-2 sm:w-3 sm:h-3 bg-primary rounded-full animate-bounce"
                        style={{ animationDelay: "300ms" }}
                      ></div>
                    </div>
                  </div>
                  <h3 className="text-lg sm:text-2xl font-bold text-foreground mb-2 sm:mb-3 text-center px-2">
                    Agent is analyzing the issue...
                  </h3>
                  <p className="text-sm sm:text-base text-muted-foreground text-center max-w-md mb-6 sm:mb-8 px-2">
                    The Coding Agent is automatically analyzing the issue and
                    preparing an implementation approach. This will appear in a
                    moment.
                  </p>
                  <div className="flex items-center gap-2 sm:gap-3 px-4 sm:px-6 py-2 sm:py-3 bg-primary/10 border border-primary/20 rounded-xl mb-6 sm:mb-8">
                    <Loader2 className="h-4 w-4 sm:h-5 sm:w-5 animate-spin text-primary flex-shrink-0" />
                    <span className="text-xs sm:text-sm text-foreground font-medium">
                      Initializing repository and analyzing issue...
                    </span>
                  </div>

                  {/* Example Prompts */}
                  <div className="w-full max-w-2xl mt-2 sm:mt-4">
                    <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-4 text-center">
                      While you wait, here are some things you can ask the
                      agent:
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                      {[
                        {
                          icon: "🔍",
                          title: "Analyze specific files",
                          example:
                            "Can you examine the authentication logic in auth.py?",
                        },
                        {
                          icon: "💡",
                          title: "Suggest improvements",
                          example:
                            "What improvements would you suggest for the database queries?",
                        },
                        {
                          icon: "🐛",
                          title: "Debug issues",
                          example:
                            "Help me understand why the login flow is failing",
                        },
                        {
                          icon: "✨",
                          title: "Add features",
                          example:
                            "Can you add input validation to the user registration form?",
                        },
                      ].map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => setInputMessage(prompt.example)}
                          className="text-left p-3 sm:p-4 bg-card border border-border rounded-xl hover:border-primary hover:shadow-md transition-all group min-h-[44px]"
                        >
                          <div className="flex items-start gap-2 sm:gap-3">
                            <span className="text-xl sm:text-2xl flex-shrink-0">
                              {prompt.icon}
                            </span>
                            <div className="flex-1 min-w-0">
                              <h4 className="text-xs sm:text-sm font-semibold text-foreground mb-0.5 sm:mb-1 group-hover:text-primary transition-colors">
                                {prompt.title}
                              </h4>
                              <p className="text-[10px] sm:text-xs text-muted-foreground line-clamp-2">
                                {prompt.example}
                              </p>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  {groupMessages(messages).map((item, index) => {
                    // Render grouped progress messages
                    if ("type" in item && item.type === "group") {
                      return (
                        <ProgressMessageGroup
                          key={`group-${index}`}
                          messages={item.messages}
                          agentStatus={task?.agent_status}
                        />
                      );
                    }

                    // Render individual message
                    const msg = item as AgentMessage;

                    // Check if this is an input request - more robust JSON detection
                    let isInputRequest = false;
                    if (
                      msg.role === "assistant" &&
                      msg.content.trim().startsWith("{")
                    ) {
                      try {
                        const parsed = JSON.parse(msg.content);
                        isInputRequest = parsed.type === "input_request";
                      } catch (e) {
                        // Not valid JSON, not an input request
                      }
                    }

                    if (isInputRequest) {
                      return (
                        <InputRequestCard
                          key={msg.id}
                          message={msg}
                          allMessages={messages}
                          onSubmit={async (response) => {
                            if (sending || agentProcessing) return;

                            try {
                              setSending(true);
                              pollingStartTimeRef.current = Date.now(); // Reset polling timer

                              // Enable auto-scroll when user responds
                              shouldAutoScrollRef.current = true;

                              // Add user response message
                              const tempUserMsg: AgentMessage = {
                                id: Date.now(),
                                workspace_task_id: parseInt(taskId!),
                                role: "user",
                                content: response,
                                created_at: new Date().toISOString(),
                                user_id: 1,
                                username: "You",
                              };
                              setMessages((prev) => [...prev, tempUserMsg]);

                              // Send the response
                              await sendChatMessage(
                                parseInt(workspaceId!),
                                parseInt(taskId!),
                                {
                                  content: response,
                                },
                              );

                              // Reload task and messages to get updated status
                              await loadTask(); // This will trigger agentProcessing update via useEffect
                              await loadMessages();
                            } catch (err) {
                              setError(
                                err instanceof Error
                                  ? err.message
                                  : "Failed to send response",
                              );
                            } finally {
                              setSending(false);
                            }
                          }}
                        />
                      );
                    }

                    return (
                      <div
                        key={msg.id}
                        className={`flex gap-4 animate-slide-up ${
                          msg.role === "user" ? "flex-row-reverse" : ""
                        }`}
                      >
                        {/* Avatar */}
                        <div
                          className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center shadow-md ${
                            msg.role === "user"
                              ? "bg-primary"
                              : msg.role === "system"
                                ? "bg-muted"
                                : "bg-primary"
                          }`}
                        >
                          {msg.role === "user" ? (
                            <User className="w-6 h-6 text-primary-foreground" />
                          ) : msg.role === "system" ? (
                            <Info className="w-6 h-6 text-muted-foreground" />
                          ) : (
                            <Bot className="w-6 h-6 text-primary-foreground" />
                          )}
                        </div>

                        {/* Message Content */}
                        <div
                          className={`flex-1 max-w-3xl ${
                            msg.role === "user" ? "flex justify-end" : ""
                          }`}
                        >
                          <div
                            className={`rounded-2xl px-6 py-4 shadow-md ${
                              msg.role === "user"
                                ? "bg-primary text-primary-foreground"
                                : msg.role === "system"
                                  ? "bg-secondary/50 border border-border text-foreground"
                                  : "bg-card border border-border text-foreground"
                            }`}
                          >
                            {msg.role === "system" &&
                            msg.content.includes("Created branch:") ? (
                              <div>
                                <div className="flex items-center gap-2 mb-3">
                                  <CheckCircle className="w-5 h-5" />
                                  <span className="font-semibold text-sm">
                                    Agent Initialized
                                  </span>
                                </div>
                                <p className="text-sm whitespace-pre-line mb-4">
                                  {msg.content}
                                </p>
                                <div className="p-4 bg-muted/50 rounded-xl border border-border">
                                  <p className="text-xs font-semibold text-foreground mb-2">
                                    Agent Capabilities:
                                  </p>
                                  <ul className="text-xs text-muted-foreground space-y-1">
                                    <li className="flex items-center gap-2">
                                      <CheckCircle className="w-3 h-3" />
                                      Read files from the repository
                                    </li>
                                    <li className="flex items-center gap-2">
                                      <CheckCircle className="w-3 h-3" />
                                      Modify existing files
                                    </li>
                                    <li className="flex items-center gap-2">
                                      <CheckCircle className="w-3 h-3" />
                                      Create new files
                                    </li>
                                    <li className="flex items-center gap-2">
                                      <CheckCircle className="w-3 h-3" />
                                      Commit changes automatically
                                    </li>
                                  </ul>
                                </div>
                              </div>
                            ) : (
                              <FormattedMessage
                                content={msg.content}
                                className="text-sm"
                              />
                            )}

                            {/* File Attachments */}
                            {msg.attachments && msg.attachments.length > 0 && (
                              <FileAttachmentsDisplay
                                attachments={msg.attachments}
                              />
                            )}

                            <div
                              className={`mt-3 text-xs flex items-center gap-2 ${
                                msg.role === "user"
                                  ? "text-primary-foreground/70"
                                  : "text-muted-foreground"
                              }`}
                            >
                              <Clock className="w-3 h-3" />
                              {new Date(
                                `${msg.created_at}Z`,
                              ).toLocaleTimeString()}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {agentProcessing && (
                    <div className="flex gap-4 animate-slide-up">
                      <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-md">
                        <Bot className="w-6 h-6 text-primary-foreground animate-pulse" />
                      </div>
                      <div className="flex-1 max-w-3xl">
                        <Card className="border-border px-6 py-4 shadow-md">
                          <div className="flex items-center gap-3">
                            <div className="flex gap-1">
                              <div
                                className="w-2 h-2 bg-primary rounded-full animate-bounce"
                                style={{ animationDelay: "0ms" }}
                              ></div>
                              <div
                                className="w-2 h-2 bg-primary rounded-full animate-bounce"
                                style={{ animationDelay: "150ms" }}
                              ></div>
                              <div
                                className="w-2 h-2 bg-primary rounded-full animate-bounce"
                                style={{ animationDelay: "300ms" }}
                              ></div>
                            </div>
                            <span className="text-sm text-muted-foreground">
                              Processing...
                            </span>
                          </div>
                        </Card>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-border bg-card shadow-lg flex-shrink-0">
            <div className="max-w-4xl mx-auto px-3 sm:px-6 py-3 sm:py-4">
              {/* Selected Files Display */}
              {selectedFiles.length > 0 && (
                <div className="mb-2 sm:mb-3 flex flex-wrap gap-2">
                  {selectedFiles.map((file, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-2 bg-primary/10 border border-primary/20 rounded-lg sm:rounded-xl text-xs sm:text-sm"
                    >
                      <FileText className="w-3 h-3 sm:w-4 sm:h-4 text-primary flex-shrink-0" />
                      <span className="text-foreground font-medium truncate max-w-[100px] sm:max-w-xs">
                        {file.name}
                      </span>
                      <span className="text-muted-foreground text-[10px] sm:text-xs hidden sm:inline">
                        {formatFileSize(file.size)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRemoveFile(index)}
                        className="ml-0.5 h-5 w-5 min-h-[20px] min-w-[20px] text-primary hover:text-primary"
                      >
                        <X className="w-3 h-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2 sm:gap-4 items-end">
                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  onChange={handleFileSelect}
                  className="hidden"
                  accept="*/*"
                />

                {/* Attach file button */}
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={sending || agentProcessing}
                  title="Attach files"
                  className="flex-shrink-0 h-11 w-11 sm:h-14 sm:w-14 rounded-xl sm:rounded-2xl min-h-[44px] min-w-[44px]"
                >
                  <Paperclip className="w-5 h-5 sm:w-6 sm:h-6" />
                </Button>

                <div className="flex-1 relative">
                  <textarea
                    ref={inputRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your message..."
                    disabled={sending || agentProcessing}
                    rows={1}
                    className="w-full px-3 sm:px-6 py-3 sm:py-4 bg-background border border-border rounded-xl sm:rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent disabled:opacity-50 text-sm sm:text-base text-foreground placeholder-muted-foreground transition-all"
                    style={{ minHeight: "44px", maxHeight: "200px" }}
                  />
                </div>
                <Button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || sending || agentProcessing}
                  size="icon"
                  className="flex-shrink-0 h-11 w-11 sm:h-14 sm:w-14 rounded-xl sm:rounded-2xl shadow-lg min-h-[44px] min-w-[44px]"
                >
                  {sending || agentProcessing ? (
                    <Loader2 className="h-5 w-5 sm:h-6 sm:w-6 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5 sm:w-6 sm:h-6" />
                  )}
                </Button>
              </div>
              <div className="flex items-center justify-between mt-2">
                <p className="text-[10px] sm:text-xs text-muted-foreground hidden sm:block">
                  Agent can read files, write code, and create commits
                  automatically
                </p>
                <div className="hidden sm:flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-[10px] font-mono">
                      Enter
                    </kbd>
                    <span>Send</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-[10px] font-mono">
                      Shift+Enter
                    </kbd>
                    <span>New line</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-[10px] font-mono">
                      Esc
                    </kbd>
                    <span>Clear</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* File Viewer Modal */}
      {selectedFileForViewing && (
        <FileViewer
          workspaceId={parseInt(workspaceId!)}
          taskId={parseInt(taskId!)}
          filePath={selectedFileForViewing}
          onClose={() => setSelectedFileForViewing(null)}
        />
      )}

      {/* Alert Modal */}
      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        type={alertModal.type}
        showCancel={alertModal.showCancel}
        onConfirm={() => {
          if (alertModal.onConfirm) {
            alertModal.onConfirm();
          } else {
            setAlertModal({ ...alertModal, isOpen: false });
          }
        }}
        onCancel={() => setAlertModal({ ...alertModal, isOpen: false })}
      />

      {/* Diff Viewer Modal */}
      <Dialog open={showDiffModal} onOpenChange={setShowDiffModal}>
        <DialogContent className="sm:max-w-7xl max-w-6xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileEdit className="w-5 h-5" />
              Code Changes
            </DialogTitle>
            <DialogDescription>
              Review changes made by the agent compared to the base branch
            </DialogDescription>
          </DialogHeader>

          {loadingDiff ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : diffData && diffData.files.length > 0 ? (
            <div className="flex-1 overflow-auto px-1">
              <DiffViewer diff={diffData.diff} files={diffData.files} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <File className="w-12 h-12 mb-3 opacity-50" />
              <p>No changes found</p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
