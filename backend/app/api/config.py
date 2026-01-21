"""Configuration API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.dependencies import require_role
from app.models import (
    ExtractionSchemaCreate,
    ExtractionSchemaUpdate,
    ExtractionSchemaResponse,
    ExtractionSchemaListResponse,
    ErrorResponse,
)
from app.services.config_service import ConfigService

router = APIRouter()


async def get_config_service(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConfigService:
    """Get config service."""
    return ConfigService(settings, db)


require_superuser_role = require_role(["superuser", "admin"])
require_admin_role = require_role(["admin"])


@router.get(
    "/schemas",
    response_model=ExtractionSchemaListResponse,
    dependencies=[Depends(require_superuser_role)],
)
async def list_schemas(
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """List all extraction schemas (superuser or admin)."""
    schemas = await config_service.list_schemas()

    return ExtractionSchemaListResponse(
        schemas=[
            ExtractionSchemaResponse(
                id=UUID(s["id"]),
                name=s["name"],
                description=s["description"],
                schema_definition=s["schema_definition"],
                is_default=s["is_default"],
                created_by=UUID(s["created_by"]) if s["created_by"] else None,
                created_at=s["created_at"],
            )
            for s in schemas
        ]
    )


@router.post(
    "/schemas",
    response_model=ExtractionSchemaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_superuser_role)],
)
async def create_schema(
    data: ExtractionSchemaCreate,
    user: Annotated[User, Depends(require_superuser_role)],
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """Create a new extraction schema (superuser or admin)."""
    result = await config_service.create_schema(
        name=data.name,
        schema_definition=data.schema_definition.model_dump(),
        description=data.description,
        created_by=user.id,
    )

    return ExtractionSchemaResponse(
        id=UUID(result["id"]),
        name=result["name"],
        description=result["description"],
        schema_definition=result["schema_definition"],
        is_default=result["is_default"],
        created_by=UUID(result["created_by"]) if result["created_by"] else None,
        created_at=result["created_at"],
    )


@router.put(
    "/schemas/{schema_id}",
    response_model=ExtractionSchemaResponse,
    dependencies=[Depends(require_superuser_role)],
    responses={404: {"model": ErrorResponse}},
)
async def update_schema(
    schema_id: UUID,
    data: ExtractionSchemaUpdate,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """Update an extraction schema (superuser or admin)."""
    schema_def = data.schema_definition.model_dump() if data.schema_definition else None

    result = await config_service.update_schema(
        schema_id=schema_id,
        name=data.name,
        description=data.description,
        schema_definition=schema_def,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Schema not found"},
        )

    return ExtractionSchemaResponse(
        id=UUID(result["id"]),
        name=result["name"],
        description=result["description"],
        schema_definition=result["schema_definition"],
        is_default=result["is_default"],
        created_by=UUID(result["created_by"]) if result["created_by"] else None,
        created_at=result["created_at"],
    )


@router.delete(
    "/schemas/{schema_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)],
    responses={404: {"model": ErrorResponse}},
)
async def delete_schema(
    schema_id: UUID,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """Delete an extraction schema (admin only)."""
    deleted = await config_service.delete_schema(schema_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Schema not found"},
        )

    return None


@router.put(
    "/schemas/{schema_id}/default",
    response_model=ExtractionSchemaResponse,
    dependencies=[Depends(require_admin_role)],
    responses={404: {"model": ErrorResponse}},
)
async def set_default_schema(
    schema_id: UUID,
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """Set a schema as the default (admin only)."""
    result = await config_service.set_default_schema(schema_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Schema not found"},
        )

    return ExtractionSchemaResponse(
        id=UUID(result["id"]),
        name=result["name"],
        description=result["description"],
        schema_definition=result["schema_definition"],
        is_default=result["is_default"],
        created_by=UUID(result["created_by"]) if result["created_by"] else None,
        created_at=result["created_at"],
    )
