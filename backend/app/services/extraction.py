"""Extraction service for metadata extraction using LLM."""

from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.schema import SchemaRepository
from app.services.llm import LLMService

logger = structlog.get_logger()


class ExtractionError(Exception):
    """Extraction error."""

    pass


class ExtractionService:
    """Service for extracting structured metadata from text."""

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        llm_service: LLMService,
    ):
        self.settings = settings
        self.session = session
        self.schema_repo = SchemaRepository(session)
        self.llm_service = llm_service

    async def extract_metadata(
        self,
        text: str,
        schema_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Extract structured metadata from text.

        Args:
            text: Text to extract from
            schema_id: Optional schema to use (uses default if not provided)

        Returns:
            Dict of extracted metadata

        Raises:
            ExtractionError: If extraction fails
        """
        # Get schema
        if schema_id:
            schema = await self.schema_repo.get_by_id(schema_id)
        else:
            schema = await self.schema_repo.get_default()

        if not schema:
            # Return empty if no schema configured
            return {}

        schema_def = schema.schema_definition

        # Build extraction prompt
        prompt = self._build_extraction_prompt(text, schema_def)

        try:
            # Call LLM for extraction
            response = await self.llm_service.chat_completion(
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2048,
            )

            # Parse response
            return self._parse_extraction_response(response, schema_def)

        except Exception as e:
            logger.error("extraction_failed", error=str(e))
            raise ExtractionError(f"Extraction failed: {e}")

    def _get_system_prompt(self) -> str:
        """Get system prompt for extraction."""
        return """You are a precise information extraction assistant. Extract structured information from text based on the provided schema.

Rules:
1. Only extract information that is explicitly stated in the text
2. Return empty arrays/null for fields where information is not found
3. Be precise - don't infer or guess
4. Return valid JSON only
5. Follow the exact field names specified"""

    def _build_extraction_prompt(
        self,
        text: str,
        schema_def: dict[str, Any],
    ) -> str:
        """Build the extraction prompt.

        Args:
            text: Text to extract from
            schema_def: Schema definition

        Returns:
            Formatted prompt
        """
        # Build schema description
        schema_parts = []

        entities = schema_def.get("entities", [])
        for entity in entities:
            examples = entity.get("examples", [])
            example_str = f" (examples: {', '.join(examples)})" if examples else ""
            schema_parts.append(
                f"- {entity['name']}: {entity['description']}{example_str}"
            )

        custom_fields = schema_def.get("custom_fields", [])
        for field in custom_fields:
            pattern = field.get("pattern")
            pattern_str = f" (pattern: {pattern})" if pattern else ""
            schema_parts.append(
                f"- {field['name']}: {field['description']}{pattern_str}"
            )

        schema_description = "\n".join(schema_parts)

        return f"""Extract the following information from the text:

SCHEMA:
{schema_description}

TEXT:
{text}

Return a JSON object with the extracted information. Use arrays for multiple values.
For entities not found, use empty arrays. For fields not found, use null."""

    def _parse_extraction_response(
        self,
        response: str,
        schema_def: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse the LLM extraction response.

        Args:
            response: LLM response text
            schema_def: Schema definition

        Returns:
            Parsed extraction results
        """
        import json

        # Try to extract JSON from response
        try:
            # Look for JSON in the response
            response = response.strip()

            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                json_lines = []
                in_json = False
                for line in lines:
                    if line.startswith("```") and not in_json:
                        in_json = True
                        continue
                    elif line.startswith("```") and in_json:
                        break
                    elif in_json:
                        json_lines.append(line)
                response = "\n".join(json_lines)

            # Parse JSON
            result = json.loads(response)

            # Validate against schema
            validated = {}

            for entity in schema_def.get("entities", []):
                name = entity["name"]
                if name in result:
                    value = result[name]
                    # Ensure it's a list
                    if not isinstance(value, list):
                        value = [value] if value else []
                    validated[name] = value
                else:
                    validated[name] = []

            for field in schema_def.get("custom_fields", []):
                name = field["name"]
                if name in result:
                    validated[name] = result[name]
                else:
                    validated[name] = None

            return validated

        except json.JSONDecodeError as e:
            logger.warning(
                "extraction_json_parse_failed",
                error=str(e),
                response=response[:500],
            )
            return {}

    async def extract_for_chunk(
        self,
        chunk_content: str,
        schema_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Extract metadata for a single chunk.

        This is a convenience method for chunk-level extraction.

        Args:
            chunk_content: Chunk text
            schema_id: Optional schema ID

        Returns:
            Extracted metadata
        """
        # Truncate if too long
        max_chars = 4000
        if len(chunk_content) > max_chars:
            chunk_content = chunk_content[:max_chars] + "..."

        return await self.extract_metadata(chunk_content, schema_id)
