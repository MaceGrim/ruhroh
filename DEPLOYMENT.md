# Ruhroh RAG - Deployment Guide

This document covers deployment options for the ruhroh RAG document chat system.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Docker Deployment](#docker-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Database Setup](#database-setup)
6. [Vector Database (Qdrant)](#vector-database-qdrant)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Python | 3.11+ | Backend runtime (manual deployment) |
| Node.js | 20+ | Frontend build (manual deployment) |

### Required API Keys

| Key | Required | Provider | Purpose |
|-----|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | [OpenAI](https://platform.openai.com/api-keys) | LLM and embeddings |
| `SUPABASE_URL` | Yes | [Supabase](https://supabase.com) | Authentication |
| `SUPABASE_ANON_KEY` | Yes | Supabase | Public client key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase | Server-side auth operations |
| `ANTHROPIC_API_KEY` | No | [Anthropic](https://console.anthropic.com) | Claude models (optional) |
| `MISTRAL_API_KEY` | No | [Mistral](https://console.mistral.ai) | OCR extraction (optional) |

### System Requirements

**Minimum (Development)**
- 4 CPU cores
- 8 GB RAM
- 20 GB disk space

**Recommended (Production)**
- 8+ CPU cores
- 16+ GB RAM
- 100+ GB SSD storage
- Dedicated volumes for PostgreSQL and Qdrant data

---

## Environment Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

### Complete Environment Variables Reference

#### Database (PostgreSQL)

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` |
| `POSTGRES_DB` | Database name | `ruhroh` |

#### Vector Database (Qdrant)

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_API_KEY` | API key for Qdrant authentication | (empty - no auth) |
| `QDRANT_COLLECTION_NAME` | Name of the vector collection | `documents` |

#### Authentication (Supabase)

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPABASE_URL` | Your Supabase project URL | Required |
| `SUPABASE_ANON_KEY` | Public anonymous key | Required |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server-side) | Required |

#### LLM Providers

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude) | (empty) |
| `MISTRAL_API_KEY` | Mistral API key (for OCR) | (empty) |

#### RAG Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `RUHROH_VECTOR_WEIGHT` | Weight for vector search in hybrid search | `0.6` |
| `RUHROH_KEYWORD_WEIGHT` | Weight for keyword search in hybrid search | `0.4` |
| `RUHROH_RRF_K` | RRF fusion constant | `60` |
| `RUHROH_ENABLE_FALLBACK` | Enable fallback to secondary LLM | `false` |
| `RUHROH_DEFAULT_MODEL` | Default LLM model | `gpt-4` |
| `RUHROH_EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `RUHROH_CHUNK_SIZE` | Document chunk size (tokens) | `512` |
| `RUHROH_CHUNK_OVERLAP` | Overlap between chunks (tokens) | `50` |

#### Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `RUHROH_RATE_LIMIT_RPM` | Requests per minute per user | `60` |
| `RUHROH_RATE_LIMIT_BURST` | Burst allowance | `10` |

#### CORS and Security

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000` |

#### Application Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode (exposes /docs endpoint) | `false` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

#### Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL for frontend | (empty - uses relative /api) |
| `VITE_DEV_MODE` | Enable frontend dev mode | `false` |

---

## Docker Deployment

### Development Setup

1. **Start all services:**

```bash
docker-compose up -d
```

2. **Check service health:**

```bash
docker-compose ps
docker-compose logs -f backend
```

3. **Access the application:**

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |

### Production Setup

For production, create a `docker-compose.prod.yml` override:

```yaml
version: "3.8"

services:
  db:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # Use strong password
    volumes:
      - /data/postgres:/var/lib/postgresql/data  # Use host path for persistence
    deploy:
      resources:
        limits:
          memory: 2G

  qdrant:
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}  # Enable API key auth
    volumes:
      - /data/qdrant:/qdrant/storage
    deploy:
      resources:
        limits:
          memory: 4G

  backend:
    environment:
      DEBUG: "false"
      LOG_LEVEL: "WARNING"
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 2G

  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
```

Deploy with:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Scaling Considerations

**Horizontal Scaling:**
- Backend can be scaled to multiple replicas behind a load balancer
- Add a load balancer (nginx, Traefik, or cloud LB) in front of backend instances
- Use Redis for session/rate limit state sharing across instances

**Vertical Scaling:**
- Qdrant benefits most from additional RAM for vector caching
- PostgreSQL benefits from more RAM for query caching
- Backend benefits from more CPU cores for concurrent request handling

**Volume Management:**
- Use named volumes for development: `ruhroh_postgres_data`, `ruhroh_qdrant_data`
- Use bind mounts or cloud storage for production data persistence
- Implement regular backup procedures for both databases

---

## Manual Deployment

### Backend Setup

1. **Create Python virtual environment:**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Set environment variables:**

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ruhroh"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
export OPENAI_API_KEY="your-key"
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

4. **Start PostgreSQL and Qdrant via Docker:**

```bash
docker-compose up -d db qdrant
```

5. **Run database migrations:**

```bash
alembic upgrade head
```

6. **Start the backend:**

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend Setup

1. **Install dependencies:**

```bash
cd frontend
npm ci  # or: npm install
```

2. **Set environment variables:**

```bash
export VITE_API_URL="http://localhost:8000"
```

3. **Development server:**

```bash
npm run dev
```

4. **Production build:**

```bash
npm run build
```

The built files will be in `frontend/dist/`.

### Reverse Proxy Configuration (nginx)

For production, place nginx in front of both services:

```nginx
upstream backend {
    server 127.0.0.1:8000;
    # Add more backend instances for load balancing:
    # server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Frontend static files
    root /var/www/ruhroh/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support for streaming responses
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        proxy_read_timeout 300s;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## Database Setup

### PostgreSQL Configuration

The application uses PostgreSQL 15+ with the following features:
- Full-text search (FTS) for keyword search
- JSONB for flexible metadata storage
- Async connections via asyncpg

**Recommended PostgreSQL settings for production** (`postgresql.conf`):

```ini
# Memory
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 256MB
maintenance_work_mem = 512MB

# Connections
max_connections = 200

# Write-Ahead Log
wal_buffers = 64MB
checkpoint_completion_target = 0.9

# Query Planning
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Running Migrations

Migrations are managed with Alembic:

```bash
cd backend

# Apply all migrations
alembic upgrade head

# Check current version
alembic current

# Generate new migration (after model changes)
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

### Backup and Restore

**Backup:**

```bash
# Using Docker
docker exec ruhroh-db pg_dump -U postgres -d ruhroh > backup_$(date +%Y%m%d).sql

# Direct
pg_dump -U postgres -d ruhroh > backup_$(date +%Y%m%d).sql
```

**Restore:**

```bash
# Using Docker
docker exec -i ruhroh-db psql -U postgres -d ruhroh < backup_20240101.sql

# Direct
psql -U postgres -d ruhroh < backup_20240101.sql
```

**Automated backups (cron):**

```bash
# Add to crontab: crontab -e
0 2 * * * docker exec ruhroh-db pg_dump -U postgres -d ruhroh | gzip > /backups/ruhroh_$(date +\%Y\%m\%d).sql.gz
```

---

## Vector Database (Qdrant)

### Configuration Options

Qdrant configuration can be set via environment variables or a config file.

**Environment variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT__SERVICE__API_KEY` | API key for authentication | (none) |
| `QDRANT__STORAGE__STORAGE_PATH` | Data storage path | `/qdrant/storage` |
| `QDRANT__SERVICE__GRPC_PORT` | gRPC port | `6334` |
| `QDRANT__SERVICE__HTTP_PORT` | HTTP port | `6333` |

**Enable API key authentication in production:**

```yaml
# docker-compose.prod.yml
qdrant:
  environment:
    QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}
```

### Data Persistence

Qdrant data is stored in a Docker volume by default. For production:

```yaml
qdrant:
  volumes:
    - /data/qdrant:/qdrant/storage  # Host path for reliability
```

### Performance Tuning

**Memory:**
- Qdrant loads vectors into memory for fast search
- Allocate RAM = (vector_count * vector_dimensions * 4 bytes) + overhead
- For 1M vectors with 1536 dimensions: ~6GB RAM recommended

**Collection configuration:**
The application creates collections with these settings:
- Vector size: 1536 (OpenAI text-embedding-3-small)
- Distance metric: Cosine similarity
- HNSW index for approximate nearest neighbor search

**Backup Qdrant:**

```bash
# Create snapshot
curl -X POST "http://localhost:6333/collections/documents/snapshots"

# List snapshots
curl "http://localhost:6333/collections/documents/snapshots"

# Download snapshot
curl "http://localhost:6333/collections/documents/snapshots/{snapshot_name}" -o snapshot.snapshot
```

---

## Monitoring and Logging

### Health Check Endpoints

| Endpoint | Auth Required | Description |
|----------|---------------|-------------|
| `GET /health` | No | Basic health status |
| `GET /api/v1/admin/health` | No | Detailed component health |

**Response format:**

```json
{
  "status": "ok",
  "database": "ok",
  "qdrant": "ok"
}
```

Status values: `ok`, `degraded`, `error`

### Log Configuration

Logs are structured JSON via `structlog`. Configure via environment:

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

**Log output example:**

```json
{
  "event": "request_completed",
  "method": "POST",
  "path": "/api/v1/chat/threads/123/messages",
  "status_code": 200,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Docker Logging

View logs:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

Configure log rotation in `docker-compose.yml`:

```yaml
backend:
  logging:
    driver: "json-file"
    options:
      max-size: "100m"
      max-file: "5"
```

### Recommended Monitoring Tools

| Tool | Purpose | Integration |
|------|---------|-------------|
| **Prometheus** | Metrics collection | Add `/metrics` endpoint with `prometheus-fastapi-instrumentator` |
| **Grafana** | Dashboards and visualization | Connect to Prometheus |
| **Sentry** | Error tracking | Add `sentry-sdk[fastapi]` |
| **Loki** | Log aggregation | Ship Docker logs via Promtail |

---

## Security Considerations

### API Key Management

1. **Never commit `.env` files** - Use `.env.example` as a template
2. **Use secrets management** in production:
   - Docker Swarm secrets
   - Kubernetes secrets
   - AWS Secrets Manager, HashiCorp Vault, etc.

3. **Rotate keys regularly:**
   - OpenAI API keys
   - Supabase service role key
   - Database passwords

### CORS Configuration

**Development:**
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**Production:**
```bash
CORS_ORIGINS=https://your-domain.com
```

Never use `*` in production.

### Rate Limiting

Built-in rate limiting protects against abuse:

```bash
RUHROH_RATE_LIMIT_RPM=60      # Requests per minute
RUHROH_RATE_LIMIT_BURST=10    # Burst allowance
```

Rate limit headers are exposed:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

### Network Security

1. **Internal network isolation:**
   ```yaml
   # docker-compose.yml
   networks:
     internal:
       internal: true
     external:

   services:
     db:
       networks:
         - internal  # Not exposed externally
     backend:
       networks:
         - internal
         - external
   ```

2. **Expose only necessary ports:**
   - Production: Only expose ports 80/443 via reverse proxy
   - Remove direct access to 5432 (PostgreSQL) and 6333/6334 (Qdrant)

3. **Enable Qdrant API key authentication** in production

### File Upload Security

- Maximum file size: 500MB (configurable via `max_file_size`)
- Allowed file types: PDF, DOCX, TXT, Markdown
- Files are validated by MIME type using `python-magic`
- Uploaded files are stored outside web root

---

## Troubleshooting

### Common Issues

#### Database Connection Failed

**Symptoms:** Backend fails to start with connection errors

**Solutions:**
1. Check PostgreSQL is running: `docker-compose ps db`
2. Verify credentials in `.env` match `docker-compose.yml`
3. Wait for healthcheck: PostgreSQL may take 10-30 seconds to be ready
4. Check logs: `docker-compose logs db`

#### Qdrant Connection Refused

**Symptoms:** Vector search fails, health check shows Qdrant error

**Solutions:**
1. Check Qdrant is running: `docker-compose ps qdrant`
2. Verify host/port settings
3. If using API key auth, ensure `QDRANT_API_KEY` matches in both Qdrant and backend config
4. Check Qdrant logs: `docker-compose logs qdrant`

#### OpenAI API Errors

**Symptoms:** Chat responses fail, embedding generation fails

**Solutions:**
1. Verify API key is valid and has credits
2. Check rate limits on your OpenAI account
3. Ensure the specified model is available to your account
4. Review backend logs for specific error messages

#### CORS Errors

**Symptoms:** Frontend cannot reach backend, browser console shows CORS errors

**Solutions:**
1. Verify `CORS_ORIGINS` includes your frontend URL
2. Include protocol and port: `http://localhost:3000` not just `localhost:3000`
3. For multiple origins, use comma separation: `http://localhost:3000,http://localhost:5173`

#### SSE Streaming Not Working

**Symptoms:** Chat messages arrive all at once instead of streaming

**Solutions:**
1. Check nginx buffering is disabled for `/api` routes
2. Verify `proxy_buffering off;` is set
3. Ensure `Connection` header is set correctly for SSE
4. Check for intermediate proxies (CloudFlare, etc.) that may buffer responses

#### Migration Failures

**Symptoms:** Alembic errors during migration

**Solutions:**
1. Check database connectivity
2. Ensure no conflicting schema changes
3. Review migration file for errors
4. If stuck, check current state: `alembic current`
5. Manual fix may be needed if migration partially applied

#### Out of Memory (Qdrant)

**Symptoms:** Qdrant crashes or becomes unresponsive with large document sets

**Solutions:**
1. Increase container memory limit
2. Enable disk-based storage for cold data
3. Consider Qdrant Cloud for larger deployments
4. Monitor vector count vs available RAM

### Debug Mode

Enable debug mode for detailed error messages and API documentation:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

This exposes:
- `/docs` - Swagger UI
- `/redoc` - ReDoc documentation
- Detailed error responses

**Do not enable in production.**

### Getting Help

1. Check application logs: `docker-compose logs -f`
2. Review health endpoints: `curl http://localhost:8000/health`
3. Check component status in admin panel
4. Review [KNOWN_PROBLEMS.md](./KNOWN_PROBLEMS.md) for known issues
