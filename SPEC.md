# ruhroh - RAG Document Chat Template

## Project Overview

**ruhroh** is a modular RAG (Retrieval-Augmented Generation) document chat system designed as a reusable template for agency client deployments. The system enables users to upload documents, intelligently process and index them, and interact with their content through an agentic chat interface.

### Purpose

This template serves as a foundation for "talk to your documents" client projects. The architecture prioritizes:

1. **Modularity** - Well-separated components that can be enhanced or replaced per-client
2. **API-first design** - Clean REST API for custom frontend integrations
3. **Evaluation capability** - Built-in tools to compare chunking strategies and retrieval quality
4. **Deployment simplicity** - Single Docker Compose command to spin up the entire stack

### Target Deployment Model

Each client gets their own deployment of ruhroh. The deployment serves multiple users within that client organization. This is NOT a multi-tenant SaaS—it's a template that gets deployed per-client.

---

## Functional Requirements

### FR-1: Document Ingestion

#### FR-1.1: File Upload
- **Drag-and-drop interface** for document upload
- Support **multiple simultaneous file uploads** with parallel processing
- Supported formats: **PDF** and **TXT**
- No file size limits (process large documents with appropriate timeout handling)
- **Replace-in-place** updates: re-uploading a document with the same name updates the existing record and re-indexes

#### FR-1.2: Processing Pipeline
The ingestion pipeline processes documents through these stages:

1. **Parsing** - Extract text content from documents
2. **OCR (optional)** - User-toggled Mistral vision model OCR for image-heavy PDFs
3. **Chunking** - Split content using configurable strategy (see FR-1.3)
4. **Metadata Extraction** - Use LangExtract to enrich chunks (see FR-1.4)
5. **Embedding** - Generate vector embeddings via OpenAI
6. **Indexing** - Store in Qdrant (vectors) and PostgreSQL (metadata, full-text)

#### FR-1.3: Chunking Strategies
Support multiple chunking strategies with the ability to compare performance:

| Strategy | Description |
|----------|-------------|
| **Fixed-size** | Token/character windows with configurable overlap |
| **Semantic** | Use embedding similarity to find natural break points |

Each chunk must retain:
- Source document reference
- Page number(s)
- Character/token offsets (for excerpt extraction)
- Strategy used for chunking

#### FR-1.4: Metadata Extraction (LangExtract Integration)
Use LangExtract to extract structured metadata from each chunk:

**Default extraction (always run):**
- Named entities (people, organizations, locations)
- Dates and temporal references
- Key terms and concepts

**Configurable extraction:**
- Super-users can define custom extraction schemas per deployment
- Schemas specify additional fields to extract (e.g., medical codes, legal citations)
- Extracted metadata stored alongside chunks for targeted retrieval

#### FR-1.5: Processing Feedback
Display detailed progress during document processing:
```
Uploading... → Parsing... → [OCR...] → Chunking... → Extracting Metadata... → Embedding... → Indexing... → Done
```

### FR-2: Retrieval System

#### FR-2.1: Hybrid Search
Combine two retrieval methods:

1. **Vector similarity** (Qdrant)
   - Semantic search using OpenAI embeddings
   - Configurable top-k retrieval

2. **Keyword search** (PostgreSQL Full-Text Search)
   - BM25-style ranking
   - Supports exact phrase matching

Fusion strategy: Reciprocal Rank Fusion (RRF) or configurable weighting.

#### FR-2.2: Agentic Retrieval
The retrieval agent has multi-step reasoning capabilities:

- **Query decomposition** - Break complex questions into sub-queries
- **Iterative search** - Refine queries based on initial results
- **Cross-chunk synthesis** - Combine information from multiple sources
- **Metadata filtering** - Use extracted entities/dates to narrow search

The agent decides whether to use keyword search, semantic search, or both based on query characteristics.

### FR-3: Chat Interface

#### FR-3.1: Conversation Management
- **Multiple conversation threads** per user
- Threads are named and persist across sessions
- Users can view conversation history
- Clear/delete thread functionality

#### FR-3.2: Response Generation
- **LLM providers:** OpenAI (GPT-4) and Anthropic (Claude)
- Configurable model selection per deployment
- **"Think-then-stream" UX:**
  1. Show "Searching documents..." indicator
  2. Show "Thinking..." while agent reasons
  3. Stream the final response

#### FR-3.3: Citation Display
- Responses include inline citations `[1]`, `[2]`, etc.
- Clicking a citation shows the **exact source text excerpt** in a panel/modal
- Includes document name and page number for reference
- Text excerpts are extracted from the source chunk (the specific relevant portion)

#### FR-3.4: Graceful Fallback
When no relevant information is found in documents:
- Clearly state: "I couldn't find this in your documents, but based on my general knowledge..."
- Response is visually distinguished (different styling/icon)
- User understands the answer is NOT from their documents

### FR-4: User Management

#### FR-4.1: Authentication
- **Supabase Auth** integration (recommended, swappable)
- Email/password authentication
- Session management with JWT

#### FR-4.2: User Roles
| Role | Capabilities |
|------|--------------|
| **User** | Upload documents, chat, manage own threads |
| **Super-user** | User + configure extraction schemas |
| **Admin** | Super-user + user management, view all documents, usage stats |

### FR-5: Admin Panel

#### FR-5.1: User Management
- View all users
- Disable/enable accounts
- Assign roles

#### FR-5.2: Document Overview
- View all uploaded documents
- See processing status
- Delete documents

#### FR-5.3: Usage Statistics
- Total documents uploaded
- Total queries processed
- Documents per user
- Active users

### FR-6: API

#### FR-6.1: REST API
Full REST API for all functionality:

| Endpoint Group | Operations |
|----------------|------------|
| `/auth` | Register, login, logout, refresh |
| `/documents` | Upload, list, get, delete, re-process |
| `/chat` | Create thread, send message, get history, delete thread |
| `/search` | Direct search (bypass chat), filter options |
| `/admin` | User management, stats (admin only) |
| `/config` | Get/set extraction schemas (super-user+) |

#### FR-6.2: OpenAPI Documentation
- Auto-generated OpenAPI/Swagger documentation
- Interactive API explorer at `/docs`
- Downloadable OpenAPI spec for client SDK generation

### FR-7: Evaluation System

#### FR-7.1: Automated Evaluation
LLM-powered evaluation framework:

1. **Question Generation** - LLM generates diverse questions from document chunks
2. **Retrieval Testing** - Run questions through retrieval system
3. **Quality Scoring** - LLM evaluates if retrieved chunks could answer the question
4. **Metrics** - Precision, recall, relevance scores

#### FR-7.2: Strategy Comparison
Compare chunking strategies:

1. Process same document with different strategies
2. Run identical question set against each
3. Compare retrieval quality metrics
4. Generate comparison report

#### FR-7.3: A/B Testing Capability
Infrastructure to run strategies in parallel on live queries (for future use).

---

## Non-Functional Requirements

### NFR-1: Performance
- Document upload: Handle files up to 500MB
- Processing: Complete typical document (<50 pages) within 60 seconds
- Chat response: First token within 3 seconds
- Search: Return results within 500ms

### NFR-2: Scalability
- Support up to 10,000 documents per deployment
- Support up to 100 concurrent users per deployment
- Horizontal scaling via container replication (future)

### NFR-3: Security
- HTTPS for all communications
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- XSS prevention in frontend
- Secure file upload handling (type validation, size limits per request)
- JWT token expiration and refresh

### NFR-4: Reliability
- Graceful error handling with user-friendly messages
- Processing failures: retry logic with exponential backoff
- Database connection pooling
- Health check endpoints for monitoring

### NFR-5: Observability
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request ID tracking across services
- Key events logged: uploads, searches, chat messages, errors

### NFR-6: Maintainability
- Modular code architecture
- Type hints throughout Python codebase
- TypeScript strict mode in frontend
- Consistent code style (Black, ESLint/Prettier)

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Applications                          │
│   ┌─────────────────┐    ┌─────────────────┐    ┌────────────────┐  │
│   │  React Frontend │    │  Custom Client  │    │   API Client   │  │
│   │   (Internal)    │    │    Frontend     │    │  (SDK/Direct)  │  │
│   └────────┬────────┘    └────────┬────────┘    └───────┬────────┘  │
└────────────┼──────────────────────┼─────────────────────┼───────────┘
             │                      │                     │
             └──────────────────────┼─────────────────────┘
                                    │
                              REST API (HTTPS)
                                    │
┌───────────────────────────────────┼─────────────────────────────────┐
│                        FastAPI Backend                               │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                      API Layer (Routes)                      │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                    │                                 │
│   ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐   │
│   │   Auth     │ │  Ingestion │ │ Retrieval  │ │     Chat       │   │
│   │  Module    │ │   Module   │ │   Module   │ │    Module      │   │
│   └────────────┘ └────────────┘ └────────────┘ └────────────────┘   │
│                                    │                                 │
│   ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐   │
│   │   Admin    │ │   Eval     │ │  LLM       │ │   Extraction   │   │
│   │  Module    │ │   Module   │ │  Module    │ │    Module      │   │
│   └────────────┘ └────────────┘ └────────────┘ └────────────────┘   │
└───────────────────────────────────┼─────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  PostgreSQL   │         │     Qdrant      │         │  File Storage   │
│               │         │                 │         │                 │
│ • Users       │         │ • Vectors       │         │ • Original docs │
│ • Documents   │         │ • Payloads      │         │ • Processed     │
│ • Chunks      │         │                 │         │                 │
│ • Threads     │         │                 │         │                 │
│ • Messages    │         │                 │         │                 │
│ • FTS Index   │         │                 │         │                 │
└───────────────┘         └─────────────────┘         └─────────────────┘
```

### Backend Modules

| Module | Responsibility |
|--------|----------------|
| **Auth** | User registration, login, JWT management, role checking |
| **Ingestion** | File upload, parsing, chunking, pipeline orchestration |
| **Extraction** | LangExtract integration, schema management, metadata extraction |
| **Retrieval** | Hybrid search, query routing, result fusion |
| **Chat** | Thread management, agent orchestration, response streaming |
| **LLM** | Provider abstraction (OpenAI, Anthropic), embedding generation |
| **Admin** | User management, stats, system configuration |
| **Eval** | Question generation, retrieval testing, metrics calculation |

### Data Models

#### User
```
User {
    id: UUID
    email: string
    password_hash: string
    role: enum (user, superuser, admin)
    created_at: timestamp
    last_login: timestamp
    is_active: boolean
}
```

#### Document
```
Document {
    id: UUID
    user_id: UUID (FK)
    filename: string
    file_type: enum (pdf, txt)
    file_path: string
    file_size: int
    page_count: int (nullable for txt)
    status: enum (pending, processing, ready, failed)
    chunking_strategy: string
    ocr_enabled: boolean
    created_at: timestamp
    updated_at: timestamp
    error_message: string (nullable)
}
```

#### Chunk
```
Chunk {
    id: UUID
    document_id: UUID (FK)
    content: text
    chunk_index: int
    page_numbers: int[] (nullable)
    start_offset: int
    end_offset: int
    token_count: int
    extracted_metadata: JSONB
    created_at: timestamp
}
```

#### Thread
```
Thread {
    id: UUID
    user_id: UUID (FK)
    name: string
    created_at: timestamp
    updated_at: timestamp
}
```

#### Message
```
Message {
    id: UUID
    thread_id: UUID (FK)
    role: enum (user, assistant)
    content: text
    citations: JSONB (nullable)
    model_used: string (nullable)
    is_from_documents: boolean
    created_at: timestamp
}
```

#### ExtractionSchema
```
ExtractionSchema {
    id: UUID
    name: string
    description: string
    schema_definition: JSONB
    is_default: boolean
    created_by: UUID (FK)
    created_at: timestamp
}
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18+, TypeScript, Vite |
| **Backend** | Python 3.11+, FastAPI, Pydantic |
| **Database** | PostgreSQL 15+ |
| **Vector Store** | Qdrant |
| **Auth** | Supabase Auth |
| **LLM** | OpenAI API, Anthropic API |
| **OCR** | Mistral vision models |
| **Extraction** | LangExtract |
| **Embeddings** | OpenAI text-embedding-3-small |
| **Deployment** | Docker, Docker Compose |

### External Dependencies

| Dependency | Purpose | Required |
|------------|---------|----------|
| OpenAI API | Embeddings, chat completion | Yes |
| Anthropic API | Chat completion (alternative) | Optional |
| Mistral API | OCR for image-heavy PDFs | Optional |
| Supabase | Authentication | Yes (or alternative) |

---

## User Experience Specifications

### Document Upload Flow
```
1. User drags files onto drop zone (or clicks to browse)
2. Files appear in upload queue with status "Pending"
3. For each file:
   a. Status: "Uploading..." (progress bar)
   b. Status: "Parsing..."
   c. [If OCR enabled] Status: "Running OCR..."
   d. Status: "Chunking..."
   e. Status: "Extracting metadata..."
   f. Status: "Generating embeddings..."
   g. Status: "Indexing..."
   h. Status: "Ready" (success) or "Failed" (with error)
4. User can start chatting once any document is "Ready"
```

### Chat Flow
```
1. User types question in chat input
2. Press Enter or click Send
3. User message appears in thread
4. Assistant response area shows:
   a. "Searching your documents..." (1-2 seconds)
   b. "Analyzing results..." (agent thinking)
   c. Response streams in with inline citations [1], [2]
5. Citations panel shows source documents
6. User can click citation to view source text excerpt
```

### Citation Detail View
```
1. User clicks citation [1] in response
2. Panel/modal opens showing:
   - Document name and page number
   - The exact source text excerpt
   - Link to download original document (optional)
3. User can close panel and continue conversation
```

### Admin Dashboard
```
1. Overview cards: Total users, Total documents, Queries today
2. Users table: Email, Role, Documents count, Last active, Actions
3. Documents table: Filename, Owner, Status, Size, Uploaded, Actions
4. System health: API status, DB status, Qdrant status
```

---

## Scope Boundaries

### In Scope (MVP)
- [x] PDF and TXT document upload
- [x] Multiple file upload with parallel processing
- [x] User-toggled OCR via Mistral
- [x] Fixed-size and semantic chunking strategies
- [x] LangExtract metadata extraction
- [x] Configurable extraction schemas
- [x] Hybrid search (vector + keyword)
- [x] Agentic multi-step retrieval
- [x] OpenAI + Anthropic LLM support
- [x] Multiple conversation threads
- [x] Text excerpt citations with source reference
- [x] Supabase authentication
- [x] User roles (user, superuser, admin)
- [x] Basic admin panel
- [x] REST API with OpenAPI docs
- [x] Evaluation framework
- [x] Docker Compose deployment

### Out of Scope (MVP)
- [ ] Office document formats (.docx, .xlsx, .pptx)
- [ ] URL/web page ingestion
- [ ] Collaborative editing
- [ ] Email/calendar integrations
- [ ] Webhooks
- [ ] Rate limiting / usage quotas
- [ ] Document versioning (full history)
- [ ] Document comparison
- [ ] Advanced analytics dashboards
- [ ] Kubernetes deployment
- [ ] Python SDK package

### Future Considerations
- GraphQL API option
- Document folders/collections
- Shared conversation threads
- Real-time collaboration
- Custom LLM fine-tuning
- On-premise deployment guide
- SSO/LDAP integration

---

## Assumptions

1. **Network connectivity** - Deployments have reliable internet for API calls
2. **API key availability** - Clients provide their own OpenAI/Anthropic API keys
3. **Document quality** - PDFs have extractable text (or OCR is enabled)
4. **User base** - Typical deployment serves <100 concurrent users
5. **Document size** - Most documents are <100 pages
6. **Browser support** - Modern browsers (Chrome, Firefox, Safari, Edge - last 2 versions)

---

## Open Questions

1. **Extraction schema format** - What's the exact JSON structure for defining custom extraction schemas?
2. **Embedding dimension** - text-embedding-3-small (1536) vs text-embedding-3-large (3072)?
3. **Chunk size defaults** - What token counts for fixed-size chunks? (512? 1024?)
4. **Supabase vs alternative** - Should we abstract auth to easily swap providers?

## Resolved Questions

1. **Citation display** - Using text excerpts instead of PDF highlighting (simpler, still verifiable)

---

## Success Criteria

1. **Deployment** - New deployment spins up with single `docker-compose up` command
2. **Upload** - Document processes and becomes searchable within 60 seconds
3. **Chat quality** - Responses cite relevant sources for domain-specific questions
4. **API usability** - External developers can integrate using OpenAPI spec
5. **Modularity** - Individual modules can be modified without affecting others
6. **Evaluation** - Can generate quality metrics for retrieval performance

---

*This SPEC.md is the source of truth for the ruhroh project. All implementation decisions should reference this document.*
