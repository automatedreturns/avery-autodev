"""
Test for document processor extension detection from Content-Type headers.
This addresses the issue where GitHub clipboard images (screenshots) are uploaded
with UUIDs but no file extensions.
"""
import pytest
from app.services.document_processor_service import DocumentProcessorService


class TestExtensionDetection:
    """Test extension detection from MIME types"""

    def setup_method(self):
        """Initialize document processor service"""
        self.service = DocumentProcessorService()

    def test_mime_to_extension_mapping_exists(self):
        """Verify MIME type to extension mapping is configured"""
        assert hasattr(self.service, 'mime_to_extension')
        assert len(self.service.mime_to_extension) > 0

    def test_image_mime_types(self):
        """Test image MIME type mappings"""
        assert self.service.mime_to_extension.get('image/png') == 'png'
        assert self.service.mime_to_extension.get('image/jpeg') == 'jpg'
        assert self.service.mime_to_extension.get('image/gif') == 'gif'
        assert self.service.mime_to_extension.get('image/webp') == 'webp'
        assert self.service.mime_to_extension.get('image/bmp') == 'bmp'

    def test_document_mime_types(self):
        """Test document MIME type mappings"""
        assert self.service.mime_to_extension.get('application/pdf') == 'pdf'
        assert self.service.mime_to_extension.get(
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ) == 'docx'

    def test_video_mime_types(self):
        """Test video MIME type mappings"""
        assert self.service.mime_to_extension.get('video/mp4') == 'mp4'
        assert self.service.mime_to_extension.get('video/quicktime') == 'mov'
        assert self.service.mime_to_extension.get('video/webm') == 'webm'
        assert self.service.mime_to_extension.get('video/x-msvideo') == 'avi'

    def test_detect_file_type_with_extension(self):
        """Test file type detection when extension is present"""
        assert self.service._detect_file_type('/path/to/image.png') == 'image'
        assert self.service._detect_file_type('/path/to/document.pdf') == 'pdf'
        assert self.service._detect_file_type('/path/to/document.docx') == 'docx'
        assert self.service._detect_file_type('/path/to/video.mp4') == 'video'

    def test_detect_file_type_without_extension(self):
        """Test file type detection when no extension is present"""
        # Without extension, should return "unknown"
        assert self.service._detect_file_type('/path/to/abc123def456') == 'unknown'
        assert self.service._detect_file_type('/path/to/clipboard-item') == 'unknown'

    def test_github_clipboard_image_scenario(self):
        """
        Test realistic scenario: GitHub clipboard image URL without extension.

        GitHub clipboard images URLs look like:
        https://github.com/user-attachments/assets/abc123def456

        When downloaded:
        1. URL has no extension
        2. Filename extracted is 'abc123def456' (no extension)
        3. HTTP response has Content-Type: image/png
        4. Extension should be added during download: 'abc123def456.png'
        5. File type detection should work on final file: 'image'
        """
        # Simulating filename extraction from GitHub URL
        github_url = "https://github.com/user-attachments/assets/abc123def456"
        filename = github_url.split('/')[-1]  # 'abc123def456'

        # Verify no extension
        assert '.' not in filename

        # Simulate Content-Type detection
        content_type = 'image/png'
        detected_ext = self.service.mime_to_extension.get(content_type.lower())
        assert detected_ext == 'png'

        # Final filename after extension is added
        final_filename = f"{filename}.{detected_ext}"
        assert final_filename == 'abc123def456.png'

        # Verify file type detection works on final file
        file_type = self.service._detect_file_type(f'/tmp/uploads/{final_filename}')
        assert file_type == 'image'

    def test_sanitize_filename_preserves_extension(self):
        """Test that filename sanitization preserves extensions"""
        # Test with various filenames
        assert '.png' in self.service._sanitize_filename('image.png')
        assert '.pdf' in self.service._sanitize_filename('document.pdf')
        assert '.docx' in self.service._sanitize_filename('spec.docx')

    def test_extension_detection_edge_cases(self):
        """Test edge cases for extension detection"""
        # File with multiple dots
        assert self.service._detect_file_type('/path/to/my.file.name.png') == 'image'

        # File with uppercase extension
        assert self.service._detect_file_type('/path/to/IMAGE.PNG') == 'image'

        # File with mixed case
        assert self.service._detect_file_type('/path/to/Document.PDF') == 'pdf'
