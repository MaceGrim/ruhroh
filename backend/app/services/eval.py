"""Evaluation service for RAG quality assessment."""

import json
import random
import time
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.document import DocumentRepository
from app.db.repositories.chunk import ChunkRepository
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService, RetrievalResult

logger = structlog.get_logger()


class EvalError(Exception):
    """Evaluation error."""

    pass


# Prompts for metric evaluation
FAITHFULNESS_PROMPT = """You are evaluating the faithfulness of an AI-generated answer to a question based on the provided context.

Faithfulness measures whether the answer contains only information that can be verified from the given context. An answer is faithful if every claim it makes is supported by the context.

Question: {question}

Context:
{context}

Generated Answer: {answer}

Evaluate the faithfulness of the answer on a scale from 0 to 1:
- 1.0: Every statement in the answer is directly supported by the context
- 0.7-0.9: Most statements are supported, with minor unsupported details
- 0.4-0.6: Some statements are supported, but significant claims are unsupported
- 0.1-0.3: Few statements are supported by the context
- 0.0: The answer contains information that contradicts or is completely unrelated to the context

Respond with ONLY a JSON object in this exact format:
{{"score": <float between 0 and 1>, "reasoning": "<brief explanation>"}}"""


ANSWER_RELEVANCY_PROMPT = """You are evaluating how relevant an AI-generated answer is to the original question.

Answer relevancy measures whether the answer directly addresses what was asked. An answer is relevant if it provides information that helps answer the question.

Question: {question}

Generated Answer: {answer}

Evaluate the answer relevancy on a scale from 0 to 1:
- 1.0: The answer directly and completely addresses the question
- 0.7-0.9: The answer mostly addresses the question with minor tangents
- 0.4-0.6: The answer partially addresses the question but misses key aspects
- 0.1-0.3: The answer barely relates to the question
- 0.0: The answer is completely irrelevant to the question

Respond with ONLY a JSON object in this exact format:
{{"score": <float between 0 and 1>, "reasoning": "<brief explanation>"}}"""


CONTEXT_PRECISION_PROMPT = """You are evaluating how precise the retrieved context chunks are for answering the question.

Context precision measures whether the retrieved chunks are relevant and useful for answering the question. High precision means most chunks contain relevant information.

Question: {question}

Retrieved Context Chunks:
{context}

For each chunk, determine if it contains information relevant to answering the question.

Evaluate the context precision on a scale from 0 to 1:
- 1.0: All context chunks are highly relevant to the question
- 0.7-0.9: Most chunks are relevant, with few irrelevant ones
- 0.4-0.6: About half the chunks are relevant
- 0.1-0.3: Few chunks are relevant
- 0.0: No chunks are relevant to the question

Respond with ONLY a JSON object in this exact format:
{{"score": <float between 0 and 1>, "reasoning": "<brief explanation>"}}"""


ANSWER_CORRECTNESS_PROMPT = """You are evaluating how correct an AI-generated answer is compared to the expected/ground truth answer.

Answer correctness measures the factual accuracy and completeness of the generated answer compared to what was expected.

Question: {question}

Expected Answer: {expected_answer}

Generated Answer: {generated_answer}

Evaluate the answer correctness on a scale from 0 to 1:
- 1.0: The generated answer is factually equivalent to the expected answer
- 0.7-0.9: The generated answer captures most key points correctly
- 0.4-0.6: The generated answer is partially correct with some errors or omissions
- 0.1-0.3: The generated answer has significant errors or misses key information
- 0.0: The generated answer is completely incorrect

Respond with ONLY a JSON object in this exact format:
{{"score": <float between 0 and 1>, "reasoning": "<brief explanation>"}}"""


RAG_SYSTEM_PROMPT = """You are a helpful document assistant. Answer questions based on the provided context from the user's documents.

RULES:
1. Only use information from the CONTEXT section below
2. If the information is not in the context, say "I couldn't find this in your documents"
3. Be concise and direct in your answers
4. Never make up information not present in the context

CONTEXT:
{context}"""


class EvalService:
    """Service for evaluating RAG pipeline quality."""

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        llm_service: LLMService,
        retrieval_service: RetrievalService,
    ):
        self.settings = settings
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.llm_service = llm_service
        self.retrieval_service = retrieval_service

        # In-memory eval storage (in production, use database)
        self._evals: dict[str, dict] = {}

    # =========================================================================
    # Single Evaluation Methods
    # =========================================================================

    async def run_single_evaluation(
        self,
        user_id: UUID,
        question: str,
        expected_answer: Optional[str] = None,
        document_ids: Optional[list[UUID]] = None,
        top_k: int = 5,
        model: Optional[str] = None,
    ) -> dict:
        """Run a single RAG evaluation.

        Args:
            user_id: User UUID
            question: The question to evaluate
            expected_answer: Optional expected answer for comparison
            document_ids: Optional document filter
            top_k: Number of context chunks to retrieve
            model: Model to use for generation

        Returns:
            Dict with evaluation results including answer and metrics
        """
        eval_id = uuid4()
        start_time = time.time()
        model_used = model or self.settings.ruhroh_default_model

        logger.info(
            "single_eval_started",
            eval_id=str(eval_id),
            question=question[:100],
        )

        try:
            # Step 1: Retrieve context
            retrieval_results = await self.retrieval_service.search(
                query=question,
                user_id=user_id,
                top_k=top_k,
                document_ids=document_ids,
            )

            # Step 2: Generate answer
            context = self._format_context_for_llm(retrieval_results)
            generated_answer = await self._generate_answer(
                question, context, model_used
            )

            # Step 3: Compute metrics
            metrics = await self._compute_metrics(
                question=question,
                answer=generated_answer,
                context=context,
                retrieval_results=retrieval_results,
                expected_answer=expected_answer,
            )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Build retrieved contexts response
            retrieved_contexts = [
                {
                    "chunk_id": result.chunk_id,
                    "document_id": result.document_id,
                    "document_name": result.document_name,
                    "content": result.content,
                    "score": result.score,
                    "page_numbers": result.page_numbers,
                }
                for result in retrieval_results
            ]

            # Store in history
            eval_record = {
                "id": str(eval_id),
                "user_id": str(user_id),
                "eval_type": "single",
                "status": "completed",
                "question": question,
                "generated_answer": generated_answer,
                "expected_answer": expected_answer,
                "retrieved_contexts": retrieved_contexts,
                "metrics": metrics,
                "model_used": model_used,
                "latency_ms": latency_ms,
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            }
            self._evals[str(eval_id)] = eval_record

            logger.info(
                "single_eval_completed",
                eval_id=str(eval_id),
                faithfulness=metrics["faithfulness"],
                answer_relevancy=metrics["answer_relevancy"],
                latency_ms=latency_ms,
            )

            return {
                "eval_id": eval_id,
                "question": question,
                "generated_answer": generated_answer,
                "expected_answer": expected_answer,
                "retrieved_contexts": retrieved_contexts,
                "metrics": metrics,
                "model_used": model_used,
                "latency_ms": latency_ms,
                "created_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error("single_eval_failed", eval_id=str(eval_id), error=str(e))
            raise EvalError(f"Single evaluation failed: {e}")

    def _format_context_for_llm(self, results: list[RetrievalResult]) -> str:
        """Format retrieval results into context string for LLM."""
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, start=1):
            page_info = ""
            if result.page_numbers:
                pages = ", ".join(str(p) for p in result.page_numbers)
                page_info = f" (pages: {pages})"

            context_parts.append(
                f"[{i}] From \"{result.document_name}\"{page_info}:\n"
                f"{result.content}"
            )

        return "\n\n".join(context_parts)

    async def _generate_answer(
        self,
        question: str,
        context: str,
        model: str,
    ) -> str:
        """Generate an answer using the RAG pipeline."""
        if not context:
            return "I couldn't find relevant information in your documents to answer this question."

        system_prompt = RAG_SYSTEM_PROMPT.format(context=context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        response = await self.llm_service.chat_completion(
            messages=messages,
            model=model,
            temperature=0.3,  # Lower temperature for more consistent answers
            max_tokens=1024,
        )

        return response.strip()

    async def _compute_metrics(
        self,
        question: str,
        answer: str,
        context: str,
        retrieval_results: list[RetrievalResult],
        expected_answer: Optional[str] = None,
    ) -> dict:
        """Compute evaluation metrics using LLM-as-judge.

        Args:
            question: The original question
            answer: Generated answer
            context: Retrieved context
            retrieval_results: List of retrieval results
            expected_answer: Optional expected answer

        Returns:
            Dict of metric scores
        """
        # Compute faithfulness, answer relevancy, and context precision in parallel
        # For efficiency, we could batch these, but for clarity we'll do them separately

        faithfulness = await self._evaluate_faithfulness(question, answer, context)
        answer_relevancy = await self._evaluate_answer_relevancy(question, answer)
        context_precision = await self._evaluate_context_precision(
            question, retrieval_results
        )

        metrics = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": None,
            "answer_correctness": None,
        }

        # If expected answer is provided, compute additional metrics
        if expected_answer:
            answer_correctness = await self._evaluate_answer_correctness(
                question, answer, expected_answer
            )
            metrics["answer_correctness"] = answer_correctness

            # Context recall requires ground truth context, which we approximate
            # based on whether the answer seems to use the retrieved context
            context_recall = await self._estimate_context_recall(
                question, answer, expected_answer, context
            )
            metrics["context_recall"] = context_recall

        return metrics

    async def _evaluate_faithfulness(
        self,
        question: str,
        answer: str,
        context: str,
    ) -> float:
        """Evaluate faithfulness using LLM-as-judge."""
        if not context:
            return 0.0

        prompt = FAITHFULNESS_PROMPT.format(
            question=question,
            context=context,
            answer=answer,
        )

        return await self._get_llm_score(prompt)

    async def _evaluate_answer_relevancy(
        self,
        question: str,
        answer: str,
    ) -> float:
        """Evaluate answer relevancy using LLM-as-judge."""
        prompt = ANSWER_RELEVANCY_PROMPT.format(
            question=question,
            answer=answer,
        )

        return await self._get_llm_score(prompt)

    async def _evaluate_context_precision(
        self,
        question: str,
        retrieval_results: list[RetrievalResult],
    ) -> float:
        """Evaluate context precision using LLM-as-judge."""
        if not retrieval_results:
            return 0.0

        # Format context chunks with indices
        context_chunks = []
        for i, result in enumerate(retrieval_results, start=1):
            context_chunks.append(
                f"Chunk {i}:\n{result.content[:500]}..."
                if len(result.content) > 500
                else f"Chunk {i}:\n{result.content}"
            )

        context = "\n\n".join(context_chunks)

        prompt = CONTEXT_PRECISION_PROMPT.format(
            question=question,
            context=context,
        )

        return await self._get_llm_score(prompt)

    async def _evaluate_answer_correctness(
        self,
        question: str,
        generated_answer: str,
        expected_answer: str,
    ) -> float:
        """Evaluate answer correctness using LLM-as-judge."""
        prompt = ANSWER_CORRECTNESS_PROMPT.format(
            question=question,
            expected_answer=expected_answer,
            generated_answer=generated_answer,
        )

        return await self._get_llm_score(prompt)

    async def _estimate_context_recall(
        self,
        question: str,
        generated_answer: str,
        expected_answer: str,
        context: str,
    ) -> float:
        """Estimate context recall.

        This is an approximation since we don't have true ground truth context.
        We estimate based on how much of the expected answer's information
        appears to be covered by the retrieved context.
        """
        # Simple heuristic: if the answer is correct, context recall is likely high
        # A more sophisticated approach would require ground truth context annotations
        correctness = await self._evaluate_answer_correctness(
            question, generated_answer, expected_answer
        )

        # Use correctness as a proxy for recall (imperfect but reasonable)
        return correctness

    async def _get_llm_score(self, prompt: str) -> float:
        """Get a score from LLM evaluation."""
        try:
            response = await self.llm_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent evaluation
                max_tokens=200,
            )

            # Parse JSON response
            response = response.strip()

            # Handle markdown code blocks
            if response.startswith("```"):
                # Remove markdown code block
                lines = response.split("\n")
                response = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                )

            parsed = json.loads(response)
            score = float(parsed.get("score", 0.5))

            # Clamp to [0, 1]
            return max(0.0, min(1.0, score))

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("llm_score_parse_failed", error=str(e), response=response[:200])
            # Return a neutral score on parse failure
            return 0.5

    # =========================================================================
    # Batch Evaluation Methods
    # =========================================================================

    async def start_batch_evaluation(
        self,
        user_id: UUID,
        test_cases: list[dict],
        document_ids: Optional[list[UUID]] = None,
        top_k: int = 5,
        model: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Start a batch evaluation run.

        Args:
            user_id: User UUID
            test_cases: List of test case dicts with question and optional expected_answer
            document_ids: Optional document filter
            top_k: Number of context chunks per question
            model: Model to use
            name: Optional name for this evaluation

        Returns:
            Dict with eval_id and status
        """
        eval_id = str(uuid4())

        self._evals[eval_id] = {
            "id": eval_id,
            "user_id": str(user_id),
            "eval_type": "batch",
            "name": name,
            "status": "pending",
            "progress": {"current": 0, "total": len(test_cases)},
            "test_cases": test_cases,
            "document_ids": [str(d) for d in document_ids] if document_ids else None,
            "top_k": top_k,
            "model": model,
            "results": [],
            "summary": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }

        logger.info(
            "batch_eval_started",
            eval_id=eval_id,
            total_cases=len(test_cases),
        )

        return {
            "eval_id": UUID(eval_id),
            "status": "pending",
            "total_cases": len(test_cases),
        }

    async def run_batch_evaluation(self, eval_id: str) -> None:
        """Run the batch evaluation pipeline.

        Args:
            eval_id: Evaluation ID
        """
        eval_data = self._evals.get(eval_id)
        if not eval_data:
            raise EvalError(f"Evaluation not found: {eval_id}")

        try:
            eval_data["status"] = "running"
            start_time = time.time()

            user_id = UUID(eval_data["user_id"])
            test_cases = eval_data["test_cases"]
            document_ids = (
                [UUID(d) for d in eval_data["document_ids"]]
                if eval_data["document_ids"]
                else None
            )
            top_k = eval_data["top_k"]
            model = eval_data["model"]

            results = []
            metrics_accumulator = {
                "faithfulness": [],
                "answer_relevancy": [],
                "context_precision": [],
                "context_recall": [],
                "answer_correctness": [],
                "latency_ms": [],
            }

            for i, test_case in enumerate(test_cases):
                eval_data["progress"]["current"] = i + 1

                try:
                    case_start_time = time.time()

                    # Run single evaluation for this test case
                    result = await self.run_single_evaluation(
                        user_id=user_id,
                        question=test_case["question"],
                        expected_answer=test_case.get("expected_answer"),
                        document_ids=document_ids,
                        top_k=top_k,
                        model=model,
                    )

                    case_latency = (time.time() - case_start_time) * 1000

                    results.append({
                        "test_case_index": i,
                        "question": test_case["question"],
                        "generated_answer": result["generated_answer"],
                        "expected_answer": test_case.get("expected_answer"),
                        "metrics": result["metrics"],
                        "retrieved_context_count": len(result["retrieved_contexts"]),
                        "latency_ms": case_latency,
                        "error": None,
                    })

                    # Accumulate metrics
                    metrics_accumulator["faithfulness"].append(result["metrics"]["faithfulness"])
                    metrics_accumulator["answer_relevancy"].append(result["metrics"]["answer_relevancy"])
                    metrics_accumulator["context_precision"].append(result["metrics"]["context_precision"])
                    metrics_accumulator["latency_ms"].append(case_latency)

                    if result["metrics"].get("context_recall") is not None:
                        metrics_accumulator["context_recall"].append(result["metrics"]["context_recall"])
                    if result["metrics"].get("answer_correctness") is not None:
                        metrics_accumulator["answer_correctness"].append(result["metrics"]["answer_correctness"])

                except Exception as e:
                    logger.warning(
                        "batch_eval_case_failed",
                        eval_id=eval_id,
                        case_index=i,
                        error=str(e),
                    )
                    results.append({
                        "test_case_index": i,
                        "question": test_case["question"],
                        "generated_answer": "",
                        "expected_answer": test_case.get("expected_answer"),
                        "metrics": {
                            "faithfulness": 0.0,
                            "answer_relevancy": 0.0,
                            "context_precision": 0.0,
                            "context_recall": None,
                            "answer_correctness": None,
                        },
                        "retrieved_context_count": 0,
                        "latency_ms": 0.0,
                        "error": str(e),
                    })

            # Calculate summary statistics
            total_duration = time.time() - start_time
            successful_cases = sum(1 for r in results if r["error"] is None)
            failed_cases = len(results) - successful_cases

            def safe_avg(values: list) -> float:
                return sum(values) / len(values) if values else 0.0

            summary = {
                "total_cases": len(test_cases),
                "successful_cases": successful_cases,
                "failed_cases": failed_cases,
                "avg_faithfulness": safe_avg(metrics_accumulator["faithfulness"]),
                "avg_answer_relevancy": safe_avg(metrics_accumulator["answer_relevancy"]),
                "avg_context_precision": safe_avg(metrics_accumulator["context_precision"]),
                "avg_context_recall": (
                    safe_avg(metrics_accumulator["context_recall"])
                    if metrics_accumulator["context_recall"]
                    else None
                ),
                "avg_answer_correctness": (
                    safe_avg(metrics_accumulator["answer_correctness"])
                    if metrics_accumulator["answer_correctness"]
                    else None
                ),
                "avg_latency_ms": safe_avg(metrics_accumulator["latency_ms"]),
                "total_duration_seconds": total_duration,
            }

            eval_data["results"] = results
            eval_data["summary"] = summary
            eval_data["status"] = "completed"
            eval_data["completed_at"] = datetime.utcnow().isoformat()

            logger.info(
                "batch_eval_completed",
                eval_id=eval_id,
                successful_cases=successful_cases,
                failed_cases=failed_cases,
                avg_faithfulness=summary["avg_faithfulness"],
            )

        except Exception as e:
            logger.error("batch_eval_failed", eval_id=eval_id, error=str(e))
            eval_data["status"] = "failed"
            eval_data["error"] = str(e)
            eval_data["completed_at"] = datetime.utcnow().isoformat()

    # =========================================================================
    # Evaluation History Methods
    # =========================================================================

    async def list_evaluations(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        eval_type: Optional[str] = None,
    ) -> dict:
        """List evaluation history for a user.

        Args:
            user_id: User UUID
            limit: Max results
            offset: Pagination offset
            eval_type: Optional filter by type (single, batch, auto)

        Returns:
            Dict with evaluations list and total count
        """
        user_evals = [
            e for e in self._evals.values()
            if e["user_id"] == str(user_id)
        ]

        if eval_type:
            user_evals = [e for e in user_evals if e["eval_type"] == eval_type]

        # Sort by created_at descending
        user_evals.sort(key=lambda x: x["created_at"], reverse=True)

        total = len(user_evals)
        paginated = user_evals[offset:offset + limit]

        evaluations = []
        for e in paginated:
            item = {
                "eval_id": UUID(e["id"]),
                "eval_type": e["eval_type"],
                "name": e.get("name"),
                "status": e["status"],
                "created_at": datetime.fromisoformat(e["created_at"]),
                "completed_at": (
                    datetime.fromisoformat(e["completed_at"])
                    if e.get("completed_at")
                    else None
                ),
            }

            # Add summary metrics if available
            if e["eval_type"] == "single" and e.get("metrics"):
                item["summary_metrics"] = {
                    "faithfulness": e["metrics"]["faithfulness"],
                    "answer_relevancy": e["metrics"]["answer_relevancy"],
                    "context_precision": e["metrics"]["context_precision"],
                }
            elif e["eval_type"] == "batch" and e.get("summary"):
                item["summary_metrics"] = {
                    "avg_faithfulness": e["summary"]["avg_faithfulness"],
                    "avg_answer_relevancy": e["summary"]["avg_answer_relevancy"],
                    "avg_context_precision": e["summary"]["avg_context_precision"],
                }
                item["total_cases"] = e["summary"]["total_cases"]
            elif e["eval_type"] == "auto" and e.get("results"):
                item["summary_metrics"] = {
                    "hit_rate": e["results"].get("hit_rate", 0),
                    "mrr": e["results"].get("mrr", 0),
                }

            evaluations.append(item)

        return {
            "evaluations": evaluations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_evaluation_by_id(
        self,
        eval_id: str,
        user_id: UUID,
    ) -> Optional[dict]:
        """Get a specific evaluation by ID.

        Args:
            eval_id: Evaluation ID
            user_id: User UUID for ownership check

        Returns:
            Evaluation dict or None
        """
        eval_data = self._evals.get(eval_id)

        if not eval_data:
            return None

        if eval_data["user_id"] != str(user_id):
            return None

        return eval_data

    # =========================================================================
    # Original Bulk Evaluation Methods (for backward compatibility)
    # =========================================================================

    async def start_evaluation(
        self,
        user_id: UUID,
        document_ids: Optional[list[UUID]] = None,
        question_count: int = 50,
        chunking_strategies: Optional[list[str]] = None,
        use_holdout: bool = False,
    ) -> dict:
        """Start an evaluation run.

        Args:
            user_id: User UUID
            document_ids: Documents to evaluate (defaults to all user docs)
            question_count: Number of questions to generate
            chunking_strategies: Strategies to compare
            use_holdout: Whether to use holdout set

        Returns:
            Dict with eval_id and status
        """
        eval_id = str(uuid4())

        # Get documents
        if document_ids:
            documents = []
            for doc_id in document_ids:
                doc = await self.doc_repo.get_by_id(doc_id, user_id)
                if doc and doc.status == "ready":
                    documents.append(doc)
        else:
            documents = await self.doc_repo.list_by_user(user_id, status="ready", limit=100)

        if not documents:
            raise EvalError("No ready documents found for evaluation")

        # Initialize eval record
        self._evals[eval_id] = {
            "id": eval_id,
            "user_id": str(user_id),
            "status": "pending",
            "progress": {"current": 0, "total": question_count},
            "document_ids": [str(d.id) for d in documents],
            "question_count": question_count,
            "chunking_strategies": chunking_strategies,
            "use_holdout": use_holdout,
            "results": None,
        }

        # In a real implementation, this would be a background task
        # For now, we'll run it inline (but it would be async)

        return {
            "eval_id": UUID(eval_id),
            "status": "pending",
        }

    async def run_evaluation(self, eval_id: str) -> None:
        """Run the evaluation pipeline.

        Args:
            eval_id: Evaluation ID
        """
        eval_data = self._evals.get(eval_id)
        if not eval_data:
            raise EvalError(f"Evaluation not found: {eval_id}")

        try:
            eval_data["status"] = "running"

            user_id = UUID(eval_data["user_id"])
            document_ids = [UUID(d) for d in eval_data["document_ids"]]

            # Generate questions
            questions = await self._generate_questions(
                user_id,
                document_ids,
                eval_data["question_count"],
            )

            eval_data["progress"]["total"] = len(questions)

            # Evaluate each question
            hits = 0
            reciprocal_ranks = []
            context_precisions = []
            answer_relevancies = []

            for i, question in enumerate(questions):
                eval_data["progress"]["current"] = i + 1

                # Get retrieval results
                results = await self.retrieval_service.search(
                    question["query"],
                    user_id,
                    top_k=10,
                    document_ids=document_ids,
                )

                # Calculate hit rate (is relevant doc in results?)
                relevant_doc_id = question["source_document_id"]
                result_doc_ids = [str(r.document_id) for r in results]

                if relevant_doc_id in result_doc_ids:
                    hits += 1
                    # Calculate reciprocal rank
                    rank = result_doc_ids.index(relevant_doc_id) + 1
                    reciprocal_ranks.append(1 / rank)
                else:
                    reciprocal_ranks.append(0)

                # Calculate context precision (simplified)
                if results:
                    relevant_in_top_k = sum(
                        1 for r in results[:5]
                        if str(r.document_id) == relevant_doc_id
                    )
                    context_precisions.append(relevant_in_top_k / 5)
                else:
                    context_precisions.append(0)

                # Answer relevancy would require generating answers
                # and comparing to ground truth - simplified here
                answer_relevancies.append(0.8 if relevant_doc_id in result_doc_ids else 0.2)

            # Calculate final metrics
            from datetime import datetime

            eval_data["results"] = {
                "hit_rate": hits / len(questions) if questions else 0,
                "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0,
                "context_precision": sum(context_precisions) / len(context_precisions) if context_precisions else 0,
                "answer_relevancy": sum(answer_relevancies) / len(answer_relevancies) if answer_relevancies else 0,
                "questions_generated": len(questions),
                "completed_at": datetime.utcnow().isoformat(),
            }

            eval_data["status"] = "completed"

            logger.info(
                "evaluation_completed",
                eval_id=eval_id,
                hit_rate=eval_data["results"]["hit_rate"],
                mrr=eval_data["results"]["mrr"],
            )

        except Exception as e:
            logger.error("evaluation_failed", eval_id=eval_id, error=str(e))
            eval_data["status"] = "failed"
            eval_data["error"] = str(e)

    async def _generate_questions(
        self,
        user_id: UUID,
        document_ids: list[UUID],
        count: int,
    ) -> list[dict]:
        """Generate evaluation questions from documents.

        Args:
            user_id: User UUID
            document_ids: Documents to generate questions from
            count: Number of questions

        Returns:
            List of question dicts with query and source info
        """
        questions = []

        # Get chunks from each document
        all_chunks = []
        for doc_id in document_ids:
            chunks = await self.chunk_repo.list_by_document(doc_id, limit=50)
            for chunk in chunks:
                all_chunks.append({
                    "document_id": str(doc_id),
                    "chunk_id": str(chunk.id),
                    "content": chunk.content,
                })

        if not all_chunks:
            return []

        # Sample chunks for question generation
        sample_size = min(count, len(all_chunks))
        sampled_chunks = random.sample(all_chunks, sample_size)

        # Generate questions for each sampled chunk
        for chunk in sampled_chunks:
            try:
                question = await self._generate_question_for_chunk(chunk["content"])
                if question:
                    questions.append({
                        "query": question,
                        "source_document_id": chunk["document_id"],
                        "source_chunk_id": chunk["chunk_id"],
                    })
            except Exception as e:
                logger.warning(
                    "question_generation_failed",
                    error=str(e),
                )
                continue

        return questions

    async def _generate_question_for_chunk(self, chunk_content: str) -> Optional[str]:
        """Generate a question that could be answered by this chunk.

        Args:
            chunk_content: Chunk text

        Returns:
            Generated question or None
        """
        prompt = f"""Based on the following text, generate a single question that could be answered by the information in this text.

Text:
{chunk_content[:1500]}

Generate a clear, specific question. Only output the question, nothing else."""

        try:
            response = await self.llm_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100,
            )
            return response.strip()
        except Exception:
            return None

    async def get_evaluation(self, eval_id: str) -> Optional[dict]:
        """Get evaluation status and results.

        Args:
            eval_id: Evaluation ID

        Returns:
            Evaluation dict or None
        """
        eval_data = self._evals.get(eval_id)
        if not eval_data:
            return None

        result = {
            "eval_id": UUID(eval_data["id"]),
            "status": eval_data["status"],
            "progress": eval_data["progress"],
        }

        if eval_data["results"]:
            result["results"] = eval_data["results"]

        return result
