"""
Script to manually process attachments for existing workspace tasks.
Useful for retroactively processing attachments for tasks created before the feature was implemented.
"""
import sys
import os
import asyncio
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models.workspace_task import WorkspaceTask
from app.models.workspace import Workspace
from app.services.document_processor_service import document_processor
from app.services import github_service
from app.services.encryption_service import decrypt_token


async def process_task_attachments(task_id: int):
    """Process attachments for a specific task."""
    db = SessionLocal()

    try:
        # Get task and workspace
        task = db.query(WorkspaceTask).filter(WorkspaceTask.id == task_id).first()
        if not task:
            print(f"❌ Task {task_id} not found")
            return False

        workspace = db.query(Workspace).filter(Workspace.id == task.workspace_id).first()
        if not workspace:
            print(f"❌ Workspace {task.workspace_id} not found")
            return False

        print(f"\n📋 Processing Task #{task_id}")
        print(f"   Issue: #{task.github_issue_number} - {task.github_issue_title}")

        # Get GitHub token
        token = decrypt_token(workspace.github_token_encrypted)

        # Get issue details to get the body
        issue_details = github_service.get_issue_details(
            token, workspace.github_repository, task.github_issue_number
        )

        if issue_details.get("error"):
            print(f"❌ Error fetching issue: {issue_details['error']}")
            return False

        issue_body = issue_details.get("body", "")

        if not issue_body:
            print("⚠️  Issue has no body/description")
            return True

        print(f"📄 Issue body length: {len(issue_body)} characters")

        # Process attachments
        print("🔄 Processing attachments...")
        attachment_results = await document_processor.process_issue_attachments(
            workspace_task_id=task.id,
            issue_body=issue_body,
            github_token=token,
            workspace_id=workspace.id,
            task_id=task.id,
            db=db
        )

        # Save results
        task.attachments_metadata = json.dumps(attachment_results)
        task.attachments_processed_at = datetime.utcnow()
        db.commit()

        # Print results
        print(f"\n✅ Processing complete!")
        print(f"   Total attachments: {attachment_results['total_attachments']}")
        print(f"   Successfully processed: {attachment_results['successfully_processed']}")
        print(f"   Failed: {attachment_results['failed']}")
        print(f"   Status: {attachment_results['processing_status']}")
        print(f"   Time: {attachment_results['processing_time_ms']}ms")

        if attachment_results['errors']:
            print(f"\n⚠️  Errors:")
            for error in attachment_results['errors']:
                print(f"   - {error.get('filename', error.get('attachment_url', 'unknown'))}: {error.get('error')}")

        if attachment_results['attachments']:
            print(f"\n📎 Processed Attachments:")
            for att in attachment_results['attachments']:
                status = "✅" if att.get('processed') else "❌"
                print(f"   {status} {att['filename']} ({att['type']})")
                if att.get('ai_provider'):
                    print(f"      Provider: {att['ai_provider']} / {att['ai_model']}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


async def process_all_tasks():
    """Process attachments for all tasks that don't have them yet."""
    db = SessionLocal()

    try:
        # Get all tasks without attachment metadata
        tasks = db.query(WorkspaceTask).filter(
            WorkspaceTask.attachments_metadata.is_(None)
        ).all()

        print(f"\n🔍 Found {len(tasks)} tasks without attachment metadata")

        if not tasks:
            print("✅ All tasks already have attachment metadata!")
            return

        success_count = 0
        for task in tasks:
            result = await process_task_attachments(task.id)
            if result:
                success_count += 1

        print(f"\n🎉 Completed! Processed {success_count}/{len(tasks)} tasks successfully")

    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Process attachments for workspace tasks')
    parser.add_argument('--task-id', type=int, help='Process specific task ID')
    parser.add_argument('--all', action='store_true', help='Process all tasks without attachments')

    args = parser.parse_args()

    if args.task_id:
        asyncio.run(process_task_attachments(args.task_id))
    elif args.all:
        asyncio.run(process_all_tasks())
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/process_existing_task_attachments.py --task-id 2")
        print("  python scripts/process_existing_task_attachments.py --all")


if __name__ == "__main__":
    main()
