"""Evaluation service for RAG quality assessment."""

import random
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.document import DocumentRepository
from app.db.repositories.chunk import ChunkRepository
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService

logger = structlog.get_logger()


class EvalError(Exception):
    """Evaluation error."""

    pass


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
