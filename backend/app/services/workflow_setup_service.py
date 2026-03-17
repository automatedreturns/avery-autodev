"""
Workflow Setup Service

Automatically installs/updates GitHub Actions workflow in workspace repositories.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.workspace import Workspace
from app.services import github_service

logger = logging.getLogger(__name__)


class WorkflowSetupService:
    """Service for managing GitHub Actions workflows in workspace repositories."""

    WORKFLOW_FILENAME = ".github/workflows/avery-ci-integration.yml"

    def __init__(self, db: Session):
        self.db = db

    def get_workflow_template(self, workspace: Workspace, avery_webhook_url: str) -> str:
        """
        Generate workflow YAML content for a workspace.

        Args:
            workspace: Workspace model instance
            avery_webhook_url: Base URL for Avery webhook

        Returns:
            Workflow YAML content as string
        """
        # Detect project type based on repo structure
        # For now, assume Python/pytest (can be enhanced later)

        workflow_content = f"""name: Avery CI Integration

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches:
      - {workspace.github_main_branch}
      - {workspace.github_dev_branch}

jobs:
  test-and-coverage:
    name: Test & Coverage Analysis
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; fi
          if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi
          pip install pytest pytest-cov

      - name: Run tests with coverage
        id: tests
        continue-on-error: true
        run: |
          pytest --cov=. --cov-report=json --cov-report=html --cov-report=term
          echo "status=$?" >> $GITHUB_OUTPUT

      - name: Extract coverage data
        if: always()
        id: coverage
        run: |
          if [ -f coverage.json ]; then
            COVERAGE=$(jq -r '.totals.percent_covered // 0' coverage.json)
            LINES_COVERED=$(jq -r '.totals.covered_lines // 0' coverage.json)
            LINES_TOTAL=$(jq -r '.totals.num_statements // 0' coverage.json)
            echo "coverage_percent=$COVERAGE" >> $GITHUB_OUTPUT
            echo "lines_covered=$LINES_COVERED" >> $GITHUB_OUTPUT
            echo "lines_total=$LINES_TOTAL" >> $GITHUB_OUTPUT
            echo "✅ Coverage: $COVERAGE% ($LINES_COVERED/$LINES_TOTAL lines)"

            # Save coverage JSON for webhook - compress to single line to avoid heredoc issues
            COVERAGE_JSON=$(jq -c '.' coverage.json)
            echo "coverage_json=$COVERAGE_JSON" >> $GITHUB_OUTPUT
          else
            echo "⚠️ No coverage.json found"
            echo "coverage_percent=0" >> $GITHUB_OUTPUT
            echo "lines_covered=0" >> $GITHUB_OUTPUT
            echo "lines_total=0" >> $GITHUB_OUTPUT
            echo "coverage_json={{}}" >> $GITHUB_OUTPUT
          fi

      - name: Upload coverage artifacts
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-report
          path: |
            htmlcov/
            coverage.json

      - name: Send results to Avery
        if: always()
        run: |
          # Create payload file to avoid argument length limits
          # Set PR number to null if 0 (push events)
          PR_NUMBER=${{{{ github.event.pull_request.number || 'null' }}}}

          cat > /tmp/avery_payload.json <<PAYLOAD_EOF
          {{
            "workspace_id": {workspace.id},
            "pr_number": $PR_NUMBER,
            "run_id": "${{{{ github.run_id }}}}",
            "job_name": "test-and-coverage",
            "status": "completed",
            "conclusion": "${{{{ steps.tests.outcome }}}}",
            "repository": "${{{{ github.repository }}}}",
            "branch": "${{{{ github.head_ref || github.ref_name }}}}",
            "commit_sha": "${{{{ github.event.pull_request.head.sha || github.sha }}}}",
            "check_results": {{
              "tests": "${{{{ steps.tests.outcome }}}}"
            }},
            "coverage": {{
              "percent": ${{{{ steps.coverage.outputs.coverage_percent }}}},
              "lines_covered": ${{{{ steps.coverage.outputs.lines_covered }}}},
              "lines_total": ${{{{ steps.coverage.outputs.lines_total }}}},
              "coverage_json": ${{{{ steps.coverage.outputs.coverage_json }}}}
            }}
          }}
          PAYLOAD_EOF

          curl -X POST "{avery_webhook_url}/api/v1/ci/webhook" \\
            -H "Content-Type: application/json" \\
            -H "Authorization: Bearer ${{{{ secrets.AVERY_API_TOKEN }}}}" \\
            --data @/tmp/avery_payload.json
        continue-on-error: true
"""
        return workflow_content

    def check_workflow_exists(self, workspace: Workspace, github_token: str) -> bool:
        """
        Check if workflow file exists in the repository.

        Args:
            workspace: Workspace instance
            github_token: GitHub access token

        Returns:
            True if workflow exists, False otherwise
        """
        try:
            result = github_service.get_file_content(
                token=github_token,
                repo=workspace.github_repository,
                branch=workspace.github_dev_branch,
                file_path=self.WORKFLOW_FILENAME,
            )
            return result.get("content") is not None and result.get("error") is None
        except Exception as e:
            logger.info(f"Workflow not found in {workspace.github_repository}: {e}")
            return False

    def setup_workflow(
        self,
        workspace: Workspace,
        github_token: str,
        avery_webhook_url: str,
        force_update: bool = False,
    ) -> dict:
        """
        Setup or update the Avery CI workflow in the workspace repository.

        Args:
            workspace: Workspace instance
            github_token: GitHub access token
            avery_webhook_url: Base URL for Avery webhook
            force_update: If True, update workflow even if it exists

        Returns:
            Dict with status and details
        """
        try:
            # Check if workflow already exists
            workflow_exists = self.check_workflow_exists(workspace, github_token)

            if workflow_exists and not force_update:
                logger.info(f"Workflow already exists in {workspace.github_repository}")
                return {
                    "status": "exists",
                    "message": "Workflow already configured",
                    "path": self.WORKFLOW_FILENAME,
                }

            # Generate workflow content
            workflow_content = self.get_workflow_template(workspace, avery_webhook_url)

            # Create or update the workflow file
            commit_message = (
                "chore: Update Avery CI integration workflow"
                if workflow_exists
                else "chore: Add Avery CI integration workflow"
            )

            # Get current file SHA if updating
            file_sha = None
            if workflow_exists:
                try:
                    existing_file = github_service.get_file_content(
                        token=github_token,
                        repo=workspace.github_repository,
                        branch=workspace.github_dev_branch,
                        file_path=self.WORKFLOW_FILENAME,
                    )
                    if existing_file and "sha" in existing_file:
                        file_sha = existing_file["sha"]
                except Exception as e:
                    logger.warning(f"Could not get existing file SHA: {e}")

            # Create or update file via GitHub API
            result = github_service.create_or_update_file(
                token=github_token,
                repo=workspace.github_repository,
                branch=workspace.github_dev_branch,
                file_path=self.WORKFLOW_FILENAME,
                content=workflow_content,
                message=commit_message,
                sha=file_sha,
            )

            if not result.get("success"):
                return {"status": "error", "message": result.get("error", "Unknown error")}

            logger.info(
                f"Successfully {'updated' if workflow_exists else 'created'} workflow in {workspace.github_repository}"
            )

            return {
                "status": "updated" if workflow_exists else "created",
                "message": f"Workflow {'updated' if workflow_exists else 'created'} successfully",
                "path": self.WORKFLOW_FILENAME,
                "commit": result.get("commit_sha"),
            }

        except Exception as e:
            logger.error(f"Failed to setup workflow for {workspace.github_repository}: {e}")
            return {"status": "error", "message": str(e)}

    def get_setup_instructions(self, workspace: Workspace, api_token: str, webhook_url: str) -> dict:
        """
        Get setup instructions for manual configuration.

        Args:
            workspace: Workspace instance
            api_token: API token for this workspace
            webhook_url: Webhook URL

        Returns:
            Dict with setup instructions
        """
        return {
            "workflow_path": self.WORKFLOW_FILENAME,
            "secrets_to_add": [
                {
                    "name": "AVERY_API_TOKEN",
                    "value": api_token,
                    "description": "Authentication token for Avery webhook",
                }
            ],
            "instructions": [
                f"1. The workflow file has been added to {workspace.github_repository}",
                "2. Add the following GitHub secret to your repository:",
                "   - Go to Settings → Secrets and variables → Actions",
                f"   - Add secret 'AVERY_API_TOKEN' with the provided token",
                "3. The workflow will run automatically on pull requests",
            ],
            "webhook_url": webhook_url,
        }
