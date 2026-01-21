"""Extraction schema Pydantic models."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import BaseSchema


class EntityDefinition(BaseModel):
    """Schema for an entity type definition."""

    name: str = Field(..., description="Entity type name")
    description: str = Field(..., description="What this entity represents")
    examples: list[str] = Field(
        default_factory=list,
        description="Example values",
    )


class CustomFieldDefinition(BaseModel):
    """Schema for a custom field definition."""

    name: str = Field(..., description="Field name")
    description: str = Field(..., description="What this field represents")
    pattern: Optional[str] = Field(
        None,
        description="Regex pattern for validation",
    )


class SchemaDefinition(BaseModel):
    """Schema for extraction schema definition."""

    entities: list[EntityDefinition] = Field(
        default_factory=list,
        description="Entity types to extract",
    )
    custom_fields: list[CustomFieldDefinition] = Field(
        default_factory=list,
        description="Custom fields to extract",
    )


class ExtractionSchemaCreate(BaseModel):
    """Schema for creating an extraction schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    schema_definition: SchemaDefinition


class ExtractionSchemaUpdate(BaseModel):
    """Schema for updating an extraction schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    schema_definition: Optional[SchemaDefinition] = None


class ExtractionSchemaResponse(BaseSchema):
    """Schema for extraction schema in API responses."""

    id: UUID
    name: str
    description: Optional[str] = None
    schema_definition: dict[str, Any]
    is_default: bool
    created_by: Optional[UUID] = None
    created_at: datetime


class ExtractionSchemaListResponse(BaseModel):
    """Schema for extraction schema list."""

    schemas: list[ExtractionSchemaResponse]
