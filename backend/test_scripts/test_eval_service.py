#!/usr/bin/env python3
"""Test script for the RAG evaluation system.

This script tests the evaluation service and routes by making API calls
to the running backend server.

Usage:
    # Make sure the backend is running first
    cd /mnt/o/Ode/Github/ruhroh/backend
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    # Then run this test script
    python test_scripts/test_eval_service.py
"""

import asyncio
import json
import sys
import httpx
from typing import Optional
from uuid import UUID


# Configuration
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Dev mode token (when DEV_MODE=true, any token works)
DEV_TOKEN = "dev-token"


class EvalTester:
    """Test client for the evaluation API."""

    def __init__(self, base_url: str = API_V1, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token or DEV_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def test_single_evaluation(self) -> dict:
        """Test single evaluation endpoint."""
        print("\n" + "="*60)
        print("Testing: POST /api/v1/eval/single")
        print("="*60)

        payload = {
            "question": "What is the main purpose of this document?",
            "expected_answer": None,  # Optional
            "top_k": 3,
        }

        print(f"Request payload: {json.dumps(payload, indent=2)}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/eval/single",
                json=payload,
                headers=self.headers,
            )

            print(f"\nStatus: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Eval ID: {result.get('eval_id')}")
                print(f"Question: {result.get('question')}")
                print(f"Generated Answer: {result.get('generated_answer', '')[:200]}...")
                print(f"Model Used: {result.get('model_used')}")
                print(f"Latency: {result.get('latency_ms', 0):.2f}ms")

                metrics = result.get("metrics", {})
                print("\nMetrics:")
                print(f"  Faithfulness: {metrics.get('faithfulness', 0):.3f}")
                print(f"  Answer Relevancy: {metrics.get('answer_relevancy', 0):.3f}")
                print(f"  Context Precision: {metrics.get('context_precision', 0):.3f}")

                contexts = result.get("retrieved_contexts", [])
                print(f"\nRetrieved Contexts: {len(contexts)}")
                for i, ctx in enumerate(contexts[:2]):
                    print(f"  [{i+1}] {ctx.get('document_name', 'Unknown')} (score: {ctx.get('score', 0):.3f})")

                return result
            else:
                print(f"Error: {response.text}")
                return {}

    async def test_single_evaluation_with_expected(self) -> dict:
        """Test single evaluation with expected answer."""
        print("\n" + "="*60)
        print("Testing: POST /api/v1/eval/single (with expected answer)")
        print("="*60)

        payload = {
            "question": "What features does the system provide?",
            "expected_answer": "The system provides document management, RAG-based chat, and search functionality.",
            "top_k": 5,
        }

        print(f"Request payload: {json.dumps(payload, indent=2)}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/eval/single",
                json=payload,
                headers=self.headers,
            )

            print(f"\nStatus: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Eval ID: {result.get('eval_id')}")

                metrics = result.get("metrics", {})
                print("\nMetrics (with expected answer):")
                print(f"  Faithfulness: {metrics.get('faithfulness', 0):.3f}")
                print(f"  Answer Relevancy: {metrics.get('answer_relevancy', 0):.3f}")
                print(f"  Context Precision: {metrics.get('context_precision', 0):.3f}")
                print(f"  Context Recall: {metrics.get('context_recall')}")
                print(f"  Answer Correctness: {metrics.get('answer_correctness')}")

                return result
            else:
                print(f"Error: {response.text}")
                return {}

    async def test_batch_evaluation(self) -> str:
        """Test batch evaluation endpoint."""
        print("\n" + "="*60)
        print("Testing: POST /api/v1/eval/batch")
        print("="*60)

        payload = {
            "name": "Test Batch Evaluation",
            "test_cases": [
                {"question": "What is the main topic of this document?"},
                {"question": "How does the system handle authentication?"},
                {
                    "question": "What database is used?",
                    "expected_answer": "PostgreSQL is used as the primary database."
                },
            ],
            "top_k": 3,
        }

        print(f"Request payload: {json.dumps(payload, indent=2)}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/eval/batch",
                json=payload,
                headers=self.headers,
            )

            print(f"\nStatus: {response.status_code}")

            if response.status_code == 202:
                result = response.json()
                eval_id = result.get("eval_id")
                print(f"Eval ID: {eval_id}")
                print(f"Status: {result.get('status')}")
                print(f"Total Cases: {result.get('total_cases')}")
                return eval_id
            else:
                print(f"Error: {response.text}")
                return ""

    async def test_get_batch_status(self, eval_id: str) -> dict:
        """Test getting batch evaluation status."""
        print("\n" + "="*60)
        print(f"Testing: GET /api/v1/eval/batch/{eval_id}")
        print("="*60)

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Poll until completed or failed
            for attempt in range(30):  # Max 30 attempts
                response = await client.get(
                    f"{self.base_url}/eval/batch/{eval_id}",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status")
                    progress = result.get("progress", {})

                    print(f"Attempt {attempt + 1}: Status={status}, Progress={progress.get('current', 0)}/{progress.get('total', 0)}")

                    if status in ["completed", "failed"]:
                        print(f"\nFinal Status: {status}")

                        if status == "completed":
                            summary = result.get("summary", {})
                            print("\nSummary:")
                            print(f"  Total Cases: {summary.get('total_cases', 0)}")
                            print(f"  Successful: {summary.get('successful_cases', 0)}")
                            print(f"  Failed: {summary.get('failed_cases', 0)}")
                            print(f"  Avg Faithfulness: {summary.get('avg_faithfulness', 0):.3f}")
                            print(f"  Avg Answer Relevancy: {summary.get('avg_answer_relevancy', 0):.3f}")
                            print(f"  Avg Context Precision: {summary.get('avg_context_precision', 0):.3f}")
                            print(f"  Avg Latency: {summary.get('avg_latency_ms', 0):.2f}ms")
                            print(f"  Total Duration: {summary.get('total_duration_seconds', 0):.2f}s")
                        else:
                            print(f"Error: {result.get('error')}")

                        return result
                else:
                    print(f"Error: {response.text}")
                    return {}

                await asyncio.sleep(2)  # Wait 2 seconds between polls

            print("Timeout waiting for batch evaluation to complete")
            return {}

    async def test_list_results(self) -> dict:
        """Test listing evaluation results."""
        print("\n" + "="*60)
        print("Testing: GET /api/v1/eval/results")
        print("="*60)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/eval/results",
                params={"limit": 10, "offset": 0},
                headers=self.headers,
            )

            print(f"\nStatus: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Total: {result.get('total', 0)}")
                print(f"Evaluations:")

                for eval_item in result.get("evaluations", []):
                    print(f"\n  [{eval_item.get('eval_type')}] {eval_item.get('eval_id')}")
                    print(f"    Name: {eval_item.get('name', 'N/A')}")
                    print(f"    Status: {eval_item.get('status')}")
                    print(f"    Created: {eval_item.get('created_at')}")
                    if eval_item.get("summary_metrics"):
                        print(f"    Metrics: {eval_item.get('summary_metrics')}")

                return result
            else:
                print(f"Error: {response.text}")
                return {}

    async def test_get_result_by_id(self, eval_id: str) -> dict:
        """Test getting a specific evaluation result."""
        print("\n" + "="*60)
        print(f"Testing: GET /api/v1/eval/results/{eval_id}")
        print("="*60)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/eval/results/{eval_id}",
                headers=self.headers,
            )

            print(f"\nStatus: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Result: {json.dumps(result, indent=2, default=str)[:1000]}...")
                return result
            else:
                print(f"Error: {response.text}")
                return {}

    async def test_health(self) -> bool:
        """Test if the server is running."""
        print("\n" + "="*60)
        print("Testing: GET /health")
        print("="*60)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{BASE_URL}/health")
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"Response: {response.json()}")
                    return True
                return False
            except Exception as e:
                print(f"Error connecting to server: {e}")
                return False


async def main():
    """Run all tests."""
    print("="*60)
    print("RAG Evaluation System Test Suite")
    print("="*60)

    tester = EvalTester()

    # Check if server is running
    if not await tester.test_health():
        print("\nERROR: Server is not running!")
        print("Please start the backend server first:")
        print("  cd /mnt/o/Ode/Github/ruhroh/backend")
        print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)

    # Run tests
    try:
        # Test 1: Single evaluation
        single_result = await tester.test_single_evaluation()
        single_eval_id = str(single_result.get("eval_id", ""))

        # Test 2: Single evaluation with expected answer
        await tester.test_single_evaluation_with_expected()

        # Test 3: Batch evaluation
        batch_eval_id = await tester.test_batch_evaluation()

        # Test 4: Get batch status (with polling)
        if batch_eval_id:
            await tester.test_get_batch_status(batch_eval_id)

        # Test 5: List all results
        await tester.test_list_results()

        # Test 6: Get specific result
        if single_eval_id:
            await tester.test_get_result_by_id(single_eval_id)

        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
