"""
PDF Processor - Extract text and structure from PDF documents
Handles: PDF files with text and tables
"""
import logging
import os
from typing import Dict, Any, Optional, List
import time

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Process PDF documents with text extraction and AI summarization"""

    def __init__(self, ai_service):
        """
        Initialize PDF processor.

        Args:
            ai_service: AIModelService instance for content analysis
        """
        self.ai_service = ai_service

    async def process(self, file_path: str) -> Dict[str, Any]:
        """
        Process PDF file with text extraction and AI analysis.

        Args:
            file_path: Path to PDF file

        Returns:
            {
                "filename": str,
                "type": str,
                "size_bytes": int,
                "page_count": int,
                "processed": bool,
                "ai_provider": str,
                "ai_model": str,
                "processing_time_ms": int,
                "extracted_content": {
                    "document_summary": str,
                    "key_requirements": list[str],
                    "technical_specs": dict,
                    "sections": list[dict],
                    "tables": list[dict],
                    "raw_text": str (truncated)
                },
                "error": Optional[str]
            }
        """
        start_time = time.time()

        result = {
            "filename": os.path.basename(file_path),
            "type": "application/pdf",
            "size_bytes": os.path.getsize(file_path),
            "page_count": 0,
            "processed": False,
            "ai_provider": "none",
            "ai_model": "none",
            "processing_time_ms": 0,
            "extracted_content": {
                "document_summary": "",
                "key_requirements": [],
                "technical_specs": {},
                "sections": [],
                "tables": [],
                "raw_text": ""
            },
            "error": None
        }

        try:
            # Extract text from PDF
            logger.info(f"Extracting text from PDF: {file_path}")
            extraction_result = await self._extract_text(file_path)

            if not extraction_result["success"]:
                result["error"] = extraction_result["error"]
                return result

            result["page_count"] = extraction_result["page_count"]
            raw_text = extraction_result["text"]
            result["extracted_content"]["tables"] = extraction_result.get("tables", [])

            # Store truncated raw text (first 2000 chars for reference)
            result["extracted_content"]["raw_text"] = raw_text[:2000] + ("..." if len(raw_text) > 2000 else "")

            # Use AI to analyze and structure the content
            logger.info(f"Analyzing PDF content with AI")
            analysis_result = await self._analyze_with_ai(raw_text, extraction_result["page_count"])

            if analysis_result["success"]:
                result["processed"] = True
                result["ai_provider"] = analysis_result["provider"]
                result["ai_model"] = analysis_result["model"]

                # Parse AI response
                parsed_content = self._parse_analysis_response(analysis_result["content"])
                result["extracted_content"].update(parsed_content)

                logger.info(f"Successfully processed PDF with {analysis_result['provider']}")
            else:
                # If AI fails, at least provide raw text
                result["processed"] = True
                result["error"] = f"AI analysis failed: {analysis_result.get('error')}, providing raw text only"
                result["extracted_content"]["document_summary"] = f"PDF document with {result['page_count']} pages. AI analysis unavailable."

        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {e}", exc_info=True)
            result["error"] = str(e)

        # Calculate processing time
        result["processing_time_ms"] = int((time.time() - start_time) * 1000)

        return result

    async def _extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text and tables from PDF.

        Args:
            file_path: Path to PDF file

        Returns:
            {
                "success": bool,
                "text": str,
                "page_count": int,
                "tables": list[dict],
                "error": Optional[str]
            }
        """
        try:
            import pdfplumber

            all_text = []
            all_tables = []
            page_count = 0

            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text
                    text = page.extract_text()
                    if text:
                        all_text.append(f"--- Page {page_num} ---\n{text}")

                    # Extract tables
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        all_tables.append({
                            "page": page_num,
                            "table_index": table_idx + 1,
                            "rows": len(table),
                            "columns": len(table[0]) if table else 0,
                            "data": table[:5]  # Store first 5 rows only
                        })

            combined_text = "\n\n".join(all_text)

            return {
                "success": True,
                "text": combined_text,
                "page_count": page_count,
                "tables": all_tables,
                "error": None
            }

        except ImportError as e:
            logger.error("pdfplumber not installed")
            # Fallback to PyPDF2
            return await self._extract_text_pypdf2(file_path)

        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return {
                "success": False,
                "text": "",
                "page_count": 0,
                "tables": [],
                "error": str(e)
            }

    async def _extract_text_pypdf2(self, file_path: str) -> Dict[str, Any]:
        """
        Fallback text extraction using PyPDF2.

        Args:
            file_path: Path to PDF file

        Returns:
            Extraction result
        """
        try:
            import PyPDF2

            all_text = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    if text:
                        all_text.append(f"--- Page {page_num} ---\n{text}")

            combined_text = "\n\n".join(all_text)

            return {
                "success": True,
                "text": combined_text,
                "page_count": page_count,
                "tables": [],
                "error": None
            }

        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            return {
                "success": False,
                "text": "",
                "page_count": 0,
                "tables": [],
                "error": str(e)
            }

    async def _analyze_with_ai(self, text: str, page_count: int) -> Dict[str, Any]:
        """
        Analyze PDF content with AI to extract structured information.

        Args:
            text: Extracted text from PDF
            page_count: Number of pages

        Returns:
            AI analysis result
        """
        # Truncate text if too long (keep first 15000 chars for context window)
        truncated_text = text[:15000]
        if len(text) > 15000:
            truncated_text += "\n\n[... content truncated ...]"

        prompt = f"""Analyze this PDF document ({page_count} pages) and extract structured information.

Provide:

1. DOCUMENT SUMMARY: Brief overview of what this document is about (2-3 sentences)

2. KEY REQUIREMENTS: List the main requirements, features, or action items mentioned
   - Focus on functional requirements
   - List technical requirements
   - Include any user stories or use cases

3. TECHNICAL SPECIFICATIONS: Extract any technical details
   - Technologies mentioned
   - System requirements
   - API specifications
   - Database schemas
   - Configuration details

4. SECTIONS: Identify main sections/chapters in the document
   - List section titles with brief description

5. IMPORTANT DETAILS: Any critical information like deadlines, priorities, constraints, or dependencies

Format your response clearly with headers for each section.
Be concise but comprehensive.
Focus on information that would help a developer implement the requirements."""

        return await self.ai_service.extract_text_content(
            text=truncated_text,
            prompt=prompt,
            max_tokens=3000
        )

    def _parse_analysis_response(self, content: str) -> Dict[str, Any]:
        """
        Parse AI analysis response into structured format.

        Args:
            content: Raw AI response

        Returns:
            Structured extracted content
        """
        result = {
            "document_summary": "",
            "key_requirements": [],
            "technical_specs": {},
            "sections": []
        }

        try:
            lines = content.split('\n')
            current_section = None
            current_subsection = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line_upper = line.upper()

                # Detect section headers
                if 'DOCUMENT SUMMARY' in line_upper or line_upper.startswith('1.'):
                    current_section = 'document_summary'
                    current_subsection = None
                    continue
                elif 'KEY REQUIREMENTS' in line_upper or line_upper.startswith('2.'):
                    current_section = 'key_requirements'
                    current_subsection = None
                    continue
                elif 'TECHNICAL SPEC' in line_upper or line_upper.startswith('3.'):
                    current_section = 'technical_specs'
                    current_subsection = None
                    continue
                elif 'SECTIONS' in line_upper or line_upper.startswith('4.'):
                    current_section = 'sections'
                    current_subsection = None
                    continue
                elif 'IMPORTANT DETAILS' in line_upper or line_upper.startswith('5.'):
                    current_section = 'important_details'
                    current_subsection = None
                    continue

                # Add content to appropriate section
                if current_section == 'document_summary':
                    if result['document_summary']:
                        result['document_summary'] += ' ' + line
                    else:
                        result['document_summary'] = line

                elif current_section == 'key_requirements':
                    clean_line = line.lstrip('-*•›→ 0123456789.)')
                    if clean_line:
                        result['key_requirements'].append(clean_line)

                elif current_section == 'technical_specs':
                    # Try to parse as key-value
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lstrip('-*•›→ 0123456789.)')
                        value = value.strip()
                        if key and value:
                            result['technical_specs'][key] = value
                    else:
                        clean_line = line.lstrip('-*•›→ 0123456789.)')
                        if clean_line:
                            result['technical_specs'][clean_line] = ""

                elif current_section == 'sections':
                    clean_line = line.lstrip('-*•›→ 0123456789.)')
                    if clean_line:
                        result['sections'].append(clean_line)

            # If parsing failed, put everything in summary
            if not result['document_summary'] and not any([
                result['key_requirements'],
                result['technical_specs'],
                result['sections']
            ]):
                result['document_summary'] = content

        except Exception as e:
            logger.warning(f"Error parsing PDF analysis: {e}")
            result['document_summary'] = content

        return result
