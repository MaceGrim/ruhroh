"""Extraction schema repository for database operations."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExtractionSchema


class SchemaRepository:
    """Repository for ExtractionSchema database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, schema_id: UUID) -> Optional[ExtractionSchema]:
        """Get schema by ID.

        Args:
            schema_id: Schema UUID

        Returns:
            Schema if found
        """
        result = await self.session.execute(
            select(ExtractionSchema).where(ExtractionSchema.id == schema_id)
        )
        return result.scalar_one_or_none()

    async def get_default(self) -> Optional[ExtractionSchema]:
        """Get the default extraction schema.

        Returns:
            Default schema if one exists
        """
        result = await self.session.execute(
            select(ExtractionSchema).where(ExtractionSchema.is_default == True)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        schema_definition: dict[str, Any],
        description: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> ExtractionSchema:
        """Create a new extraction schema.

        Args:
            name: Schema name
            schema_definition: Schema definition dict
            description: Optional description
            created_by: Creator user ID

        Returns:
            Created schema
        """
        schema = ExtractionSchema(
            name=name,
            description=description,
            schema_definition=schema_definition,
            created_by=created_by,
        )
        self.session.add(schema)
        await self.session.flush()
        return schema

    async def update(
        self,
        schema_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        schema_definition: Optional[dict[str, Any]] = None,
    ) -> Optional[ExtractionSchema]:
        """Update an extraction schema.

        Args:
            schema_id: Schema UUID
            name: New name
            description: New description
            schema_definition: New definition

        Returns:
            Updated schema
        """
        values = {}
        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description
        if schema_definition is not None:
            values["schema_definition"] = schema_definition

        if values:
            await self.session.execute(
                update(ExtractionSchema)
                .where(ExtractionSchema.id == schema_id)
                .values(**values)
            )

        return await self.get_by_id(schema_id)

    async def set_default(self, schema_id: UUID) -> Optional[ExtractionSchema]:
        """Set a schema as the default.

        Args:
            schema_id: Schema UUID

        Returns:
            Updated schema
        """
        # Clear existing default
        await self.session.execute(
            update(ExtractionSchema)
            .where(ExtractionSchema.is_default == True)
            .values(is_default=False)
        )

        # Set new default
        await self.session.execute(
            update(ExtractionSchema)
            .where(ExtractionSchema.id == schema_id)
            .values(is_default=True)
        )

        return await self.get_by_id(schema_id)

    async def delete(self, schema_id: UUID) -> bool:
        """Delete an extraction schema.

        Args:
            schema_id: Schema UUID

        Returns:
            True if deleted
        """
        result = await self.session.execute(
            delete(ExtractionSchema).where(ExtractionSchema.id == schema_id)
        )
        return result.rowcount > 0

    async def list_all(self) -> list[ExtractionSchema]:
        """List all extraction schemas.

        Returns:
            List of schemas
        """
        result = await self.session.execute(
            select(ExtractionSchema).order_by(ExtractionSchema.name)
        )
        return list(result.scalars().all())
