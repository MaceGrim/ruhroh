"""Compare retrieval results with original vs rewritten queries."""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import Settings
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService
from app.db.repositories.document import DocumentRepository


async def test_retrieval_comparison():
    """Compare retrieval with original vs rewritten queries."""
    settings = Settings()

    # Create database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        llm_service = LLMService(settings)
        retrieval_service = RetrievalService(settings, session, llm_service)
        doc_repo = DocumentRepository(session)

        # Get all users with documents
        from sqlalchemy import text
        result = await session.execute(text("SELECT DISTINCT user_id FROM documents WHERE status = 'ready'"))
        users = result.fetchall()

        if not users:
            print("No documents found in the database. Please upload a document first.")
            await llm_service.close()
            return

        user_id = users[0][0]
        # Convert to UUID if it's a string
        if isinstance(user_id, str):
            user_id = user_id
        print(f"Using user_id: {user_id}")

        # Get documents for this user
        docs = await doc_repo.list_by_user(user_id)
        print(f"\nDocuments for this user:")
        for doc in docs:
            print(f"  - {doc.filename} (id: {doc.id})")

        # Test queries
        original_query = "Can you tell me more about DDP3?"
        rewritten_query = "Dataset Design Practices DDP3 Balancing datasets Co-ML paper"

        print("\n" + "=" * 70)
        print("ORIGINAL QUERY RETRIEVAL")
        print("=" * 70)
        print(f"Query: {original_query}\n")

        results1 = await retrieval_service.search(
            original_query, user_id, top_k=5
        )

        if not results1:
            print("  No results found")
        else:
            for i, result in enumerate(results1, 1):
                pages = f" (pages {result.page_numbers})" if result.page_numbers else ""
                print(f"[{i}] Score: {result.score:.4f} | {result.document_name}{pages}")
                # Show snippet
                snippet = result.content[:200].replace('\n', ' ')
                print(f"    Snippet: {snippet}...")
                print()

        print("\n" + "=" * 70)
        print("REWRITTEN QUERY RETRIEVAL")
        print("=" * 70)
        print(f"Query: {rewritten_query}\n")

        results2 = await retrieval_service.search(
            rewritten_query, user_id, top_k=5
        )

        if not results2:
            print("  No results found")
        else:
            for i, result in enumerate(results2, 1):
                pages = f" (pages {result.page_numbers})" if result.page_numbers else ""
                print(f"[{i}] Score: {result.score:.4f} | {result.document_name}{pages}")
                # Show snippet
                snippet = result.content[:200].replace('\n', ' ')
                print(f"    Snippet: {snippet}...")
                print()

        # Also test just "DDP3" to see what keyword search finds
        print("\n" + "=" * 70)
        print("KEYWORD-ONLY SEARCH: 'DDP3'")
        print("=" * 70)

        results3 = await retrieval_service.search(
            "DDP3", user_id, top_k=5, use_vector=False, use_keyword=True
        )

        if not results3:
            print("  No results found with keyword search for 'DDP3'")
        else:
            for i, result in enumerate(results3, 1):
                pages = f" (pages {result.page_numbers})" if result.page_numbers else ""
                print(f"[{i}] Score: {result.score:.4f} | {result.document_name}{pages}")
                snippet = result.content[:200].replace('\n', ' ')
                print(f"    Snippet: {snippet}...")
                print()

        # Vector-only search with original query
        print("\n" + "=" * 70)
        print("VECTOR-ONLY SEARCH: Original query")
        print("=" * 70)

        results4 = await retrieval_service.search(
            original_query, user_id, top_k=5, use_vector=True, use_keyword=False
        )

        if not results4:
            print("  No results found")
        else:
            for i, result in enumerate(results4, 1):
                pages = f" (pages {result.page_numbers})" if result.page_numbers else ""
                print(f"[{i}] Score: {result.score:.4f} | {result.document_name}{pages}")
                snippet = result.content[:200].replace('\n', ' ')
                print(f"    Snippet: {snippet}...")
                print()

        await llm_service.close()

    await engine.dispose()
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_retrieval_comparison())
