"""OCR service using Mistral Vision API."""

import base64
from pathlib import Path
from typing import Optional

import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger()


class OCRError(Exception):
    """OCR processing error."""

    pass


class OCRService:
    """Service for OCR using Mistral Vision API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    async def extract_text_from_image(
        self,
        image_path: str | Path,
    ) -> str:
        """Extract text from an image using Mistral Vision.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text

        Raises:
            OCRError: If extraction fails
        """
        image_path = Path(image_path)

        if not image_path.exists():
            raise OCRError(f"Image file not found: {image_path}")

        # Read and encode image
        image_data = image_path.read_bytes()
        base64_image = base64.b64encode(image_data).decode("utf-8")

        # Determine media type
        suffix = image_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/png")

        return await self._call_mistral_vision(base64_image, media_type)

    async def extract_text_from_pdf_page(
        self,
        pdf_path: str | Path,
        page_number: int,
    ) -> str:
        """Extract text from a PDF page using OCR.

        This converts the PDF page to an image first, then runs OCR.

        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-indexed)

        Returns:
            Extracted text

        Raises:
            OCRError: If extraction fails
        """
        # For PDF OCR, we'd need to convert to image first
        # This is a placeholder - real implementation would use
        # pdf2image or similar library
        raise OCRError("PDF page OCR not yet implemented - use image input")

    async def _call_mistral_vision(
        self,
        base64_image: str,
        media_type: str,
    ) -> str:
        """Call Mistral Vision API.

        Args:
            base64_image: Base64 encoded image
            media_type: MIME type of image

        Returns:
            Extracted text
        """
        if not self.settings.mistral_api_key:
            raise OCRError("Mistral API key not configured")

        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.mistral_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "pixtral-large-latest",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Please extract all text from this image. "
                                        "Preserve the original formatting and structure "
                                        "as much as possible. Only output the extracted "
                                        "text, no explanations."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 4096,
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                raise OCRError(
                    f"Mistral API error: {error_data.get('error', {}).get('message', 'Unknown error')}"
                )

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPError as e:
            logger.error("mistral_ocr_error", error=str(e))
            raise OCRError(f"OCR request failed: {e}")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
