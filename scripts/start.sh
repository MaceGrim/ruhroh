#!/bin/bash
# Production startup script for ruhroh using Docker Compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check for .env file
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "   Copy .env.example to .env and configure your settings"
    exit 1
fi

# Check for required environment variables
source .env
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY is not set in .env"
    exit 1
fi

echo "🐳 Building and starting services..."
docker-compose build
docker-compose up -d

echo ""
echo "✅ ruhroh is starting up!"
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📊 View logs with: docker-compose logs -f"
echo "🛑 Stop with:      docker-compose down"
