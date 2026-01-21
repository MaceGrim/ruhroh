"""Security utilities for input validation and sanitization."""

import re
import html
from typing import BinaryIO

import magic
import structlog

from app.exceptions import ValidationException

logger = structlog.get_logger()

# Allowed MIME types for file uploads
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "txt",
}

# Maximum file size (500MB)
MAX_FILE_SIZE = 500 * 1024 * 1024


def sanitize_html(text: str) -> str:
    """
    Remove HTML tags from text while preserving content.

    Args:
        text: Input text that may contain HTML

    Returns:
        Text with HTML tags stripped
    """
    if not text:
        return ""

    # First, decode HTML entities
    text = html.unescape(text)

    # Remove script and style elements completely
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def validate_file_upload(
    file_content: bytes | BinaryIO,
    filename: str,
    file_size: int | None = None,
) -> str:
    """
    Validate uploaded file for allowed type and size.

    Args:
        file_content: File content as bytes or file-like object
        filename: Original filename
        file_size: Size in bytes (calculated if not provided)

    Returns:
        Detected file type extension

    Raises:
        ValidationException: If file fails validation
    """
    # Get content as bytes if needed
    if hasattr(file_content, "read"):
        content = file_content.read(2048)
        file_content.seek(0)
    else:
        content = file_content[:2048] if len(file_content) > 2048 else file_content

    # Calculate size if not provided
    if file_size is None:
        if hasattr(file_content, "seek") and hasattr(file_content, "tell"):
            current_pos = file_content.tell()
            file_content.seek(0, 2)  # Seek to end
            file_size = file_content.tell()
            file_content.seek(current_pos)  # Restore position
        else:
            file_size = len(file_content)

    # Check file size
    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        logger.warning(
            "File too large",
            filename=filename,
            size_mb=file_size / (1024 * 1024),
            max_mb=max_mb,
        )
        raise ValidationException(
            message=f"File size exceeds maximum of {max_mb}MB",
            errors=[{"field": "file", "message": f"File size exceeds {max_mb}MB limit"}],
        )

    # Detect MIME type using python-magic
    mime_type = magic.from_buffer(content, mime=True)

    if mime_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "Invalid file type",
            filename=filename,
            mime_type=mime_type,
            allowed=list(ALLOWED_MIME_TYPES.keys()),
        )
        raise ValidationException(
            message="Invalid file type. Only PDF and TXT files are allowed.",
            errors=[{
                "field": "file",
                "message": f"File type '{mime_type}' is not allowed. Allowed types: PDF, TXT",
            }],
        )

    logger.info(
        "File validated",
        filename=filename,
        mime_type=mime_type,
        size_mb=round(file_size / (1024 * 1024), 2),
    )

    return ALLOWED_MIME_TYPES[mime_type]


def sanitize_prompt_input(text: str) -> str:
    """
    Sanitize user input intended for LLM prompts.

    Escapes characters that could be used for prompt injection
    while preserving the semantic content of the text.

    Args:
        text: User input text

    Returns:
        Sanitized text safe for prompt inclusion
    """
    if not text:
        return ""

    # Escape common template/prompt injection patterns
    # These are markers that could be used to inject instructions

    # Escape curly braces (Jinja2, f-strings)
    text = text.replace("{", "{{").replace("}", "}}")

    # Escape common prompt delimiters
    text = text.replace("```", "'''")

    # Remove null bytes and control characters (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Limit consecutive newlines
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # Trim excessive whitespace
    text = text.strip()

    return text


def validate_uuid(value: str, field_name: str = "id") -> None:
    """
    Validate that a string is a valid UUID.

    Args:
        value: String to validate
        field_name: Name of field for error message

    Raises:
        ValidationException: If not a valid UUID
    """
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    if not uuid_pattern.match(value):
        raise ValidationException(
            message=f"Invalid {field_name}",
            errors=[{"field": field_name, "message": "Must be a valid UUID"}],
        )
