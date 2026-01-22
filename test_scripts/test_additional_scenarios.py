"""Test additional query rewriting scenarios."""

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


async def test_scenario(chat_service, user_id, scenario_name, messages):
    """Run a test scenario with multiple messages."""
    print(f"\n{'=' * 70}")
    print(f"SCENARIO: {scenario_name}")
    print("=" * 70)

    # Create a thread
    thread = await chat_service.create_thread(user_id, f"Test: {scenario_name}")
    thread_id = UUID(thread["id"])

    for i, msg in enumerate(messages, 1):
        print(f"\n--- Message {i} ---")
        print(f"User: {msg}")

        response = ""
        citations = []
        async for event in chat_service.send_message_stream(thread_id, user_id, msg):
            if event["event"] == "token":
                response += event["data"]["content"]
            elif event["event"] == "citation":
                citations.append(event["data"])
            elif event["event"] == "done":
                break

        print(f"\nAssistant: {response[:600]}{'...' if len(response) > 600 else ''}")
        if citations:
            cite_strs = [f"[{c['index']}] pages {c['pages']}" for c in citations]
            print(f"\nCitations: {cite_strs}")

    # Clean up
    await chat_service.delete_thread(thread_id, user_id)
    return True


async def main():
    """Run multiple test scenarios."""
    settings = Settings()

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        llm_service = LLMService(settings)
        retrieval_service = RetrievalService(settings, session, llm_service)
        chat_service = ChatService(settings, session, llm_service, retrieval_service)

        from sqlalchemy import text
        result = await session.execute(text("SELECT DISTINCT user_id FROM documents WHERE status = 'ready'"))
        users = result.fetchall()

        if not users:
            print("No documents found.")
            await llm_service.close()
            return

        user_id = users[0][0]

        # Scenario 1: Pronoun resolution - "it"
        await test_scenario(
            chat_service, user_id,
            "Pronoun Resolution ('it')",
            [
                "What is the main evaluation method described in the Co-ML paper?",
                "How long did it last?"  # "it" refers to the evaluation
            ]
        )
        await session.commit()

        # Scenario 2: Multiple follow-ups on same topic
        await test_scenario(
            chat_service, user_id,
            "Multiple Follow-ups",
            [
                "What tools does Co-ML provide for data collection?",
                "How do users add images?",
                "What about deleting them?"
            ]
        )
        await session.commit()

        # Scenario 3: Reference to previous answer
        await test_scenario(
            chat_service, user_id,
            "Reference to Previous Answer",
            [
                "What are the key findings from the participant study?",
                "You mentioned collaboration - what role did it play specifically?"
            ]
        )
        await session.commit()

        await llm_service.close()

    await engine.dispose()
    print(f"\n{'=' * 70}")
    print("ALL SCENARIOS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
