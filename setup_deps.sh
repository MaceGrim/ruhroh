#!/bin/bash
# Setup dependencies between tasks

echo "Setting up task dependencies..."

# Get task IDs by searching titles
get_id() {
  bd search "$1" --json 2>/dev/null | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"//;s/"//'
}

# INFRASTRUCTURE DEPENDENCIES
# Backend and Frontend structure are independent P0 tasks
# Docker Compose depends on both project structures
BACKEND_INIT=$(get_id "Initialize Backend Project Structure")
FRONTEND_INIT=$(get_id "Initialize Frontend Project Structure")
DOCKER_COMPOSE=$(get_id "Create Docker Compose Configuration")
ALEMBIC=$(get_id "Setup Alembic Migrations")

bd dep add $DOCKER_COMPOSE $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $DOCKER_COMPOSE $FRONTEND_INIT --type blocks 2>/dev/null
bd dep add $ALEMBIC $BACKEND_INIT --type blocks 2>/dev/null

# DATABASE LAYER DEPENDENCIES
DB_MODELS=$(get_id "Create SQLAlchemy Database Models")
DB_CONN=$(get_id "Create Database Connection Pool")
MIGRATION=$(get_id "Create Initial Migration")
USER_REPO=$(get_id "Create User Repository")
DOC_REPO=$(get_id "Create Document Repository")
CHUNK_REPO=$(get_id "Create Chunk Repository")
THREAD_REPO=$(get_id "Create Thread Repository")
MSG_REPO=$(get_id "Create Message Repository")
SCHEMA_REPO=$(get_id "Create Schema Repository")
AUDIT_REPO=$(get_id "Create AuditLog Repository")

bd dep add $DB_MODELS $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $DB_CONN $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $MIGRATION $DB_MODELS --type blocks 2>/dev/null
bd dep add $MIGRATION $ALEMBIC --type blocks 2>/dev/null

# All repos depend on DB models
bd dep add $USER_REPO $DB_MODELS --type blocks 2>/dev/null
bd dep add $DOC_REPO $DB_MODELS --type blocks 2>/dev/null
bd dep add $CHUNK_REPO $DB_MODELS --type blocks 2>/dev/null
bd dep add $THREAD_REPO $DB_MODELS --type blocks 2>/dev/null
bd dep add $MSG_REPO $DB_MODELS --type blocks 2>/dev/null
bd dep add $SCHEMA_REPO $DB_MODELS --type blocks 2>/dev/null
bd dep add $AUDIT_REPO $DB_MODELS --type blocks 2>/dev/null

# PYDANTIC MODELS - depend on backend init
USER_PYDANTIC=$(get_id "Create User Pydantic Models")
DOC_PYDANTIC=$(get_id "Create Document Pydantic Models")
CHUNK_PYDANTIC=$(get_id "Create Chunk Pydantic Models")
THREAD_PYDANTIC=$(get_id "Create Thread/Message Pydantic Models")
SCHEMA_PYDANTIC=$(get_id "Create Schema Pydantic Models")
ERROR_PYDANTIC=$(get_id "Create Error Response Models")

bd dep add $USER_PYDANTIC $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $DOC_PYDANTIC $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $CHUNK_PYDANTIC $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $THREAD_PYDANTIC $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $SCHEMA_PYDANTIC $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $ERROR_PYDANTIC $BACKEND_INIT --type blocks 2>/dev/null

# CORE SERVICES DEPENDENCIES
CONFIG_SVC=$(get_id "Implement Config Service")
LLM_SVC=$(get_id "Implement LLM Service")
AUTH_SVC=$(get_id "Implement Auth Service")
INGESTION_SVC=$(get_id "Implement Ingestion Service")
CHUNKING_UTIL=$(get_id "Implement Chunking Utilities")
PDF_UTIL=$(get_id "Implement PDF Utilities")
OCR_SVC=$(get_id "Implement OCR Service")
EXTRACT_SVC=$(get_id "Implement Extraction Service")
QDRANT_SVC=$(get_id "Implement Qdrant Vector Store Service")
RETRIEVAL_SVC=$(get_id "Implement Retrieval Service")
CHAT_SVC=$(get_id "Implement Chat Service")
STREAMING_SVC=$(get_id "Implement Streaming Response Handler")
ADMIN_SVC=$(get_id "Implement Admin Service")
EVAL_SVC=$(get_id "Implement Eval Service")

# Config depends on backend init
bd dep add $CONFIG_SVC $BACKEND_INIT --type blocks 2>/dev/null

# LLM service depends on config
bd dep add $LLM_SVC $CONFIG_SVC --type blocks 2>/dev/null

# Auth service depends on config and user repo
bd dep add $AUTH_SVC $CONFIG_SVC --type blocks 2>/dev/null
bd dep add $AUTH_SVC $USER_REPO --type blocks 2>/dev/null

# Chunking and PDF utils depend on backend init
bd dep add $CHUNKING_UTIL $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $PDF_UTIL $BACKEND_INIT --type blocks 2>/dev/null

# OCR depends on LLM service
bd dep add $OCR_SVC $LLM_SVC --type blocks 2>/dev/null

# Extraction depends on LLM service
bd dep add $EXTRACT_SVC $LLM_SVC --type blocks 2>/dev/null

# Qdrant service depends on config
bd dep add $QDRANT_SVC $CONFIG_SVC --type blocks 2>/dev/null

# Ingestion depends on chunking, PDF, LLM, Qdrant, chunk repo
bd dep add $INGESTION_SVC $CHUNKING_UTIL --type blocks 2>/dev/null
bd dep add $INGESTION_SVC $PDF_UTIL --type blocks 2>/dev/null
bd dep add $INGESTION_SVC $LLM_SVC --type blocks 2>/dev/null
bd dep add $INGESTION_SVC $QDRANT_SVC --type blocks 2>/dev/null
bd dep add $INGESTION_SVC $CHUNK_REPO --type blocks 2>/dev/null
bd dep add $INGESTION_SVC $DOC_REPO --type blocks 2>/dev/null

# Retrieval depends on Qdrant and chunk repo
bd dep add $RETRIEVAL_SVC $QDRANT_SVC --type blocks 2>/dev/null
bd dep add $RETRIEVAL_SVC $CHUNK_REPO --type blocks 2>/dev/null

# Chat depends on retrieval and LLM
bd dep add $CHAT_SVC $RETRIEVAL_SVC --type blocks 2>/dev/null
bd dep add $CHAT_SVC $LLM_SVC --type blocks 2>/dev/null
bd dep add $CHAT_SVC $THREAD_REPO --type blocks 2>/dev/null
bd dep add $CHAT_SVC $MSG_REPO --type blocks 2>/dev/null

# Streaming depends on chat
bd dep add $STREAMING_SVC $CHAT_SVC --type blocks 2>/dev/null

# Admin depends on user and doc repos
bd dep add $ADMIN_SVC $USER_REPO --type blocks 2>/dev/null
bd dep add $ADMIN_SVC $DOC_REPO --type blocks 2>/dev/null

# Eval depends on retrieval and LLM
bd dep add $EVAL_SVC $RETRIEVAL_SVC --type blocks 2>/dev/null
bd dep add $EVAL_SVC $LLM_SVC --type blocks 2>/dev/null

# API ROUTES DEPENDENCIES
AUTH_ROUTES=$(get_id "Implement Auth Routes")
DOC_ROUTES=$(get_id "Implement Document Routes")
CHAT_ROUTES=$(get_id "Implement Chat Routes")
SEARCH_ROUTES=$(get_id "Implement Search Routes")
ADMIN_ROUTES=$(get_id "Implement Admin Routes")
CONFIG_ROUTES=$(get_id "Implement Config Routes")
EVAL_ROUTES=$(get_id "Implement Eval Routes")

bd dep add $AUTH_ROUTES $AUTH_SVC --type blocks 2>/dev/null
bd dep add $AUTH_ROUTES $USER_PYDANTIC --type blocks 2>/dev/null

bd dep add $DOC_ROUTES $INGESTION_SVC --type blocks 2>/dev/null
bd dep add $DOC_ROUTES $DOC_PYDANTIC --type blocks 2>/dev/null
bd dep add $DOC_ROUTES $AUTH_SVC --type blocks 2>/dev/null

bd dep add $CHAT_ROUTES $STREAMING_SVC --type blocks 2>/dev/null
bd dep add $CHAT_ROUTES $THREAD_PYDANTIC --type blocks 2>/dev/null
bd dep add $CHAT_ROUTES $AUTH_SVC --type blocks 2>/dev/null

bd dep add $SEARCH_ROUTES $RETRIEVAL_SVC --type blocks 2>/dev/null
bd dep add $SEARCH_ROUTES $CHUNK_PYDANTIC --type blocks 2>/dev/null
bd dep add $SEARCH_ROUTES $AUTH_SVC --type blocks 2>/dev/null

bd dep add $ADMIN_ROUTES $ADMIN_SVC --type blocks 2>/dev/null
bd dep add $ADMIN_ROUTES $AUTH_SVC --type blocks 2>/dev/null

bd dep add $CONFIG_ROUTES $SCHEMA_REPO --type blocks 2>/dev/null
bd dep add $CONFIG_ROUTES $SCHEMA_PYDANTIC --type blocks 2>/dev/null
bd dep add $CONFIG_ROUTES $AUTH_SVC --type blocks 2>/dev/null

bd dep add $EVAL_ROUTES $EVAL_SVC --type blocks 2>/dev/null
bd dep add $EVAL_ROUTES $AUTH_SVC --type blocks 2>/dev/null

# MIDDLEWARE DEPENDENCIES
RATE_LIMIT=$(get_id "Implement Rate Limiting")
REQ_ID=$(get_id "Implement Request ID Tracking")
LOGGING=$(get_id "Implement Structured Logging")
SECURITY=$(get_id "Implement Security Utilities")
ERROR_HANDLING=$(get_id "Implement Error Handling")
OPENAPI=$(get_id "Create OpenAPI Documentation")

bd dep add $RATE_LIMIT $CONFIG_SVC --type blocks 2>/dev/null
bd dep add $REQ_ID $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $LOGGING $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $SECURITY $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $ERROR_HANDLING $ERROR_PYDANTIC --type blocks 2>/dev/null
bd dep add $OPENAPI $AUTH_ROUTES --type blocks 2>/dev/null
bd dep add $OPENAPI $DOC_ROUTES --type blocks 2>/dev/null
bd dep add $OPENAPI $CHAT_ROUTES --type blocks 2>/dev/null

# FRONTEND DEPENDENCIES
STATE_MGMT=$(get_id "Setup Frontend State Management")
API_CLIENT=$(get_id "Implement Frontend API Client")
AUTH_PAGES=$(get_id "Implement Auth Pages")
LAYOUT=$(get_id "Implement Layout Components")
UPLOAD_COMP=$(get_id "Implement File Upload Component")
DOC_LIST=$(get_id "Implement Document List Component")
STATUS_POLL=$(get_id "Implement Document Status Polling")
THREAD_LIST=$(get_id "Implement Thread List Component")
CHAT_MSG=$(get_id "Implement Chat Message Components")
SSE_HANDLER=$(get_id "Implement SSE Chat Handler")
CHAT_INPUT=$(get_id "Implement Chat Input Component")
PDF_VIEWER=$(get_id "Implement PDF Viewer with Highlighting")
USER_MGMT=$(get_id "Implement User Management Page")
STATS_DASH=$(get_id "Implement Stats Dashboard")
HEALTH_DISP=$(get_id "Implement System Health Display")

bd dep add $STATE_MGMT $FRONTEND_INIT --type blocks 2>/dev/null
bd dep add $API_CLIENT $FRONTEND_INIT --type blocks 2>/dev/null
bd dep add $LAYOUT $FRONTEND_INIT --type blocks 2>/dev/null

bd dep add $AUTH_PAGES $API_CLIENT --type blocks 2>/dev/null
bd dep add $AUTH_PAGES $STATE_MGMT --type blocks 2>/dev/null

bd dep add $UPLOAD_COMP $API_CLIENT --type blocks 2>/dev/null
bd dep add $DOC_LIST $API_CLIENT --type blocks 2>/dev/null
bd dep add $STATUS_POLL $UPLOAD_COMP --type blocks 2>/dev/null

bd dep add $THREAD_LIST $API_CLIENT --type blocks 2>/dev/null
bd dep add $CHAT_MSG $FRONTEND_INIT --type blocks 2>/dev/null
bd dep add $SSE_HANDLER $API_CLIENT --type blocks 2>/dev/null
bd dep add $CHAT_INPUT $FRONTEND_INIT --type blocks 2>/dev/null
bd dep add $PDF_VIEWER $FRONTEND_INIT --type blocks 2>/dev/null

bd dep add $USER_MGMT $API_CLIENT --type blocks 2>/dev/null
bd dep add $STATS_DASH $API_CLIENT --type blocks 2>/dev/null
bd dep add $HEALTH_DISP $API_CLIENT --type blocks 2>/dev/null

# TESTING DEPENDENCIES
TEST_INFRA=$(get_id "Setup Backend Testing Infrastructure")
REPO_TESTS=$(get_id "Write Database Repository Tests")
SVC_TESTS=$(get_id "Write Service Layer Tests")
API_TESTS=$(get_id "Write API Integration Tests")
FE_TEST_SETUP=$(get_id "Setup Frontend Testing")
FE_COMP_TESTS=$(get_id "Write Frontend Component Tests")

bd dep add $TEST_INFRA $BACKEND_INIT --type blocks 2>/dev/null
bd dep add $REPO_TESTS $TEST_INFRA --type blocks 2>/dev/null
bd dep add $SVC_TESTS $TEST_INFRA --type blocks 2>/dev/null
bd dep add $API_TESTS $TEST_INFRA --type blocks 2>/dev/null
bd dep add $FE_TEST_SETUP $FRONTEND_INIT --type blocks 2>/dev/null
bd dep add $FE_COMP_TESTS $FE_TEST_SETUP --type blocks 2>/dev/null

# DOCUMENTATION DEPENDENCIES
README=$(get_id "Create README.md")
ENV_EXAMPLE=$(get_id "Create .env.example")
DEPLOY_DOCS=$(get_id "Create Deployment Documentation")
STARTUP=$(get_id "Create Startup Scripts")

bd dep add $ENV_EXAMPLE $CONFIG_SVC --type blocks 2>/dev/null
bd dep add $STARTUP $BACKEND_INIT --type blocks 2>/dev/null

echo ""
echo "Dependencies configured!"
echo "Run 'bd ready' to see tasks ready to start"
echo "Run 'bd graph' to visualize dependencies"
