#!/bin/bash
# Stop all ruhroh services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🛑 Stopping ruhroh services..."
docker-compose down

echo "✅ All services stopped"
