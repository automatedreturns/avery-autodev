"""
Document Processor Service - Main orchestrator for processing GitHub issue attachments
Handles: detection, download, routing, and compilation of all attachment types
"""
import logging
import os
import re
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from sqlalchemy.orm import Session

from app.services.ai_model_service import ai_service
from app.services.processors.image_processor import ImageProcessor
from app.services.processors.pdf_processor import PDFProcessor
from app.services.processors.docx_processor import DOCXProcessor
from app.services.processors.video_processor import VideoProcessor

logger = logging.getLogger(__name__)


class DocumentProcessorService:
    """Main service for processing all types of document attachments from GitHub issues"""

    def __init__(self):
        """Initialize document processor with all specialized processors"""
        self.image_processor = ImageProcessor(ai_service)
        self.pdf_processor = PDFProcessor(ai_service)
        self.docx_processor = DOCXProcessor(ai_service)
        self.video_processor = VideoProcessor(ai_service)

        # File size limits (in bytes)
        self.max_file_size = 50 * 1024 * 1024  # 50 MB
        self.max_attachments = 10  # Max attachments per issue

        # Supported file types
        self.supported_extensions = {
            'image': ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'],
            'pdf': ['pdf'],
            'docx': ['docx'],
            'video': ['mp4', 'mov', 'webm', 'avi']
        }

        # MIME type to extension mapping (for files without extensions)
        self.mime_to_extension = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/gif': 'gif',
            'image/webp': 'webp',
            'image/bmp': 'bmp',
            'application/pdf': 'pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'video/mp4': 'mp4',
            'video/quicktime': 'mov',
            'video/webm': 'webm',
            'video/x-msvideo': 'avi'
        }

    async def process_issue_attachments(
        self,
        workspace_task_id: int,
        issue_body: str,
        github_token: str,
        workspace_id: int,
        task_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Main entry point for processing all attachments in a GitHub issue.

        Args:
            workspace_task_id: Database ID of the workspace task
            issue_body: GitHub issue body (markdown)
            github_token: GitHub API token for authenticated downloads
            workspace_id: Workspace ID
            task_id: Task ID
            db: Database session

        Returns:
            {
                "attachments": list[dict],  # Processed attachment results
                "processing_status": "completed" | "partial" | "failed",
                "processing_started_at": str (ISO8601),
                "processing_completed_at": str (ISO8601),
                "processing_time_ms": int,
                "total_attachments": int,
                "successfully_processed": int,
                "failed": int,
                "errors": list[dict]
            }
        """
        start_time = time.time()
        started_at = datetime.utcnow().isoformat()

        result = {
            "attachments": [],
            "processing_status": "failed",
            "processing_started_at": started_at,
            "processing_completed_at": None,
            "processing_time_ms": 0,
            "total_attachments": 0,
            "successfully_processed": 0,
            "failed": 0,
            "errors": []
        }

        try:
            # Extract attachment URLs from issue body
            logger.info(f"Extracting attachments from issue for task {workspace_task_id}")
            attachment_urls = self.extract_attachment_urls(issue_body)

            result["total_attachments"] = len(attachment_urls)

            if len(attachment_urls) > self.max_attachments:
                logger.warning(f"Issue has {len(attachment_urls)} attachments, limiting to {self.max_attachments}")
                attachment_urls = attachment_urls[:self.max_attachments]
                result["total_attachments"] = self.max_attachments

            if not attachment_urls:
                logger.info("No attachments found in issue")
                result["processing_status"] = "completed"
                result["processing_completed_at"] = datetime.utcnow().isoformat()
                result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                return result

            # Create storage directory
            storage_dir = self._get_storage_path(workspace_id, task_id)
            os.makedirs(storage_dir, exist_ok=True)

            # Process each attachment
            for idx, url_info in enumerate(attachment_urls):
                try:
                    logger.info(f"Processing attachment {idx + 1}/{len(attachment_urls)}: {url_info['url']}")

                    # Download attachment
                    download_result = await self._download_attachment(
                        url=url_info['url'],
                        storage_dir=storage_dir,
                        filename=url_info['filename'],
                        github_token=github_token
                    )

                    if not download_result["success"]:
                        result["failed"] += 1
                        result["errors"].append({
                            "attachment_url": url_info['url'],
                            "filename": url_info['filename'],
                            "error": download_result["error"]
                        })
                        continue

                    file_path = download_result["file_path"]
                    file_type = self._detect_file_type(file_path)

                    # Route to appropriate processor
                    processing_result = await self._process_attachment(file_path, file_type)

                    # Add URL and original filename to result
                    processing_result["url"] = url_info['url']
                    processing_result["downloaded_path"] = file_path

                    if processing_result.get("processed"):
                        result["successfully_processed"] += 1
                    else:
                        result["failed"] += 1

                    result["attachments"].append(processing_result)

                except Exception as e:
                    logger.error(f"Error processing attachment {url_info['url']}: {e}", exc_info=True)
                    result["failed"] += 1
                    result["errors"].append({
                        "attachment_url": url_info['url'],
                        "filename": url_info.get('filename', 'unknown'),
                        "error": str(e)
                    })

            # Determine overall status
            if result["successfully_processed"] == result["total_attachments"]:
                result["processing_status"] = "completed"
            elif result["successfully_processed"] > 0:
                result["processing_status"] = "partial"
            else:
                result["processing_status"] = "failed"

        except Exception as e:
            logger.error(f"Error in process_issue_attachments: {e}", exc_info=True)
            result["processing_status"] = "failed"
            result["errors"].append({
                "error": f"Processing pipeline error: {str(e)}"
            })

        # Finalize result
        result["processing_completed_at"] = datetime.utcnow().isoformat()
        result["processing_time_ms"] = int((time.time() - start_time) * 1000)

        logger.info(f"Attachment processing completed: {result['successfully_processed']}/{result['total_attachments']} successful")

        return result

    def extract_attachment_urls(self, markdown_text: str) -> List[Dict[str, str]]:
        """
        Extract all attachment URLs from GitHub issue markdown.

        Args:
            markdown_text: GitHub issue body (markdown format)

        Returns:
            List of dicts with 'url' and 'filename' keys
        """
        attachments = []

        if not markdown_text:
            return attachments

        # Pattern 1: Markdown image syntax: ![alt](url)
        markdown_image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        for match in re.finditer(markdown_image_pattern, markdown_text):
            alt_text = match.group(1)
            url = match.group(2)
            filename = self._extract_filename_from_url(url) or f"image_{len(attachments) + 1}"
            attachments.append({
                "url": url,
                "filename": filename,
                "alt_text": alt_text
            })

        # Pattern 2: Markdown link syntax (for PDFs, DOCX, videos): [text](url)
        markdown_link_pattern = r'(?<!!)\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(markdown_link_pattern, markdown_text):
            link_text = match.group(1)
            url = match.group(2)

            # Check if URL points to supported file type
            ext = self._get_extension_from_url(url)
            if ext and any(ext in exts for exts in self.supported_extensions.values()):
                filename = self._extract_filename_from_url(url) or link_text
                attachments.append({
                    "url": url,
                    "filename": filename,
                    "link_text": link_text
                })

        # Pattern 3: HTML img tags: <img src="url">
        html_img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        for match in re.finditer(html_img_pattern, markdown_text):
            url = match.group(1)
            filename = self._extract_filename_from_url(url) or f"image_{len(attachments) + 1}"
            attachments.append({
                "url": url,
                "filename": filename
            })

        # Pattern 4: Direct URLs to GitHub user-attachments
        github_attachment_pattern = r'(https://(?:github\.com|user-attachments\.githubusercontent\.com)/[^\s<>)"\']+)'
        for match in re.finditer(github_attachment_pattern, markdown_text):
            url = match.group(1)
            # Avoid duplicates
            if not any(a['url'] == url for a in attachments):
                ext = self._get_extension_from_url(url)
                if ext and any(ext in exts for exts in self.supported_extensions.values()):
                    filename = self._extract_filename_from_url(url) or f"file_{len(attachments) + 1}.{ext}"
                    attachments.append({
                        "url": url,
                        "filename": filename
                    })

        logger.info(f"Extracted {len(attachments)} attachments from issue body")
        return attachments

    async def _download_attachment(
        self,
        url: str,
        storage_dir: str,
        filename: str,
        github_token: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Download attachment from URL with retry logic.
        Automatically detects file extension from Content-Type header if missing.

        Args:
            url: URL to download from
            storage_dir: Directory to save file
            filename: Filename to save as
            github_token: GitHub token for authentication
            max_retries: Maximum retry attempts

        Returns:
            {
                "success": bool,
                "file_path": str,
                "error": Optional[str]
            }
        """
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        file_path = os.path.join(storage_dir, safe_filename)

        # GitHub requires different auth headers for different URL types
        headers = {
            "User-Agent": "Avery-Document-Processor",
            "Accept": "application/octet-stream"
        }

        # Special handling for GitHub user-attachments URLs
        # These are public CDN URLs that don't require authentication
        is_user_attachment = "github.com/user-attachments" in url

        # For GitHub API URLs and private repo content (not user-attachments)
        if "github.com" in url or "githubusercontent.com" in url:
            headers["Authorization"] = f"Bearer {github_token}"

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=60.0,
                    follow_redirects=True,
                    max_redirects=10
                ) as client:
                    # For user-attachments, try without auth first (they're usually public CDN links)
                    if is_user_attachment and attempt == 0:
                        response = await client.get(url, headers={
                            "User-Agent": "Avery-Document-Processor",
                            "Accept": "application/octet-stream"
                        })
                    else:
                        response = await client.get(url, headers=headers)
                    response.raise_for_status()

                    # Check file size
                    content_length = int(response.headers.get('content-length', 0))
                    if content_length > self.max_file_size:
                        return {
                            "success": False,
                            "file_path": None,
                            "error": f"File size {content_length} bytes exceeds limit of {self.max_file_size} bytes"
                        }

                    # Check if filename has extension, if not, detect from Content-Type
                    final_file_path = file_path
                    if '.' not in safe_filename or safe_filename.endswith('.'):
                        content_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
                        if content_type in self.mime_to_extension:
                            detected_ext = self.mime_to_extension[content_type]
                            # Remove trailing dot if present
                            base_filename = safe_filename.rstrip('.')
                            final_file_path = os.path.join(storage_dir, f"{base_filename}.{detected_ext}")
                            logger.info(f"Added extension '.{detected_ext}' based on Content-Type: {content_type}")
                        else:
                            logger.warning(f"Could not detect extension for Content-Type: {content_type}")

                    # Save file
                    with open(final_file_path, 'wb') as f:
                        f.write(response.content)

                    logger.info(f"Successfully downloaded {os.path.basename(final_file_path)} ({len(response.content)} bytes)")

                    return {
                        "success": True,
                        "file_path": final_file_path,
                        "error": None
                    }

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error downloading {url} (attempt {attempt + 1}/{max_retries}): {e}")

                # Special handling for 404 errors on non-user-attachment GitHub URLs
                if e.response.status_code == 404 and attempt == 0 and not is_user_attachment:
                    # Try without Authorization header for non-user-attachment URLs
                    try:
                        logger.info(f"Retrying {url} without authentication")
                        headers_public = {
                            "User-Agent": "Avery-Document-Processor",
                            "Accept": "application/octet-stream"
                        }
                        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                            response = await client.get(url, headers=headers_public)
                            response.raise_for_status()

                            # Check if filename has extension, if not, detect from Content-Type
                            final_file_path = file_path
                            if '.' not in safe_filename or safe_filename.endswith('.'):
                                content_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
                                if content_type in self.mime_to_extension:
                                    detected_ext = self.mime_to_extension[content_type]
                                    base_filename = safe_filename.rstrip('.')
                                    final_file_path = os.path.join(storage_dir, f"{base_filename}.{detected_ext}")
                                    logger.info(f"Added extension '.{detected_ext}' based on Content-Type: {content_type}")

                            with open(final_file_path, 'wb') as f:
                                f.write(response.content)

                            logger.info(f"Successfully downloaded {os.path.basename(final_file_path)} without auth ({len(response.content)} bytes)")
                            return {
                                "success": True,
                                "file_path": final_file_path,
                                "error": None
                            }
                    except:
                        pass  # Continue with normal retry logic

                if attempt == max_retries - 1:
                    error_msg = f"HTTP {e.response.status_code}: {str(e)}"
                    if e.response.status_code == 404:
                        if is_user_attachment:
                            error_msg += " (GitHub user-attachment not found. Possible causes: 1) Attachment was deleted from GitHub, 2) Attachment is in an issue comment not the issue body, 3) URL has expired)"
                        else:
                            error_msg += " (Resource not found. Check if the URL is valid and accessible)"
                    return {
                        "success": False,
                        "file_path": None,
                        "error": error_msg
                    }

            except Exception as e:
                logger.warning(f"Error downloading {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "file_path": None,
                        "error": str(e)
                    }

            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                await self._async_sleep(2 ** attempt)

        return {
            "success": False,
            "file_path": None,
            "error": "Max retries exceeded"
        }

    async def _process_attachment(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Route attachment to appropriate processor based on file type.

        Args:
            file_path: Path to downloaded file
            file_type: Detected file type (image, pdf, docx, video)

        Returns:
            Processing result from appropriate processor
        """
        try:
            if file_type == 'image':
                return await self.image_processor.process(file_path)
            elif file_type == 'pdf':
                return await self.pdf_processor.process(file_path)
            elif file_type == 'docx':
                return await self.docx_processor.process(file_path)
            elif file_type == 'video':
                return await self.video_processor.process(file_path)
            else:
                return {
                    "filename": os.path.basename(file_path),
                    "type": "unknown",
                    "processed": False,
                    "error": f"Unsupported file type: {file_type}"
                }

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            return {
                "filename": os.path.basename(file_path),
                "type": file_type,
                "processed": False,
                "error": str(e)
            }

    def compile_agent_context(self, attachments: List[Dict[str, Any]]) -> str:
        """
        Compile processed attachments into formatted context for agent.

        Args:
            attachments: List of processed attachment results

        Returns:
            Formatted string ready for agent context
        """
        if not attachments:
            return ""

        context_parts = ["=== ATTACHED DOCUMENTS ===\n"]

        image_count = 0
        pdf_count = 0
        docx_count = 0
        video_count = 0

        for attachment in attachments:
            if not attachment.get("processed"):
                continue

            file_type = attachment.get("type", "unknown")
            filename = attachment.get("filename", "unknown")
            extracted = attachment.get("extracted_content", {})

            # Images
            if file_type.startswith("image/"):
                image_count += 1
                context_parts.append(f"\n📷 Image {image_count}: {filename}")

                if extracted.get("dimensions"):
                    context_parts.append(f"   Dimensions: {extracted['dimensions']}")

                if extracted.get("visual_description"):
                    context_parts.append(f"   Visual Analysis: {extracted['visual_description'][:300]}")

                if extracted.get("detected_text"):
                    text_items = extracted['detected_text'][:10]  # Limit to 10 items
                    context_parts.append(f"   Detected Text: {', '.join(text_items)}")

                if extracted.get("identified_issues"):
                    context_parts.append(f"   Identified Issues:")
                    for issue in extracted['identified_issues'][:5]:
                        context_parts.append(f"     • {issue}")

                if extracted.get("key_insights"):
                    context_parts.append(f"   Key Insights:")
                    for insight in extracted['key_insights'][:5]:
                        context_parts.append(f"     • {insight}")

            # PDFs
            elif file_type == "application/pdf":
                pdf_count += 1
                context_parts.append(f"\n📄 PDF {pdf_count}: {filename}")

                if attachment.get("page_count"):
                    context_parts.append(f"   Pages: {attachment['page_count']}")

                if extracted.get("document_summary"):
                    context_parts.append(f"   Summary: {extracted['document_summary'][:300]}")

                if extracted.get("key_requirements"):
                    context_parts.append(f"   Key Requirements:")
                    for req in extracted['key_requirements'][:10]:
                        context_parts.append(f"     • {req}")

                if extracted.get("technical_specs"):
                    context_parts.append(f"   Technical Specifications:")
                    for key, value in list(extracted['technical_specs'].items())[:5]:
                        context_parts.append(f"     • {key}: {value}")

            # DOCX
            elif "wordprocessingml" in file_type:
                docx_count += 1
                context_parts.append(f"\n📝 DOCX {docx_count}: {filename}")

                if extracted.get("document_type"):
                    context_parts.append(f"   Type: {extracted['document_type']}")

                if extracted.get("summary"):
                    context_parts.append(f"   Summary: {extracted['summary'][:300]}")

                if extracted.get("main_points"):
                    context_parts.append(f"   Main Points:")
                    for point in extracted['main_points'][:10]:
                        context_parts.append(f"     • {point}")

                if extracted.get("action_items"):
                    context_parts.append(f"   Action Items:")
                    for item in extracted['action_items'][:10]:
                        context_parts.append(f"     • {item}")

                if extracted.get("test_scenarios"):
                    context_parts.append(f"   Test Scenarios: {len(extracted['test_scenarios'])} scenarios")

            # Videos
            elif file_type.startswith("video/"):
                video_count += 1
                context_parts.append(f"\n🎥 Video {video_count}: {filename}")

                if attachment.get("duration_seconds"):
                    duration = int(attachment['duration_seconds'])
                    context_parts.append(f"   Duration: {duration // 60:02d}:{duration % 60:02d}")

                if extracted.get("video_summary"):
                    context_parts.append(f"   Summary: {extracted['video_summary'][:300]}")

                if extracted.get("timeline"):
                    context_parts.append(f"   Timeline:")
                    for frame in extracted['timeline'][:8]:  # Limit to 8 frames
                        context_parts.append(f"     [{frame['timestamp']}] {frame['description'][:150]}")

                if extracted.get("identified_bug"):
                    bug = extracted['identified_bug']
                    if bug.get("description"):
                        context_parts.append(f"   Identified Bug: {bug['description'][:200]}")

        context_parts.append("\n=== END ATTACHED DOCUMENTS ===\n")

        return "\n".join(context_parts)

    def _get_storage_path(self, workspace_id: int, task_id: int) -> str:
        """Get storage path for attachments"""
        # Get base path from environment or use default
        base_path = os.getenv("REPOS_BASE_PATH", "/tmp/repos")
        uploads_path = os.path.join(os.path.dirname(base_path), "uploads")
        return os.path.join(uploads_path, f"workspace-{workspace_id}", f"task-{task_id}")

    def _detect_file_type(self, file_path: str) -> str:
        """
        Detect file type from extension.
        Returns file type category (image, pdf, docx, video) or "unknown".
        """
        # Extract extension from file path
        filename = os.path.basename(file_path).lower()

        # Check if file has an extension
        if '.' not in filename:
            logger.warning(f"File has no extension: {file_path}")
            return "unknown"

        ext = filename.split('.')[-1]

        # Match against supported extensions
        for file_type, extensions in self.supported_extensions.items():
            if ext in extensions:
                return file_type

        logger.warning(f"Unsupported file extension: {ext}")
        return "unknown"

    def _get_extension_from_url(self, url: str) -> Optional[str]:
        """Extract file extension from URL"""
        # Remove query parameters
        url_path = url.split('?')[0]
        # Get extension
        if '.' in url_path:
            ext = url_path.split('.')[-1].lower()
            return ext
        return None

    def _extract_filename_from_url(self, url: str) -> Optional[str]:
        """Extract filename from URL"""
        # Remove query parameters
        url_path = url.split('?')[0]
        # Get filename
        if '/' in url_path:
            filename = url_path.split('/')[-1]
            return filename
        return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be safe for filesystem"""
        # Remove/replace unsafe characters
        safe = re.sub(r'[^\w\s\-\.]', '_', filename)
        # Remove multiple consecutive underscores/spaces
        safe = re.sub(r'[_\s]+', '_', safe)
        # Limit length
        if len(safe) > 100:
            name, ext = os.path.splitext(safe)
            safe = name[:95] + ext
        return safe

    async def _async_sleep(self, seconds: float):
        """Async sleep helper"""
        import asyncio
        await asyncio.sleep(seconds)


# Global instance
document_processor = DocumentProcessorService()
