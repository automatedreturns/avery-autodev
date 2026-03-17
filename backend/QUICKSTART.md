# AutoDev - Quickstart

AutoDev is an open-source AI coding agent that autonomously fixes GitHub issues, generates tests, and self-heals CI failures.

## Install

```bash
pip install autodev
```

Or from source:

```bash
git clone https://github.com/your-org/autodev.git
cd autodev/backend
pip install -e .
```

## Configure

Set your API keys in `.env` or as environment variables:

```bash
# Required: at least one AI provider
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...

# Required: GitHub token with repo scope
export GITHUB_TOKEN=ghp_...

# Required: app secret (any random string)
export SECRET_KEY=your-secret-key-here
```

## CLI Usage

### Fix a GitHub issue

```bash
autodev run --repo owner/repo --issue 42 --branch main
```

This will:
1. Fetch the issue details
2. Analyze your repository structure
3. Generate code changes with Claude
4. Create a branch and draft PR

### Start the web server

```bash
autodev serve --port 8000
```

Then open `http://localhost:8000/docs` for the API explorer.

### Check version

```bash
autodev version
```

## Docker

```bash
docker-compose up -d
```

This starts the API server, Redis, and Celery worker.

## Extending with Plugins

AutoDev uses a plugin system. The default (Community Edition) plugin provides:
- API keys from environment variables
- Unlimited access to all features
- No-op lifecycle hooks

To create a custom plugin (e.g., for a hosted platform):

```python
from avery_core.engine.plugins import AveryPlugin, ExecutionContext, ExecutionUsage

class MyPlugin(AveryPlugin):
    def resolve_api_key(self, provider: str) -> str:
        return my_key_pool.get_next_key(provider)

    def check_access(self, user_id: str, action: str) -> bool:
        return my_billing.has_credits(user_id, action)

    def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        hold = my_billing.reserve_credits(context.user_id, context.action)
        context.metadata["hold_id"] = hold.id
        return context

    def after_execute(self, context: ExecutionContext, result: dict, usage: ExecutionUsage):
        my_billing.settle(context.metadata["hold_id"], usage.total_tokens)
```

Activate it via environment variable:

```bash
export AVERY_PLUGIN_CLASS=my_package.plugin.MyPlugin
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/{workspace_id}/tasks/{task_id}/execute-agent` | Run coder agent |
| `GET /api/v1/{workspace_id}/tasks/{task_id}/agent-status` | Check agent status |
| `GET /api/v1/dashboard/extras` | Plugin dashboard widgets |
| `GET /health` | Health check |
| `GET /docs` | Swagger UI |

## Architecture

```
autodev/
  app/                  # FastAPI server
    api/v1/             # REST endpoints
    core/               # Config, auth, permissions
    engine/             # Plugin system
      plugins.py        # AveryPlugin base class
    models/             # SQLAlchemy models
    services/           # Business logic
      coder_agent_service.py
      test_generator_service.py
      ci_self_fix_service.py
      ai_model_service.py
  avery_core/           # Public package API
    cli.py              # CLI entry point
    engine/             # Re-exports plugin system
    services/           # Re-exports services
```

## License

MIT
