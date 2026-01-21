# ruhroh Implementation Tasks

## Epic: Project Infrastructure Setup
- type: epic
- description: Core project scaffolding and infrastructure

### Initialize Backend Project Structure
- type: task
- priority: 0
- description: |
    Create FastAPI backend project structure:
    - backend/app/ directory with __init__.py, main.py, config.py, dependencies.py
    - backend/app/api/, services/, models/, db/, utils/ subdirectories
    - backend/requirements.txt with core dependencies
    - backend/Dockerfile
    - backend/.env.example

### Initialize Frontend Project Structure
- type: task
- priority: 0
- description: |
    Create React/TypeScript/Vite frontend project:
    - frontend/src/ with components/, pages/, hooks/, services/, stores/, types/
    - frontend/Dockerfile
    - frontend/package.json with dependencies
    - Configure TypeScript, ESLint, Prettier

### Create Docker Compose Configuration
- type: task
- priority: 0
- description: |
    Create docker-compose.yml with services:
    - backend (FastAPI)
    - frontend (React)
    - db (PostgreSQL 15)
    - qdrant (Qdrant 1.7+)
    Configure volumes, ports, environment variables, dependencies

### Setup Alembic Migrations
- type: task
- priority: 1
- description: |
    Initialize Alembic for database migrations:
    - alembic init backend/alembic
    - Configure alembic.ini
    - Create initial migration script structure

---

## Epic: Database Layer
- type: epic
- description: PostgreSQL models, repositories, and migrations

### Create SQLAlchemy Database Models
- type: task
- priority: 1
- description: |
    Implement SQLAlchemy ORM models in backend/app/db/models.py:
    - User model (id, email, role, created_at, last_login, is_active)
    - Document model (id, user_id, filename, normalized_filename, file_type, file_path, file_size, page_count, status, chunking_strategy, ocr_enabled, error_message, timestamps)
    - Chunk model (id, document_id, content, chunk_index, page_numbers, start_offset, end_offset, token_count, extracted_metadata, content_tsv)
    - Thread model (id, user_id, name, timestamps)
    - Message model (id, thread_id, role, content, citations, model_used, is_from_documents, token_count)
    - ExtractionSchema model (id, name, description, schema_definition, is_default, created_by)
    - AuditLog model (id, user_id, action, resource_type, resource_id, details, ip_address)

### Create Database Connection Pool
- type: task
- priority: 1
- description: |
    Implement database connection management in backend/app/db/database.py:
    - Async SQLAlchemy engine with QueuePool (pool_size=10, max_overflow=20)
    - Session factory and dependency injection
    - Database health check function

### Create Initial Migration
- type: task
- priority: 1
- depends: Create SQLAlchemy Database Models
- description: |
    Generate Alembic migration for all tables:
    - users, documents, chunks, threads, messages, extraction_schemas, audit_logs
    - All indexes including FTS GIN index on chunks.content_tsv
    - Foreign key constraints with ON DELETE CASCADE

### Create User Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/user.py:
    - get_by_id, get_by_email, create, update, delete
    - list_all with pagination and filters (role, is_active)
    - update_last_login

### Create Document Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/document.py:
    - get_by_id, create, update, delete
    - list_by_user with pagination and status filter
    - get_by_user_and_filename
    - update_status with error_message support
    - atomic status claim for processing (optimistic lock)

### Create Chunk Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/chunk.py:
    - create_bulk (batch insert)
    - get_by_document
    - delete_by_document
    - full_text_search with tsvector
    - get_by_ids

### Create Thread Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/thread.py:
    - get_by_id, create, update, delete
    - list_by_user with pagination (ordered by updated_at DESC)

### Create Message Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/message.py:
    - create, get_by_thread
    - get_conversation_history (for context window)

### Create Schema Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/schema.py:
    - CRUD operations
    - get_default_schema
    - set_default_schema

### Create AuditLog Repository
- type: task
- priority: 2
- depends: Create SQLAlchemy Database Models
- description: |
    Implement backend/app/db/repositories/audit.py:
    - create_log
    - list_by_user, list_by_resource
    - list_recent with pagination

---

## Epic: Pydantic Models
- type: epic
- description: Request/response models for API validation

### Create User Pydantic Models
- type: task
- priority: 1
- description: |
    Implement backend/app/models/user.py:
    - UserCreate, UserUpdate, UserResponse
    - Role enum (user, superuser, admin)

### Create Document Pydantic Models
- type: task
- priority: 1
- description: |
    Implement backend/app/models/document.py:
    - DocumentUpload (chunking_strategy, ocr_enabled, force_replace)
    - DocumentResponse, DocumentListResponse
    - DocumentStatus enum

### Create Chunk Pydantic Models
- type: task
- priority: 1
- description: |
    Implement backend/app/models/chunk.py:
    - ChunkCreate, ChunkResponse
    - SearchResult with highlight_offsets

### Create Thread/Message Pydantic Models
- type: task
- priority: 1
- description: |
    Implement backend/app/models/thread.py and message.py:
    - ThreadCreate, ThreadResponse
    - MessageCreate, MessageResponse
    - Citation model

### Create Schema Pydantic Models
- type: task
- priority: 1
- description: |
    Implement backend/app/models/schema.py:
    - ExtractionSchemaCreate, ExtractionSchemaUpdate, ExtractionSchemaResponse
    - EntityDefinition, CustomFieldDefinition

### Create Error Response Models
- type: task
- priority: 1
- description: |
    Implement backend/app/models/errors.py:
    - ErrorResponse with code, message, details
    - Standard error codes enum

---

## Epic: Core Backend Services
- type: epic
- description: Business logic layer services

### Implement Config Service
- type: task
- priority: 1
- description: |
    Create backend/app/config.py with Pydantic Settings:
    - Load all environment variables
    - Validate VECTOR_WEIGHT + KEYWORD_WEIGHT = 1.0
    - Defaults for optional settings
    - Type validation for all config values

### Implement LLM Service
- type: task
- priority: 1
- description: |
    Create backend/app/services/llm.py:
    - Abstract LLMProvider interface
    - OpenAI implementation (GPT-4)
    - Anthropic implementation (Claude 3)
    - generate_completion (sync and streaming)
    - generate_embeddings (text-embedding-3-small, 1536 dims)
    - Retry logic with tenacity (3 attempts, exponential backoff)

### Implement Auth Service
- type: task
- priority: 1
- description: |
    Create backend/app/services/auth.py:
    - Supabase JWT validation against public key
    - get_current_user dependency
    - require_role decorator
    - Token extraction from Authorization header

### Implement Ingestion Service
- type: task
- priority: 2
- depends: Create Chunk Repository, Implement LLM Service
- description: |
    Create backend/app/services/ingestion.py:
    - Pipeline orchestration: parse → OCR (optional) → chunk → extract → embed → index
    - Document status updates at each stage
    - Idempotent processing with optimistic locking
    - Error handling with status='failed' and error_message

### Implement Chunking Utilities
- type: task
- priority: 2
- description: |
    Create backend/app/utils/chunking.py:
    - Fixed-size chunking (512 tokens, 50 overlap)
    - Semantic chunking (sentence boundaries)
    - Token counting using tiktoken
    - Track start_offset, end_offset, page_numbers

### Implement PDF Utilities
- type: task
- priority: 2
- description: |
    Create backend/app/utils/pdf.py:
    - PDF text extraction with page tracking
    - Page count detection
    - Coordinate mapping for highlights

### Implement OCR Service
- type: task
- priority: 2
- depends: Implement LLM Service
- description: |
    Create OCR integration using Mistral Vision:
    - PDF page to image conversion
    - pixtral-large-latest API calls
    - Text extraction from images
    - Merge OCR text with native text

### Implement Extraction Service
- type: task
- priority: 2
- depends: Implement LLM Service
- description: |
    Create backend/app/services/extraction.py:
    - LangExtract integration
    - Schema loading and application
    - Entity extraction (people, dates, terms)
    - Custom field extraction with patterns
    - Store extracted metadata in chunk.extracted_metadata

### Implement Qdrant Vector Store Service
- type: task
- priority: 2
- depends: Implement LLM Service
- description: |
    Create backend/app/services/vectorstore.py:
    - Qdrant client connection with API key and TLS support
    - Collection creation (1536 dimensions, cosine similarity)
    - Batch vector upsert with payloads (chunk_id, document_id, user_id)
    - Vector search with filters
    - Delete vectors by document_id

### Implement Retrieval Service
- type: task
- priority: 2
- depends: Implement Qdrant Vector Store Service, Create Chunk Repository
- description: |
    Create backend/app/services/retrieval.py:
    - Hybrid search combining vector and keyword
    - RRF fusion with configurable weights
    - Query embedding generation
    - Result ranking and deduplication
    - Filter by user_id and document status='ready'

### Implement Chat Service
- type: task
- priority: 2
- depends: Implement Retrieval Service, Implement LLM Service
- description: |
    Create backend/app/services/chat.py:
    - Thread management
    - Agentic retrieval logic:
      - Query type analysis (factual, synthesis, comparison)
      - Sub-query decomposition for complex queries
      - Relevance threshold checking (default 0.6)
      - Query refinement on low relevance
    - Context building from retrieved chunks
    - Prompt construction with SYSTEM_PROMPT_TEMPLATE
    - Citation extraction and formatting
    - Fallback behavior (RUHROH_ENABLE_FALLBACK)

### Implement Streaming Response Handler
- type: task
- priority: 2
- depends: Implement Chat Service
- description: |
    Create SSE streaming for chat:
    - EventSourceResponse from sse-starlette
    - Status events (searching, thinking, generating)
    - Token streaming
    - Citation events during generation
    - Done/error terminal events
    - Proper event ordering

### Implement Admin Service
- type: task
- priority: 2
- depends: Create User Repository, Create Document Repository
- description: |
    Create backend/app/services/admin.py:
    - User listing with filters
    - User role/status updates
    - Stats aggregation (users, documents, queries)
    - Document listing across all users
    - System health checks

### Implement Eval Service
- type: task
- priority: 3
- depends: Implement Retrieval Service, Implement LLM Service
- description: |
    Create backend/app/services/eval.py:
    - Question generation from chunks using LLM
    - Ground truth storage
    - Retrieval testing against questions
    - Metrics calculation:
      - Hit Rate
      - MRR (Mean Reciprocal Rank)
      - Context Precision
      - Answer Relevancy (LLM-judged)
    - Strategy comparison reports
    - Holdout split support (80/20)
    - Cost controls (50 questions max, document sampling)

---

## Epic: API Routes
- type: epic
- description: FastAPI route handlers

### Implement Auth Routes
- type: task
- priority: 2
- depends: Implement Auth Service
- description: |
    Create backend/app/api/auth.py:
    - POST /auth/register (proxy to Supabase)
    - POST /auth/login (proxy to Supabase)
    - POST /auth/refresh (proxy to Supabase)
    - POST /auth/logout

### Implement Document Routes
- type: task
- priority: 2
- depends: Implement Ingestion Service
- description: |
    Create backend/app/api/documents.py:
    - POST /documents/upload (multipart, 409 on conflict unless force_replace)
    - GET /documents (list with pagination)
    - GET /documents/{id}
    - GET /documents/{id}/status
    - DELETE /documents/{id}
    - POST /documents/{id}/reprocess

### Implement Chat Routes
- type: task
- priority: 2
- depends: Implement Chat Service, Implement Streaming Response Handler
- description: |
    Create backend/app/api/chat.py:
    - GET /chat/threads (list with pagination)
    - POST /chat/threads
    - GET /chat/threads/{id} (with messages)
    - DELETE /chat/threads/{id}
    - POST /chat/threads/{id}/messages (SSE streaming response)

### Implement Search Routes
- type: task
- priority: 2
- depends: Implement Retrieval Service
- description: |
    Create backend/app/api/search.py:
    - POST /search (direct search endpoint)
    - Support top_k, document_ids filter, use_keyword, use_vector toggles

### Implement Admin Routes
- type: task
- priority: 2
- depends: Implement Admin Service
- description: |
    Create backend/app/api/admin.py:
    - GET /admin/users (admin only)
    - PATCH /admin/users/{id} (admin only)
    - GET /admin/stats (admin/superuser)
    - GET /admin/documents (admin only)
    - DELETE /admin/documents/{id} (admin only)
    - GET /admin/health

### Implement Config Routes
- type: task
- priority: 2
- depends: Create Schema Repository
- description: |
    Create backend/app/api/config.py:
    - GET /config/schemas (superuser/admin)
    - POST /config/schemas (superuser/admin)
    - PUT /config/schemas/{id} (superuser/admin)
    - DELETE /config/schemas/{id} (admin only)
    - PUT /config/schemas/{id}/default (admin only)

### Implement Eval Routes
- type: task
- priority: 3
- depends: Implement Eval Service
- description: |
    Create backend/app/api/eval.py:
    - POST /eval/run (superuser/admin)
    - GET /eval/{id} (status and results)

---

## Epic: Backend Middleware & Utilities
- type: epic
- description: Cross-cutting concerns

### Implement Rate Limiting
- type: task
- priority: 2
- description: |
    Create rate limiting middleware:
    - Configurable RPM (RUHROH_RATE_LIMIT_RPM, default 60)
    - Burst allowance (RUHROH_RATE_LIMIT_BURST, default 10)
    - Token bucket or sliding window algorithm
    - Rate limit headers in responses
    - 429 response with retry-after

### Implement Request ID Tracking
- type: task
- priority: 2
- description: |
    Create middleware for request tracking:
    - Generate or extract X-Request-ID
    - Bind to structlog context
    - Include in all responses
    - Include in error responses

### Implement Structured Logging
- type: task
- priority: 2
- description: |
    Create backend/app/utils/logging.py:
    - structlog configuration with JSON output
    - Log levels from environment
    - Key event logging (uploads, searches, chat, errors)
    - Request/response logging middleware

### Implement Security Utilities
- type: task
- priority: 2
- description: |
    Create backend/app/utils/security.py:
    - HTML sanitization
    - Prompt injection pattern detection
    - File MIME type validation using python-magic
    - File size validation (500MB max)

### Implement Error Handling
- type: task
- priority: 2
- description: |
    Create global exception handlers:
    - Custom exception classes for each error code
    - Exception handler middleware
    - Consistent ErrorResponse format
    - Request ID in error responses

### Create OpenAPI Documentation
- type: task
- priority: 2
- description: |
    Configure FastAPI OpenAPI:
    - Swagger UI at /docs
    - ReDoc at /redoc
    - Security scheme for Bearer tokens
    - Example requests/responses
    - Tag grouping for endpoints

---

## Epic: Frontend Core
- type: epic
- description: React frontend foundation

### Setup Frontend State Management
- type: task
- priority: 2
- description: |
    Implement state management:
    - Zustand or React Context for auth state
    - User info, tokens, role
    - Persist to localStorage
    - Auth refresh handling

### Implement API Client
- type: task
- priority: 2
- description: |
    Create frontend/src/services/api.ts:
    - Axios or fetch wrapper
    - Base URL configuration
    - Auth token injection
    - Error handling
    - Request/response interceptors

### Implement Auth Pages
- type: task
- priority: 2
- depends: Implement API Client
- description: |
    Create auth pages:
    - Login page with email/password
    - Register page
    - Protected route wrapper
    - Redirect logic

### Implement Layout Components
- type: task
- priority: 2
- description: |
    Create layout components:
    - Sidebar navigation
    - Header with user menu
    - Main content area
    - Responsive design

---

## Epic: Frontend Document Management
- type: epic
- description: Document upload and management UI

### Implement File Upload Component
- type: task
- priority: 2
- depends: Implement API Client
- description: |
    Create drag-and-drop upload:
    - react-dropzone or similar
    - Multiple file support
    - File type validation (PDF, TXT)
    - Size validation display
    - OCR toggle per file
    - Chunking strategy selector
    - Upload progress indicator

### Implement Document List Component
- type: task
- priority: 2
- depends: Implement API Client
- description: |
    Create document list:
    - Table/grid view
    - Status badges (pending, processing, ready, failed)
    - Pagination
    - Delete with confirmation
    - Reprocess action

### Implement Document Status Polling
- type: task
- priority: 2
- depends: Implement File Upload Component
- description: |
    Create status polling:
    - Poll /documents/{id}/status during processing
    - Progress stage display
    - Auto-update list on completion
    - Error display for failed documents

---

## Epic: Frontend Chat Interface
- type: epic
- description: Chat UI with SSE streaming

### Implement Thread List Component
- type: task
- priority: 2
- depends: Implement API Client
- description: |
    Create thread sidebar:
    - List of conversation threads
    - Create new thread button
    - Thread selection
    - Delete thread with confirmation
    - Thread name display

### Implement Chat Message Components
- type: task
- priority: 2
- description: |
    Create message display:
    - User message bubbles
    - Assistant message bubbles
    - Citation links [1], [2] format
    - Markdown rendering
    - Code block syntax highlighting

### Implement SSE Chat Handler
- type: task
- priority: 2
- depends: Implement API Client
- description: |
    Create SSE streaming handler:
    - EventSource connection
    - Handle status events (searching, thinking, generating)
    - Token accumulation and display
    - Citation extraction
    - Error handling
    - Reconnection logic

### Implement Chat Input Component
- type: task
- priority: 2
- description: |
    Create chat input:
    - Text input with submit
    - Enter to send, Shift+Enter for newline
    - Disable during streaming
    - Status indicators (searching, thinking, generating)

### Implement PDF Viewer with Highlighting
- type: task
- priority: 3
- description: |
    Create PDF citation viewer:
    - react-pdf or pdf.js integration
    - Load PDF from document endpoint
    - Highlight cited sections
    - Page navigation
    - Click citation to jump to page

---

## Epic: Frontend Admin Panel
- type: epic
- description: Admin dashboard and management

### Implement User Management Page
- type: task
- priority: 3
- depends: Implement API Client
- description: |
    Create admin user management:
    - User list table
    - Role display and edit
    - Active/inactive toggle
    - Filter by role
    - Admin role check

### Implement Stats Dashboard
- type: task
- priority: 3
- depends: Implement API Client
- description: |
    Create stats overview:
    - Total users, active today
    - Total documents by status
    - Queries today
    - Simple charts/metrics display

### Implement System Health Display
- type: task
- priority: 3
- depends: Implement API Client
- description: |
    Create health status component:
    - API status
    - Database status
    - Qdrant status
    - Supabase status
    - Auto-refresh

---

## Epic: Testing
- type: epic
- description: Test coverage

### Setup Backend Testing Infrastructure
- type: task
- priority: 2
- description: |
    Configure pytest:
    - pytest.ini
    - conftest.py with fixtures
    - Test database setup/teardown
    - Mock Supabase, OpenAI, Qdrant

### Write Database Repository Tests
- type: task
- priority: 2
- depends: Setup Backend Testing Infrastructure
- description: |
    Test all repository operations:
    - CRUD for each repository
    - Edge cases
    - Constraint violations
    - Pagination

### Write Service Layer Tests
- type: task
- priority: 3
- depends: Setup Backend Testing Infrastructure
- description: |
    Test service business logic:
    - Ingestion pipeline stages
    - Retrieval and fusion
    - Chat agent logic
    - Auth validation

### Write API Integration Tests
- type: task
- priority: 3
- depends: Setup Backend Testing Infrastructure
- description: |
    Test API endpoints:
    - Auth flow
    - Document upload/processing
    - Chat streaming
    - Admin operations
    - Error responses

### Setup Frontend Testing
- type: task
- priority: 3
- description: |
    Configure Vitest/Jest:
    - Component testing setup
    - Mock API responses
    - Test utilities

### Write Frontend Component Tests
- type: task
- priority: 3
- depends: Setup Frontend Testing
- description: |
    Test key components:
    - Upload component
    - Chat interface
    - Auth forms

---

## Epic: Documentation & Deployment
- type: epic
- description: Final documentation and deployment prep

### Create README.md
- type: task
- priority: 2
- description: |
    Write comprehensive README:
    - Project overview
    - Quick start guide
    - Environment variables reference
    - API documentation link
    - Development setup
    - Architecture overview

### Create .env.example
- type: task
- priority: 1
- description: |
    Create example environment file:
    - All required variables
    - All optional variables with defaults
    - Comments explaining each

### Create Deployment Documentation
- type: task
- priority: 3
- description: |
    Write deployment guide:
    - Pre-flight checklist
    - Docker Compose instructions
    - Environment configuration
    - Supabase setup
    - First user creation
    - Troubleshooting

### Create Startup Scripts
- type: task
- priority: 2
- description: |
    Create scripts/start.sh:
    - Database migration
    - Server startup
    - Health check wait
