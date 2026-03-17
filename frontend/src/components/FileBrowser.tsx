import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Folder,
  FolderOpen,
  File,
  FileText,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { getFileTree, type FileTreeNode } from "../api/agent_chat";

interface FileBrowserProps {
  workspaceId: number;
  taskId: number;
  onFileSelect: (filePath: string) => void;
}

export default function FileBrowser({
  workspaceId,
  taskId,
  onFileSelect,
}: FileBrowserProps) {
  const [fileTree, setFileTree] = useState<FileTreeNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(
    new Set()
  );
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFileTree = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getFileTree(workspaceId, taskId);
      setFileTree(response.tree);

      // Auto-expand root level folders
      const rootFolders = response.tree
        .filter((node) => node.type === "dir")
        .map((node) => node.path);
      setExpandedFolders(new Set(rootFolders));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load repository structure"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFileTree();
  }, [workspaceId, taskId]);

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  };

  const handleFileClick = (path: string) => {
    setSelectedFile(path);
    onFileSelect(path);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const renderTree = (nodes: FileTreeNode[], depth = 0) => {
    return nodes.map((node) => {
      const isExpanded = expandedFolders.has(node.path);
      const isSelected = selectedFile === node.path;
      const paddingLeft = depth * 16 + 8;

      if (node.type === "dir") {
        return (
          <div key={node.path}>
            {/* Folder */}
            <button
              onClick={() => toggleFolder(node.path)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 hover:bg-muted/50 rounded transition-colors ${
                isExpanded ? "bg-muted/30" : ""
              }`}
              style={{ paddingLeft: `${paddingLeft}px` }}
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              ) : (
                <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              )}
              {isExpanded ? (
                <FolderOpen className="w-4 h-4 text-blue-500 flex-shrink-0" />
              ) : (
                <Folder className="w-4 h-4 text-blue-500 flex-shrink-0" />
              )}
              <span className="text-sm font-medium text-foreground truncate">
                {node.name}
              </span>
            </button>

            {/* Children */}
            {isExpanded && node.children && node.children.length > 0 && (
              <div>{renderTree(node.children, depth + 1)}</div>
            )}
          </div>
        );
      } else {
        // File
        return (
          <button
            key={node.path}
            onClick={() => handleFileClick(node.path)}
            className={`w-full flex items-center gap-2 px-2 py-1.5 hover:bg-muted/50 rounded transition-colors ${
              isSelected ? "bg-primary/10 border-l-2 border-primary" : ""
            }`}
            style={{ paddingLeft: `${paddingLeft + 20}px` }}
          >
            <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <span className="text-sm text-foreground truncate flex-1 text-left">
              {node.name}
            </span>
            {node.size !== undefined && (
              <span className="text-xs text-muted-foreground flex-shrink-0">
                {formatFileSize(node.size)}
              </span>
            )}
          </button>
        );
      }
    });
  };

  return (
    <Card className="h-full flex flex-col border-r rounded-none">
      <CardHeader className="pb-3 border-b">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <File className="w-4 h-4" />
            Files
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={loadFileTree}
            disabled={loading}
            className="h-7 w-7"
          >
            <RefreshCw
              className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto p-2">
        {loading && fileTree.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
            <p className="text-sm text-muted-foreground">Loading files...</p>
          </div>
        ) : error ? (
          <Alert variant="destructive" className="m-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : fileTree.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center px-4">
            <File className="w-12 h-12 text-muted-foreground/50 mb-3" />
            <p className="text-sm text-muted-foreground mb-1">
              No files available
            </p>
            <p className="text-xs text-muted-foreground">
              Repository not initialized yet
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">{renderTree(fileTree)}</div>
        )}
      </CardContent>
    </Card>
  );
}
