import { useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus, vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Copy,
  Check,
  Loader2,
  AlertCircle,
  FileText,
  Info,
} from "lucide-react";
import { getFileContent } from "../api/agent_chat";

interface FileViewerProps {
  workspaceId: number;
  taskId: number;
  filePath: string;
  onClose: () => void;
}

export default function FileViewer({
  workspaceId,
  taskId,
  filePath,
  onClose,
}: FileViewerProps) {
  const [content, setContent] = useState<string>("");
  const [fileSize, setFileSize] = useState<number>(0);
  const [isBinary, setIsBinary] = useState<boolean>(false);
  const [isTruncated, setIsTruncated] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

  useEffect(() => {
    loadFileContent();
  }, [workspaceId, taskId, filePath]);

  const loadFileContent = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getFileContent(workspaceId, taskId, filePath);
      setContent(response.content);
      setFileSize(response.size);
      setIsBinary(response.is_binary);
      setIsTruncated(response.truncated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load file content"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCopyPath = () => {
    navigator.clipboard.writeText(filePath);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLanguageFromPath = (path: string): string => {
    const extension = path.split(".").pop()?.toLowerCase();
    const languageMap: Record<string, string> = {
      js: "javascript",
      jsx: "jsx",
      ts: "typescript",
      tsx: "tsx",
      py: "python",
      java: "java",
      cpp: "cpp",
      c: "c",
      cs: "csharp",
      php: "php",
      rb: "ruby",
      go: "go",
      rs: "rust",
      swift: "swift",
      kt: "kotlin",
      scala: "scala",
      sh: "bash",
      bash: "bash",
      sql: "sql",
      html: "html",
      css: "css",
      scss: "scss",
      sass: "sass",
      json: "json",
      xml: "xml",
      yaml: "yaml",
      yml: "yaml",
      md: "markdown",
      txt: "text",
      log: "text",
    };
    return languageMap[extension || ""] || "text";
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const fileName = filePath.split("/").pop() || filePath;

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <DialogTitle className="flex items-center gap-2 truncate">
                <FileText className="w-5 h-5 flex-shrink-0" />
                <span className="truncate">{fileName}</span>
              </DialogTitle>
              <DialogDescription className="flex items-center gap-2 mt-1">
                <code className="text-xs bg-muted px-2 py-0.5 rounded">
                  {filePath}
                </code>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyPath}
                  className="h-6 px-2"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 mr-1" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 mr-1" />
                      Copy path
                    </>
                  )}
                </Button>
              </DialogDescription>
            </div>
            <div className="text-xs text-muted-foreground flex-shrink-0">
              {formatFileSize(fileSize)}
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-auto border rounded-lg bg-muted/30">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
              <p className="text-sm text-muted-foreground">Loading file...</p>
            </div>
          ) : error ? (
            <Alert variant="destructive" className="m-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : isBinary ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <FileText className="w-12 h-12 text-muted-foreground/50 mb-3" />
              <p className="text-sm font-medium text-foreground mb-1">
                Cannot display binary file
              </p>
              <p className="text-xs text-muted-foreground">
                This file appears to be a binary file (image, video, executable,
                etc.)
              </p>
            </div>
          ) : (
            <div>
              {isTruncated && (
                <Alert className="m-4 mb-0 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800">
                  <Info className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  <AlertDescription className="text-amber-800 dark:text-amber-300">
                    This file is large and has been truncated to 500KB for
                    display.
                  </AlertDescription>
                </Alert>
              )}
              <SyntaxHighlighter
                language={getLanguageFromPath(filePath)}
                style={isDark ? vscDarkPlus : vs}
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  fontSize: "0.875rem",
                  padding: "1rem",
                  background: "transparent",
                }}
                showLineNumbers={true}
                wrapLongLines={false}
              >
                {content}
              </SyntaxHighlighter>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
