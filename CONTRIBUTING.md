# Contributing to AutoDev

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.13+
- Node.js 20+
- Redis (for Celery background tasks)
- Git

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your API keys

# Run the server
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pytest
```

## How to Contribute

### Reporting Bugs

- Open an issue with a clear title and description
- Include steps to reproduce, expected vs actual behavior
- Include your Python version and OS

### Suggesting Features

- Open an issue with the `enhancement` label
- Describe the use case and why it would be valuable

### Pull Requests

1. Fork the repo and create a branch from `trunk`
2. Make your changes with clear commit messages
3. Add tests for new functionality
4. Ensure all tests pass (`pytest`)
5. Ensure code passes linting (`ruff check .`)
6. Submit a PR with a clear description of your changes

### Code Style

- Python: Follow PEP 8, enforced by `ruff`
- TypeScript: Follow the existing patterns in the codebase
- Keep changes focused — one feature or fix per PR

### Commit Messages

- Use present tense: "add feature" not "added feature"
- Keep the first line under 72 characters
- Reference issue numbers when applicable: "fix login redirect (#42)"

## Project Structure

```
backend/
  app/              # FastAPI application
    api/v1/         # API route handlers
    core/           # Config, security
    models/         # SQLAlchemy models
    services/       # Business logic
    engine/         # Plugin system
  avery_core/       # Public package API surface
  tests/            # Test suite

frontend/
  src/
    api/            # API client functions
    components/     # React components
    pages/          # Page components
    types/          # TypeScript types
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
