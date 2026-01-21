"""Configuration service for runtime settings and schema management."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import Settings
from app.db.repositories.schema import SchemaRepository

logger = structlog.get_logger()


class ConfigService:
    """Service for managing configuration and extraction schemas."""

    def __init__(self, settings: Settings, session: AsyncSession):
        self.settings = settings
        self.schema_repo = SchemaRepository(session)

    async def get_default_schema(self) -> Optional[dict[str, Any]]:
        """Get the default extraction schema.

        Returns:
            Schema definition dict or None
        """
        schema = await self.schema_repo.get_default()
        if schema:
            return schema.schema_definition
        return None

    async def get_schema(self, schema_id: UUID) -> Optional[dict[str, Any]]:
        """Get a specific extraction schema.

        Args:
            schema_id: Schema UUID

        Returns:
            Schema definition dict or None
        """
        schema = await self.schema_repo.get_by_id(schema_id)
        if schema:
            return schema.schema_definition
        return None

    async def list_schemas(self) -> list[dict[str, Any]]:
        """List all extraction schemas.

        Returns:
            List of schema dicts with metadata
        """
        schemas = await self.schema_repo.list_all()
        return [
            {
                "id": str(schema.id),
                "name": schema.name,
                "description": schema.description,
                "schema_definition": schema.schema_definition,
                "is_default": schema.is_default,
                "created_by": str(schema.created_by) if schema.created_by else None,
                "created_at": schema.created_at.isoformat(),
            }
            for schema in schemas
        ]

    async def create_schema(
        self,
        name: str,
        schema_definition: dict[str, Any],
        description: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Create a new extraction schema.

        Args:
            name: Schema name
            schema_definition: Schema definition
            description: Optional description
            created_by: Creator user ID

        Returns:
            Created schema dict
        """
        schema = await self.schema_repo.create(
            name=name,
            schema_definition=schema_definition,
            description=description,
            created_by=created_by,
        )

        logger.info(
            "schema_created",
            schema_id=str(schema.id),
            name=name,
            created_by=str(created_by) if created_by else None,
        )

        return {
            "id": str(schema.id),
            "name": schema.name,
            "description": schema.description,
            "schema_definition": schema.schema_definition,
            "is_default": schema.is_default,
            "created_by": str(schema.created_by) if schema.created_by else None,
            "created_at": schema.created_at.isoformat(),
        }

    async def update_schema(
        self,
        schema_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        schema_definition: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Update an extraction schema.

        Args:
            schema_id: Schema UUID
            name: New name
            description: New description
            schema_definition: New definition

        Returns:
            Updated schema dict or None if not found
        """
        schema = await self.schema_repo.update(
            schema_id=schema_id,
            name=name,
            description=description,
            schema_definition=schema_definition,
        )

        if not schema:
            return None

        logger.info("schema_updated", schema_id=str(schema_id))

        return {
            "id": str(schema.id),
            "name": schema.name,
            "description": schema.description,
            "schema_definition": schema.schema_definition,
            "is_default": schema.is_default,
            "created_by": str(schema.created_by) if schema.created_by else None,
            "created_at": schema.created_at.isoformat(),
        }

    async def set_default_schema(self, schema_id: UUID) -> Optional[dict[str, Any]]:
        """Set a schema as the default.

        Args:
            schema_id: Schema UUID

        Returns:
            Updated schema dict or None
        """
        schema = await self.schema_repo.set_default(schema_id)

        if not schema:
            return None

        logger.info("default_schema_set", schema_id=str(schema_id))

        return {
            "id": str(schema.id),
            "name": schema.name,
            "description": schema.description,
            "schema_definition": schema.schema_definition,
            "is_default": schema.is_default,
            "created_by": str(schema.created_by) if schema.created_by else None,
            "created_at": schema.created_at.isoformat(),
        }

    async def delete_schema(self, schema_id: UUID) -> bool:
        """Delete an extraction schema.

        Args:
            schema_id: Schema UUID

        Returns:
            True if deleted
        """
        deleted = await self.schema_repo.delete(schema_id)

        if deleted:
            logger.info("schema_deleted", schema_id=str(schema_id))

        return deleted

    def get_chunking_config(self) -> dict[str, Any]:
        """Get chunking configuration.

        Returns:
            Dict with chunk_size and chunk_overlap
        """
        return {
            "chunk_size": self.settings.ruhroh_chunk_size,
            "chunk_overlap": self.settings.ruhroh_chunk_overlap,
        }

    def get_search_config(self) -> dict[str, Any]:
        """Get search configuration.

        Returns:
            Dict with vector_weight, keyword_weight, rrf_k
        """
        return {
            "vector_weight": self.settings.ruhroh_vector_weight,
            "keyword_weight": self.settings.ruhroh_keyword_weight,
            "rrf_k": self.settings.ruhroh_rrf_k,
        }

    def get_llm_config(self) -> dict[str, Any]:
        """Get LLM configuration.

        Returns:
            Dict with default_model, embedding_model, enable_fallback
        """
        return {
            "default_model": self.settings.ruhroh_default_model,
            "embedding_model": self.settings.ruhroh_embedding_model,
            "enable_fallback": self.settings.ruhroh_enable_fallback,
        }
