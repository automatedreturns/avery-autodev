# AutoDev

Open-source AI coding agent that autonomously resolves GitHub issues, generates tests, and fixes CI failures.

## What It Does

- **Agent Execution** — Point AutoDev at a GitHub issue, it analyzes the codebase, writes code, and opens a PR
- **Test Generation** — Automatically generates unit tests for your code using AI
- **CI Self-Fix** — Detects CI failures and autonomously fixes them
- **Multi-Provider AI** — Works with Claude, OpenAI, Azure OpenAI, and Gemini
- **GitHub + GitLab** — Supports both platforms via git provider abstraction

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 20+
- Redis
- At least one AI API key (Anthropic recommended)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Add your API keys to .env

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### CLI

```bash
pip install autodev

# Run the agent on a GitHub issue
autodev run --repo owner/repo --issue 42

# Generate tests
autodev test --repo owner/repo --file src/utils.py

# Start the web server
autodev serve
```

### Docker

```bash
docker compose up
```

Open http://localhost:5173 for the dashboard, http://localhost:8000/docs for the API.

## Architecture

```
backend/
  app/                  # FastAPI application
    api/v1/             # REST API endpoints
    services/           # Core services (coder agent, test gen, CI fix)
    engine/plugins.py   # Plugin system for extensions
  avery_core/           # Public Python package API

frontend/               # React + TypeScript dashboard
```

### Plugin System

AutoDev includes an extension system. Create custom plugins to add functionality:

```python
from avery_core.engine.plugins import AveryPlugin, ExecutionContext, ExecutionUsage

class MyPlugin(AveryPlugin):
    def before_execute(self, ctx: ExecutionContext) -> ExecutionContext:
        print(f"Running: {ctx.action}")
        return ctx

    def after_execute(self, ctx, result, usage: ExecutionUsage):
        print(f"Used {usage.total_tokens} tokens")
```

Configure via environment variable:

```bash
AVERY_PLUGIN_CLASS=my_package.MyPlugin
```

## Configuration

Key environment variables (see `backend/.env.example` for full list):

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing key |
| `ANTHROPIC_API_KEY` | Yes* | Claude API key |
| `OPENAI_API_KEY` | No | OpenAI API key |
| `GEMINI_API_KEY` | No | Gemini API key |
| `DATABASE_URL` | No | Default: SQLite |

*At least one AI provider key is required.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/workspaces/{id}/tasks/{id}/execute` | Run the coding agent |
| GET | `/api/v1/workspaces` | List workspaces |
| POST | `/api/v1/test-generation/generate` | Generate tests |
| POST | `/api/v1/ci-runs/{id}/fix` | Auto-fix CI failure |
| GET | `/docs` | Interactive API docs |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT - see [LICENSE](LICENSE)
