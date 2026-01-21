"""PDF processing utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pypdf import PdfReader
import structlog

logger = structlog.get_logger()


@dataclass
class PDFPage:
    """Information about a PDF page."""

    page_number: int
    text: str
    start_offset: int


@dataclass
class PDFContent:
    """Extracted PDF content."""

    text: str
    page_count: int
    pages: list[PDFPage]
    page_boundaries: list[tuple[int, int]]  # (start_offset, page_number)


def extract_text_from_pdf(file_path: str | Path) -> PDFContent:
    """Extract text from a PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        PDFContent with extracted text and page info

    Raises:
        ValueError: If PDF cannot be processed
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise ValueError(f"PDF file not found: {file_path}")

    try:
        reader = PdfReader(str(file_path))
        pages = []
        page_boundaries = []
        full_text_parts = []
        current_offset = 0

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            # Clean up text
            text = text.strip()
            if text:
                pages.append(PDFPage(
                    page_number=page_num,
                    text=text,
                    start_offset=current_offset,
                ))
                page_boundaries.append((current_offset, page_num))
                full_text_parts.append(text)
                current_offset += len(text) + 2  # +2 for \n\n separator

        full_text = "\n\n".join(full_text_parts)

        return PDFContent(
            text=full_text,
            page_count=len(reader.pages),
            pages=pages,
            page_boundaries=page_boundaries,
        )

    except Exception as e:
        logger.error("pdf_extraction_failed", error=str(e), path=str(file_path))
        raise ValueError(f"Failed to extract text from PDF: {e}")


def extract_text_from_txt(file_path: str | Path) -> str:
    """Extract text from a plain text file.

    Args:
        file_path: Path to text file

    Returns:
        File contents as string

    Raises:
        ValueError: If file cannot be read
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise ValueError(f"Text file not found: {file_path}")

    try:
        # Try UTF-8 first, fall back to latin-1
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="latin-1")

    except Exception as e:
        logger.error("txt_extraction_failed", error=str(e), path=str(file_path))
        raise ValueError(f"Failed to read text file: {e}")


def get_page_count(file_path: str | Path) -> Optional[int]:
    """Get page count from a PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Number of pages or None if not a PDF
    """
    file_path = Path(file_path)

    if file_path.suffix.lower() != ".pdf":
        return None

    try:
        reader = PdfReader(str(file_path))
        return len(reader.pages)
    except Exception:
        return None
