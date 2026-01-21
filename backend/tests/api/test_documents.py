"""Tests for document management API endpoints."""

import io
from uuid import UUID, uuid4
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID, create_test_pdf_content, create_test_txt_content


async def create_test_document(client: AsyncClient, filename: str = "test.pdf") -> dict:
    """Helper to create a test document via the upload API."""
    pdf_content = create_test_pdf_content()

    with patch("app.api.documents.magic.from_buffer") as mock_magic:
        with patch("app.api.documents.IngestionService") as mock_class:
            mock_magic.return_value = "application/pdf"
            # Use MagicMock for the instance, not AsyncMock
            # AsyncMock would make normalize_filename return a coroutine
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            # normalize_filename is a regular method, not async
            mock_instance.normalize_filename.return_value = filename
            # process_document is async, so use AsyncMock for it
            mock_instance.process_document = AsyncMock(return_value=None)
            mock_instance.delete_document = AsyncMock(return_value=True)

            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": (filename, io.BytesIO(pdf_content), "application/pdf")},
                data={"chunking_strategy": "fixed", "ocr_enabled": "false"},
            )

    assert response.status_code == 202
    return response.json()


class TestListDocuments:
    """Test list documents endpoint."""

    async def test_list_documents_empty(self, client: AsyncClient):
        """Test listing documents when none exist."""
        response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert data["documents"] == []
        assert data["total"] == 0

    async def test_list_documents_with_data(self, client: AsyncClient):
        """Test listing documents when documents exist."""
        # Create document via API
        await create_test_document(client, "list_test.pdf")

        response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 1
        assert data["total"] >= 1

    async def test_list_documents_pagination(self, client: AsyncClient):
        """Test pagination for document list."""
        # Create multiple documents via API
        for i in range(3):
            await create_test_document(client, f"pagination_test_{i}.pdf")

        # Get first 2 documents
        response = await client.get("/api/v1/documents?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2
        assert data["total"] >= 3

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_list_documents_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that listing documents requires authentication."""
        response = await unauthenticated_client.get("/api/v1/documents")

        assert response.status_code == 401


class TestGetDocument:
    """Test get document endpoint."""

    async def test_get_document_success(self, client: AsyncClient):
        """Test getting a document that exists."""
        # Create document via API
        doc = await create_test_document(client, "get_test.pdf")
        doc_id = doc["document_id"]

        response = await client.get(f"/api/v1/documents/{doc_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc_id
        assert "chunk_count" in data

    async def test_get_document_not_found(self, client: AsyncClient):
        """Test getting a document that does not exist."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_get_document_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that getting a document requires authentication."""
        fake_id = str(uuid4())
        response = await unauthenticated_client.get(f"/api/v1/documents/{fake_id}")

        assert response.status_code == 401


class TestDeleteDocument:
    """Test delete document endpoint."""

    async def test_delete_document_success(self, client: AsyncClient):
        """Test deleting a document successfully."""
        # Create document via API
        doc = await create_test_document(client, "delete_test.pdf")
        doc_id = doc["document_id"]

        # Mock the ingestion service delete
        with patch("app.api.documents.IngestionService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.delete_document = AsyncMock(return_value=True)

            response = await client.delete(f"/api/v1/documents/{doc_id}")

        assert response.status_code == 204

    async def test_delete_document_not_found(self, client: AsyncClient):
        """Test deleting a document that does not exist."""
        fake_id = str(uuid4())
        response = await client.delete(f"/api/v1/documents/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_delete_document_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that deleting a document requires authentication."""
        fake_id = str(uuid4())
        response = await unauthenticated_client.delete(f"/api/v1/documents/{fake_id}")

        assert response.status_code == 401


class TestUploadDocument:
    """Test upload document endpoint."""

    async def test_upload_pdf_document(self, client: AsyncClient):
        """Test uploading a PDF document."""
        pdf_content = create_test_pdf_content()

        # Mock the file type detection and ingestion service
        with patch("app.api.documents.magic.from_buffer") as mock_magic:
            with patch("app.api.documents.IngestionService") as mock_class:
                mock_magic.return_value = "application/pdf"
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                mock_instance.normalize_filename.return_value = "upload_test.pdf"
                mock_instance.process_document = AsyncMock(return_value=None)

                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("upload_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                    data={"chunking_strategy": "fixed", "ocr_enabled": "false"},
                )

        assert response.status_code == 202
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "pending"

    async def test_upload_txt_document(self, client: AsyncClient):
        """Test uploading a TXT document."""
        txt_content = create_test_txt_content()

        with patch("app.api.documents.magic.from_buffer") as mock_magic:
            with patch("app.api.documents.IngestionService") as mock_class:
                mock_magic.return_value = "text/plain"
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                mock_instance.normalize_filename.return_value = "upload_test.txt"
                mock_instance.process_document = AsyncMock(return_value=None)

                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("upload_test.txt", io.BytesIO(txt_content), "text/plain")},
                    data={"chunking_strategy": "fixed"},
                )

        assert response.status_code == 202
        data = response.json()
        assert "document_id" in data

    async def test_upload_unsupported_file_type(self, client: AsyncClient):
        """Test uploading an unsupported file type."""
        with patch("app.api.documents.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "image/png"

            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.png", io.BytesIO(b"fake png content"), "image/png")},
            )

        assert response.status_code == 415
        data = response.json()
        assert data["detail"]["code"] == "UNSUPPORTED_FILE_TYPE"

    async def test_upload_duplicate_document(self, client: AsyncClient):
        """Test uploading a duplicate document without force_replace."""
        # First upload
        await create_test_document(client, "duplicate_test.pdf")

        # Try to upload again
        pdf_content = create_test_pdf_content()

        with patch("app.api.documents.magic.from_buffer") as mock_magic:
            with patch("app.api.documents.IngestionService") as mock_class:
                mock_magic.return_value = "application/pdf"
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                mock_instance.normalize_filename.return_value = "duplicate_test.pdf"
                mock_instance.process_document = AsyncMock(return_value=None)

                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("duplicate_test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                )

        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["code"] == "DOCUMENT_EXISTS"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_upload_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that uploading requires authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(b"test"), "application/pdf")},
        )

        assert response.status_code == 401


class TestDocumentStatus:
    """Test document status endpoint."""

    async def test_get_document_status(self, client: AsyncClient):
        """Test getting document status."""
        # Create document via API
        doc = await create_test_document(client, "status_test.pdf")
        doc_id = doc["document_id"]

        response = await client.get(f"/api/v1/documents/{doc_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["pending", "processing", "ready", "failed"]

    async def test_get_document_status_not_found(self, client: AsyncClient):
        """Test getting status for non-existent document."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{fake_id}/status")

        assert response.status_code == 404


class TestReprocessDocument:
    """Test reprocess document endpoint."""

    async def test_reprocess_document(self, client: AsyncClient):
        """Test reprocessing a document."""
        # Create document via API
        doc = await create_test_document(client, "reprocess_test.pdf")
        doc_id = doc["document_id"]

        with patch("app.api.documents.IngestionService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.reprocess_document = AsyncMock(return_value=None)

            response = await client.post(
                f"/api/v1/documents/{doc_id}/reprocess",
                json={"chunking_strategy": "semantic", "ocr_enabled": True},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"

    async def test_reprocess_document_not_found(self, client: AsyncClient):
        """Test reprocessing a non-existent document."""
        fake_id = str(uuid4())
        response = await client.post(
            f"/api/v1/documents/{fake_id}/reprocess",
            json={"chunking_strategy": "semantic"},
        )

        assert response.status_code == 404
