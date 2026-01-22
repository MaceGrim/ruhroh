# RAG Auto-Evaluation Framework - PRD

## Executive Summary

The Auto-Eval Framework enables administrators to quantitatively measure and improve RAG quality by automatically generating questions from document chunks, testing retrieval and answer generation, and tracking metrics over time. This addresses the critical need for data-driven validation of prompt changes, chunking strategies, and retrieval configurations.

## Problem Statement

**Current Pain:**
- No way to objectively measure RAG quality after configuration changes
- Prompt tweaks are deployed based on gut feel, not data
- Regressions in retrieval quality go undetected until user complaints
- Different chunking strategies cannot be compared systematically

**Who Has It:**
- Administrators managing RAG deployments
- Developers iterating on retrieval parameters and prompts
- Teams needing confidence that changes improve (not degrade) quality

## Target Users

### Primary: System Administrator
- **Goals:** Ensure RAG quality, validate changes before deployment, catch regressions
- **Pain Points:** No visibility into retrieval quality, time-consuming manual testing
- **Capabilities:** Can trigger evals, interpret results, mark baselines

### Secondary: Developer
- **Goals:** Iterate on prompts and parameters with fast feedback
- **Pain Points:** Slow feedback loop, no A/B testing capability
- **Capabilities:** Use CLI for quick evals, compare configurations

## User Stories

1. **As an admin**, I want to trigger an evaluation run so that I can measure current RAG quality
2. **As an admin**, I want to compare two configuration profiles so that I can choose the better one
3. **As an admin**, I want to mark a run as baseline so that I can detect regressions
4. **As a developer**, I want quick mode evaluation so that I can get fast feedback on changes
5. **As an admin**, I want to create new chunk configurations so that I can test different chunking strategies
6. **As an admin**, I want to view metric trends over time so that I can track quality improvements

## Functional Requirements

### Core Capabilities (MVP)

1. **Question Generation**
   - Automatically generate evaluation questions from document chunks
   - Content-adaptive density (more questions from information-dense chunks)
   - Tag questions by type (factual, reasoning, multi-hop)

2. **Retrieval Testing**
   - Run questions through retrieval pipeline
   - Track source chunk recall@k
   - Support multiple chunk configurations per document

3. **Configuration Profiles**
   - Named profiles with retrieval params (top_k, weights) and prompts
   - Clone and modify profiles for A/B testing
   - Mark profiles as production or baseline

4. **Evaluation Execution**
   - API, CLI, and Admin UI triggering
   - Quick mode (stratified sample ~100) and Full mode (all questions)
   - Background execution with progress tracking

5. **Admin UI**
   - Eval Runs: trigger, list, view results
   - Config Profiles: create, edit, clone, delete
   - Chunk Configs: create, apply to documents
   - Baseline marking

### Phase 2
- Full LLM-as-judge metrics (answer accuracy, hallucination, citations)
- Regression alerts
- Profile comparison in single run

### Phase 3
- Dashboard visualizations and trend charts
- A/B tournament UI with recommendations
- Per-document performance heatmap

## Success Metrics

| Metric | Target |
|--------|--------|
| Question Quality | >90% generated questions answerable from source |
| Metric Accuracy | >95% agreement with manual verification |
| Admin Usability | Non-technical admins can trigger and interpret evals |
| Performance | Full eval <60 min for 1000 questions |

## Scope

### In Scope
- Multi-index storage for chunk configurations (max 10 per doc)
- Content-adaptive question generation
- Retrieval recall@k metric
- Named config profiles with versioning
- Admin UI with full CRUD
- Background job execution with checkpointing

### Out of Scope
- Load/stress testing
- UI/UX testing
- Automated CI/CD integration
- Auto-promotion of winning configs

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM rate limits | Eval jobs slow/fail | Rate limiting, batching, priority queue |
| Storage explosion | Costs increase | Max 10 chunk configs per doc, tiered retention |
| Question quality | Invalid metrics | LLM density classification, skip unevaluable chunks |

## Access Control

**Admin + Super-user only.** Evaluation tab hidden from regular users.

---

*This PRD defines the Auto-Evaluation Framework for ruhroh from a product perspective.*
