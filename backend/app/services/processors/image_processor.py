"""
Image Processor - Process images with Vision AI and OCR fallback
Handles: PNG, JPG, JPEG, GIF, WebP
"""
import logging
import os
from typing import Dict, Any, Optional
from PIL import Image
import base64

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Process images using Vision AI with OCR fallback"""

    def __init__(self, ai_service):
        """
        Initialize image processor.

        Args:
            ai_service: AIModelService instance for vision analysis
        """
        self.ai_service = ai_service

    async def process(self, file_path: str) -> Dict[str, Any]:
        """
        Process image file with AI vision analysis.

        Args:
            file_path: Path to image file

        Returns:
            {
                "filename": str,
                "type": str,
                "size_bytes": int,
                "dimensions": str,
                "processed": bool,
                "ai_provider": str,
                "ai_model": str,
                "processing_time_ms": int,
                "extracted_content": {
                    "visual_description": str,
                    "detected_text": list[str],
                    "ui_elements": list[str],
                    "identified_issues": list[str],
                    "key_insights": list[str]
                },
                "error": Optional[str]
            }
        """
        import time
        start_time = time.time()

        result = {
            "filename": os.path.basename(file_path),
            "type": self._get_mime_type(file_path),
            "size_bytes": os.path.getsize(file_path),
            "dimensions": None,
            "processed": False,
            "ai_provider": "none",
            "ai_model": "none",
            "processing_time_ms": 0,
            "extracted_content": {
                "visual_description": "",
                "detected_text": [],
                "ui_elements": [],
                "identified_issues": [],
                "key_insights": []
            },
            "error": None
        }

        try:
            # Get image dimensions
            with Image.open(file_path) as img:
                result["dimensions"] = f"{img.width}x{img.height}"

            # Perform AI vision analysis
            logger.info(f"Starting AI vision analysis for {file_path}")
            analysis_result = await self._analyze_with_vision_ai(file_path)

            if analysis_result["success"]:
                result["processed"] = True
                result["ai_provider"] = analysis_result["provider"]
                result["ai_model"] = analysis_result["model"]

                # Parse AI response into structured format
                parsed_content = self._parse_vision_response(analysis_result["content"])
                result["extracted_content"] = parsed_content

                logger.info(f"Successfully processed image with {analysis_result['provider']}")
            else:
                # Fallback to OCR if vision AI fails
                logger.warning(f"Vision AI failed: {analysis_result.get('error')}, attempting OCR fallback")
                ocr_result = await self._ocr_fallback(file_path)

                if ocr_result["success"]:
                    result["processed"] = True
                    result["ai_provider"] = "tesseract_ocr"
                    result["ai_model"] = "tesseract"
                    result["extracted_content"]["detected_text"] = ocr_result["text"]
                    result["extracted_content"]["visual_description"] = "OCR text extraction only (Vision AI unavailable)"
                else:
                    result["error"] = f"Both Vision AI and OCR failed: {ocr_result.get('error')}"

        except Exception as e:
            logger.error(f"Error processing image {file_path}: {e}", exc_info=True)
            result["error"] = str(e)

        # Calculate processing time
        result["processing_time_ms"] = int((time.time() - start_time) * 1000)

        return result

    async def _analyze_with_vision_ai(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze image using AI vision models.

        Args:
            file_path: Path to image file

        Returns:
            AI analysis result with success status
        """
        prompt = """Analyze this image in detail and provide:

1. VISUAL DESCRIPTION: Describe what you see in the image (UI elements, layout, content, etc.)

2. DETECTED TEXT: List any text visible in the image (buttons, labels, error messages, etc.)

3. UI ELEMENTS: Identify UI components (buttons, inputs, forms, navigation, etc.)

4. IDENTIFIED ISSUES: List any bugs, errors, or problems visible in the image (misalignment, cut-off elements, errors, etc.)

5. KEY INSIGHTS: Important observations that would help a developer understand what needs to be implemented or fixed

Format your response as structured text with clear sections.
If this is a screenshot of a bug, focus on describing the issue clearly.
If this is a design mockup, focus on the layout and components.
If this is an error message, focus on the error details."""

        return await self.ai_service.analyze_image(
            image_path=file_path,
            prompt=prompt,
            detail="high"
        )

    def _parse_vision_response(self, content: str) -> Dict[str, Any]:
        """
        Parse AI vision response into structured format.

        Args:
            content: Raw AI response text

        Returns:
            Structured extracted content
        """
        result = {
            "visual_description": "",
            "detected_text": [],
            "ui_elements": [],
            "identified_issues": [],
            "key_insights": []
        }

        try:
            # Simple parsing - look for sections in the response
            lines = content.split('\n')
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Detect section headers
                line_upper = line.upper()
                if 'VISUAL DESCRIPTION' in line_upper or line_upper.startswith('1.'):
                    current_section = 'visual_description'
                    continue
                elif 'DETECTED TEXT' in line_upper or line_upper.startswith('2.'):
                    current_section = 'detected_text'
                    continue
                elif 'UI ELEMENTS' in line_upper or line_upper.startswith('3.'):
                    current_section = 'ui_elements'
                    continue
                elif 'IDENTIFIED ISSUES' in line_upper or line_upper.startswith('4.'):
                    current_section = 'identified_issues'
                    continue
                elif 'KEY INSIGHTS' in line_upper or line_upper.startswith('5.'):
                    current_section = 'key_insights'
                    continue

                # Add content to current section
                if current_section:
                    if current_section == 'visual_description':
                        if result['visual_description']:
                            result['visual_description'] += ' ' + line
                        else:
                            result['visual_description'] = line
                    else:
                        # For list sections, add as list items
                        # Remove bullet points, numbers, dashes
                        clean_line = line.lstrip('-*•›→ 0123456789.)')
                        if clean_line:
                            result[current_section].append(clean_line)

            # If parsing failed to find sections, put everything in visual_description
            if not result['visual_description'] and not any([
                result['detected_text'],
                result['ui_elements'],
                result['identified_issues'],
                result['key_insights']
            ]):
                result['visual_description'] = content

        except Exception as e:
            logger.warning(f"Error parsing vision response: {e}")
            # Fallback: put entire content in visual description
            result['visual_description'] = content

        return result

    async def _ocr_fallback(self, file_path: str) -> Dict[str, Any]:
        """
        Fallback OCR using Tesseract if Vision AI fails.

        Args:
            file_path: Path to image file

        Returns:
            {
                "success": bool,
                "text": list[str],
                "error": Optional[str]
            }
        """
        try:
            import pytesseract
            from PIL import Image

            # Open and process image
            img = Image.open(file_path)

            # Extract text
            text = pytesseract.image_to_string(img)

            # Split into lines and clean
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            return {
                "success": True,
                "text": lines,
                "error": None
            }

        except ImportError:
            logger.warning("pytesseract not installed, OCR fallback unavailable")
            return {
                "success": False,
                "text": [],
                "error": "pytesseract not installed"
            }
        except Exception as e:
            logger.error(f"OCR fallback failed: {e}")
            return {
                "success": False,
                "text": [],
                "error": str(e)
            }

    def _get_mime_type(self, file_path: str) -> str:
        """
        Get MIME type from file extension.

        Args:
            file_path: Path to file

        Returns:
            MIME type string
        """
        ext = file_path.lower().split('.')[-1]
        mime_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
            'svg': 'image/svg+xml'
        }
        return mime_types.get(ext, 'image/unknown')
