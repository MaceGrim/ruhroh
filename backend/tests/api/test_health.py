"""Tests for health check endpoint."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Test health check endpoint."""

    async def test_health_returns_200(self, client: AsyncClient):
        """Test that health endpoint returns 200 status."""
        response = await client.get("/health")

        assert response.status_code == 200

    async def test_health_returns_correct_structure(self, client: AsyncClient):
        """Test that health endpoint returns expected JSON structure."""
        response = await client.get("/health")

        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "qdrant" in data

    async def test_health_status_values(self, client: AsyncClient):
        """Test that health status contains valid values."""
        response = await client.get("/health")

        data = response.json()
        assert data["status"] in ["ok", "degraded"]
        assert data["database"] in ["ok", "error"]
        assert data["qdrant"] in ["ok", "error"]

    async def test_health_no_auth_required(self, unauthenticated_client: AsyncClient):
        """Test that health endpoint works without authentication."""
        response = await unauthenticated_client.get("/health")

        # Health check should be accessible without auth
        assert response.status_code == 200


class TestAdminHealthEndpoint:
    """Test admin health endpoint with detailed status."""

    async def test_admin_health_returns_200(self, client: AsyncClient):
        """Test that admin health endpoint returns 200 status."""
        response = await client.get("/api/v1/admin/health")

        assert response.status_code == 200

    async def test_admin_health_returns_detailed_structure(self, client: AsyncClient):
        """Test that admin health returns detailed health info."""
        response = await client.get("/api/v1/admin/health")

        data = response.json()
        assert "api" in data
        assert "database" in data
        assert "qdrant" in data
        assert "supabase" in data

    async def test_admin_health_status_values(self, client: AsyncClient):
        """Test that admin health status contains valid values."""
        response = await client.get("/api/v1/admin/health")

        data = response.json()
        assert data["api"] in ["ok", "degraded"]
        assert data["database"] in ["ok", "error"]
        assert data["qdrant"] in ["ok", "error"]
        assert data["supabase"] in ["ok", "error"]
