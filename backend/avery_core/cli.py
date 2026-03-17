"""
AutoDev CLI - Command-line interface for the AutoDev coding agent.

Usage:
    autodev run --repo owner/repo --issue 42 --branch dev
    autodev fix --repo owner/repo --ci-run 12345
    autodev serve
    autodev version
"""

import argparse
import os
import sys


def cmd_run(args: argparse.Namespace) -> None:
    """Execute the coder agent on a GitHub issue."""
    from app.engine.plugins import load_plugin
    from app.services.coder_agent_service import execute_coder_agent
    from app.services.git_providers import get_git_provider

    load_plugin()

    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required. Pass --token or set GITHUB_TOKEN env var.")
        sys.exit(1)

    provider_name = args.provider or "github"
    git_provider = get_git_provider(provider_name)

    print(f"Running coder agent on {args.repo} issue #{args.issue} (branch: {args.branch})...")

    result = execute_coder_agent(
        token=token,
        repo=args.repo,
        base_branch=args.branch,
        issue_number=args.issue,
        user_context=args.context or "",
        git_provider=git_provider,
    )

    if result["success"]:
        print(f"Success! PR created: {result['pr_url']}")
        print(f"  Branch: {result['branch_name']}")
        print(f"  PR #{result['pr_number']}")
    else:
        print(f"Failed: {result['error']}")
        sys.exit(1)


def cmd_fix(args: argparse.Namespace) -> None:
    """Analyze and fix a CI failure (stub - requires DB context)."""
    print("CI self-fix via CLI is not yet supported.")
    print("Use the web API: POST /api/v1/ci/self-fix")
    print(f"  --repo {args.repo}")
    print(f"  --ci-run {args.ci_run}")
    sys.exit(1)


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the AutoDev API server."""
    import uvicorn

    host = args.host or "0.0.0.0"
    port = args.port or 8000
    reload = args.reload

    print(f"Starting AutoDev server on {host}:{port} (reload={reload})...")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


def cmd_version(_args: argparse.Namespace) -> None:
    """Print version info."""
    from avery_core import __version__

    edition = os.getenv("AVERY_EDITION", "ce")
    print(f"autodev {__version__} ({edition})")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="autodev",
        description="AutoDev - AI coding agent for GitHub issues",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # autodev run
    run_parser = subparsers.add_parser("run", help="Execute coder agent on a GitHub issue")
    run_parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    run_parser.add_argument("--issue", required=True, type=int, help="Issue number")
    run_parser.add_argument("--branch", default="main", help="Base branch (default: main)")
    run_parser.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN)")
    run_parser.add_argument("--context", help="Additional context for the agent")
    run_parser.add_argument("--provider", default="github", help="Git provider: github or gitlab")
    run_parser.set_defaults(func=cmd_run)

    # avery fix
    fix_parser = subparsers.add_parser("fix", help="Fix a CI failure")
    fix_parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    fix_parser.add_argument("--ci-run", required=True, help="CI run ID")
    fix_parser.set_defaults(func=cmd_fix)

    # avery serve
    serve_parser = subparsers.add_parser("serve", help="Start the Avery API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.set_defaults(func=cmd_serve)

    # avery version
    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=cmd_version)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
