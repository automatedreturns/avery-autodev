"""
AI Model Service - Multi-provider AI with intelligent fallbacks
Supports: Azure OpenAI, OpenAI, Google Gemini, Anthropic Claude
"""
import os
import logging
import base64
from typing import Optional, Dict, Any, List, Literal
from enum import Enum
import httpx
from anthropic import Anthropic
from openai import AzureOpenAI, OpenAI
from app.core.config import settings
from app.engine.plugins import get_plugin

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    """Available AI providers"""
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"


class AIModelService:
    """
    Unified AI model service with automatic fallback handling.
    Uses the best model for each task type with graceful degradation.
    """

    def __init__(self):
        """Initialize all available AI clients"""
        self._plugin = get_plugin()
        self.azure_client = self._init_azure_openai()
        self.openai_client = self._init_openai()
        self.claude_client = self._init_claude()
        # Gemini uses direct HTTP API (no official Python SDK yet)
        self.gemini_api_key = self._plugin.resolve_api_key("gemini") or getattr(settings, 'GEMINI_API_KEY', None) or os.getenv("GEMINI_API_KEY")

        # Log which providers are available
        logger.info(f"AI Service initialized - Azure: {bool(self.azure_client)}, "
                   f"OpenAI: {bool(self.openai_client)}, "
                   f"Claude: {bool(self.claude_client)}, "
                   f"Gemini: {bool(self.gemini_api_key)}")

        # Model preferences for different tasks
        self.vision_preference = [
            AIProvider.CLAUDE,  # Claude 3.5 Sonnet has excellent vision
            AIProvider.GEMINI,  # Gemini 2.0 Flash has great vision
            AIProvider.AZURE_OPENAI,  # GPT-4 Vision
            AIProvider.OPENAI,  # GPT-4 Vision fallback
        ]

        self.text_extraction_preference = [
            AIProvider.AZURE_OPENAI,  # GPT-4 for structured extraction
            AIProvider.CLAUDE,  # Claude for long documents
            AIProvider.GEMINI,  # Gemini for speed
            AIProvider.OPENAI,  # OpenAI fallback
        ]

        self.summarization_preference = [
            AIProvider.CLAUDE,  # Claude excels at summarization
            AIProvider.AZURE_OPENAI,  # GPT-4 for quality
            AIProvider.GEMINI,  # Gemini for speed
            AIProvider.OPENAI,  # OpenAI fallback
        ]

    def _init_azure_openai(self) -> Optional[AzureOpenAI]:
        """Initialize Azure OpenAI client"""
        try:
            api_key = self._plugin.resolve_api_key("azure_openai") or getattr(settings, 'AZURE_OPENAI_API_KEY', None) or os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = getattr(settings, 'AZURE_OPENAI_ENDPOINT', None) or os.getenv("AZURE_OPENAI_ENDPOINT")
            api_version = getattr(settings, 'AZURE_OPENAI_API_VERSION', None) or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

            if api_key and endpoint:
                logger.info(f"Initializing Azure OpenAI with endpoint: {endpoint}")
                return AzureOpenAI(
                    api_key=api_key,
                    azure_endpoint=endpoint,
                    api_version=api_version
                )
            else:
                logger.info("Azure OpenAI not configured (missing API key or endpoint)")
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize Azure OpenAI: {e}")
            return None

    def _init_openai(self) -> Optional[OpenAI]:
        """Initialize OpenAI client"""
        try:
            api_key = self._plugin.resolve_api_key("openai") or getattr(settings, 'OPENAI_API_KEY', None) or os.getenv("OPENAI_API_KEY")
            if api_key:
                logger.info("Initializing OpenAI client")
                return OpenAI(api_key=api_key)
            else:
                logger.info("OpenAI not configured (missing API key)")
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI: {e}")
            return None

    def _init_claude(self) -> Optional[Anthropic]:
        """Initialize Anthropic Claude client"""
        try:
            # Try plugin first, then settings, then env var
            api_key = self._plugin.resolve_api_key("anthropic") or settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
            if api_key and api_key.strip():  # Check for empty strings
                logger.info("Initializing Claude client")
                return Anthropic(api_key=api_key)
            else:
                logger.info("Claude not configured (missing API key)")
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize Claude: {e}")
            return None

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        detail: Literal["low", "high", "auto"] = "high"
    ) -> Dict[str, Any]:
        """
        Analyze image using vision models with fallback.

        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            detail: Level of detail for analysis

        Returns:
            {
                "success": bool,
                "content": str,
                "provider": str,
                "model": str,
                "error": Optional[str]
            }
        """
        errors = []  # Collect all errors for better diagnostics

        for provider in self.vision_preference:
            try:
                if provider == AIProvider.CLAUDE and self.claude_client:
                    logger.info(f"Attempting image analysis with Claude")
                    result = await self._analyze_image_claude(image_path, prompt)
                    if result["success"]:
                        return result
                    errors.append(f"Claude: {result.get('error', 'Unknown error')}")
                elif provider == AIProvider.CLAUDE:
                    errors.append("Claude: Client not initialized (API key missing)")

                elif provider == AIProvider.GEMINI and self.gemini_api_key:
                    logger.info(f"Attempting image analysis with Gemini")
                    result = await self._analyze_image_gemini(image_path, prompt)
                    if result["success"]:
                        return result
                    errors.append(f"Gemini: {result.get('error', 'Unknown error')}")
                elif provider == AIProvider.GEMINI:
                    errors.append("Gemini: API key not set")

                elif provider == AIProvider.AZURE_OPENAI and self.azure_client:
                    logger.info(f"Attempting image analysis with Azure OpenAI")
                    result = await self._analyze_image_azure(image_path, prompt, detail)
                    if result["success"]:
                        return result
                    errors.append(f"Azure OpenAI: {result.get('error', 'Unknown error')}")
                elif provider == AIProvider.AZURE_OPENAI:
                    errors.append("Azure OpenAI: Client not initialized (API key missing)")

                elif provider == AIProvider.OPENAI and self.openai_client:
                    logger.info(f"Attempting image analysis with OpenAI")
                    result = await self._analyze_image_openai(image_path, prompt, detail)
                    if result["success"]:
                        return result
                    errors.append(f"OpenAI: {result.get('error', 'Unknown error')}")
                elif provider == AIProvider.OPENAI:
                    errors.append("OpenAI: Client not initialized (API key missing)")

            except Exception as e:
                logger.warning(f"Image analysis failed with {provider}: {e}")
                errors.append(f"{provider}: {str(e)}")
                continue

        error_msg = f"All vision models failed: {'; '.join(errors)}"
        logger.error(error_msg)

        return {
            "success": False,
            "content": "",
            "provider": "none",
            "model": "none",
            "error": error_msg
        }

    async def _analyze_image_claude(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Analyze image using Claude Vision"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            # Detect image type
            ext = image_path.lower().split('.')[-1]
            media_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            media_type = media_type_map.get(ext, 'image/jpeg')

            message = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }],
            )

            return {
                "success": True,
                "content": message.content[0].text,
                "provider": AIProvider.CLAUDE,
                "model": "claude-sonnet-4-5-20250929",
                "error": None
            }
        except Exception as e:
            logger.error(f"Claude vision analysis failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.CLAUDE,
                "model": "claude-sonnet-4-5-20250929",
                "error": str(e)
            }

    async def _analyze_image_gemini(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Analyze image using Google Gemini Vision"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_data
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 2048,
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                content = result["candidates"][0]["content"]["parts"][0]["text"]

                return {
                    "success": True,
                    "content": content,
                    "provider": AIProvider.GEMINI,
                    "model": "gemini-2.0-flash",
                    "error": None
                }
        except Exception as e:
            logger.error(f"Gemini vision analysis failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.GEMINI,
                "model": "gemini-2.0-flash",
                "error": str(e)
            }

    async def _analyze_image_azure(
        self,
        image_path: str,
        prompt: str,
        detail: str
    ) -> Dict[str, Any]:
        """Analyze image using Azure OpenAI Vision"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            ext = image_path.lower().split('.')[-1]
            mime_type = f"image/{ext}" if ext in ['jpeg', 'jpg', 'png', 'gif', 'webp'] else "image/jpeg"

            response = self.azure_client.chat.completions.create(
                model="gpt-4o",  # Azure deployment name
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}",
                                    "detail": detail
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "provider": AIProvider.AZURE_OPENAI,
                "model": "gpt-4o",
                "error": None
            }
        except Exception as e:
            logger.error(f"Azure OpenAI vision analysis failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.AZURE_OPENAI,
                "model": "gpt-4o",
                "error": str(e)
            }

    async def _analyze_image_openai(
        self,
        image_path: str,
        prompt: str,
        detail: str
    ) -> Dict[str, Any]:
        """Analyze image using OpenAI Vision"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            ext = image_path.lower().split('.')[-1]
            mime_type = f"image/{ext}" if ext in ['jpeg', 'jpg', 'png', 'gif', 'webp'] else "image/jpeg"

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}",
                                    "detail": detail
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "provider": AIProvider.OPENAI,
                "model": "gpt-4o",
                "error": None
            }
        except Exception as e:
            logger.error(f"OpenAI vision analysis failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.OPENAI,
                "model": "gpt-4o",
                "error": str(e)
            }

    async def extract_text_content(
        self,
        text: str,
        prompt: str,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Extract structured information from text using AI.

        Args:
            text: Source text to analyze
            prompt: Extraction instructions
            max_tokens: Maximum response tokens

        Returns:
            {
                "success": bool,
                "content": str,
                "provider": str,
                "model": str,
                "error": Optional[str]
            }
        """
        for provider in self.text_extraction_preference:
            try:
                if provider == AIProvider.AZURE_OPENAI and self.azure_client:
                    result = await self._extract_text_azure(text, prompt, max_tokens)
                    if result["success"]:
                        return result

                elif provider == AIProvider.CLAUDE and self.claude_client:
                    result = await self._extract_text_claude(text, prompt, max_tokens)
                    if result["success"]:
                        return result

                elif provider == AIProvider.GEMINI and self.gemini_api_key:
                    result = await self._extract_text_gemini(text, prompt, max_tokens)
                    if result["success"]:
                        return result

                elif provider == AIProvider.OPENAI and self.openai_client:
                    result = await self._extract_text_openai(text, prompt, max_tokens)
                    if result["success"]:
                        return result

            except Exception as e:
                logger.warning(f"Text extraction failed with {provider}: {e}")
                continue

        return {
            "success": False,
            "content": "",
            "provider": "none",
            "model": "none",
            "error": "All text extraction models failed"
        }

    async def _extract_text_azure(
        self,
        text: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text using Azure OpenAI"""
        try:
            response = self.azure_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting and structuring information from documents."
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n=== DOCUMENT CONTENT ===\n{text}"
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "provider": AIProvider.AZURE_OPENAI,
                "model": "gpt-4o",
                "error": None
            }
        except Exception as e:
            logger.error(f"Azure text extraction failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.AZURE_OPENAI,
                "model": "gpt-4o",
                "error": str(e)
            }

    async def _extract_text_claude(
        self,
        text: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text using Claude"""
        try:
            message = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=max_tokens,
                system="You are an expert at extracting and structuring information from documents.",
                messages=[{
                    "role": "user",
                    "content": f"{prompt}\n\n=== DOCUMENT CONTENT ===\n{text}"
                }],
                temperature=0.3
            )

            return {
                "success": True,
                "content": message.content[0].text,
                "provider": AIProvider.CLAUDE,
                "model": "claude-sonnet-4-5-20250929",
                "error": None
            }
        except Exception as e:
            logger.error(f"Claude text extraction failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.CLAUDE,
                "model": "claude-sonnet-4-5-20250929",
                "error": str(e)
            }

    async def _extract_text_gemini(
        self,
        text: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text using Gemini"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"{prompt}\n\n=== DOCUMENT CONTENT ===\n{text}"
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": max_tokens,
                },
                "systemInstruction": {
                    "parts": [{
                        "text": "You are an expert at extracting and structuring information from documents."
                    }]
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                content = result["candidates"][0]["content"]["parts"][0]["text"]

                return {
                    "success": True,
                    "content": content,
                    "provider": AIProvider.GEMINI,
                    "model": "gemini-2.0-flash",
                    "error": None
                }
        except Exception as e:
            logger.error(f"Gemini text extraction failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.GEMINI,
                "model": "gemini-2.0-flash",
                "error": str(e)
            }

    async def _extract_text_openai(
        self,
        text: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text using OpenAI"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting and structuring information from documents."
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n=== DOCUMENT CONTENT ===\n{text}"
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "provider": AIProvider.OPENAI,
                "model": "gpt-4o",
                "error": None
            }
        except Exception as e:
            logger.error(f"OpenAI text extraction failed: {e}")
            return {
                "success": False,
                "content": "",
                "provider": AIProvider.OPENAI,
                "model": "gpt-4o",
                "error": str(e)
            }


# Global instance
ai_service = AIModelService()
