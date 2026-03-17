import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FilePlus,
  FileMinus,
  FileEdit,
  Copy,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

interface DiffViewerProps {
  diff: string;
  files: Array<{ status: string; path: string }>;
}

interface ParsedDiff {
  filePath: string;
  status: string;
  hunks: DiffHunk[];
}

interface DiffHunk {
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

interface DiffLine {
  type: 'add' | 'remove' | 'context' | 'header';
  content: string;
  oldLineNo?: number;
  newLineNo?: number;
}

function parseDiff(diffText: string): ParsedDiff[] {
  const files: ParsedDiff[] = [];
  const lines = diffText.split('\n');
  let currentFile: ParsedDiff | null = null;
  let currentHunk: DiffHunk | null = null;
  let oldLineNo = 0;
  let newLineNo = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // New file
    if (line.startsWith('diff --git')) {
      // Finalize the current hunk before pushing the current file
      if (currentHunk && currentFile) {
        currentFile.hunks.push(currentHunk);
      }

      if (currentFile) {
        files.push(currentFile);
      }

      // Extract file path from "diff --git a/path b/path"
      const match = line.match(/diff --git a\/(.*) b\/(.*)/);
      const filePath = match ? match[2] : 'unknown';

      currentFile = {
        filePath,
        status: 'M', // Will be updated by looking at the next lines
        hunks: [],
      };
      currentHunk = null;
      continue;
    }

    // File status indicators
    if (line.startsWith('new file mode')) {
      if (currentFile) currentFile.status = 'A';
      continue;
    }
    if (line.startsWith('deleted file mode')) {
      if (currentFile) currentFile.status = 'D';
      continue;
    }

    // Hunk header: @@ -oldStart,oldLines +newStart,newLines @@
    if (line.startsWith('@@')) {
      const match = line.match(/@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@/);
      if (match && currentFile) {
        if (currentHunk) {
          currentFile.hunks.push(currentHunk);
        }

        oldLineNo = parseInt(match[1]);
        const oldCount = match[2] ? parseInt(match[2]) : 1;
        newLineNo = parseInt(match[3]);
        const newCount = match[4] ? parseInt(match[4]) : 1;

        currentHunk = {
          oldStart: oldLineNo,
          oldLines: oldCount,
          newStart: newLineNo,
          newLines: newCount,
          lines: [{
            type: 'header',
            content: line,
          }],
        };
      }
      continue;
    }

    // Skip metadata lines
    if (
      line.startsWith('index ') ||
      line.startsWith('---') ||
      line.startsWith('+++') ||
      line.startsWith('Binary files')
    ) {
      continue;
    }

    // Diff content lines
    if (currentHunk) {
      if (line.startsWith('+')) {
        currentHunk.lines.push({
          type: 'add',
          content: line.slice(1),
          newLineNo: newLineNo++,
        });
      } else if (line.startsWith('-')) {
        currentHunk.lines.push({
          type: 'remove',
          content: line.slice(1),
          oldLineNo: oldLineNo++,
        });
      } else if (line.startsWith(' ')) {
        currentHunk.lines.push({
          type: 'context',
          content: line.slice(1),
          oldLineNo: oldLineNo++,
          newLineNo: newLineNo++,
        });
      }
    }
  }

  // Add the last file and hunk
  if (currentHunk && currentFile) {
    currentFile.hunks.push(currentHunk);
  }
  if (currentFile) {
    files.push(currentFile);
  }

  return files;
}

function FileIcon({ status }: { status: string }) {
  if (status === 'A')
    return <FilePlus className="w-4 h-4 text-green-600 dark:text-green-400" />;
  if (status === 'D')
    return <FileMinus className="w-4 h-4 text-red-600 dark:text-red-400" />;
  return <FileEdit className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
}

function FileStatusBadge({ status }: { status: string }) {
  const labels = { A: 'Added', M: 'Modified', D: 'Deleted' };
  const colors = {
    A: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    M: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    D: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  };

  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${
        colors[status as keyof typeof colors] || 'bg-gray-100 text-gray-700'
      }`}
    >
      {labels[status as keyof typeof labels] || status}
    </span>
  );
}

function DiffHunkView({ hunk }: { hunk: DiffHunk }) {
  return (
    <div className="border-t border-border">
      {hunk.lines.map((line, idx) => {
        if (line.type === 'header') {
          return (
            <div
              key={idx}
              className="bg-muted/50 text-muted-foreground text-xs font-mono px-4 py-1 border-b border-border"
            >
              {line.content}
            </div>
          );
        }

        const bgColor =
          line.type === 'add'
            ? 'bg-green-50 dark:bg-green-900/10'
            : line.type === 'remove'
            ? 'bg-red-50 dark:bg-red-900/10'
            : 'bg-background';

        const lineNoColor =
          line.type === 'add'
            ? 'text-green-700 dark:text-green-400'
            : line.type === 'remove'
            ? 'text-red-700 dark:text-red-400'
            : 'text-muted-foreground';

        const marker =
          line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ';
        const markerColor =
          line.type === 'add'
            ? 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30'
            : line.type === 'remove'
            ? 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30'
            : 'text-transparent';

        return (
          <div
            key={idx}
            className={`flex font-mono text-xs ${bgColor} hover:bg-muted/30 transition-colors`}
          >
            {/* Old line number */}
            <div
              className={`w-12 text-right px-2 py-1 select-none border-r border-border/50 ${lineNoColor}`}
            >
              {line.oldLineNo || ''}
            </div>
            {/* New line number */}
            <div
              className={`w-12 text-right px-2 py-1 select-none border-r border-border/50 ${lineNoColor}`}
            >
              {line.newLineNo || ''}
            </div>
            {/* Marker */}
            <div
              className={`w-6 text-center py-1 select-none border-r border-border/50 font-bold ${markerColor}`}
            >
              {marker}
            </div>
            {/* Content */}
            <div className="flex-1 px-3 py-1 overflow-x-auto">
              <code className="whitespace-pre">{line.content}</code>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FileDiffView({ file }: { file: ParsedDiff }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const fullDiff = useMemo(() => {
    return file.hunks
      .flatMap((h) => h.lines)
      .filter((l) => l.type !== 'header')
      .map((l) => l.content)
      .join('\n');
  }, [file.hunks]);

  const handleCopy = () => {
    navigator.clipboard.writeText(fullDiff);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden mb-4">
      {/* File Header */}
      <div className="bg-muted/50 px-4 py-3 flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="hover:bg-muted rounded p-1 transition-colors"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
          <FileIcon status={file.status} />
          <span className="font-mono text-sm font-medium truncate">
            {file.filePath}
          </span>
          <FileStatusBadge status={file.status} />
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="ml-2"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 mr-1" />
              Copied
            </>
          ) : (
            <>
              <Copy className="w-3 h-3 mr-1" />
              Copy
            </>
          )}
        </Button>
      </div>

      {/* Diff Content */}
      {isExpanded && (
        <div className="bg-background">
          {file.hunks.map((hunk, idx) => (
            <DiffHunkView key={idx} hunk={hunk} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DiffViewer({ diff, files }: DiffViewerProps) {
  const parsedFiles = useMemo(() => parseDiff(diff), [diff]);

  // Match parsed files with file status info
  const enrichedFiles = useMemo(() => {
    return parsedFiles.map((pf) => {
      const fileInfo = files.find((f) => f.path === pf.filePath);
      return {
        ...pf,
        status: fileInfo?.status || pf.status,
      };
    });
  }, [parsedFiles, files]);

  if (!diff || enrichedFiles.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No changes to display
      </div>
    );
  }

  const stats = {
    added: enrichedFiles.filter((f) => f.status === 'A').length,
    modified: enrichedFiles.filter((f) => f.status === 'M').length,
    deleted: enrichedFiles.filter((f) => f.status === 'D').length,
  };

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center justify-between pb-2 border-b border-border">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            {enrichedFiles.length} file{enrichedFiles.length !== 1 ? 's' : ''} changed
          </span>
          {stats.added > 0 && (
            <span className="text-green-600 dark:text-green-400">
              +{stats.added} added
            </span>
          )}
          {stats.modified > 0 && (
            <span className="text-blue-600 dark:text-blue-400">
              ~{stats.modified} modified
            </span>
          )}
          {stats.deleted > 0 && (
            <span className="text-red-600 dark:text-red-400">
              -{stats.deleted} deleted
            </span>
          )}
        </div>
      </div>

      {/* File Diffs */}
      <div>
        {enrichedFiles.map((file) => (
          <FileDiffView key={file.filePath} file={file} />
        ))}
      </div>
    </div>
  );
}
