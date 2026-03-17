"""
Video Processor - Extract keyframes and analyze with Vision AI
Handles: MP4, MOV, WebM (screen recordings, bug reproductions)
"""
import logging
import os
from typing import Dict, Any, Optional, List
import time

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Process videos by extracting keyframes and analyzing with Vision AI"""

    def __init__(self, ai_service):
        """
        Initialize video processor.

        Args:
            ai_service: AIModelService instance for frame analysis
        """
        self.ai_service = ai_service
        self.max_duration_seconds = 300  # 5 minutes max
        self.keyframe_interval_seconds = 15  # Extract frame every 15 seconds

    async def process(self, file_path: str) -> Dict[str, Any]:
        """
        Process video file by extracting and analyzing keyframes.

        Args:
            file_path: Path to video file

        Returns:
            {
                "filename": str,
                "type": str,
                "size_bytes": int,
                "duration_seconds": float,
                "keyframes_extracted": int,
                "processed": bool,
                "ai_provider": str,
                "ai_model": str,
                "processing_time_ms": int,
                "extracted_content": {
                    "video_summary": str,
                    "timeline": list[dict],
                    "identified_bug": dict,
                    "key_actions": list[str]
                },
                "error": Optional[str]
            }
        """
        start_time = time.time()

        result = {
            "filename": os.path.basename(file_path),
            "type": self._get_mime_type(file_path),
            "size_bytes": os.path.getsize(file_path),
            "duration_seconds": 0,
            "keyframes_extracted": 0,
            "processed": False,
            "ai_provider": "none",
            "ai_model": "none",
            "processing_time_ms": 0,
            "extracted_content": {
                "video_summary": "",
                "timeline": [],
                "identified_bug": {},
                "key_actions": []
            },
            "error": None
        }

        try:
            # Extract keyframes from video
            logger.info(f"Extracting keyframes from video: {file_path}")
            extraction_result = await self._extract_keyframes(file_path)

            if not extraction_result["success"]:
                result["error"] = extraction_result["error"]
                return result

            result["duration_seconds"] = extraction_result["duration"]
            result["keyframes_extracted"] = len(extraction_result["frames"])

            # Analyze each keyframe with Vision AI
            logger.info(f"Analyzing {len(extraction_result['frames'])} keyframes with AI")
            timeline = []

            for frame_info in extraction_result["frames"]:
                frame_analysis = await self.ai_service.analyze_image(
                    image_path=frame_info["path"],
                    prompt=f"""Analyze this video frame (timestamp: {frame_info['timestamp']}s).

Describe:
1. What is happening in this frame
2. Any UI elements or screen content visible
3. Any text, errors, or messages displayed
4. User actions or interactions visible
5. Any issues or bugs apparent

Be concise but specific. Focus on technical details that would help understand what's happening in the video.""",
                    detail="high"
                )

                if frame_analysis["success"]:
                    timeline.append({
                        "timestamp": self._format_timestamp(frame_info["timestamp"]),
                        "timestamp_seconds": frame_info["timestamp"],
                        "frame_file": frame_info["filename"],
                        "description": frame_analysis["content"][:500],  # Truncate long descriptions
                        "ai_provider": frame_analysis["provider"]
                    })

            result["extracted_content"]["timeline"] = timeline

            # Use AI to create overall summary and identify bugs
            if timeline:
                summary_result = await self._create_summary(timeline, result["duration_seconds"])
                if summary_result["success"]:
                    result["processed"] = True
                    result["ai_provider"] = summary_result["provider"]
                    result["ai_model"] = summary_result["model"]
                    result["extracted_content"]["video_summary"] = summary_result["summary"]
                    result["extracted_content"]["identified_bug"] = summary_result.get("identified_bug", {})
                    result["extracted_content"]["key_actions"] = summary_result.get("key_actions", [])
                else:
                    result["processed"] = True
                    result["extracted_content"]["video_summary"] = f"Video showing {len(timeline)} key moments over {int(result['duration_seconds'])} seconds"
            else:
                result["error"] = "No keyframes could be analyzed"

        except Exception as e:
            logger.error(f"Error processing video {file_path}: {e}", exc_info=True)
            result["error"] = str(e)

        # Calculate processing time
        result["processing_time_ms"] = int((time.time() - start_time) * 1000)

        return result

    async def _extract_keyframes(self, file_path: str) -> Dict[str, Any]:
        """
        Extract keyframes from video at regular intervals.

        Args:
            file_path: Path to video file

        Returns:
            {
                "success": bool,
                "duration": float,
                "frames": list[dict],
                "error": Optional[str]
            }
        """
        try:
            import cv2

            # Open video
            video = cv2.VideoCapture(file_path)

            if not video.isOpened():
                return {
                    "success": False,
                    "duration": 0,
                    "frames": [],
                    "error": "Could not open video file"
                }

            # Get video properties
            fps = video.get(cv2.CAP_PROP_FPS)
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            # Check duration limit
            if duration > self.max_duration_seconds:
                logger.warning(f"Video duration {duration}s exceeds max {self.max_duration_seconds}s, truncating")
                duration = self.max_duration_seconds

            # Calculate frame extraction points
            frames_to_extract = []
            current_time = 0
            while current_time <= duration:
                frame_number = int(current_time * fps)
                if frame_number < total_frames:
                    frames_to_extract.append({
                        "timestamp": current_time,
                        "frame_number": frame_number
                    })
                current_time += self.keyframe_interval_seconds

            # Extract frames
            extracted_frames = []
            temp_dir = os.path.join(os.path.dirname(file_path), "frames")
            os.makedirs(temp_dir, exist_ok=True)

            for frame_info in frames_to_extract:
                video.set(cv2.CAP_PROP_POS_FRAMES, frame_info["frame_number"])
                ret, frame = video.read()

                if ret:
                    # Save frame
                    frame_filename = f"frame_{int(frame_info['timestamp']):04d}.jpg"
                    frame_path = os.path.join(temp_dir, frame_filename)
                    cv2.imwrite(frame_path, frame)

                    extracted_frames.append({
                        "timestamp": frame_info["timestamp"],
                        "filename": frame_filename,
                        "path": frame_path
                    })

            video.release()

            return {
                "success": True,
                "duration": duration,
                "frames": extracted_frames,
                "error": None
            }

        except ImportError:
            logger.error("opencv-python not installed")
            return {
                "success": False,
                "duration": 0,
                "frames": [],
                "error": "opencv-python library not installed"
            }

        except Exception as e:
            logger.error(f"Keyframe extraction failed: {e}")
            return {
                "success": False,
                "duration": 0,
                "frames": [],
                "error": str(e)
            }

    async def _create_summary(self, timeline: List[Dict], duration: float) -> Dict[str, Any]:
        """
        Create overall summary from timeline using AI.

        Args:
            timeline: List of analyzed frames with timestamps
            duration: Total video duration

        Returns:
            Summary result with identified bugs and actions
        """
        # Build timeline text
        timeline_text = "\n\n".join([
            f"[{frame['timestamp']}] {frame['description']}"
            for frame in timeline
        ])

        prompt = f"""Analyze this video timeline from a screen recording ({len(timeline)} keyframes, {int(duration)}s duration).

Timeline:
{timeline_text}

Provide:

1. VIDEO SUMMARY: Brief overview of what happens in the video (2-3 sentences)

2. KEY ACTIONS: List the main user actions or events in chronological order

3. IDENTIFIED BUG (if applicable): If this appears to be a bug reproduction video, describe:
   - Type of bug
   - Description of the issue
   - Steps to reproduce
   - Root cause hypothesis (if apparent)

4. IMPORTANT OBSERVATIONS: Any technical details that would help a developer understand the issue

Format your response clearly with headers."""

        analysis_result = await self.ai_service.extract_text_content(
            text=timeline_text[:10000],  # Truncate if too long
            prompt=prompt,
            max_tokens=2000
        )

        if analysis_result["success"]:
            parsed = self._parse_summary_response(analysis_result["content"])
            return {
                "success": True,
                "provider": analysis_result["provider"],
                "model": analysis_result["model"],
                "summary": parsed["summary"],
                "key_actions": parsed["key_actions"],
                "identified_bug": parsed["identified_bug"]
            }
        else:
            return {
                "success": False,
                "error": analysis_result.get("error")
            }

    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        """Parse AI summary response into structured format."""
        result = {
            "summary": "",
            "key_actions": [],
            "identified_bug": {}
        }

        try:
            lines = content.split('\n')
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line_upper = line.upper()

                if 'VIDEO SUMMARY' in line_upper or line_upper.startswith('1.'):
                    current_section = 'summary'
                    continue
                elif 'KEY ACTIONS' in line_upper or line_upper.startswith('2.'):
                    current_section = 'key_actions'
                    continue
                elif 'IDENTIFIED BUG' in line_upper or line_upper.startswith('3.'):
                    current_section = 'identified_bug'
                    continue

                if current_section == 'summary':
                    if result['summary']:
                        result['summary'] += ' ' + line
                    else:
                        result['summary'] = line

                elif current_section == 'key_actions':
                    clean_line = line.lstrip('-*•›→ 0123456789.)')
                    if clean_line:
                        result['key_actions'].append(clean_line)

                elif current_section == 'identified_bug':
                    # Store bug description
                    if not result['identified_bug'].get('description'):
                        result['identified_bug']['description'] = line
                    else:
                        result['identified_bug']['description'] += ' ' + line

        except Exception as e:
            logger.warning(f"Error parsing video summary: {e}")
            result['summary'] = content

        return result

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type from file extension."""
        ext = file_path.lower().split('.')[-1]
        mime_types = {
            'mp4': 'video/mp4',
            'mov': 'video/quicktime',
            'webm': 'video/webm',
            'avi': 'video/x-msvideo',
            'mkv': 'video/x-matroska'
        }
        return mime_types.get(ext, 'video/unknown')
