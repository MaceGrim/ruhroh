#!/usr/bin/env python3
"""
Test script to verify conversation context is preserved across messages.

This tests the fix for the bug where the LLM wasn't receiving previous
conversation history when users asked follow-up questions.
"""

import asyncio
import httpx
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

async def test_conversation_context():
    """Test that conversation context is preserved."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        print("=" * 60)
        print("Testing Conversation Context Preservation")
        print("=" * 60)

        # 1. Create a new thread
        print("\n1. Creating new thread...")
        response = await client.post(f"{BASE_URL}/chat/threads", json={})
        if response.status_code not in (200, 201):
            print(f"   FAILED: Could not create thread (status {response.status_code}): {response.text}")
            return False

        thread = response.json()
        thread_id = thread["id"]
        print(f"   SUCCESS: Created thread: {thread_id}")

        # 2. Send first message: A question that the LLM will answer
        print("\n2. Sending first message: 'Remember the number 42 for later'...")
        response = await client.post(
            f"{BASE_URL}/chat/threads/{thread_id}/messages",
            json={"content": "Please remember the number 42. I will ask you about it later."},
            headers={"Accept": "text/event-stream"}
        )

        if response.status_code != 200:
            print(f"   FAILED: Could not send message: {response.text}")
            return False

        # Read SSE stream
        first_response = ""
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "content" in data and "message_id" not in data:
                    first_response += data["content"]
                elif "message_id" in data:
                    if "content" in data:
                        first_response = data["content"]
                    break

        print(f"   LLM Response: {first_response[:100]}...")

        # 3. Send follow-up: Ask about the remembered number
        print("\n3. Sending follow-up: 'What number did I ask you to remember?'...")
        response = await client.post(
            f"{BASE_URL}/chat/threads/{thread_id}/messages",
            json={"content": "What number did I ask you to remember?"},
            headers={"Accept": "text/event-stream"}
        )

        if response.status_code != 200:
            print(f"   FAILED: Could not send message: {response.text}")
            return False

        # Read SSE stream
        second_response = ""
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "content" in data and "message_id" not in data:
                    second_response += data["content"]
                elif "message_id" in data:
                    if "content" in data:
                        second_response = data["content"]
                    break

        print(f"   LLM Response: {second_response}")

        # 4. Check if the response mentions "42"
        print("\n4. Checking if LLM remembered the context...")

        # The LLM should reference "42" in its response
        if "42" in second_response:
            print("   SUCCESS: LLM correctly remembered '42' from conversation history")
            success = True
        else:
            print("   FAILED: LLM did not reference '42' in response")
            print(f"   Full response: {second_response}")
            success = False

        # 5. Verify thread has all messages
        print("\n5. Verifying thread contains all messages...")
        response = await client.get(f"{BASE_URL}/chat/threads/{thread_id}")
        thread_data = response.json()
        messages = thread_data.get("messages", [])

        print(f"   Thread has {len(messages)} messages")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:50]
            print(f"   [{i+1}] {role}: {content}...")

        if len(messages) >= 4:  # 2 user + 2 assistant
            print("   SUCCESS: All messages saved to thread")
        else:
            print("   WARNING: Expected at least 4 messages")

        # Cleanup - delete the test thread
        print("\n6. Cleaning up test thread...")
        await client.delete(f"{BASE_URL}/chat/threads/{thread_id}")
        print("   Deleted test thread")

        print("\n" + "=" * 60)
        if success:
            print("TEST PASSED: Conversation context is preserved!")
        else:
            print("TEST FAILED: Conversation context is NOT preserved")
        print("=" * 60)

        return success


if __name__ == "__main__":
    result = asyncio.run(test_conversation_context())
    sys.exit(0 if result else 1)
