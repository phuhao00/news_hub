# GitHub Copilot Project Instructions (NewsHub)

Purpose: Enable AI coding agents to make correct, idiomatic, safe changes quickly. Focus on THIS codebase’s architecture, patterns, and workflows.

## 1. High-Level Architecture
- Three major parts:
  - Frontend: Next.js 14 (App Router) in `src/`.
  - Backend API: Go + Gin in `server/` (MongoDB persistence, now Redis queue + WebSocket realtime).
  - Crawler Service: Python FastAPI in `crawler-service/` (invoked via backend proxy or scheduled service). Planned evolution toward queued jobs.
- Data store: MongoDB (collections: `crawler_tasks`, `crawler_contents`, `creators`, `posts`, `videos`, `publish_tasks`, `jobs`, `job_events`).
- Realtime: Raw WebSocket endpoint at `/ws` broadcasting job updates (JSON: `{ "type": "job_update", "data": Job }`).
- Queue: Redis list `jobs:queue` (producer: API enqueue; consumer: worker in `server/cmd/job-worker`).

## 2. Core Directories & Responsibilities
- `server/config/`: DB, Redis, storage, JSON config loader (`config.json` root fallback).
- `server/models/models.go`: Mongo document schemas. Add new models here; keep `primitive.ObjectID` and JSON/BSON tags aligned.
- `server/handlers/`: HTTP endpoint logic (thin—validation + DB ops + logging). Add new route file per domain.
- `server/middleware/`: Cross-cutting concerns (logging, rate limit, request ID, error wrapper, metrics).
- `server/jobs/`: Queue abstraction (enqueue, dequeue, status updates, events, broadcasting).
- `crawler-service/`: Python scraping logic; extend platforms in `crawlers/`.
- `src/app/*`: Next.js route segments (each `page.tsx`). API routes under `src/app/api/` call Go backend endpoints (not internal DB directly).
- `src/lib/`: Client utilities (error handling, websocket, API wrappers).

## 3. Patterns & Conventions
- Mongo Write Pattern: Context with timeout (5–10s). Always log failures; return JSON error with `error` string.
- Timestamps: Use `time.Now()` on insert; update `UpdatedAt` manually when modifying docs.
- Status Fields: String enums (e.g. task: `pending|running|completed|failed`; job: `queued|running|succeeded|failed|cancelled`). Keep consistent.
- Deduplication: Content hash via SHA-256 of normalized title+content (`handlers/crawler_task.go: generateContentHash`). Reuse when adding new ingestion features.
- Job Progress: Update with `jobs.UpdateStatus` OR finer granularity with `jobs.AppendEvent` (also triggers broadcast). Always keep progress monotonic (0→100).
- WebSocket Broadcast: Call `handlers.BroadcastJobUpdate(job)` after state changes. Avoid large payloads—embed summary only (no huge blobs).
- Request ID: Access with `c.Get("request_id")` for trace correlation (propagate as `TraceID` in jobs).
- Config Precedence: ENV > `config.json` > defaults in code.
- Frontend Data Fetch: Use REST endpoints on Go backend (`/api/...`). Avoid direct DB queries.

## 4. Adding a New Feature (Example Workflow)
1. Define model (append struct in `models.go`).
2. Create handler file with CRUD endpoints (`handlers/<entity>.go`). Use context timeouts, proper BSON filters, and sorting.
3. Register routes in `main.go` under `/api/<entity>` group.
4. If background processing needed: enqueue job (`jobs.Enqueue(ctx, "<type>", payload, maxRetries, traceID)`), implement worker logic in worker process.
5. Broadcast progress as stages complete.
6. Frontend: Create page under `src/app/<entity>/page.tsx`; consume REST + WebSocket if realtime needed.

## 5. Job Queue Guidelines
- Enqueue: Minimal payload (IDs / params). Heavy logic executes in worker.
- Idempotency: Workers should tolerate retries (check existing output before reprocessing).
- Error Handling: On failure set status `failed`, include concise `error` message; DO NOT dump stack traces to clients.
- Events: Use for multi-stage tasks (e.g. `fetch`, `transform`, `store`).

## 6. MongoDB Usage
- Index Suggestions:
  - `crawler_contents.content_hash` (unique-ish) to minimize duplicates.
  - `jobs.queued_at` for list ordering.
  - Add compound indexes when new list filters become hot.
- Use `primitive.ObjectIDFromHex` for path parameters.

## 7. Frontend Conventions
- React components co-located by route; keep logic minimal in `page.tsx` and abstract fetch logic to `src/utils/api.ts` or `enhanced-api.ts`.
- Realtime: `src/lib/websocket.ts` helper; update state immutably (replace or prepend in arrays).
- Error Boundary present (`components/ErrorBoundary.tsx`)—wrap new complex UI if needed.

## 8. Crawler Integration Notes
- Current Go handlers proxy to Python service for certain endpoints and manage Mongo persistence.
- Future queued crawler tasks should: enqueue job → worker triggers Python HTTP call → store normalized documents → broadcast job completion.

## 9. Logging & Metrics
- Logging via custom middleware (`middleware/logger.go`). Add concise contextual fields (task/job IDs).
- Metrics endpoint `/metrics` already exposed—extend with domain counters in middleware if adding new critical flows.

## 10. Safe Change Checklist (Agent)
- Validate JSON input (`ShouldBindJSON`) and default missing numeric limits.
- Always set / update timestamp fields consistently.
- Keep response shapes stable (wrap lists as `{ "<plural>": [...], "total": n }`).
- Do not block request handlers with long-running jobs—use queue.
- Test with: `go run main.go` + `go run cmd/job-worker/main.go` + frontend dev server.

## 11. Useful Commands
- Backend deps: `cd server && go mod tidy`
- Start backend: `go run server/main.go` (or from `server` dir: `go run .`)
- Start worker: `go run server/cmd/job-worker/main.go`
- Frontend dev: `npm run dev`
- Crawler dev: `cd crawler-service && uvicorn main:app --reload --port 8001`
- Enqueue test job: `curl -X POST localhost:8080/api/jobs -H 'Content-Type: application/json' -d '{"type":"test"}'`

## 12. When Unsure
Prefer reading analogous existing handler or model and mirror its pattern. Keep changes incremental and reversible.

---
Feedback welcome: identify missing patterns or ambiguous areas before large refactors.
