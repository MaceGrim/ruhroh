"""Pytest fixtures for ruhroh backend tests."""

import asyncio
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.models import Base, User
from app.dependencies import get_current_user, get_current_user_id
from app.db.database import get_db_session


# Test user ID (same as dev mode for consistency)
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_EMAIL = "test@example.com"


# =============================================================================
# Test Settings
# =============================================================================


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with SQLite and mocked services."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        qdrant_host="localhost",
        qdrant_port=6333,
        qdrant_collection_name="test_documents",
        supabase_url="http://localhost:54321",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-key",
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        dev_mode=True,
        debug=True,
        upload_dir="/tmp/ruhroh_test_uploads",
        processed_dir="/tmp/ruhroh_test_processed",
        cors_origins="*",
        # High rate limits for testing
        ruhroh_rate_limit_rpm=10000,
        ruhroh_rate_limit_burst=1000,
    )


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
async def async_engine(test_settings):
    """Create async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # SQLite doesn't support some PostgreSQL features, so we need to handle this
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield engine

    await engine.dispose()


@pytest.fixture
async def async_session_factory(async_engine):
    """Create async session factory."""
    return async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest.fixture
async def init_db(async_engine):
    """Initialize database schema for tests."""
    # Create SQLite-compatible versions of the models
    # We need to create tables manually for SQLite compatibility
    async with async_engine.begin() as conn:
        # Drop all tables first
        await conn.run_sync(Base.metadata.drop_all)

        # For SQLite, we need to create compatible tables
        # Create users table (SQLite compatible)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """))

        # Create documents table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                normalized_filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                page_count INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                chunking_strategy TEXT NOT NULL DEFAULT 'fixed',
                ocr_enabled BOOLEAN DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create chunks table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                page_numbers TEXT,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                token_count INTEGER NOT NULL,
                extracted_metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create threads table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT 'New Conversation',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create messages table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                model_used TEXT,
                is_from_documents BOOLEAN DEFAULT 1,
                token_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create extraction_schemas table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS extraction_schemas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                schema_definition TEXT NOT NULL,
                is_default BOOLEAN DEFAULT 0,
                created_by TEXT REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create audit_logs table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES users(id),
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

    yield

    async with async_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS audit_logs"))
        await conn.execute(text("DROP TABLE IF EXISTS extraction_schemas"))
        await conn.execute(text("DROP TABLE IF EXISTS messages"))
        await conn.execute(text("DROP TABLE IF EXISTS threads"))
        await conn.execute(text("DROP TABLE IF EXISTS chunks"))
        await conn.execute(text("DROP TABLE IF EXISTS documents"))
        await conn.execute(text("DROP TABLE IF EXISTS users"))


@pytest.fixture
async def db_session(
    async_session_factory, init_db
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for tests."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# User Fixtures
# =============================================================================


@pytest.fixture
async def test_user(db_session) -> User:
    """Create a test user in the database."""
    from uuid import uuid4

    user = User(
        id=TEST_USER_ID,
        email=TEST_USER_EMAIL,
        role="admin",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def regular_user(db_session) -> User:
    """Create a regular (non-admin) test user."""
    from uuid import uuid4

    user = User(
        id=uuid4(),
        email="regular@example.com",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def inactive_user(db_session) -> User:
    """Create an inactive test user."""
    from uuid import uuid4

    user = User(
        id=uuid4(),
        email="inactive@example.com",
        role="user",
        is_active=False,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


# =============================================================================
# Mock External Services
# =============================================================================


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for tests."""
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    mock_client.create_collection.return_value = None
    mock_client.upsert.return_value = None
    mock_client.query_points.return_value = MagicMock(points=[])
    mock_client.delete.return_value = None

    return mock_client


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for tests."""
    mock = AsyncMock()

    # Mock embeddings - return 1536-dim vectors
    mock.generate_embeddings.return_value = [[0.1] * 1536]
    mock.generate_embedding.return_value = [0.1] * 1536

    # Mock chat completions
    mock.chat_completion.return_value = "This is a test response."
    mock.count_tokens.return_value = 10

    return mock


@pytest.fixture
def mock_auth_service():
    """Mock auth service for tests."""
    mock = AsyncMock()
    mock.verify_token.return_value = TEST_USER_ID
    mock.register_user.return_value = {
        "user_id": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
    }
    mock.login_user.return_value = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "expires_in": 3600,
        "user_id": TEST_USER_ID,
    }
    return mock


@pytest.fixture
def mock_ingestion_service():
    """Mock ingestion service for tests."""
    mock = AsyncMock()
    mock.normalize_filename.return_value = "test_document.pdf"
    mock.process_document.return_value = None
    mock.reprocess_document.return_value = None
    mock.delete_document.return_value = True
    return mock


# =============================================================================
# FastAPI Test Client
# =============================================================================


@pytest.fixture
async def app(
    test_settings,
    async_session_factory,
    init_db,
    test_user,
    mock_qdrant_client,
):
    """Create FastAPI app with test overrides."""
    from app.main import app as fastapi_app
    from app.config import get_settings
    from app.services.qdrant import get_qdrant_client
    from app.middleware.rate_limit import RateLimitMiddleware

    # Override settings
    def override_get_settings():
        return test_settings

    # Override database session
    async def override_get_db_session():
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Override auth to return test user
    async def override_get_current_user_id():
        return TEST_USER_ID

    async def override_get_current_user(
        db: AsyncSession = None,
    ):
        # Return a mock user object
        return test_user

    # Apply overrides
    fastapi_app.dependency_overrides[get_settings] = override_get_settings
    fastapi_app.dependency_overrides[get_db_session] = override_get_db_session
    fastapi_app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    fastapi_app.dependency_overrides[get_current_user] = lambda: test_user

    # Disable rate limiting for tests by patching the check method to always allow
    def always_allow_rate_limit(self, key):
        return (True, 10000, 9999, 9999999999)

    # Mock Qdrant at module level and disable rate limiting
    with patch("app.services.qdrant.get_qdrant_client", return_value=mock_qdrant_client):
        with patch("app.services.qdrant._client", mock_qdrant_client):
            with patch.object(RateLimitMiddleware, "_check_rate_limit", always_allow_rate_limit):
                yield fastapi_app

    # Clear overrides after test
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token"},
    ) as ac:
        yield ac


@pytest.fixture
async def unauthenticated_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client without auth headers."""
    # Remove auth override for this client
    from app.main import app as fastapi_app
    from app.dependencies import get_current_user_id, get_current_user

    # Temporarily remove auth overrides
    original_overrides = dict(fastapi_app.dependency_overrides)
    if get_current_user_id in fastapi_app.dependency_overrides:
        del fastapi_app.dependency_overrides[get_current_user_id]
    if get_current_user in fastapi_app.dependency_overrides:
        del fastapi_app.dependency_overrides[get_current_user]

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    # Restore overrides
    fastapi_app.dependency_overrides = original_overrides


# =============================================================================
# Helper Fixtures for Test Data
# =============================================================================


@pytest.fixture
def sample_document_data():
    """Sample document data for creating test documents."""
    return {
        "filename": "test_document.pdf",
        "normalized_filename": "test_document.pdf",
        "file_type": "pdf",
        "file_path": "/tmp/test_document.pdf",
        "file_size": 1024,
        "chunking_strategy": "fixed",
        "ocr_enabled": False,
    }


@pytest.fixture
def sample_chunk_data():
    """Sample chunk data for creating test chunks."""
    return {
        "content": "This is test content for a chunk.",
        "chunk_index": 0,
        "page_numbers": [1],
        "start_offset": 0,
        "end_offset": 100,
        "token_count": 10,
        "extracted_metadata": {},
    }


@pytest.fixture
def sample_thread_data():
    """Sample thread data for creating test threads."""
    return {
        "name": "Test Conversation",
    }


@pytest.fixture
def sample_message_data():
    """Sample message data for creating test messages."""
    return {
        "role": "user",
        "content": "What is the meaning of life?",
        "is_from_documents": True,
    }


# =============================================================================
# Cleanup Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
async def cleanup_test_files():
    """Clean up test files after each test."""
    import shutil
    from pathlib import Path

    yield

    # Clean up test upload/processed directories
    test_dirs = [
        Path("/tmp/ruhroh_test_uploads"),
        Path("/tmp/ruhroh_test_processed"),
    ]
    for test_dir in test_dirs:
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)


# =============================================================================
# Utility Functions for Tests
# =============================================================================


def create_test_pdf_content() -> bytes:
    """Create minimal valid PDF content for testing."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""
    return pdf_content


def create_test_txt_content() -> bytes:
    """Create test text file content."""
    return b"This is test content for a text file.\nIt has multiple lines.\nFor testing purposes."
