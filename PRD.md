# ruhroh - Product Requirements Document

> **Status:** Approved (3-model consensus: Claude, Codex, Gemini)
> **Version:** 1.0
> **Last Updated:** 2026-01-20

---

## Executive Summary

ruhroh is a modular RAG (Retrieval-Augmented Generation) document chat template designed for agency deployments. It enables organizations to upload documents (PDF, TXT), intelligently process and index them, and interact with document content through an agentic chat interface with verifiable source citations.

The product serves as a reusable foundation for "talk to your documents" client projects. Each client receives their own deployment serving multiple users within their organization. The architecture prioritizes:

1. **Modularity** - Well-separated components that can be enhanced or replaced per-client
2. **API-first design** - Clean REST API for custom frontend integrations
3. **Evaluation capability** - Built-in tools to compare chunking strategies and retrieval quality
4. **Deployment simplicity** - Single Docker Compose command to spin up the entire stack

**Key differentiators:** Hybrid search (vector + keyword), agentic multi-step retrieval with defined decision logic, verifiable text excerpt citations, and a built-in evaluation framework for comparing retrieval strategies.

---

## Problem Statement

Organizations accumulate vast document repositories but struggle to extract insights efficiently. Traditional search returns documents, not answers. Users must read through multiple files to synthesize information, leading to:

- **Time waste**: Hours spent searching and reading documents for specific information
- **Missed insights**: Connections across documents go unnoticed
- **Knowledge silos**: Institutional knowledge locked in unstructured documents
- **Inconsistent answers**: Different employees find different information for the same query

Current solutions either require expensive custom development or offer generic chat interfaces that lack source grounding, making users unable to verify or trust responses.

---

## Target Users

### Primary Persona: Knowledge Worker
**Profile**: Employees who regularly need to reference organizational documents (policies, reports, technical docs, contracts)

**Goals**:
- Find specific information quickly without reading entire documents
- Get answers with verifiable sources
- Trust that responses come from their actual documents

**Pain Points**:
- Ctrl+F doesn't work for conceptual questions
- Can't remember which document contains needed information
- Answers from generic AI can't be verified or trusted

### Secondary Persona: Administrator
**Profile**: IT or operations staff managing the deployment for their organization

**Goals**:
- Manage users and access
- Monitor system usage
- Ensure documents are properly indexed

**Pain Points**:
- Complex deployment and maintenance
- No visibility into usage patterns
- Difficult to troubleshoot issues

### Tertiary Persona: Super-User / Domain Expert
**Profile**: Power users who configure the system for their domain (legal, medical, technical)

**Goals**:
- Customize extraction to capture domain-specific entities
- Optimize retrieval for their document types using their own test documents
- Evaluate and improve system performance

**Pain Points**:
- Generic extraction misses domain terminology
- Can't tune the system for better results

---

## User Stories

### Document Management
| ID | Story | Priority |
|----|-------|----------|
| US-1 | As a user, I want to drag and drop documents so I can upload them without navigating file dialogs | Must |
| US-2 | As a user, I want to upload multiple files at once so I can batch process documents | Must |
| US-3 | As a user, I want to see detailed processing progress so I know when documents are ready | Must |
| US-4 | As a user, I want to enable OCR for scanned PDFs so image-based documents are searchable | Must |
| US-5 | As a user, I want to re-upload a document with confirmation so I can keep content current without accidental overwrites | Must |

### Chat & Search
| ID | Story | Priority |
|----|-------|----------|
| US-6 | As a user, I want to ask questions about my documents and get sourced answers | Must |
| US-7 | As a user, I want to see where answers come from so I can verify accuracy | Must |
| US-8 | As a user, I want to click citations to see the exact source text excerpt | Must |
| US-9 | As a user, I want the system to clearly indicate when it cannot find relevant information | Must |
| US-10 | As a user, I want to have multiple conversation threads so I can organize different topics | Must |

### Administration
| ID | Story | Priority |
|----|-------|----------|
| US-11 | As an admin, I want to view all users so I can manage access | Must |
| US-12 | As an admin, I want to see usage statistics so I can understand adoption | Should |
| US-13 | As an admin, I want to disable accounts so I can control access | Must |

### Configuration
| ID | Story | Priority |
|----|-------|----------|
| US-14 | As a super-user, I want to define custom extraction schemas so the system captures domain-specific entities | Should |
| US-15 | As a super-user, I want to compare chunking strategies on my own documents so I can optimize retrieval | Should |

---

## Functional Requirements

### FR-1: Document Ingestion

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Drag-and-drop file upload interface | Must |
| FR-1.2 | Support multiple simultaneous uploads with parallel processing | Must |
| FR-1.3 | Support PDF and TXT file formats | Must |
| FR-1.4 | User-toggled OCR for image-heavy PDFs (via Mistral vision models) | Must |
| FR-1.5 | Replace-in-place with explicit confirmation (API returns 409 Conflict for existing files) | Must |
| FR-1.6 | Display detailed processing status per document (upload → parse → OCR → chunk → extract → embed → index) | Must |
| FR-1.7 | Support fixed-size and semantic chunking strategies | Must |
| FR-1.8 | Extract metadata via LangExtract (entities, dates, key terms) | Must |
| FR-1.9 | Configurable extraction schemas for super-users | Should |

### FR-2: Retrieval & Chat

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Hybrid search combining vector similarity (Qdrant) and keyword search (PostgreSQL FTS) | Must |
| FR-2.2 | Agentic retrieval with defined decision tree (see Agentic Retrieval section) | Must |
| FR-2.3 | Multiple conversation threads per user | Must |
| FR-2.4 | "Think-then-stream" response UX (search indicator → thinking indicator → streamed response) | Must |
| FR-2.5 | Inline citations [1], [2] with clickable source links | Must |
| FR-2.6 | Citation detail view showing source text excerpt, document name, and page number | Must |
| FR-2.7 | Configurable fallback behavior (see Fallback Behavior section) | Must |
| FR-2.8 | Support OpenAI and Anthropic LLM providers | Must |

### FR-3: User Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | User registration and authentication (Supabase Auth) | Must |
| FR-3.2 | Three user roles with explicit permissions (see Permissions Matrix) | Must |
| FR-3.3 | JWT-based session management | Must |

### FR-4: Admin Panel

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | View and manage all users | Must |
| FR-4.2 | View all documents with status | Must |
| FR-4.3 | Usage statistics (documents, queries, active users) | Should |
| FR-4.4 | System health indicators (API, DB, Qdrant status) | Should |

### FR-5: API

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | REST API for all functionality | Must |
| FR-5.2 | OpenAPI/Swagger documentation at /docs | Must |
| FR-5.3 | Direct search endpoint (bypass chat) | Should |
| FR-5.4 | Rate limiting with configurable limits | Must |

### FR-6: Evaluation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | LLM-powered question generation from document chunks | Should |
| FR-6.2 | Automated retrieval quality scoring (Hit Rate, MRR, Context Precision) | Should |
| FR-6.3 | Chunking strategy comparison reports | Should |
| FR-6.4 | Optional holdout split for evaluation validity | Should |

---

## Permissions Matrix

| Capability | Admin | Super-User | User |
|------------|:-----:|:----------:|:----:|
| Manage users | ✅ | ❌ | ❌ |
| View all documents | ✅ | ❌ | ❌ |
| View usage stats | ✅ | ✅ | ❌ |
| Configure extraction schemas | ✅ | ✅ | ❌ |
| Compare chunking strategies (own docs) | ✅ | ✅ | ❌ |
| Upload documents | ✅ | ✅ | ✅ |
| Delete own documents | ✅ | ✅ | ✅ |
| Chat with own documents | ✅ | ✅ | ✅ |
| Chat with all documents | ✅ | ❌ | ❌ |

**Note:** Users can ONLY see and chat with their own documents. Super-users compare chunking strategies using their own uploaded test documents.

---

## Agentic Retrieval (Decision Tree)

The retrieval agent follows this defined logic:

```
1. ANALYZE query type
   ├── Factual lookup (who, what, when, where)
   ├── Synthesis (summarize, compare, explain)
   └── Comparison (X vs Y, differences between)

2. EXECUTE search
   ├── Simple factual → Direct hybrid search, return top-k
   └── Complex query → Decompose into 2-3 sub-queries, execute in parallel

3. EVALUATE results
   ├── Relevance score ≥ threshold (default 0.6) → Synthesize answer
   └── Relevance score < threshold → Refine query using LLM, retry once

4. RESPOND
   ├── Relevant chunks found → Generate answer with citations
   └── No relevant chunks → Follow Fallback Behavior policy
```

---

## Hybrid Search Strategy

**Default fusion:** Reciprocal Rank Fusion (RRF)

| Parameter | Default | Environment Variable |
|-----------|---------|---------------------|
| RRF k parameter | 60 | `RUHROH_RRF_K` |
| Vector weight | 0.6 | `RUHROH_VECTOR_WEIGHT` |
| Keyword weight | 0.4 | `RUHROH_KEYWORD_WEIGHT` |

**Validation:** Weights must sum to 1.0

The agent may override weights based on query characteristics (e.g., increase keyword weight for queries with specific terms/names).

---

## Fallback Behavior

**Environment Variable:** `RUHROH_ENABLE_FALLBACK` (default: `false`)

| Setting | Behavior |
|---------|----------|
| `false` (default) | "I could not find relevant information in your documents." |
| `true` | "I couldn't find this in your documents. Based on general knowledge..." (visually distinguished) |

**Rationale:** Default disabled to honor the "only your documents" promise. Deployments can opt-in when general knowledge fallback is appropriate for their use case.

---

## Non-Functional Requirements

### Performance (Qualified)

| Metric | Target | Conditions |
|--------|--------|------------|
| Document processing | <60 seconds | Text-based PDF, <50 pages, <10MB |
| Document processing | <120 seconds | OCR-enabled PDF, <50 pages |
| First response token | <3 seconds | After retrieval completes |
| Search latency | <500ms | Top-20 results against 10K documents |

**Reference sizing:** 4 vCPU, 8GB RAM handles 100 concurrent users at 5 QPS average

### Scale

| Metric | Target |
|--------|--------|
| Documents per deployment | 10,000 |
| Concurrent users | 100 |
| Queries per second (average) | 5 |
| Queries per second (burst) | 15 |

### Security

| Requirement | Details |
|-------------|---------|
| Transport | HTTPS required for all communications |
| Input validation | Size limits, type checks, sanitization |
| Prompt injection | Structured prompt templates, output validation |
| Data isolation | Each deployment is fully isolated |
| Encryption at rest | PostgreSQL and file storage (configurable) |
| Audit logging | Document access and chat queries logged |
| File validation | MIME whitelist (PDF, TXT), signature verification, 500MB max |
| Qdrant security | API key support (`QDRANT_API_KEY`), TLS (`QDRANT_USE_TLS`) |

### Rate Limiting

| Parameter | Default | Environment Variable |
|-----------|---------|---------------------|
| Requests per minute | 60 | `RUHROH_RATE_LIMIT_RPM` |
| Burst allowance | 10 | `RUHROH_RATE_LIMIT_BURST` |

Rate limit headers included in API responses. Graceful degradation with clear error messages.

### Reliability

- Graceful error handling with user-friendly messages
- Processing failures: retry logic with exponential backoff
- Database connection pooling
- Health check endpoints for monitoring

### Observability

- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request ID tracking across requests
- Key events logged: uploads, searches, chat messages, errors

---

## Deployment Requirements

### Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Embeddings and chat completion |
| `SUPABASE_URL` | Yes | Authentication service |
| `SUPABASE_ANON_KEY` | Yes | Authentication service |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `QDRANT_HOST` | Yes | Vector store host |
| `QDRANT_PORT` | Yes | Vector store port |
| `ANTHROPIC_API_KEY` | No | Claude models (optional) |
| `MISTRAL_API_KEY` | No | OCR feature (optional) |
| `QDRANT_API_KEY` | No | Qdrant authentication |
| `QDRANT_USE_TLS` | No | Enable TLS for Qdrant |

### Deployment Command

```bash
docker-compose up -d
```

Pre-flight checklist provided in deployment documentation.

---

## Evaluation Framework

### Purpose
Internal QA tool for testing retrieval quality, not a benchmark for generalization.

### Metrics

| Metric | Description |
|--------|-------------|
| Hit Rate | % of queries where correct chunk appears in top-k |
| Mean Reciprocal Rank (MRR) | Average of 1/rank for correct chunk |
| Context Precision | % of retrieved chunks that are relevant |
| Answer Relevancy | LLM-judged score of answer quality |

### Process

1. LLM generates N questions (default: 50) from document chunks
2. Store questions with ground truth chunk IDs
3. Run questions through retrieval system
4. Calculate metrics, store results
5. Generate comparison report per strategy

### Cost Controls

- Sample documents if corpus >100
- Limit to 50 questions per evaluation run
- Use cheaper model for question generation

### Optional Holdout

For more valid metrics, enable 80/20 document split:
- Generate questions from 80% of documents
- Test retrieval against full corpus
- Provides more realistic performance estimate

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Deployment Time | <5 minutes | Time from `docker-compose up` to functional system |
| Document Processing | <60 seconds | Time for typical (<50 page) document to become searchable |
| Response Relevance | >80% | Percentage of responses with relevant citations (eval framework) |
| API Integration | <1 day | Time for developer to integrate using OpenAPI spec |
| Module Independence | Full | Any module can be modified without affecting others |

---

## Scope

### In Scope (MVP)

- [x] PDF and TXT document upload with parallel processing
- [x] User-toggled OCR via Mistral vision models
- [x] Fixed-size and semantic chunking with comparison capability
- [x] LangExtract metadata extraction with configurable schemas
- [x] Hybrid search (vector + keyword) with agentic retrieval
- [x] Multi-threaded chat with text excerpt citations
- [x] Supabase authentication with three role tiers
- [x] Basic admin panel with usage stats
- [x] REST API with OpenAPI documentation
- [x] Configurable rate limiting
- [x] Evaluation framework for retrieval quality
- [x] Docker Compose deployment

### Out of Scope (MVP)

- [ ] Office document formats (.docx, .xlsx, .pptx)
- [ ] URL/web page ingestion
- [ ] Collaborative editing
- [ ] Email/calendar integrations
- [ ] Webhooks
- [ ] Document versioning (full history)
- [ ] Advanced analytics dashboards
- [ ] Kubernetes deployment
- [ ] Python SDK package

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM API costs exceed budget | Medium | High | Token tracking (future), efficient model selection, rate limiting |
| OCR quality inconsistent | Medium | Medium | Clear user guidance, allow re-processing, quality indicators |
| Retrieval misses relevant content | Medium | High | Evaluation framework, multiple chunking strategies, hybrid search |
| Long document processing times | Low | Medium | Background processing, progress feedback, timeout handling |
| External API dependencies | Medium | High | Graceful degradation, clear error messages, health checks |
| Prompt injection attacks | Medium | High | Structured templates, output validation, input sanitization |

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Custom extraction schema JSON structure | To be defined in Tech Spec |
| Embedding model size | text-embedding-3-small (1536 dimensions) for cost efficiency |
| Citation display | Text excerpts (PDF highlighting deferred to future enhancement) |
| Default chunk size | 512 tokens with 50 token overlap |
| Abstract auth layer | Yes, to allow provider swapping |

---

*This PRD is the approved product requirements document for ruhroh. Technical implementation details are specified in TECH_SPEC.md.*
