# RAG Auto-Evaluation Framework - Technical Specification

## Overview

This technical specification defines the implementation details for the RAG Auto-Evaluation Framework. It covers database models, API endpoints, service architecture, and integration points.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EVAL FRAMEWORK                                     │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Question   │    │  Retrieval  │    │   Answer    │    │   Metrics   │  │
│  │ Generation  │───▶│   Testing   │───▶│  Evaluation │───▶│  & Storage  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Chunks    │    │  Config     │    │ LLM Judge   │    │  Dashboard  │  │
│  │ (Multi-Idx) │    │  Profiles   │    │ (Phase 2)   │    │  & History  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Database Models

### ChunkConfig
```sql
CREATE TABLE chunk_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    strategy VARCHAR(20) NOT NULL CHECK (strategy IN ('fixed_size', 'semantic')),
    chunk_size INT,  -- for fixed_size
    chunk_overlap INT,  -- for fixed_size
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### DocumentChunkSet
```sql
CREATE TABLE document_chunk_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_config_id UUID NOT NULL REFERENCES chunk_configs(id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    chunk_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id, chunk_config_id)
);
-- Constraint: max 10 chunk sets per document (enforced in application layer)
```

### EvalConfigProfile
```sql
CREATE TABLE eval_config_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    version INT DEFAULT 1,

    -- Retrieval params
    top_k INT DEFAULT 5,
    vector_weight FLOAT DEFAULT 0.6,
    keyword_weight FLOAT DEFAULT 0.4,
    rrf_k INT DEFAULT 60,
    similarity_threshold FLOAT DEFAULT 0.0,

    -- Prompt params
    system_prompt TEXT,
    query_rewrite_prompt TEXT,
    query_rewrite_enabled BOOLEAN DEFAULT TRUE,

    -- Judge config (Phase 2)
    judge_model VARCHAR(50),

    -- Metadata
    is_production BOOLEAN DEFAULT FALSE,
    is_baseline BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### EvalQuestion
```sql
CREATE TABLE eval_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    question_type VARCHAR(20) CHECK (question_type IN ('factual', 'reasoning', 'multi_hop')),
    source_chunk_ids UUID[] NOT NULL,
    source_chunk_config_ids UUID[],
    expected_keywords TEXT[],
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    dedup_threshold_used FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    regenerated_at TIMESTAMP
);

CREATE INDEX idx_eval_questions_document ON eval_questions(document_id);
CREATE INDEX idx_eval_questions_type ON eval_questions(question_type);
```

### EvalRun
```sql
CREATE TABLE eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'cancelling')),
    mode VARCHAR(10) CHECK (mode IN ('quick', 'full')),
    config_profile_ids UUID[],
    chunk_config_ids UUID[],
    question_count INT,
    sample_size INT,  -- null if full mode
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    triggered_by UUID REFERENCES users(id),
    trigger_method VARCHAR(20) CHECK (trigger_method IN ('api', 'cli', 'admin_ui')),
    error_message TEXT,
    profile_snapshots JSONB,  -- snapshot of profile params at run start
    checkpoint_id UUID
);

CREATE INDEX idx_eval_runs_status ON eval_runs(status);
CREATE INDEX idx_eval_runs_triggered_by ON eval_runs(triggered_by);
```

### EvalResult
```sql
CREATE TABLE eval_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES eval_questions(id),
    config_profile_id UUID NOT NULL REFERENCES eval_config_profiles(id),
    chunk_config_id UUID NOT NULL REFERENCES chunk_configs(id),
    config_profile_version INT,

    -- Retrieval results
    retrieved_chunk_ids UUID[],
    source_chunk_retrieved BOOLEAN,
    source_chunk_rank INT,
    retrieval_scores FLOAT[],

    -- Answer results (Phase 2)
    generated_answer TEXT,
    citations_in_answer JSONB,

    -- LLM judge scores (Phase 2)
    semantic_coverage_score FLOAT,
    answer_accuracy_score FLOAT,
    factual_coverage_score FLOAT,
    hallucination_score FLOAT,
    citation_accuracy_score FLOAT,
    judge_explanations JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_eval_results_run ON eval_results(run_id);
CREATE INDEX idx_eval_results_question ON eval_results(question_id);
```

### EvalBaseline
```sql
CREATE TABLE eval_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    marked_by UUID REFERENCES users(id),
    marked_at TIMESTAMP DEFAULT NOW()
);
```

### EvalCheckpoint
```sql
CREATE TABLE eval_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    completed_question_ids UUID[],
    current_config_index INT,
    phase VARCHAR(30),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

All endpoints require Admin or Super-user role. Base path: `/api/v1/eval`

### Eval Runs

```
POST /eval/runs
Body: {
    "mode": "quick" | "full",
    "config_profile_ids": ["uuid", ...],
    "chunk_config_ids": ["uuid", ...],
    "sample_size": 100  // only for quick mode
}
Response: { "job_id": "uuid", "status": "pending" }

GET /eval/runs?limit=50&offset=0&status=completed
Response: { "runs": [...], "total": 100 }

GET /eval/runs/{id}
Response: {
    "job_id": "uuid",
    "status": "running",
    "progress": { "total_questions": 500, "completed": 127, "current_phase": "retrieval_testing" },
    "started_at": "timestamp",
    "completed_at": null
}

GET /eval/runs/{id}/results?limit=50&offset=0&question_type=factual&config_profile_id=uuid
Response: { "results": [...], "total": 847 }

DELETE /eval/runs/{id}
Response: { "status": "cancelling" }  // soft delete
```

### Questions

```
GET /eval/questions?limit=50&offset=0&question_type=factual&document_id=uuid
Response: { "questions": [...], "total": 1000 }

POST /eval/questions/regenerate
Body: { "document_id": "uuid" }  // optional, regenerates all if omitted
Response: { "job_id": "uuid" }

GET /eval/questions/stats
Response: {
    "total": 1000,
    "by_type": { "factual": 500, "reasoning": 350, "multi_hop": 150 },
    "by_document": [...]
}
```

### Config Profiles

```
GET /eval/profiles
Response: { "profiles": [...] }

POST /eval/profiles
Body: {
    "name": "experimental_v2",
    "top_k": 8,
    "vector_weight": 0.7,
    "keyword_weight": 0.3,
    "query_rewrite_enabled": true,
    "system_prompt": "...",
    "query_rewrite_prompt": "..."
}
Response: { "id": "uuid", ... }

GET /eval/profiles/{id}
PUT /eval/profiles/{id}
DELETE /eval/profiles/{id}

POST /eval/profiles/{id}/clone
Body: { "name": "experimental_v3" }
Response: { "id": "uuid", ... }
```

### Chunk Configurations

```
GET /eval/chunk-configs
Response: { "configs": [...] }

POST /eval/chunk-configs
Body: {
    "name": "fixed_1024",
    "strategy": "fixed_size",
    "chunk_size": 1024,
    "chunk_overlap": 100
}
Response: { "id": "uuid", ... }

POST /eval/chunk-configs/{id}/apply
Body: { "document_ids": ["uuid", ...] }
Response: { "job_id": "uuid", "affected_documents": 5 }

DELETE /eval/chunk-configs/{id}
```

### Baselines & Comparison

```
GET /eval/baselines
POST /eval/baselines
Body: { "run_id": "uuid", "name": "v1.0 baseline", "description": "..." }
DELETE /eval/baselines/{id}

GET /eval/compare?run_id_1=uuid&run_id_2=uuid
Response: {
    "metrics_comparison": {
        "recall_at_5": { "run_1": 0.74, "run_2": 0.78, "delta": 0.04 },
        ...
    },
    "by_question_type": { ... }
}

GET /eval/metrics/history?metric=recall_at_5&days=30
Response: { "data_points": [{ "timestamp": "...", "value": 0.74 }, ...] }
```

## Service Layer

### EvalService

```python
class EvalService:
    """Main service for evaluation operations."""

    async def trigger_run(
        self,
        mode: str,
        config_profile_ids: list[UUID],
        chunk_config_ids: list[UUID],
        triggered_by: UUID,
        trigger_method: str,
        sample_size: int | None = None,
    ) -> UUID:
        """Start a new evaluation run. Returns job_id."""

    async def get_run_status(self, run_id: UUID) -> dict:
        """Get current status and progress of a run."""

    async def cancel_run(self, run_id: UUID) -> bool:
        """Cancel a running evaluation. Returns success."""

    async def get_run_results(
        self,
        run_id: UUID,
        limit: int = 50,
        offset: int = 0,
        filters: dict | None = None,
    ) -> dict:
        """Get paginated, filtered results for a run."""
```

### QuestionGenerationService

```python
class QuestionGenerationService:
    """Service for generating evaluation questions from chunks."""

    async def generate_for_document(self, document_id: UUID) -> list[EvalQuestion]:
        """Generate questions for all chunk sets of a document."""

    async def classify_chunk_density(self, chunk_content: str) -> str:
        """Classify chunk as DENSE, MODERATE, or SPARSE."""

    async def deduplicate_questions(
        self,
        questions: list[EvalQuestion],
        threshold: float = 0.9,
    ) -> list[EvalQuestion]:
        """Remove semantically similar questions."""
```

### EvalWorker

```python
class EvalWorker:
    """Background worker for evaluation execution."""

    async def run_evaluation(self, run_id: UUID):
        """Execute a full evaluation run with checkpointing."""

    async def checkpoint(self, run_id: UUID, state: dict):
        """Save checkpoint for resume capability."""

    async def resume_from_checkpoint(self, run_id: UUID, checkpoint_id: UUID):
        """Resume evaluation from a checkpoint."""
```

## Qdrant Integration

### Vector Tagging

All vectors include payload fields for filtering:
- `user_id`: UUID string
- `document_id`: UUID string
- `chunk_config_id`: UUID string

### Filtered Search

```python
async def search_with_config(
    self,
    query_embedding: list[float],
    user_id: UUID,
    chunk_config_id: UUID,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Search against a specific chunk configuration."""

    filter_conditions = models.Filter(
        must=[
            models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id))),
            models.FieldCondition(key="chunk_config_id", match=models.MatchValue(value=str(chunk_config_id))),
        ]
    )
    # ... execute search with filter
```

## Rate Limiting

### Global LLM Rate Limiter

```python
class LLMRateLimiter:
    """Global rate limiter for LLM API calls."""

    def __init__(self, max_rpm: int = 60, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = TokenBucket(max_rpm)
        self.queue = asyncio.PriorityQueue()

    async def acquire(self, priority: int = 1):
        """Acquire permission to make an LLM call. Priority 0 = highest."""
        await self.queue.put((priority, asyncio.get_event_loop().time()))
        async with self.semaphore:
            await self.rate_limiter.acquire()
            yield
```

### Priority Levels

- Priority 0: User chat requests
- Priority 1: Eval jobs

## LLM Prompts

### Chunk Density Classification

```
Analyze this text chunk and classify its information density.

CHUNK:
{chunk_content}

CRITERIA:
- DENSE: Contains multiple facts, definitions, statistics, procedures, or technical details
- MODERATE: Contains some factual content but with filler/transitions
- SPARSE: Mostly boilerplate, headers, transitions, or repetitive content

Respond with exactly one word: DENSE, MODERATE, or SPARSE
```

### Question Generation

```
Generate {count} evaluation questions from this document chunk.

CHUNK:
{chunk_content}

REQUIREMENTS:
1. Questions must be answerable using ONLY this chunk
2. Include question type tag: [FACTUAL], [REASONING], or [MULTI_HOP]
3. For each question, list 3-5 expected keywords from the chunk

Format each question as:
Q: [question text]
TYPE: [FACTUAL|REASONING|MULTI_HOP]
KEYWORDS: [keyword1, keyword2, ...]

Generate {count} questions:
```

### Expected Keywords Extraction

```
Given this question and its source chunk, extract 3-5 key terms that
should appear in any retrieved content that could answer this question.

QUESTION: {question}
SOURCE CHUNK: {chunk_content}

Return a JSON array of lowercase keywords, e.g.: ["neural network", "training", "epoch"]
```

## CLI Interface

```bash
# Run evaluations
python -m app.eval run --mode=full --profiles=production,experimental
python -m app.eval run --mode=quick --sample=100

# Check status
python -m app.eval status <job_id>

# List runs
python -m app.eval list --limit=10

# Compare runs
python -m app.eval compare <run_id_1> <run_id_2>

# Regenerate questions
python -m app.eval regenerate-questions --document=<doc_id>
python -m app.eval regenerate-questions --all

# Profile management
python -m app.eval profiles list
python -m app.eval profiles show <profile_id>

# Chunk config management
python -m app.eval chunk-configs list
python -m app.eval chunk-configs apply <config_id> --document=<doc_id>
```

## Non-Functional Requirements

### Performance
- Question generation: 100 chunks in 5 minutes
- Retrieval testing: 10 questions/second (without judge)
- Full eval with GPT-4 judge: ~1 question/second
- Full eval (1000 questions): 15-60 minutes

### Storage
- Max 10 chunk configs per document
- Tiered retention:
  - 0-30 days: Full detailed results
  - 30-90 days: Aggregates + 100 sample results
  - 90+ days: Aggregates only

### Reliability
- Checkpoints every 50 questions or 5 minutes
- Max 3 retries per LLM call with exponential backoff
- Graceful degradation on individual question failures

## Implementation Phases

### MVP (Phase 1)
- Database models and migrations
- EvalConfigProfile CRUD
- ChunkConfig CRUD + apply to documents
- Question generation service
- Retrieval testing with recall@k
- EvalRun execution with checkpointing
- Basic Admin UI (runs, profiles, chunk configs)
- CLI interface

### Phase 2
- LLM-as-judge evaluation (answer accuracy, hallucination, citations)
- Regression alerts
- Profile comparison in single run

### Phase 3
- Dashboard visualizations
- Metric trend charts
- A/B tournament UI

---

*This EVAL_TECH_SPEC.md defines the technical implementation details for the ruhroh Auto-Evaluation Framework.*
