"""Test query rewriting for follow-up questions."""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.config import Settings
from app.services.llm import LLMService

# Simulated conversation history
class MockMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


QUERY_REWRITE_PROMPT = """You are a query rewriter for a document retrieval system. Your job is to rewrite follow-up questions into standalone search queries that will retrieve relevant document chunks.

Given the conversation history and the current user query, rewrite the query to be a standalone search query that:
1. Expands any pronouns or references (e.g., "it", "that", "this") to their full meaning from context
2. Includes key terms and concepts mentioned in the conversation that are relevant to the query
3. Is optimized for semantic search (clear, specific, includes relevant keywords)
4. Does NOT include conversational phrases like "tell me more about" or "can you explain"

CONVERSATION HISTORY:
{history}

CURRENT QUERY: {query}

Return ONLY the rewritten search query, nothing else. If the query is already standalone and doesn't need rewriting, return it as-is."""


async def test_query_rewrite():
    """Test query rewriting with the DDP3 example."""
    settings = Settings()
    llm_service = LLMService(settings)

    # Test case 1: DDP3 follow-up
    history = [
        MockMessage("user", "Can you outline the Dataset Design Practices in the Co-ML paper?"),
        MockMessage("assistant", """Sure, the Co-ML paper outlines the following Dataset Design Practices (DDPs):

1. **DDP1 - Incorporating dataset diversity:** This involves ensuring the data is representative and considers the diverse characteristics of a label and the variety of use cases where a model might be used.

2. **DDP2 - Evaluating model performance and its relationship to data:** This practice involves understanding how well a model is performing, identifying gaps or confounding factors in data that might affect model performance, and assessing whether a model has improved after dataset revisions and model retraining.

3. **DDP3 - Balancing datasets:** This involves designing datasets that have roughly equal distribution of samples across labels and ensuring model performance is consistent across labels.

4. **DDP4 - Inspecting for data quality:** This practice is about checking that data is properly labeled and of sufficient quality. An example would be ensuring that image data is not blurry."""),
    ]

    query = "Can you tell me more about DDP3?"

    # Format history
    history_parts = []
    for msg in history[-6:]:
        role = "User" if msg.role == "user" else "Assistant"
        content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        history_parts.append(f"{role}: {content}")
    history_text = "\n".join(history_parts)

    print("=" * 60)
    print("TEST CASE 1: DDP3 Follow-up")
    print("=" * 60)
    print(f"\nOriginal query: {query}")
    print(f"\nConversation history:")
    for msg in history:
        print(f"  {msg.role}: {msg.content[:100]}...")

    messages = [
        {
            "role": "user",
            "content": QUERY_REWRITE_PROMPT.format(history=history_text, query=query),
        }
    ]

    rewritten = await llm_service.chat_completion(messages, max_tokens=200, temperature=0.0)
    rewritten = rewritten.strip()

    print(f"\nRewritten query: {rewritten}")

    # Test case 2: Another follow-up
    print("\n" + "=" * 60)
    print("TEST CASE 2: Pronoun reference")
    print("=" * 60)

    history2 = [
        MockMessage("user", "What are the main findings about the transformer architecture?"),
        MockMessage("assistant", "The transformer architecture introduced attention mechanisms that allow the model to weigh the importance of different parts of the input sequence..."),
    ]
    query2 = "How does it handle long sequences?"

    history_parts2 = []
    for msg in history2[-6:]:
        role = "User" if msg.role == "user" else "Assistant"
        content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        history_parts2.append(f"{role}: {content}")
    history_text2 = "\n".join(history_parts2)

    print(f"\nOriginal query: {query2}")

    messages2 = [
        {
            "role": "user",
            "content": QUERY_REWRITE_PROMPT.format(history=history_text2, query=query2),
        }
    ]

    rewritten2 = await llm_service.chat_completion(messages2, max_tokens=200, temperature=0.0)
    rewritten2 = rewritten2.strip()

    print(f"Rewritten query: {rewritten2}")

    # Test case 3: Standalone query (shouldn't change much)
    print("\n" + "=" * 60)
    print("TEST CASE 3: Standalone query (no rewrite needed)")
    print("=" * 60)

    query3 = "What is the definition of machine learning?"
    history3 = []

    print(f"\nOriginal query: {query3}")

    messages3 = [
        {
            "role": "user",
            "content": QUERY_REWRITE_PROMPT.format(history="(no history)", query=query3),
        }
    ]

    rewritten3 = await llm_service.chat_completion(messages3, max_tokens=200, temperature=0.0)
    rewritten3 = rewritten3.strip()

    print(f"Rewritten query: {rewritten3}")

    await llm_service.close()
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_query_rewrite())
