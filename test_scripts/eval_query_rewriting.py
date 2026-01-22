"""
Auto-evaluation framework for query rewriting.

Tests query rewriting quality by:
1. Comparing retrieval results with/without rewriting
2. Checking if expected content is retrieved
3. Measuring retrieval quality metrics
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import Settings
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService
from app.services.chat import ChatService


@dataclass
class TestCase:
    """A test case for evaluation."""
    name: str
    conversation_history: list[tuple[str, str]]  # [(role, content), ...]
    query: str
    expected_pages: Optional[list[int]] = None  # Pages that should be in top results
    expected_keywords: Optional[list[str]] = None  # Keywords that should appear in results


@dataclass
class EvalResult:
    """Result of evaluating a test case."""
    test_name: str
    original_query: str
    rewritten_query: str
    original_pages: list[int]
    rewritten_pages: list[int]
    expected_pages_found_original: bool
    expected_pages_found_rewritten: bool
    keywords_found_original: int
    keywords_found_rewritten: int
    improvement: str  # "better", "same", "worse"


# Test cases for Co-ML paper
TEST_CASES = [
    TestCase(
        name="DDP3 Follow-up",
        conversation_history=[
            ("user", "Can you outline the Dataset Design Practices in the Co-ML paper?"),
            ("assistant", """The Co-ML paper outlines the following Dataset Design Practices (DDPs):
1. DDP1 - Incorporating dataset diversity: ensuring data is representative
2. DDP2 - Evaluating model performance: understanding model performance and data relationship
3. DDP3 - Balancing datasets: equal distribution of samples across labels
4. DDP4 - Inspecting for data quality: checking data is properly labeled"""),
        ],
        query="Can you tell me more about DDP3?",
        expected_pages=[27, 28],  # Detailed DDP3 section
        expected_keywords=["balancing", "distribution", "labels"],
    ),
    TestCase(
        name="Pronoun Resolution - 'it'",
        conversation_history=[
            ("user", "What evaluation method did the Co-ML study use?"),
            ("assistant", "The study used a mixed-methods approach over a 2-week ML Summer Camp with 22 middle school students."),
        ],
        query="How long did it last?",
        expected_pages=[15, 16],  # Study details
        expected_keywords=["weeks", "summer", "camp", "duration"],
    ),
    TestCase(
        name="Reference to Previous Content",
        conversation_history=[
            ("user", "What were the main findings about collaboration in Co-ML?"),
            ("assistant", "Collaboration played a key role in data design practices, helping participants identify issues and coordinate solutions."),
        ],
        query="Can you give specific examples?",
        expected_pages=[31, 32],  # Collaboration examples
        expected_keywords=["collaboration", "team", "together"],
    ),
    TestCase(
        name="Acronym Expansion",
        conversation_history=[
            ("user", "What is TensorFlow.js mentioned for in the paper?"),
            ("assistant", "TensorFlow.js is used for ML model training in the Co-ML mobile app."),
        ],
        query="How does TF.js handle the training?",
        expected_keywords=["tensorflow", "training", "model"],
    ),
    TestCase(
        name="Context Carryover",
        conversation_history=[
            ("user", "What tools does Co-ML provide for data collection?"),
            ("assistant", "Co-ML provides camera-based image capture and a shared dataset synchronized across tablets."),
            ("user", "How do users add images?"),
            ("assistant", "Users select a label and use the tablet camera to capture images."),
        ],
        query="What about deleting them?",
        expected_keywords=["delete", "remove", "image"],
    ),
]


class MockMessage:
    """Mock message for testing."""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


async def get_pages_from_results(results) -> list[int]:
    """Extract all page numbers from retrieval results."""
    pages = []
    for r in results:
        if r.page_numbers:
            pages.extend(r.page_numbers)
    return sorted(set(pages))


async def count_keywords_in_results(results, keywords: list[str]) -> int:
    """Count how many keywords appear in result content."""
    if not keywords:
        return 0
    combined_content = " ".join(r.content.lower() for r in results)
    return sum(1 for kw in keywords if kw.lower() in combined_content)


async def evaluate_test_case(
    test_case: TestCase,
    retrieval_service: RetrievalService,
    llm_service: LLMService,
    user_id: UUID,
) -> EvalResult:
    """Evaluate a single test case."""
    # Build mock conversation history
    history = [
        MockMessage(role, content)
        for role, content in test_case.conversation_history
    ]

    # Get rewritten query using the chat service's method
    from app.services.chat import QUERY_REWRITE_PROMPT

    history_parts = []
    for msg in history[-6:]:
        role = "User" if msg.role == "user" else "Assistant"
        content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        history_parts.append(f"{role}: {content}")
    history_text = "\n".join(history_parts)

    messages = [
        {
            "role": "user",
            "content": QUERY_REWRITE_PROMPT.format(history=history_text, query=test_case.query),
        }
    ]
    rewritten_query = await llm_service.chat_completion(messages, max_tokens=200, temperature=0.0)
    rewritten_query = rewritten_query.strip()

    # Get retrieval results for original query
    original_results = await retrieval_service.search(test_case.query, user_id, top_k=5)
    original_pages = await get_pages_from_results(original_results)

    # Get retrieval results for rewritten query
    rewritten_results = await retrieval_service.search(rewritten_query, user_id, top_k=5)
    rewritten_pages = await get_pages_from_results(rewritten_results)

    # Check expected pages
    expected_pages_found_original = False
    expected_pages_found_rewritten = False
    if test_case.expected_pages:
        expected_pages_found_original = any(p in original_pages for p in test_case.expected_pages)
        expected_pages_found_rewritten = any(p in rewritten_pages for p in test_case.expected_pages)

    # Count keywords
    keywords_found_original = await count_keywords_in_results(
        original_results, test_case.expected_keywords or []
    )
    keywords_found_rewritten = await count_keywords_in_results(
        rewritten_results, test_case.expected_keywords or []
    )

    # Determine improvement
    improvement = "same"
    if test_case.expected_pages:
        if expected_pages_found_rewritten and not expected_pages_found_original:
            improvement = "better"
        elif expected_pages_found_original and not expected_pages_found_rewritten:
            improvement = "worse"
    elif test_case.expected_keywords:
        if keywords_found_rewritten > keywords_found_original:
            improvement = "better"
        elif keywords_found_rewritten < keywords_found_original:
            improvement = "worse"

    return EvalResult(
        test_name=test_case.name,
        original_query=test_case.query,
        rewritten_query=rewritten_query,
        original_pages=original_pages,
        rewritten_pages=rewritten_pages,
        expected_pages_found_original=expected_pages_found_original,
        expected_pages_found_rewritten=expected_pages_found_rewritten,
        keywords_found_original=keywords_found_original,
        keywords_found_rewritten=keywords_found_rewritten,
        improvement=improvement,
    )


async def run_evaluation():
    """Run the full evaluation suite."""
    settings = Settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        llm_service = LLMService(settings)
        retrieval_service = RetrievalService(settings, session, llm_service)

        # Get user_id
        from sqlalchemy import text
        result = await session.execute(text("SELECT DISTINCT user_id FROM documents WHERE status = 'ready'"))
        users = result.fetchall()

        if not users:
            print("No documents found in the database.")
            await llm_service.close()
            return

        user_id = users[0][0]

        print("=" * 80)
        print("QUERY REWRITING EVALUATION")
        print(f"Date: {datetime.now().isoformat()}")
        print("=" * 80)

        results = []
        for test_case in TEST_CASES:
            print(f"\nEvaluating: {test_case.name}...")
            result = await evaluate_test_case(test_case, retrieval_service, llm_service, user_id)
            results.append(result)

        # Print summary
        print("\n" + "=" * 80)
        print("EVALUATION RESULTS")
        print("=" * 80)

        better_count = sum(1 for r in results if r.improvement == "better")
        same_count = sum(1 for r in results if r.improvement == "same")
        worse_count = sum(1 for r in results if r.improvement == "worse")

        print(f"\nSummary: {better_count} better, {same_count} same, {worse_count} worse")
        print(f"Success rate: {(better_count + same_count) / len(results) * 100:.1f}%")

        print("\n" + "-" * 80)
        for r in results:
            status = "✅" if r.improvement == "better" else ("⚠️" if r.improvement == "same" else "❌")
            print(f"\n{status} {r.test_name}")
            print(f"   Original:  \"{r.original_query}\"")
            print(f"   Rewritten: \"{r.rewritten_query}\"")
            print(f"   Pages - Original: {r.original_pages[:5]}, Rewritten: {r.rewritten_pages[:5]}")
            if r.expected_pages_found_original or r.expected_pages_found_rewritten:
                print(f"   Expected pages found: Original={r.expected_pages_found_original}, Rewritten={r.expected_pages_found_rewritten}")
            if r.keywords_found_original or r.keywords_found_rewritten:
                print(f"   Keywords found: Original={r.keywords_found_original}, Rewritten={r.keywords_found_rewritten}")
            print(f"   Result: {r.improvement.upper()}")

        # Save results to JSON
        results_json = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "better": better_count,
                "same": same_count,
                "worse": worse_count,
                "total": len(results),
            },
            "results": [
                {
                    "test_name": r.test_name,
                    "original_query": r.original_query,
                    "rewritten_query": r.rewritten_query,
                    "original_pages": r.original_pages,
                    "rewritten_pages": r.rewritten_pages,
                    "expected_pages_found_original": r.expected_pages_found_original,
                    "expected_pages_found_rewritten": r.expected_pages_found_rewritten,
                    "keywords_found_original": r.keywords_found_original,
                    "keywords_found_rewritten": r.keywords_found_rewritten,
                    "improvement": r.improvement,
                }
                for r in results
            ],
        }

        output_file = os.path.join(os.path.dirname(__file__), "eval_results.json")
        with open(output_file, "w") as f:
            json.dump(results_json, f, indent=2)
        print(f"\n\nResults saved to: {output_file}")

        await llm_service.close()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_evaluation())
