# Extension Detection for GitHub Clipboard Images

## Problem
GitHub clipboard images (screenshots pasted with Ctrl+V/Cmd+V) are uploaded to GitHub's CDN with URLs that have NO file extensions, such as:
```
https://github.com/user-attachments/assets/abc123-def456-...
```

This caused the document processor to fail because:
1. The URL has no extension
2. The extracted filename has no extension (e.g., `abc123-def456`)
3. File type detection relied solely on file extensions
4. Files were saved without extensions and couldn't be processed

## Solution
Implemented **Content-Type header detection** during file download:

### Changes Made

1. **Added MIME type to extension mapping** (lines 46-60)
   - Maps common MIME types to file extensions
   - Covers images (PNG, JPEG, GIF, WebP, BMP)
   - Covers documents (PDF, DOCX)
   - Covers videos (MP4, MOV, WebM, AVI)

2. **Enhanced `_download_attachment()` method** (lines 344-356, 385-393)
   - Checks if filename is missing an extension
   - Reads `Content-Type` header from HTTP response
   - Automatically appends appropriate extension based on MIME type
   - Works for both authenticated and public downloads
   - Logs detected extensions for debugging

3. **Improved `_detect_file_type()` method** (lines 607-628)
   - More robust extension extraction using `os.path.basename()`
   - Better handling of edge cases (no extension, multiple dots)
   - Added warning logging for debugging
   - Case-insensitive extension matching

4. **Comprehensive test suite** (`tests/test_document_processor_extension_detection.py`)
   - Tests MIME type mappings
   - Tests file type detection with/without extensions
   - Tests realistic GitHub clipboard image scenario
   - Tests edge cases (multiple dots, uppercase extensions, etc.)
   - All 9 tests passing ✓

## How It Works

### Before (Failed)
```
1. URL: https://github.com/user-attachments/assets/abc123
2. Extracted filename: abc123 (no extension)
3. Saved as: /tmp/uploads/abc123 (no extension)
4. File type detection: "unknown" (no extension to detect)
5. Processing: FAILED ❌
```

### After (Success)
```
1. URL: https://github.com/user-attachments/assets/abc123
2. Extracted filename: abc123 (no extension)
3. HTTP download: Content-Type: image/png
4. Extension detected: .png
5. Saved as: /tmp/uploads/abc123.png ✓
6. File type detection: "image" ✓
7. Processing: SUCCESS ✅
```

## Benefits
- ✅ Handles GitHub clipboard images (screenshots)
- ✅ Works with any extensionless file URL
- ✅ Maintains backward compatibility (files with extensions work as before)
- ✅ Robust error handling and logging
- ✅ Comprehensive test coverage
- ✅ Zero breaking changes to existing functionality

## Testing
Run tests with:
```bash
python -m pytest tests/test_document_processor_extension_detection.py -v
```

## Related Issues
- GitHub clipboard images have no file extensions in URLs
- Files uploaded via paste operations often lack extensions
- Content-Type headers provide reliable file type information
