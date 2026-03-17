# Automatic Issue Polling & Linking

Avery Developer automatically monitors your GitHub repositories for new issues labeled with `avery-developer` and creates task links for them.

## How It Works

1. **Background Polling**: The backend runs a background scheduler that polls all workspaces every 5 minutes
2. **Label Detection**: Looks for GitHub issues with the `avery-developer` label
3. **Auto-Linking**: Automatically creates WorkspaceTask links for new issues
4. **Deduplication**: Skips issues that are already linked to avoid duplicates

## Setup

### 1. Label Your GitHub Issues

Add the label `avery-developer` to any GitHub issue you want to be automatically linked to your workspace:

```bash
# Via GitHub CLI
gh issue edit 123 --add-label "avery-developer"

# Via GitHub Web UI
# Go to issue → Labels → Add "avery-developer"
```

### 2. Background Polling (Automatic)

The background scheduler starts automatically when the backend server starts. It polls every 5 minutes by default.

**To change the polling interval**, edit `backend/app/main.py`:

```python
# Change from 5 to your desired interval (in minutes)
start_scheduler(poll_interval_minutes=5)
```

### 3. Manual Polling (Optional)

You can also trigger polling manually via API:

**Poll a specific workspace:**
```bash
POST /api/v1/workspaces/{workspace_id}/poll-issues
Authorization: Bearer <your-token>
```

**Poll all workspaces (admin):**
```bash
POST /api/v1/workspaces/poll-all-workspaces
Authorization: Bearer <your-token>
```

**Response:**
```json
{
  "success": true,
  "issues_found": 5,
  "issues_linked": 3,
  "issues_skipped": 2,
  "error": null
}
```

## Database Migration

If you're upgrading from a previous version, run the migration:

```bash
cd backend
sqlite3 app.db < migrations/001_add_last_issue_poll.sql
```

Or the database will be automatically updated on next startup (SQLAlchemy auto-creates new columns).

## Monitoring

Check the backend logs to monitor polling activity:

```bash
tail -f logs/backend.log | grep "issue polling"
```

You'll see entries like:
```
INFO: Starting issue polling task...
INFO: Issue polling complete: 3 workspaces polled, 2 issues auto-linked
INFO: Next poll in 5 minutes
```

## Troubleshooting

### Issues Not Being Linked

1. **Check the label**: Ensure issue has exact label `avery-developer` (case-sensitive)
2. **Check GitHub token**: Workspace owner must have GitHub account connected
3. **Check repository**: Issue must be in the workspace's configured repository
4. **Check issue state**: Only open issues are polled (closed issues are ignored)

### Polling Errors

Check backend logs for error messages:
```bash
tail -f logs/backend.log | grep ERROR
```

Common issues:
- GitHub API rate limiting (wait or use authenticated requests)
- Invalid GitHub token (reconnect GitHub account)
- Network connectivity issues

## Workflow Example

1. Create a GitHub issue in your repository
2. Add the label `avery-developer` to the issue
3. Wait up to 5 minutes (or trigger manual poll)
4. The issue automatically appears in your workspace's task list
5. The Coding Agent automatically analyzes the issue and provides an approach

## API Endpoints

### Poll Workspace Issues
```
POST /api/v1/workspaces/{workspace_id}/poll-issues
```

**Response:**
```typescript
{
  success: boolean;
  issues_found: number;
  issues_linked: number;
  issues_skipped: number;
  error: string | null;
}
```

### Poll All Workspaces
```
POST /api/v1/workspaces/poll-all-workspaces
```

**Response:**
```typescript
{
  success: boolean;
  workspaces_polled: number;
  total_issues_linked: number;
  errors: string[];
}
```

## Configuration

The polling behavior can be configured in `backend/app/services/issue_poller_service.py`:

- `label_filter`: Change the label to look for (default: `"avery-developer"`)
- `state`: Change issue state filter (default: `"open"`)
- `per_page`: Adjust how many issues to fetch per request (default: `100`)

## Security

- Only workspace members can trigger manual polling for their workspaces
- Background polling uses workspace owner's GitHub token
- Issues are only linked if they belong to the workspace's configured repository
- Duplicate detection prevents the same issue from being linked multiple times
