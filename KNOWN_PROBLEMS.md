# Known Problems

Issues identified during code review that need to be addressed before production deployment.

---

## Critical (Immediate Action Required)

### 1. API Key Exposed in Git History
- **Files:** `.env`, `backend/.env`
- **Issue:** OpenAI API key was committed to the repository and pushed to GitHub
- **Action:** Rotate the API key immediately, then clean git history or accept the key is compromised

### 2. Auth Bypass in Dev/Debug Mode
- **Files:** `backend/app/dependencies.py`, `backend/app/services/auth.py`
- **Issue:** `DEV_MODE=true` returns a fixed admin user ID; `DEBUG=true` bypasses JWT signature verification
- **Action:** Ensure these are `false` in production; consider removing debug auth bypass entirely

### 3. Path Traversal Risk in File Uploads
- **Files:** `backend/app/services/ingestion.py`, `backend/app/api/documents.py`
- **Issue:** `normalize_filename()` doesn't strip path separators; filename like `../../etc/passwd` could escape upload directory
- **Action:** Use `Path(filename).name` and explicitly strip `/` and `\` characters

### 4. Unauthenticated Sensitive Endpoints
- **Files:** `backend/app/api/admin.py`, `backend/app/api/eval.py`
- **Issue:** `GET /api/v1/admin/health` and `GET /api/v1/eval/{eval_id}` have no authentication
- **Action:** Add auth/role checks to these endpoints

---

## High Priority

### 5. Memory DoS Risk on File Uploads
- **File:** `backend/app/api/documents.py`
- **Issue:** `UploadFile.read()` loads entire file into memory; large files can exhaust server memory
- **Action:** Stream uploads to disk with size limits

### 6. CORS Configuration Too Permissive
- **Files:** `backend/app/config.py`, `backend/app/main.py`
- **Issue:** `cors_origins="*"` with `allow_credentials=True` is unsafe for production
- **Action:** Restrict to specific origins in production

### 7. In-Memory Eval Storage
- **File:** `backend/app/services/eval.py`
- **Issue:** Eval state stored in `self._evals` dict; lost on restart, doesn't work with multiple workers
- **Action:** Persist eval runs in database with user ownership

---

## Medium Priority

### 8. No Dependency Lockfile
- **File:** `backend/requirements.txt`
- **Issue:** No lockfile means non-deterministic builds; versions use `>=` with no upper bounds
- **Action:** Add `requirements.lock` or migrate to poetry/pip-tools

### 9. Dev/Test Dependencies Mixed with Production
- **File:** `backend/requirements.txt`
- **Issue:** pytest, ruff, black, mypy are in same file as production deps
- **Action:** Split into `requirements.txt` and `dev-requirements.txt`

### 10. Duplicate Dependency
- **File:** `backend/requirements.txt`
- **Issue:** `httpx` is listed twice
- **Action:** Remove duplicate entry

### 11. Duplicate MIME Validation Logic
- **Files:** `backend/app/api/documents.py`, `backend/app/utils/security.py`
- **Issue:** MIME type validation exists in two places
- **Action:** Consolidate to use `validate_file_upload` from security utils

---

## Low Priority

### 12. No README
- **Issue:** No quick-start documentation; specs exist but no setup instructions
- **Action:** Add `README.md` with setup, env vars, and run instructions

### 13. Build Artifacts in Repo
- **Files:** `backend/uvicorn.log`, `backend/app/__pycache__/`
- **Issue:** Log files and bytecode committed to repo
- **Action:** Add to `.gitignore` and remove from tracking

### 14. IngestionService is a "God Object"
- **File:** `backend/app/services/ingestion.py`
- **Issue:** Handles file IO, text extraction, chunking, embeddings, vector DB, and DB writes
- **Action:** Consider splitting into smaller focused services if complexity grows

---

## Architecture Notes (Not Problems)

These are observations, not issues:

- **Good:** Clean layered architecture (API → Services → Repositories)
- **Good:** Consistent FastAPI dependency injection pattern
- **Good:** No circular dependencies detected
- **Good:** Well-documented code with docstrings
- **Good:** No TODO/FIXME comments (low tech debt)
