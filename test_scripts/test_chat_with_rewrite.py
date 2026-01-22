"""Test the full chat flow with query rewriting."""

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
from app.services.chat import ChatService
from app.db.repositories.thread import ThreadRepository


async def test_chat_with_rewrite():
    """Test the full chat service with query rewriting."""
    settings = Settings()

    # Create database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        llm_service = LLMService(settings)
        retrieval_service = RetrievalService(settings, session, llm_service)
        chat_service = ChatService(settings, session, llm_service, retrieval_service)

        # Get user_id
        from sqlalchemy import text
        result = await session.execute(text("SELECT DISTINCT user_id FROM documents WHERE status = 'ready'"))
        users = result.fetchall()

        if not users:
            print("No documents found in the database.")
            await llm_service.close()
            return

        user_id = users[0][0]
        print(f"Using user_id: {user_id}")

        # Create a new thread
        thread = await chat_service.create_thread(user_id, "Test DDP3 Follow-up")
        thread_id = UUID(thread["id"])
        print(f"Created thread: {thread_id}")

        # First message - ask about DDPs
        print("\n" + "=" * 70)
        print("MESSAGE 1: Ask about DDPs")
        print("=" * 70)
        message1 = "Can you outline the Dataset Design Practices in the Co-ML paper?"
        print(f"User: {message1}\n")

        response1 = ""
        async for event in chat_service.send_message_stream(thread_id, user_id, message1):
            if event["event"] == "token":
                response1 += event["data"]["content"]
            elif event["event"] == "done":
                break

        print(f"Assistant: {response1[:500]}...")
        await session.commit()

        # Second message - follow-up about DDP3
        print("\n" + "=" * 70)
        print("MESSAGE 2: Follow-up about DDP3 (with query rewriting)")
        print("=" * 70)
        message2 = "Can you tell me more about DDP3?"
        print(f"User: {message2}\n")

        response2 = ""
        citations2 = []
        async for event in chat_service.send_message_stream(thread_id, user_id, message2):
            if event["event"] == "token":
                response2 += event["data"]["content"]
            elif event["event"] == "citation":
                citations2.append(event["data"])
            elif event["event"] == "done":
                break

        print(f"Assistant: {response2}")

        if citations2:
            print("\nCitations:")
            for cite in citations2:
                print(f"  [{cite['index']}] {cite['document_name']} - pages {cite['pages']}")

        await session.commit()

        # Clean up - delete the test thread
        await chat_service.delete_thread(thread_id, user_id)
        await session.commit()

        await llm_service.close()

    await engine.dispose()
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_chat_with_rewrite())
