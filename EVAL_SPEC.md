# RAG Auto-Evaluation Framework Specification

## Overview

The Auto-Eval Framework is a comprehensive testing system for measuring and improving RAG (Retrieval-Augmented Generation) quality. It automatically generates questions from document chunks, tests retrieval and answer generation, and tracks metrics over time to validate prompt changes, chunking strategies, and retrieval configurations.

### Purpose

1. **Validate Changes** - Quantitatively measure the impact of prompt tweaks, retrieval parameter changes, and chunking strategies
2. **Prevent Regressions** - Track metrics over time to catch quality degradation
3. **Compare Configurations** - A/B test different settings to find optimal configurations
4. **Client-Specific Testing** - Each deployment generates eval sets from its own documents

---

## Architecture

### High-Level Flow

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
│  │ (Multi-Idx) │    │  Profiles   │    │ (Configurable)   │  & History  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Multi-Index Storage Model

Documents can have multiple chunk sets, each with different chunking configurations:

```
Document: "report.pdf"
│
├── ChunkSet A (config: fixed_512, overlap=50)
│   ├── chunks: [chunk_1, chunk_2, chunk_3, ...]
│   └── embeddings in Qdrant (tagged with chunk_config_id)
│
├── ChunkSet B (config: fixed_1024, overlap=100)
│   ├── chunks: [chunk_1, chunk_2, ...]
│   └── embeddings in Qdrant (tagged with chunk_config_id)
│
└── ChunkSet C (config: semantic)
    ├── chunks: [chunk_1, chunk_2, chunk_3, chunk_4, ...]
    └── embeddings in Qdrant (tagged with chunk_config_id)
```

**Behavior:**
- Normal upload creates chunks with default config only
- Admin manually triggers additional chunk sets for eval purposes
- **Maximum 10 chunk configurations per document** (prevents storage explosion)
- Each chunk set has independent embeddings in Qdrant

---

## Functional Requirements

### FR-EVAL-1: Question Generation

#### FR-EVAL-1.1: Content-Adaptive Generation
Generate evaluation questions from document chunks with adaptive density:
- **Dense chunks** (high information content): Generate 3-5 questions
- **Moderate chunks**: Generate 1-3 questions
- **Sparse chunks** (boilerplate, transitions): Generate 0-1 questions

**Density Classification Prompt:**
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

Fallback: If LLM returns invalid response, default to MODERATE.

#### FR-EVAL-1.2: Question Types
Generate diverse question types, each tagged for metric breakdown:

| Type | Description | Example |
|------|-------------|---------|
| **Factual** | Explicit answers in chunk (who, what, when, where) | "What year was the study conducted?" |
| **Reasoning** | Requires inference within the chunk | "Why did the researchers choose this methodology?" |
| **Multi-hop** | Benefits from combining multiple chunks | "How do the findings in section 3 relate to the limitations discussed?" |

**Multi-hop Recall Calculation:**
- Source: Multiple chunk_ids stored in `source_chunk_ids[]`
- Partial credit: If 2 of 3 source chunks retrieved, recall = 0.67
- Full credit: All source chunks in top-k
- **Limitation (MVP):** Multi-hop within single document only; cross-document multi-hop is out of scope

#### FR-EVAL-1.3: Stratified Generation Across Chunk Sets
When multiple chunk sets exist:
1. Generate candidate questions from EACH chunk set
2. Deduplicate semantically similar questions (configurable threshold, default 0.9)
3. Tag each question with originating chunk set(s)
4. Final question set tests ALL questions against ALL chunk sets

**Deduplication Configuration:**
- `dedup_threshold`: 0.0-1.0, default 0.9 (higher = fewer duplicates merged)
- Threshold stored per question generation run for reproducibility
- Different embedding models may require different thresholds

#### FR-EVAL-1.4: Unevaluable Chunk Handling
Skip and log chunks that cannot generate meaningful questions:
- Tables without context
- Image placeholders
- Gibberish/OCR errors
- Headers/footers only

Log includes: chunk_id, reason, chunk preview.

#### FR-EVAL-1.5: Regeneration Triggers
Regenerate eval questions when:
- Documents are added, updated, or deleted
- New chunk configurations are created
- Admin manually triggers regeneration

---

### FR-EVAL-2: Retrieval Testing

#### FR-EVAL-2.1: Ground Truth Tracking
For each generated question, track:
- **Source chunk ID(s)** - The exact chunk(s) the question was derived from
- **Source chunk set** - Which chunking configuration produced the source
- **Expected content** - Key facts/phrases that should appear in retrieval

#### FR-EVAL-2.2: Retrieval Execution
Run each question through the retrieval pipeline:
1. Apply query rewriting (if enabled in config profile)
2. Execute hybrid search (vector + keyword)
3. Record top-k results with scores and ranks
4. Track which chunk sets were searched

#### FR-EVAL-2.3: Multi-Config Testing
Single eval run can test against multiple configurations:
- **Runtime params**: Different profiles applied to same chunk set
- **Chunk configs**: Same questions run against different chunk sets
- Results stored with configuration context for comparison

---

### FR-EVAL-3: Answer Evaluation

#### FR-EVAL-3.1: Answer Generation
For each question + retrieved context:
1. Generate answer using configured LLM and system prompt
2. Track which chunks were provided as context
3. Record the full response with citations

#### FR-EVAL-3.2: LLM-as-Judge Evaluation
Use configurable judge model to evaluate answers on multiple dimensions:

| Dimension | Evaluation Prompt |
|-----------|-------------------|
| **Utilization** | "Does this answer correctly use the provided context to address the question?" |
| **Factual Coverage** | "Do the key facts from the source material appear in the answer?" |
| **Hallucination** | "Does the answer contain claims not supported by the provided context?" |
| **Citation Accuracy** | "Do the citations correctly reference the source material they claim to?" |

Each dimension scored 0-1 with explanation.

#### FR-EVAL-3.3: Judge Model Configuration
- Judge model is configurable separately from answer model
- Default: Same as deployment's default LLM
- Can specify: gpt-4, claude-3-opus, etc.
- Stored in eval config profile

---

### FR-EVAL-4: Metrics & Reporting

#### FR-EVAL-4.1: Core Metrics
Track all metrics individually:

| Metric | Definition | Calculation |
|--------|------------|-------------|
| **Retrieval Recall@k** | Source chunk in top-k results | exact_matches / total_questions (multi-hop: partial credit averaged) |
| **Semantic Coverage** | Retrieved content could answer question | llm_judge_score average |
| **Answer Accuracy** | Answer correctly uses context | llm_judge_score average |
| **Factual Coverage** | Source facts appear in answer | llm_judge_score average |
| **Hallucination Rate** | Unsupported claims in answer | hallucinations / total_answers |
| **Citation Accuracy** | Citations reference correct sources | correct_citations / total_citations |

#### FR-EVAL-4.2: Metric Breakdown
Always report metrics broken down by:
- **Question type** (factual, reasoning, multi-hop)
- **Source chunk set** (which chunking config the question came from)
- **Config profile** (which retrieval/prompt config was tested)

#### FR-EVAL-4.3: Historical Comparison
- **Aggregated metrics** retained indefinitely (summary stats per run)
- **Detailed results** follow tiered retention (see NFR Storage)
- Compare any run against any historical run (using aggregates)
- Admin marks "blessed" baselines for regression detection
- Track metric trends over time

#### FR-EVAL-4.4: Dashboard Visualization
Admin dashboard includes:
- Metric trend charts over time
- Config comparison side-by-side
- Question type breakdown charts
- Per-document performance heatmap
- Regression alerts (vs baseline)

---

### FR-EVAL-5: Configuration Profiles

#### FR-EVAL-5.1: Profile Parameters
Named profiles contain adjustable parameters:

**Retrieval Parameters:**
| Parameter | Description | Default |
|-----------|-------------|---------|
| `top_k` | Number of chunks to retrieve | 5 |
| `vector_weight` | Weight for vector search in RRF | 0.6 |
| `keyword_weight` | Weight for keyword search in RRF | 0.4 |
| `rrf_k` | RRF constant | 60 |
| `similarity_threshold` | Minimum similarity score | 0.0 |

**Prompt Parameters:**
| Parameter | Description |
|-----------|-------------|
| `system_prompt` | Main RAG system prompt for answer generation |
| `query_rewrite_prompt` | Prompt for rewriting follow-up queries |
| `query_rewrite_enabled` | Whether to apply query rewriting |

**Chunk Configuration Reference:**
| Parameter | Description |
|-----------|-------------|
| `chunk_config_id` | Which chunk set to search against |

#### FR-EVAL-5.2: Profile Management
- Create/edit profiles via Admin UI only
- Profiles stored in database
- One profile marked as "production" (current deployment config)
- Profiles can be cloned and modified

#### FR-EVAL-5.3: A/B Tournament
Run evaluation comparing multiple profiles:
1. Select 2+ profiles to compare
2. Run same question set against each
3. Generate comparison report with rankings
4. **Output is recommendations only** - human decides what to promote

---

### FR-EVAL-6: Execution & Triggering

#### FR-EVAL-6.1: Trigger Methods
Three ways to trigger evaluation:

| Method | Interface | Use Case |
|--------|-----------|----------|
| **API** | `POST /eval/runs` | Programmatic triggering, integrations |
| **CLI** | `python -m app.eval run` | Developer workflow, scripts |
| **Admin UI** | "Run Evaluation" button | Non-technical users |

#### FR-EVAL-6.2: Eval Modes
- **Quick mode**: Stratified sample of questions (default ~100) for fast feedback
- **Full mode**: Complete question set for thorough evaluation

**Quick Mode Sampling Strategy:**
- Stratified by question_type: proportional representation (e.g., 50% factual, 35% reasoning, 15% multi-hop)
- Then random within each stratum
- Ensures metric breakdowns remain meaningful even with sampling

Mode specified at trigger time.

#### FR-EVAL-6.3: Background Execution
- Trigger returns immediately with `job_id`
- Evaluation runs as background job
- Poll status via `GET /eval/runs/{job_id}`
- Long runs can take minutes to hours depending on question count

**Cancellation Behavior:**
- `DELETE /eval/runs/{id}` on running job: Sets status to `cancelling`, job stops at next checkpoint
- Job saves partial results before terminating
- Cancelled runs retain all completed results, marked `status=cancelled`

#### FR-EVAL-6.4: Job Status
```
{
  "job_id": "uuid",
  "status": "pending|running|completed|failed|cancelled|cancelling",
  "progress": {
    "total_questions": 500,
    "completed": 127,
    "current_phase": "retrieval_testing"
  },
  "started_at": "timestamp",
  "completed_at": "timestamp|null",
  "checkpoint_id": "uuid|null"  -- for resume capability
}
```

**Checkpoint Format:**
```
{
  "checkpoint_id": "uuid",
  "run_id": "uuid",
  "completed_question_ids": ["uuid", ...],
  "current_config_index": 2,
  "phase": "answer_evaluation",
  "created_at": "timestamp"
}
```
Checkpoints saved every 50 questions or 5 minutes, whichever comes first.

---

### FR-EVAL-7: Multi-Index Management

#### FR-EVAL-7.1: Chunk Configuration Model
```
ChunkConfig {
    id: UUID
    name: string (e.g., "fixed_512", "semantic_v1")
    strategy: enum (fixed_size, semantic)
    chunk_size: int (for fixed_size)
    chunk_overlap: int (for fixed_size)
    is_default: boolean
    created_at: timestamp
}
```

#### FR-EVAL-7.2: Document-ChunkSet Relationship
```
DocumentChunkSet {
    id: UUID
    document_id: UUID (FK)
    chunk_config_id: UUID (FK)
    status: enum (pending, processing, ready, failed)
    chunk_count: int
    created_at: timestamp
}
```

#### FR-EVAL-7.3: Qdrant Vector Tagging
All vectors tagged with:
- `user_id`
- `document_id`
- `chunk_config_id`

Enables filtered search against specific chunk configurations.

#### FR-EVAL-7.4: Admin Operations
- Create new chunk configuration
- Apply chunk config to document(s) → triggers re-chunking + embedding
- Delete chunk set (removes chunks + vectors)
- View storage usage per config

---

## Data Models

### EvalRun
```
EvalRun {
    id: UUID
    status: enum (pending, running, completed, failed, cancelled, cancelling)
    mode: enum (quick, full)
    config_profile_ids: UUID[] -- profiles being tested
    chunk_config_ids: UUID[] -- chunk sets being tested
    question_count: int
    sample_size: int (null if full mode)
    started_at: timestamp
    completed_at: timestamp
    triggered_by: UUID (user_id)
    trigger_method: enum (api, cli, admin_ui)
    error_message: string (nullable)
}
```

### EvalQuestion
```
EvalQuestion {
    id: UUID
    content: text -- the question text
    question_type: enum (factual, reasoning, multi_hop)
    source_chunk_ids: UUID[] -- chunks question was derived from
    source_chunk_config_ids: UUID[] -- which chunk sets produced source chunks
    expected_keywords: string[] -- key terms expected in retrieval (LLM-extracted)
    document_id: UUID
    is_active: boolean -- false if source chunk deleted
    dedup_threshold_used: float -- threshold when this question was generated
    created_at: timestamp
    regenerated_at: timestamp
}
```

**Expected Keywords Generation Prompt:**
```
Given this question and its source chunk, extract 3-5 key terms that
should appear in any retrieved content that could answer this question.

QUESTION: {question}
SOURCE CHUNK: {chunk_content}

Return a JSON array of lowercase keywords, e.g.: ["neural network", "training", "epoch"]
```
```

### EvalResult
```
EvalResult {
    id: UUID
    run_id: UUID (FK)
    question_id: UUID (FK)
    config_profile_id: UUID (FK)
    chunk_config_id: UUID (FK)

    -- Retrieval results
    retrieved_chunk_ids: UUID[]
    source_chunk_retrieved: boolean
    source_chunk_rank: int (nullable)
    retrieval_scores: float[]

    -- Answer results
    generated_answer: text
    citations_in_answer: JSONB

    -- LLM judge scores (0-1)
    semantic_coverage_score: float
    answer_accuracy_score: float
    factual_coverage_score: float
    hallucination_score: float
    citation_accuracy_score: float

    -- Judge explanations
    judge_explanations: JSONB

    -- Profile version snapshot for reproducibility
    config_profile_version: int

    created_at: timestamp
}
```

### EvalConfigProfile
```
EvalConfigProfile {
    id: UUID
    name: string
    description: text
    version: int -- auto-incremented on any change

    -- Retrieval params
    top_k: int
    vector_weight: float
    keyword_weight: float
    rrf_k: int
    similarity_threshold: float

    -- Prompt params
    system_prompt: text
    query_rewrite_prompt: text
    query_rewrite_enabled: boolean

    -- Judge config
    judge_model: string

    -- Metadata
    is_production: boolean
    is_baseline: boolean
    created_by: UUID
    created_at: timestamp
    updated_at: timestamp
}
```

**Profile Versioning:**
- `version` auto-increments on any update (1, 2, 3, ...)
- EvalResult stores `config_profile_id` + `config_profile_version` for reproducibility
- **Snapshot storage**: When an eval run starts, profile params are snapshotted into EvalRun metadata (JSONB)
- This ensures reproducibility even if profile is later modified
- For cleaner workflow, recommend cloning profile before experimental changes

### EvalBaseline
```
EvalBaseline {
    id: UUID
    run_id: UUID (FK)
    name: string
    description: text
    marked_by: UUID (user_id)
    marked_at: timestamp
}
```

---

## API Endpoints

**Access Control:** All `/eval/*` endpoints require Admin or Super-user role. Returns 403 Forbidden for regular users.

### Eval Runs
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/eval/runs` | Trigger new evaluation run |
| `GET` | `/eval/runs` | List evaluation runs (paginated) |
| `GET` | `/eval/runs/{id}` | Get run status and summary |
| `GET` | `/eval/runs/{id}/results` | Get detailed results (paginated, filterable) |
| `DELETE` | `/eval/runs/{id}` | Cancel running eval (soft delete: marks cancelled, retains aggregates) |

**Query params for `/eval/runs/{id}/results`:**
- `limit` (default 50, max 200)
- `offset` (default 0)
- `question_type` (factual, reasoning, multi_hop)
- `config_profile_id` (filter by profile)
- `chunk_config_id` (filter by chunk set)
- `source_retrieved` (true/false - filter by retrieval success)

### Questions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/eval/questions` | List generated questions (paginated) |
| `POST` | `/eval/questions/regenerate` | Trigger question regeneration |
| `GET` | `/eval/questions/stats` | Question set statistics |

**Query params for `/eval/questions`:**
- `limit` (default 50, max 200)
- `offset` (default 0)
- `question_type` (factual, reasoning, multi_hop)
- `document_id` (filter by document)
- `chunk_config_id` (filter by chunk set)

### Config Profiles
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/eval/profiles` | List config profiles |
| `POST` | `/eval/profiles` | Create new profile |
| `GET` | `/eval/profiles/{id}` | Get profile details |
| `PUT` | `/eval/profiles/{id}` | Update profile |
| `DELETE` | `/eval/profiles/{id}` | Delete profile |
| `POST` | `/eval/profiles/{id}/clone` | Clone profile |

### Chunk Configurations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/eval/chunk-configs` | List chunk configurations |
| `POST` | `/eval/chunk-configs` | Create new chunk config |
| `POST` | `/eval/chunk-configs/{id}/apply` | Apply config to document(s) |
| `DELETE` | `/eval/chunk-configs/{id}` | Delete chunk config |

### Baselines
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/eval/baselines` | List marked baselines |
| `POST` | `/eval/baselines` | Mark run as baseline |
| `DELETE` | `/eval/baselines/{id}` | Remove baseline marker |

### Comparison
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/eval/compare` | Compare two runs |
| `GET` | `/eval/metrics/history` | Metric trends over time |

---

## Admin UI Design

### Navigation & Access Control

**Access:** Admin and Super-user roles only. The Evaluation tab is hidden for regular users.

```
Sidebar (when logged in as Admin or Super-user)
├── Chat
├── Documents
├── Evaluation        ← Visible to Admin + Super-user only
│   ├── Runs
│   ├── Config Profiles
│   └── Chunk Configs
└── Admin             ← Admin only (user management, etc.)
```

### Eval Runs Page (`/admin/eval/runs`)

**Header:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Evaluation Runs                              [Run New Evaluation ▼] │
│                                                                     │
│  Filter: [All Statuses ▼]  [All Profiles ▼]  [Last 30 days ▼]      │
└─────────────────────────────────────────────────────────────────────┘
```

**Run New Evaluation Modal:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  New Evaluation Run                                           [X]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Mode:        ○ Quick (sample ~100 questions)                       │
│               ● Full (all questions)                                │
│                                                                     │
│  Profiles to test:                                                  │
│               ☑ production                                          │
│               ☑ experimental_v2                                     │
│               ☐ high_recall                                         │
│                                                                     │
│  Chunk configs to test:                                             │
│               ☑ fixed_512 (default)                                 │
│               ☑ semantic_v1                                         │
│               ☐ fixed_1024                                          │
│                                                                     │
│                                    [Cancel]  [Start Evaluation]     │
└─────────────────────────────────────────────────────────────────────┘
```

**Runs Table:**
```
┌────────┬─────────┬──────────────────┬──────────┬─────────┬─────────┐
│ Status │ Mode    │ Profiles         │ Questions│ Recall  │ Started │
├────────┼─────────┼──────────────────┼──────────┼─────────┼─────────┤
│ ✓ Done │ Full    │ prod, exp_v2     │ 847      │ 78.2%   │ 2h ago  │
│ ● Run  │ Quick   │ production       │ 100/100  │ --      │ 5m ago  │
│ ✓ Done │ Full    │ production       │ 832      │ 74.1%   │ 1d ago  │
│ ✗ Fail │ Full    │ high_recall      │ 412/847  │ --      │ 2d ago  │
└────────┴─────────┴──────────────────┴──────────┴─────────┴─────────┘
                                              [Mark as Baseline ☆]
```

### Run Results Page (`/admin/eval/runs/{id}`)

**Summary Cards:**
```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Retrieval    │ │ vs Baseline  │ │ Questions    │ │ Duration     │
│    78.2%     │ │   +4.1% ↑    │ │    847       │ │   12m 34s    │
│  Recall@5    │ │  (74.1%)     │ │   tested     │ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

**Comparison Chart (when multiple profiles tested):**
```
Retrieval Recall by Profile
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  production     ████████████████████████████░░░░  74.1%             │
│  experimental   ████████████████████████████████  78.2%  ← Best    │
│  high_recall    ██████████████████████████████████████  82.4%      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Breakdown by Question Type:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Question Type Breakdown                                            │
├─────────────────────────────────────────────────────────────────────┤
│                    Factual    Reasoning   Multi-hop                 │
│  Questions            412         298         137                   │
│  Recall@5           84.2%       71.8%       68.4%                   │
│  vs Baseline        +2.1%       +5.2%       +8.9%                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Chunk Config Comparison (when multiple tested):**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Chunk Config Comparison                                            │
├─────────────────────────────────────────────────────────────────────┤
│                    fixed_512   semantic_v1   fixed_1024             │
│  Recall@5           74.1%       78.2%         71.3%                 │
│  Avg Rank            2.4         1.8           2.9                  │
│  Questions from      312         298           237                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Config Profiles Page (`/admin/eval/profiles`)

**Profiles List:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Config Profiles                                   [+ New Profile]  │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┬───────┬─────────┬──────────────┬────────────────┐
│ Name             │ top_k │ Weights │ Query Rewrite│ Actions        │
├──────────────────┼───────┼─────────┼──────────────┼────────────────┤
│ production    ★☆ │ 5     │ 0.6/0.4 │ Enabled      │ [Edit] [Clone] │
│ experimental_v2  │ 8     │ 0.7/0.3 │ Enabled      │ [Edit] [Clone] │
│ high_recall      │ 10    │ 0.5/0.5 │ Disabled     │ [Edit] [Clone] │
│ keyword_heavy    │ 5     │ 0.3/0.7 │ Enabled      │ [Edit] [Clone] │
└──────────────────┴───────┴─────────┴──────────────┴────────────────┘

★ = Production   ☆ = Baseline
```

**Edit Profile Modal:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Edit Profile: experimental_v2                                [X]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Name: [experimental_v2                              ]              │
│                                                                     │
│  ─── Retrieval Parameters ───                                       │
│  Top K:              [8    ]                                        │
│  Vector Weight:      [0.7  ]  (keyword = 0.3)                       │
│  RRF K:              [60   ]                                        │
│  Similarity Threshold: [0.0]                                        │
│                                                                     │
│  ─── Prompts ───                                                    │
│  Query Rewrite:      [✓] Enabled                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Rewrite this follow-up question into a standalone search   │    │
│  │ query for document retrieval...                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  System Prompt:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ You are a helpful document assistant...                    │    │
│  │                                                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ─── Judge Model ───                                                │
│  Model: [gpt-4 ▼]                                                   │
│                                                                     │
│                        [Delete]    [Cancel]  [Save Changes]         │
└─────────────────────────────────────────────────────────────────────┘
```

### Chunk Configs Page (`/admin/eval/chunk-configs`)

**Chunk Configs List:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Chunk Configurations                           [+ New Config]      │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────┬──────────┬───────┬─────────┬───────────┬──────────┐
│ Name           │ Strategy │ Size  │ Overlap │ Documents │ Actions  │
├────────────────┼──────────┼───────┼─────────┼───────────┼──────────┤
│ fixed_512   ★  │ Fixed    │ 512   │ 50      │ 24 (all)  │ [Edit]   │
│ fixed_1024     │ Fixed    │ 1024  │ 100     │ 5         │ [Apply]  │
│ semantic_v1    │ Semantic │ --    │ --      │ 12        │ [Apply]  │
└────────────────┴──────────┴───────┴─────────┴───────────┴──────────┘

★ = Default (used for new uploads)
```

**Apply Config Modal:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Apply "semantic_v1" to Documents                             [X]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Select documents to re-chunk with this configuration:              │
│                                                                     │
│  ☑ Select All (24 documents)                                        │
│  ───────────────────────────────────────────                        │
│  ☑ annual_report_2024.pdf                                           │
│  ☑ product_manual.pdf                                               │
│  ☑ research_paper.pdf                                               │
│  ☐ meeting_notes.txt  (already has this config)                     │
│  ...                                                                │
│                                                                     │
│  ⚠️  This will create additional chunk sets and embeddings.         │
│     Estimated storage: +45 MB                                       │
│                                                                     │
│                                    [Cancel]  [Apply to 12 docs]     │
└─────────────────────────────────────────────────────────────────────┘
```

### Metrics History Page (`/admin/eval/history`)

**Trend Chart:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Retrieval Recall Over Time            [Last 30 days ▼] [Recall ▼] │
├─────────────────────────────────────────────────────────────────────┤
│  85% ┤                                                              │
│      │                              ╭─────☆ 78.2% (baseline)        │
│  80% ┤                    ╭────────╯                                │
│      │              ╭────╯                                          │
│  75% ┤    ╭────────╯                                                │
│      │───╯                                                          │
│  70% ┤                                                              │
│      └──────────────────────────────────────────────────────────────│
│       Jan 1    Jan 8    Jan 15    Jan 22                            │
└─────────────────────────────────────────────────────────────────────┘
```

## CLI Interface

```bash
# Trigger evaluation
python -m app.eval run --mode=full --profiles=production,experimental
python -m app.eval run --mode=quick --sample=100

# Check status
python -m app.eval status <job_id>

# List recent runs
python -m app.eval list --limit=10

# Compare runs
python -m app.eval compare <run_id_1> <run_id_2>

# Regenerate questions
python -m app.eval regenerate-questions --document=<doc_id>
python -m app.eval regenerate-questions --all

# Manage profiles
python -m app.eval profiles list
python -m app.eval profiles show <profile_id>

# Manage chunk configs
python -m app.eval chunk-configs list
python -m app.eval chunk-configs apply <config_id> --document=<doc_id>
```

---

## Scope Boundaries

### In Scope (MVP)
- [x] Multi-index storage model for chunk configurations
- [x] Content-adaptive question generation
- [x] Question type tagging (factual, reasoning, multi-hop)
- [x] Stratified generation across chunk sets with deduplication
- [x] Retrieval recall@k metric
- [x] Full API endpoints for CRUD + triggering + results
- [x] CLI for developer workflow
- [x] Named config profiles (retrieval params + prompts)
- [x] **Admin UI with Full CRUD:**
  - [x] Eval Runs: trigger, list, view summary results
  - [x] Config Profiles: create, edit, clone, delete
  - [x] Chunk Configs: create, edit, apply to documents, delete
  - [x] Summary dashboard with comparison charts
  - [x] Baseline marking
- [x] Background job execution
- [x] Quick vs Full eval modes

### Phase 2
- [ ] Full LLM-as-judge metrics (answer accuracy, hallucination, citations)
- [ ] Semantic coverage scoring
- [ ] Judge model configuration
- [ ] Regression alerts (baseline comparison already in MVP)
- [ ] Profile comparison in single run

### Phase 3
- [ ] Dashboard charts and visualization
- [ ] Metric trend history charts
- [ ] A/B tournament UI with recommendations
- [ ] Per-document performance heatmap
- [ ] Conversation follow-up eval mode

### Out of Scope
- Load/stress testing
- UI/UX testing
- Security testing
- Conversation follow-up eval (architecture supports, implement later)
- Automated CI/CD integration (manual triggering only for now)
- Auto-promotion of winning configs

---

## Non-Functional Requirements

### Performance
- Question generation: Process 100 chunks within 5 minutes
- Retrieval testing (without judge): 10 questions/second throughput
- **Full eval with LLM judge:**
  - GPT-4 judge: ~1 question/second (rate limited)
  - GPT-3.5/fast model judge: ~5 questions/second
  - Full eval (1000 questions): 15-60 minutes depending on judge model
- Background jobs: No blocking of main API (separate worker process)

### Storage
- Eval history: Retained indefinitely (aggregated metrics)
- Multi-index overhead: ~3x storage per additional chunk config (max 10 per doc)
- **Detailed results retention:**
  - Last 30 days: Full detailed results (all EvalResult rows)
  - 30-90 days: Aggregated metrics + sample of 100 detailed results per run
  - 90+ days: Aggregated metrics only (summary stats, no individual results)
- Admin can export full results to JSON before archival

### Reliability
- Failed jobs: Retry logic with checkpointing
- Partial results: Save progress, allow resume
- Graceful degradation: Continue eval if individual questions fail

**Retry Configuration:**
- Max retries per LLM call: 3
- Backoff: Exponential (1s, 2s, 4s)
- After max retries: Log error, mark question as `eval_failed`, continue to next

### LLM Rate Limiting
Background eval jobs must not overwhelm LLM APIs:
- **Concurrency limit**: Max 5 parallel LLM calls per eval job
- **Rate limit**: Max 60 requests/minute to judge model (global across all eval jobs)
- **Judge call batching**: Single judge call evaluates all 4 dimensions (utilization, factual, hallucination, citation) to minimize requests
- **Queue management**: Global limiter shared between user chat and eval; user chat requests have priority
- **Backpressure**: If queue depth > 100, pause eval job until queue drains

---

## Success Criteria

1. **Question Quality**: Generated questions are answerable from source chunks (>90% valid)
2. **Metric Accuracy**: Retrieval recall matches manual verification (>95% agreement)
3. **Comparison Utility**: A/B tests surface meaningful differences between configs
4. **Usability**: Non-technical admins can trigger and interpret evals via UI
5. **Performance**: Full eval completes in reasonable time (<30 min for 1000 questions)

---

## Open Questions

1. ~~**Question deduplication threshold**: What embedding similarity threshold for merging questions?~~ **RESOLVED:** Configurable per run, default 0.9
2. ~~**Chunk density heuristics**: How to determine "dense" vs "sparse" chunks for adaptive generation?~~ **RESOLVED:** LLM classification with explicit prompt
3. **Judge prompt engineering**: What specific prompts yield most reliable LLM-as-judge scores? (Phase 2)
4. ~~**Storage optimization**: Should we archive old eval results to cold storage after N days?~~ **RESOLVED:** Tiered retention (30/90 days)
5. **Qdrant index strategy**: Optimal index configuration for multi-filter queries (user_id × document_id × chunk_config_id)
6. **expected_keywords metric**: Currently tracked but not used in metrics (candidate for keyword hit rate metric in Phase 2)

---

*This EVAL_SPEC.md defines the Auto-Evaluation Framework for ruhroh. Implementation should reference this document for all eval-related decisions.*
