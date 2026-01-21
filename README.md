# ruhroh

A modular RAG (Retrieval-Augmented Generation) document chat system that lets you chat with your documents using AI.

## Features

- **Document Upload & Processing**: Upload PDFs, DOCX, TXT, and Markdown files
- **Hybrid Search**: Combines vector similarity search with full-text keyword search using RRF fusion
- **RAG Chat**: Chat with your documents, get AI responses with source citations
- **Multi-Model Support**: Works with OpenAI GPT-4 (and Claude with configuration)
- **Citation Tracking**: Every response includes clickable citations back to source documents
- **Admin Dashboard**: User management, system stats, and health monitoring

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key

### Setup

1. Clone the repository:
```bash
git clone https://github.com/MaceGrim/ruhroh.git
cd ruhroh
```

2. Copy the example environment file:
```bash
cp .env.example .env
```

3. Edit `.env` and add your API keys:
```env
OPENAI_API_KEY=your-openai-api-key
```

4. Start the services:
```bash
docker-compose up -d
```

5. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Development Setup

For local development without Docker:

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start Postgres and Qdrant (via Docker)
docker-compose up -d db qdrant

# Run migrations
alembic upgrade head

# Start the backend
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                  │
├─────────────────┬─────────────────────────────────────────────────────────┤
│  React Frontend │                  Direct API Access                      │
└────────┬────────┴─────────────────────────┬───────────────────────────────┘
         │                                  │
         └──────────────────────────────────┘
                           │
                     HTTPS / REST API
                           │
┌──────────────────────────┼──────────────────────────────────────────────┐
│                    FASTAPI BACKEND                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        API LAYER (Routes)                          │ │
│  │  /auth  /documents  /chat  /search  /admin  /config                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                │                                         │
│  ┌─────────────────────────────┼─────────────────────────────────────┐  │
│  │                       SERVICE LAYER                                │  │
│  │  Auth │ Ingestion │ Retrieval │ Chat │ Admin │ LLM │ Config        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────────────┐
         │                         │                                 │
         ▼                         ▼                                 ▼
┌─────────────────┐     ┌─────────────────┐              ┌─────────────────┐
│   PostgreSQL    │     │     Qdrant      │              │  File Storage   │
│ (metadata, FTS) │     │ (vector search) │              │   (uploads)     │
└─────────────────┘     └─────────────────┘              └─────────────────┘
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Zustand |
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL 15+ (with FTS) |
| Vector Store | Qdrant |
| LLM | OpenAI (GPT-4, text-embedding-3-small) |

## API Endpoints

### Documents
- `POST /api/v1/documents` - Upload a document
- `GET /api/v1/documents` - List user's documents
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete a document

### Chat
- `POST /api/v1/chat/threads` - Create a new chat thread
- `GET /api/v1/chat/threads` - List user's threads
- `GET /api/v1/chat/threads/{id}` - Get thread with messages
- `POST /api/v1/chat/threads/{id}/messages` - Send a message (SSE streaming)
- `DELETE /api/v1/chat/threads/{id}` - Delete a thread

### Search
- `POST /api/v1/search` - Search across documents

### Admin
- `GET /api/v1/admin/stats` - System statistics
- `GET /api/v1/admin/users` - List users
- `PATCH /api/v1/admin/users/{id}` - Update user
- `GET /api/v1/admin/health` - System health check

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/ruhroh` |
| `QDRANT_HOST` | Qdrant host | `localhost` |
| `QDRANT_PORT` | Qdrant port | `6333` |
| `RUHROH_DEFAULT_MODEL` | Default LLM model | `gpt-4` |
| `RUHROH_EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `RUHROH_CHUNK_SIZE` | Document chunk size | `512` |
| `RUHROH_CHUNK_OVERLAP` | Chunk overlap | `50` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |

## Project Structure

```
ruhroh/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes
│   │   ├── db/            # Database models and repositories
│   │   ├── services/      # Business logic
│   │   └── utils/         # Helpers
│   ├── alembic/           # Database migrations
│   └── tests/             # Backend tests
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── stores/        # Zustand stores
│   │   ├── services/      # API client
│   │   └── types/         # TypeScript types
│   └── public/            # Static assets
├── docker-compose.yml     # Docker services
└── .env                   # Environment variables
```

## Known Issues

See [KNOWN_PROBLEMS.md](./KNOWN_PROBLEMS.md) for a list of known issues and their planned resolutions.

## License

MIT
