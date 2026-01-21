#!/bin/bash
# Create ruhroh implementation tasks

# ========================
# EPICS
# ========================

# Infrastructure Setup Epic
bd create "Project Infrastructure Setup" -t epic -p 0 -d "Core project scaffolding and infrastructure for backend, frontend, and Docker deployment"

# Database Epic
bd create "Database Layer" -t epic -p 0 -d "PostgreSQL models, repositories, migrations, and data access layer"

# Pydantic Models Epic
bd create "Pydantic Models" -t epic -p 1 -d "Request/response models for API validation"

# Core Services Epic
bd create "Core Backend Services" -t epic -p 0 -d "Business logic layer: LLM, Auth, Ingestion, Retrieval, Chat, Admin, Eval services"

# API Routes Epic
bd create "API Routes" -t epic -p 1 -d "FastAPI route handlers for auth, documents, chat, search, admin, config, eval"

# Middleware Epic
bd create "Backend Middleware & Utilities" -t epic -p 1 -d "Rate limiting, request tracking, logging, security, error handling"

# Frontend Core Epic
bd create "Frontend Core" -t epic -p 1 -d "React frontend foundation: state management, API client, auth, layout"

# Frontend Documents Epic
bd create "Frontend Document Management" -t epic -p 1 -d "Document upload and management UI with drag-drop and status tracking"

# Frontend Chat Epic
bd create "Frontend Chat Interface" -t epic -p 1 -d "Chat UI with SSE streaming, thread management, PDF viewer"

# Frontend Admin Epic
bd create "Frontend Admin Panel" -t epic -p 2 -d "Admin dashboard: user management, stats, system health"

# Testing Epic
bd create "Testing" -t epic -p 2 -d "Backend and frontend test coverage"

# Documentation Epic
bd create "Documentation & Deployment" -t epic -p 1 -d "README, deployment docs, startup scripts"

echo "Epics created. Now creating tasks..."

# ========================
# INFRASTRUCTURE TASKS
# ========================

bd create "Initialize Backend Project Structure" -t task -p 0 -d "Create FastAPI backend project structure:
- backend/app/ directory with __init__.py, main.py, config.py, dependencies.py
- backend/app/api/, services/, models/, db/, utils/ subdirectories
- backend/requirements.txt with core dependencies (FastAPI, SQLAlchemy, Pydantic, etc.)
- backend/Dockerfile
- backend/.env.example"

bd create "Initialize Frontend Project Structure" -t task -p 0 -d "Create React/TypeScript/Vite frontend project:
- frontend/src/ with components/, pages/, hooks/, services/, stores/, types/
- frontend/Dockerfile
- frontend/package.json with dependencies (React 18+, TypeScript 5+)
- Configure TypeScript, ESLint, Prettier"

bd create "Create Docker Compose Configuration" -t task -p 0 -d "Create docker-compose.yml with services:
- backend (FastAPI on port 8000)
- frontend (React on port 3000)
- db (PostgreSQL 15 on port 5432)
- qdrant (Qdrant 1.7+ on port 6333)
Configure volumes, ports, environment variables, service dependencies"

bd create "Setup Alembic Migrations" -t task -p 1 -d "Initialize Alembic for database migrations:
- alembic init backend/alembic
- Configure alembic.ini with async support
- Create initial migration script structure"

# ========================
# DATABASE TASKS
# ========================

bd create "Create SQLAlchemy Database Models" -t task -p 1 -d "Implement SQLAlchemy ORM models in backend/app/db/models.py:
- User (id, email, role enum, created_at, last_login, is_active)
- Document (id, user_id FK, filename, normalized_filename, file_type, file_path, file_size, page_count, status enum, chunking_strategy, ocr_enabled, error_message, timestamps, UNIQUE(user_id, normalized_filename))
- Chunk (id, document_id FK CASCADE, content, chunk_index, page_numbers array, start_offset, end_offset, token_count, extracted_metadata JSONB, content_tsv tsvector GENERATED)
- Thread (id, user_id FK CASCADE, name, timestamps)
- Message (id, thread_id FK CASCADE, role, content, citations JSONB, model_used, is_from_documents, token_count)
- ExtractionSchema (id, name, description, schema_definition JSONB, is_default, created_by FK)
- AuditLog (id, user_id FK, action, resource_type, resource_id, details JSONB, ip_address INET)"

bd create "Create Database Connection Pool" -t task -p 1 -d "Implement database connection management in backend/app/db/database.py:
- Async SQLAlchemy engine with QueuePool (pool_size=10, max_overflow=20, pool_timeout=30)
- AsyncSession factory with sessionmaker
- get_db dependency for FastAPI injection
- Database health check function"

bd create "Create Initial Migration" -t task -p 1 -d "Generate Alembic migration for all tables:
- All 7 tables: users, documents, chunks, threads, messages, extraction_schemas, audit_logs
- All indexes including GIN index on chunks.content_tsv for FTS
- Foreign key constraints with ON DELETE CASCADE where appropriate"

bd create "Create User Repository" -t task -p 2 -d "Implement backend/app/db/repositories/user.py:
- get_by_id(id) -> User | None
- get_by_email(email) -> User | None
- create(user_data) -> User
- update(id, user_data) -> User
- delete(id) -> bool
- list_all(skip, limit, role_filter, is_active_filter) -> list[User]
- update_last_login(id)"

bd create "Create Document Repository" -t task -p 2 -d "Implement backend/app/db/repositories/document.py:
- get_by_id(id) -> Document | None
- create(doc_data) -> Document
- update(id, doc_data) -> Document
- delete(id) -> bool (also deletes chunks)
- list_by_user(user_id, skip, limit, status_filter) -> list[Document]
- get_by_user_and_filename(user_id, normalized_filename) -> Document | None
- update_status(id, status, error_message=None)
- claim_for_processing(id) -> bool (atomic WHERE status='pending')"

bd create "Create Chunk Repository" -t task -p 2 -d "Implement backend/app/db/repositories/chunk.py:
- create_bulk(chunks: list) -> list[Chunk]
- get_by_document(document_id) -> list[Chunk]
- delete_by_document(document_id) -> int (count deleted)
- full_text_search(query, user_id, document_ids=None, limit=20) -> list[Chunk]
- get_by_ids(ids: list[UUID]) -> list[Chunk]"

bd create "Create Thread Repository" -t task -p 2 -d "Implement backend/app/db/repositories/thread.py:
- get_by_id(id, user_id) -> Thread | None
- create(user_id, name) -> Thread
- update(id, name) -> Thread
- delete(id) -> bool
- list_by_user(user_id, skip, limit) -> list[Thread] (ORDER BY updated_at DESC)"

bd create "Create Message Repository" -t task -p 2 -d "Implement backend/app/db/repositories/message.py:
- create(message_data) -> Message
- get_by_thread(thread_id, skip, limit) -> list[Message]
- get_conversation_history(thread_id, limit) -> list[Message] (for context window)"

bd create "Create Schema Repository" -t task -p 2 -d "Implement backend/app/db/repositories/schema.py:
- CRUD operations (get_by_id, create, update, delete)
- list_all() -> list[ExtractionSchema]
- get_default_schema() -> ExtractionSchema | None
- set_default_schema(id) -> ExtractionSchema (unset previous default)"

bd create "Create AuditLog Repository" -t task -p 2 -d "Implement backend/app/db/repositories/audit.py:
- create_log(user_id, action, resource_type, resource_id, details, ip_address)
- list_by_user(user_id, skip, limit) -> list[AuditLog]
- list_by_resource(resource_type, resource_id) -> list[AuditLog]
- list_recent(skip, limit) -> list[AuditLog]"

# ========================
# PYDANTIC MODEL TASKS
# ========================

bd create "Create User Pydantic Models" -t task -p 1 -d "Implement backend/app/models/user.py:
- Role enum (user, superuser, admin)
- UserCreate (email, password)
- UserUpdate (role?, is_active?)
- UserResponse (id, email, role, created_at, last_login, is_active)"

bd create "Create Document Pydantic Models" -t task -p 1 -d "Implement backend/app/models/document.py:
- DocumentStatus enum (pending, processing, ready, failed)
- ChunkingStrategy enum (fixed, semantic)
- DocumentUpload (chunking_strategy=fixed, ocr_enabled=false, force_replace=false)
- DocumentResponse (all fields)
- DocumentListResponse (documents, total)
- DocumentStatusResponse (status, progress, error_message?)"

bd create "Create Chunk Pydantic Models" -t task -p 1 -d "Implement backend/app/models/chunk.py:
- ChunkCreate (content, chunk_index, page_numbers, offsets, token_count)
- ChunkResponse (id, document_id, content, chunk_index, page_numbers, extracted_metadata)
- SearchResult (chunk_id, document_id, document_name, content, page_numbers, score, highlight_offsets)"

bd create "Create Thread/Message Pydantic Models" -t task -p 1 -d "Implement backend/app/models/thread.py and message.py:
- ThreadCreate (name?)
- ThreadResponse (id, name, created_at, updated_at)
- ThreadWithMessages (thread + messages)
- MessageCreate (content, model?)
- Citation (index, chunk_id, document_id, page?)
- MessageResponse (id, thread_id, role, content, citations, model_used, is_from_documents, created_at)"

bd create "Create Schema Pydantic Models" -t task -p 1 -d "Implement backend/app/models/schema.py:
- EntityDefinition (name, description, examples)
- CustomFieldDefinition (name, description, pattern?)
- SchemaDefinition (entities, custom_fields)
- ExtractionSchemaCreate (name, description, schema_definition)
- ExtractionSchemaUpdate (name?, description?, schema_definition?)
- ExtractionSchemaResponse (id, name, description, schema_definition, is_default, created_by, created_at)"

bd create "Create Error Response Models" -t task -p 1 -d "Implement backend/app/models/errors.py:
- ErrorCode enum (UNAUTHORIZED, FORBIDDEN, NOT_FOUND, CONFLICT, VALIDATION_ERROR, RATE_LIMITED, PROCESSING_FAILED, LLM_ERROR, SERVICE_UNAVAILABLE)
- ErrorDetail (code, message, details?)
- ErrorResponse (error: ErrorDetail, request_id)"

# ========================
# CORE BACKEND SERVICES
# ========================

bd create "Implement Config Service" -t task -p 1 -d "Create backend/app/config.py with Pydantic BaseSettings:
- Required: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL, QDRANT_HOST, QDRANT_PORT
- Optional LLM: ANTHROPIC_API_KEY, MISTRAL_API_KEY
- Optional Qdrant: QDRANT_API_KEY, QDRANT_USE_TLS
- Config: RUHROH_VECTOR_WEIGHT (0.6), RUHROH_KEYWORD_WEIGHT (0.4), RUHROH_RRF_K (60)
- Config: RUHROH_ENABLE_FALLBACK (false), RUHROH_RATE_LIMIT_RPM (60), RUHROH_RATE_LIMIT_BURST (10)
- Config: RUHROH_DEFAULT_MODEL (gpt-4), RUHROH_CHUNK_SIZE (512), RUHROH_CHUNK_OVERLAP (50)
- Validator: VECTOR_WEIGHT + KEYWORD_WEIGHT = 1.0"

bd create "Implement LLM Service" -t task -p 1 -d "Create backend/app/services/llm.py:
- Abstract LLMProvider protocol with generate_completion and generate_completion_stream
- OpenAIProvider: GPT-4 implementation
- AnthropicProvider: Claude 3 implementation
- generate_embeddings(texts: list[str]) -> list[list[float]] using text-embedding-3-small (1536 dims)
- Retry logic with tenacity (stop_after_attempt=3, wait_exponential multiplier=1, min=2, max=30)
- Provider factory based on config"

bd create "Implement Auth Service" -t task -p 1 -d "Create backend/app/services/auth.py:
- Supabase JWT validation against SUPABASE_URL public key
- get_current_user(token) -> User dependency
- require_role(allowed_roles: list[str]) decorator
- Extract token from 'Authorization: Bearer <token>' header
- Look up user role from local DB for authorization"

bd create "Implement Ingestion Service" -t task -p 2 -d "Create backend/app/services/ingestion.py:
- process_document_pipeline(document_id) orchestrator
- Stages: parse -> OCR (if enabled) -> chunk -> extract -> embed -> index
- Update document status at each stage for progress tracking
- Idempotent processing with atomic status claim (WHERE status='pending')
- Error handling: set status='failed', store error_message
- Delete existing chunks before reprocessing"

bd create "Implement Chunking Utilities" -t task -p 2 -d "Create backend/app/utils/chunking.py:
- fixed_size_chunking(text, chunk_size=512, overlap=50) -> list[ChunkData]
- semantic_chunking(text) -> list[ChunkData] (split at sentence boundaries)
- count_tokens(text) -> int using tiktoken (cl100k_base)
- ChunkData: content, start_offset, end_offset, token_count
- Track page_numbers from PDF extraction"

bd create "Implement PDF Utilities" -t task -p 2 -d "Create backend/app/utils/pdf.py:
- extract_text_from_pdf(file_path) -> ExtractedPDF
- ExtractedPDF: text, page_count, page_boundaries list
- Map character offsets to page numbers
- Support for PDF coordinate extraction for highlighting"

bd create "Implement OCR Service" -t task -p 2 -d "Create OCR integration using Mistral Vision:
- pdf_to_images(pdf_path) -> list[bytes] (page images)
- ocr_image(image_bytes) -> str using pixtral-large-latest
- process_pdf_with_ocr(pdf_path) -> str (merged text)
- Merge OCR text with native PDF text where applicable"

bd create "Implement Extraction Service" -t task -p 2 -d "Create backend/app/services/extraction.py:
- LangExtract integration for entity extraction
- extract_from_chunk(chunk_text, schema) -> dict
- Load default schema or user-specified schema
- Extract entities: people, dates, key terms
- Extract custom fields with regex patterns
- Return extracted_metadata dict for chunk storage"

bd create "Implement Qdrant Vector Store Service" -t task -p 2 -d "Create backend/app/services/vectorstore.py:
- QdrantClient initialization with QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_USE_TLS
- ensure_collection() - create if not exists (1536 dims, cosine similarity)
- upsert_vectors(vectors: list[VectorData]) - batch upsert with payloads (chunk_id, document_id, user_id)
- search_vectors(query_vector, user_id, document_ids?, top_k) -> list[ScoredPoint]
- delete_by_document(document_id) -> int count deleted
- health_check() -> bool"

bd create "Implement Retrieval Service" -t task -p 2 -d "Create backend/app/services/retrieval.py:
- hybrid_search(query, user_id, document_ids?, top_k=10) -> list[SearchResult]
- Execute vector search via Qdrant
- Execute keyword search via PostgreSQL FTS
- RRF fusion: score = sum(1/(k + rank)) with configurable k
- Apply configurable weights (vector_weight, keyword_weight)
- Deduplicate results by chunk_id
- Filter: only documents with status='ready'"

bd create "Implement Chat Service" -t task -p 2 -d "Create backend/app/services/chat.py:
- process_message(thread_id, content, user) -> AsyncGenerator[ChatEvent]
- Agentic retrieval logic:
  1. Analyze query type (factual, synthesis, comparison)
  2. Simple factual -> direct hybrid search
  3. Complex -> decompose into 2-3 sub-queries, execute in parallel
  4. Check relevance scores >= threshold (0.6)
  5. If low relevance, refine query with LLM, retry once
- Build context from retrieved chunks
- Construct prompt with SYSTEM_PROMPT_TEMPLATE
- Extract and format citations [1], [2]
- Fallback behavior based on RUHROH_ENABLE_FALLBACK"

bd create "Implement Streaming Response Handler" -t task -p 2 -d "Create SSE streaming for chat responses:
- Use sse-starlette EventSourceResponse
- ChatEvent types: status, token, citation, error, done
- Yield status events: {stage: 'searching' | 'thinking' | 'generating'}
- Yield token events during LLM streaming: {content: string}
- Yield citation events: {index, chunk_id, document_id, page}
- Yield done event: {message_id, is_from_documents}
- Yield error event on failure: {code, message}
- Event ordering: status* -> token* -> citation* -> (done | error)"

bd create "Implement Admin Service" -t task -p 2 -d "Create backend/app/services/admin.py:
- list_users(role_filter?, is_active_filter?) -> list[User]
- update_user(id, role?, is_active?) -> User
- get_stats() -> Stats (total_users, active_today, total_documents, queries_today, documents_by_status)
- list_all_documents(user_id?, status?) -> list[Document]
- delete_document(id) -> bool (admin can delete any)
- get_health() -> HealthStatus (api, database, qdrant, supabase status)"

bd create "Implement Eval Service" -t task -p 3 -d "Create backend/app/services/eval.py:
- run_evaluation(document_ids?, question_count=50, strategies?, use_holdout=false) -> eval_id
- generate_questions(chunks, count) -> list[Question] using LLM
- Store questions with ground truth chunk IDs
- run_retrieval_tests(questions, strategy) -> list[TestResult]
- Calculate metrics:
  - Hit Rate: % queries where correct chunk in top-k
  - MRR: mean(1/rank) for correct chunk
  - Context Precision: relevant_retrieved / total_retrieved
  - Answer Relevancy: LLM-judged score
- Strategy comparison if multiple strategies
- Holdout split: generate from 80%, test against 100%
- Cost controls: max 50 questions, sample if corpus >100 docs"

# ========================
# API ROUTES
# ========================

bd create "Implement Auth Routes" -t task -p 2 -d "Create backend/app/api/auth.py:
- POST /auth/register: proxy to Supabase, create local user record
- POST /auth/login: proxy to Supabase, return tokens
- POST /auth/refresh: proxy to Supabase refresh
- POST /auth/logout: 204 response
- Handle Supabase errors and translate to API errors"

bd create "Implement Document Routes" -t task -p 2 -d "Create backend/app/api/documents.py:
- POST /documents/upload: multipart/form-data, 409 Conflict if exists and !force_replace, 202 with document_id
- GET /documents: list with pagination (limit, offset, status filter)
- GET /documents/{id}: full details with chunk count
- GET /documents/{id}/status: status, progress stage, error_message
- DELETE /documents/{id}: 204, cascade delete chunks/vectors
- POST /documents/{id}/reprocess: 202, reset and requeue
- All routes check user owns document"

bd create "Implement Chat Routes" -t task -p 2 -d "Create backend/app/api/chat.py:
- GET /chat/threads: list user's threads with pagination
- POST /chat/threads: create new thread, 201
- GET /chat/threads/{id}: thread + messages
- DELETE /chat/threads/{id}: 204
- POST /chat/threads/{id}/messages: SSE streaming response
- All routes check user owns thread"

bd create "Implement Search Routes" -t task -p 2 -d "Create backend/app/api/search.py:
- POST /search: direct search endpoint (bypass chat)
- Body: query (required), top_k (default 10), document_ids (optional filter), use_keyword (true), use_vector (true)
- Response: results array of SearchResult
- Only search user's documents with status='ready'"

bd create "Implement Admin Routes" -t task -p 2 -d "Create backend/app/api/admin.py:
- GET /admin/users: admin only, list with filters
- PATCH /admin/users/{id}: admin only, update role/is_active
- GET /admin/stats: admin/superuser, aggregated stats
- GET /admin/documents: admin only, list all documents
- DELETE /admin/documents/{id}: admin only, delete any document
- GET /admin/health: public health check endpoint"

bd create "Implement Config Routes" -t task -p 2 -d "Create backend/app/api/config.py:
- GET /config/schemas: superuser/admin, list all schemas
- POST /config/schemas: superuser/admin, create schema
- PUT /config/schemas/{id}: superuser/admin, update schema
- DELETE /config/schemas/{id}: admin only
- PUT /config/schemas/{id}/default: admin only, set as default"

bd create "Implement Eval Routes" -t task -p 3 -d "Create backend/app/api/eval.py:
- POST /eval/run: superuser/admin, start evaluation, 202 with eval_id
- GET /eval/{id}: get status and results when completed
- Body: document_ids?, question_count?, chunking_strategies?, use_holdout?
- Response: eval_id, status, progress, results (when complete)"

# ========================
# MIDDLEWARE & UTILITIES
# ========================

bd create "Implement Rate Limiting" -t task -p 2 -d "Create rate limiting middleware:
- Token bucket or sliding window algorithm
- Configurable: RUHROH_RATE_LIMIT_RPM (60), RUHROH_RATE_LIMIT_BURST (10)
- Key by user_id (authenticated) or IP (unauthenticated)
- Add headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
- Return 429 with Retry-After header when exceeded"

bd create "Implement Request ID Tracking" -t task -p 2 -d "Create request tracking middleware:
- Extract X-Request-ID from request headers or generate UUID
- Bind request_id to structlog context
- Include X-Request-ID in all response headers
- Include request_id in error responses"

bd create "Implement Structured Logging" -t task -p 2 -d "Create backend/app/utils/logging.py:
- structlog configuration with JSONRenderer
- TimeStamper with ISO format
- Log level from LOG_LEVEL env var (default INFO)
- Log key events: document_uploaded, document_processed, search_executed, chat_message, error
- Include request_id, user_id, duration_ms in logs"

bd create "Implement Security Utilities" -t task -p 2 -d "Create backend/app/utils/security.py:
- sanitize_html(text) -> str (strip HTML tags)
- validate_file_upload(file) -> None (raises on invalid)
  - Check size <= 500MB
  - Check MIME type with python-magic (PDF, TXT only)
- sanitize_prompt_input(text) -> str (escape template chars)"

bd create "Implement Error Handling" -t task -p 2 -d "Create global exception handlers:
- Custom exception classes: UnauthorizedException, ForbiddenException, NotFoundException, ConflictException, ValidationException, RateLimitedException, ProcessingException, LLMException, ServiceUnavailableException
- FastAPI exception_handler for each
- Consistent ErrorResponse format with request_id
- Log errors with full context"

bd create "Create OpenAPI Documentation" -t task -p 2 -d "Configure FastAPI OpenAPI:
- Title: ruhroh API
- Version: 1.0.0
- Swagger UI at /docs
- ReDoc at /redoc
- SecurityScheme: Bearer token (JWT)
- Tag grouping: auth, documents, chat, search, admin, config, eval
- Example request/response bodies"

# ========================
# FRONTEND CORE
# ========================

bd create "Setup Frontend State Management" -t task -p 2 -d "Implement state management:
- Zustand store for auth state
- Store: user info, access_token, refresh_token, role
- Persist to localStorage
- Auto-refresh token before expiry
- isAuthenticated, isAdmin, isSuperuser getters"

bd create "Implement Frontend API Client" -t task -p 2 -d "Create frontend/src/services/api.ts:
- Axios instance with base URL from VITE_API_URL
- Request interceptor: add Authorization header
- Response interceptor: handle 401 (trigger refresh or logout)
- Generic request methods: get, post, put, patch, delete
- Type-safe API methods for each endpoint"

bd create "Implement Auth Pages" -t task -p 2 -d "Create auth pages:
- LoginPage: email/password form, submit to /auth/login
- RegisterPage: email/password form with confirmation
- ProtectedRoute wrapper component
- Redirect to login if unauthenticated
- Redirect to home after successful auth"

bd create "Implement Layout Components" -t task -p 2 -d "Create layout components:
- AppLayout: main layout wrapper
- Sidebar: navigation links, user menu, role-based items
- Header: title, user dropdown
- MainContent: scrollable content area
- Responsive design for tablet/desktop"

# ========================
# FRONTEND DOCUMENTS
# ========================

bd create "Implement File Upload Component" -t task -p 2 -d "Create drag-and-drop upload:
- Use react-dropzone or similar
- Accept multiple files
- File type validation (PDF, TXT only)
- Size validation display (<500MB)
- Per-file options: OCR toggle, chunking strategy dropdown
- Upload progress bar per file
- Call POST /documents/upload for each file"

bd create "Implement Document List Component" -t task -p 2 -d "Create document list:
- Table view with columns: name, type, status, created, actions
- Status badges with colors (pending=yellow, processing=blue, ready=green, failed=red)
- Pagination controls
- Delete button with confirmation modal
- Reprocess button for failed documents
- Click to view document details"

bd create "Implement Document Status Polling" -t task -p 2 -d "Create status polling:
- Poll GET /documents/{id}/status every 2s for processing documents
- Display current processing stage
- Stop polling when status is ready or failed
- Auto-refresh document list on completion
- Show error message for failed documents"

# ========================
# FRONTEND CHAT
# ========================

bd create "Implement Thread List Component" -t task -p 2 -d "Create thread sidebar:
- List of conversation threads
- Display thread name and last updated
- 'New Thread' button at top
- Click to select thread
- Delete thread with confirmation
- Active thread highlight"

bd create "Implement Chat Message Components" -t task -p 2 -d "Create message display:
- UserMessage component (right-aligned, user bubble)
- AssistantMessage component (left-aligned, assistant bubble)
- Citation links [1], [2] format, clickable
- Markdown rendering with react-markdown
- Code block syntax highlighting with highlight.js or prism
- Loading state for streaming messages"

bd create "Implement SSE Chat Handler" -t task -p 2 -d "Create SSE streaming handler:
- EventSource connection to POST /chat/threads/{id}/messages
- Handle 'status' events: show searching/thinking/generating indicator
- Handle 'token' events: accumulate and display text
- Handle 'citation' events: store for rendering
- Handle 'done' event: finalize message
- Handle 'error' event: show error message
- Clean up EventSource on unmount"

bd create "Implement Chat Input Component" -t task -p 2 -d "Create chat input:
- Textarea with auto-resize
- Submit button
- Enter to send, Shift+Enter for newline
- Disable during streaming
- Status indicator (searching, thinking, generating)
- Character count or limit indicator"

bd create "Implement PDF Viewer with Highlighting" -t task -p 3 -d "Create PDF citation viewer:
- Use react-pdf or pdf.js
- Load PDF via /documents/{id}/file endpoint
- Page navigation controls
- Click citation to jump to page
- Highlight cited text sections (may need backend coordinate data)
- Side panel or modal display"

# ========================
# FRONTEND ADMIN
# ========================

bd create "Implement User Management Page" -t task -p 3 -d "Create admin user management:
- Table: email, role, active status, last login, actions
- Role dropdown to change roles (user/superuser/admin)
- Active toggle button
- Filter by role dropdown
- Admin-only access check"

bd create "Implement Stats Dashboard" -t task -p 3 -d "Create stats overview:
- Cards: total users, active users today, total documents, queries today
- Documents by status pie/bar chart
- Use a charting library (recharts, chart.js)
- Admin/superuser access check"

bd create "Implement System Health Display" -t task -p 3 -d "Create health status component:
- Poll GET /admin/health periodically
- Status indicators for: API, Database, Qdrant, Supabase
- Green/red icons
- Last checked timestamp
- Auto-refresh every 30s"

# ========================
# TESTING
# ========================

bd create "Setup Backend Testing Infrastructure" -t task -p 2 -d "Configure pytest:
- pytest.ini with async plugin
- conftest.py with fixtures
- Test database setup/teardown (use test DB or SQLite)
- Mock Supabase JWT validation
- Mock OpenAI API calls
- Mock Qdrant client"

bd create "Write Database Repository Tests" -t task -p 2 -d "Test all repository operations:
- User CRUD tests
- Document CRUD tests with cascade delete
- Chunk bulk insert and FTS tests
- Thread and Message tests
- Schema CRUD tests
- Constraint violation tests
- Pagination tests"

bd create "Write Service Layer Tests" -t task -p 3 -d "Test service business logic:
- Ingestion pipeline stages (mock dependencies)
- Retrieval and RRF fusion
- Chat agent logic (query decomposition, refinement)
- Auth JWT validation
- Config validation"

bd create "Write API Integration Tests" -t task -p 3 -d "Test API endpoints:
- Auth flow (register, login, refresh, logout)
- Document upload and processing
- Chat streaming (test SSE events)
- Admin operations (role check)
- Error responses (401, 403, 404, 409, 422)"

bd create "Setup Frontend Testing" -t task -p 3 -d "Configure Vitest/Jest:
- vitest.config.ts
- Test utilities setup
- Mock API responses
- React Testing Library setup"

bd create "Write Frontend Component Tests" -t task -p 3 -d "Test key components:
- Upload component: drag-drop, validation
- Chat interface: message display, input
- Auth forms: validation, submission
- Protected route: redirect logic"

# ========================
# DOCUMENTATION
# ========================

bd create "Create README.md" -t task -p 2 -d "Write comprehensive README:
- Project overview and features
- Quick start: docker-compose up
- Environment variables reference
- API documentation link (/docs)
- Development setup instructions
- Architecture overview diagram"

bd create "Create .env.example" -t task -p 1 -d "Create example environment file:
- All required variables with placeholder values
- All optional variables with defaults
- Comments explaining each variable
- Group by category (required, LLM, Qdrant, config)"

bd create "Create Deployment Documentation" -t task -p 3 -d "Write deployment guide (docs/DEPLOYMENT.md):
- Pre-flight checklist
- Docker Compose instructions
- Environment configuration guide
- Supabase project setup
- First admin user creation
- Troubleshooting common issues"

bd create "Create Startup Scripts" -t task -p 2 -d "Create scripts/start.sh:
- Wait for database availability
- Run alembic upgrade head
- Start uvicorn server
- Make script executable"

echo ""
echo "All tasks created successfully!"
echo "Run 'bd list' to see all issues"
echo "Run 'bd ready' to see issues ready to work on"
