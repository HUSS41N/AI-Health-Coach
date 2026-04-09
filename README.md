# AI Health Coach (Reeba)

WhatsApp-style **AI health coach**: **FastAPI** backend, **PostgreSQL** persistence, **Redis** (Upstash) for cache and rate limits, **Next.js** UI with streaming chat. No vector DB—episodic recall uses **Postgres tag overlap** and keywords.

---

## System design: HLD, LLD, and flows

### High-level design (HLD)

System context: who talks to what, and which external services the API depends on.

```mermaid
flowchart TB
  subgraph actors [Actors]
    U[User]
  end
  subgraph client [Client tier]
    UI[Next.js UI]
  end
  subgraph api [API tier]
    FAST[FastAPI app]
  end
  subgraph data [Data and models]
    PG[(PostgreSQL)]
    RD[(Redis / Upstash)]
  end
  subgraph models [LLM providers]
    OAI[OpenAI API]
    GROQ[Groq API]
  end
  U --> UI
  UI -->|HTTPS SSE / REST| FAST
  FAST --> PG
  FAST --> RD
  FAST --> OAI
  FAST --> GROQ
```

### Low-level design (LLD)

Major **Python packages** under `server/` and how the chat path wires them (simplified).

```mermaid
flowchart LR
  subgraph entry [Entry]
    M[main.py]
  end
  subgraph http [HTTP]
    CR[chat/router.py]
    AR[admin/router.py]
  end
  subgraph orchestration [Orchestration]
    CS[chat/service.py]
  end
  subgraph domain [Domain logic]
    ON[onboarding/]
    MEM[memory/]
    AG[agents/]
    PR[protocol/]
    PM[prompts/]
  end
  subgraph infra [Infrastructure]
    LLM[llm/client.py]
    GR[guardrails/]
    RC[redis_client.py]
    DB[db/session.py]
    SSE[streaming/sse.py]
  end
  M --> CR
  M --> AR
  CR --> CS
  CS --> ON
  CS --> MEM
  CS --> AG
  CS --> PR
  CS --> PM
  CS --> LLM
  CS --> GR
  CS --> RC
  CS --> DB
  CS --> SSE
  AR --> DB
  AR --> PM
```

### User flow: send a message (end-to-end)

From the browser through guardrails, branching (onboarding vs coach), streaming, and post-reply work.

```mermaid
flowchart TD
  A[User sends message in UI] --> B[POST /chat/stream SSE]
  B --> C[Rate limit + dedupe Redis]
  C --> D[prepare_user_message guardrails]
  D --> E{Valid input?}
  E -->|no| F[Persist user row + fixed reply + done]
  E -->|yes| G[Ensure user + persist user message]
  G --> H[SSE meta + onboarding state]
  H --> I{safety override?}
  I -->|yes| F
  I -->|no| J{Onboarding not done and not emergency?}
  J -->|yes| K[apply_onboarding_turn chips + reply]
  K --> F
  J -->|no| L[Invalidate message cache]
  L --> M[Parallel: intent LLM thread + build_memory_context]
  M --> N[Protocol engine + maybe emergency boost]
  N --> O[Question agent UI chips/scales]
  O --> P[build_system_prompt + stream LLM]
  P --> Q[filter_output + persist assistant]
  Q --> R[SSE done]
  R --> S{Committed and skip_memory?}
  S -->|no skip| T[Background: post-chat memory work]
  S -->|skip| U[End]
  T --> U
```

### Memory flow: read path (same turn as the coach)

How **short-term**, **profile**, **summary**, and **episodic** data are assembled for `build_system_prompt` (inside `build_memory_context` → `memory/retrieval.py`).

```mermaid
flowchart TD
  A[build_memory_context session user_id message] --> B[load_short_term_messages]
  B --> C{Redis coach:msgs hit?}
  C -->|yes| D[Recent message rows JSON]
  C -->|no| E[Query messages table + Redis set]
  D --> F[Slice for MemoryContext vs full window for LLM]
  E --> F
  F --> G[get_summary_for_context]
  G --> H{Redis summary key?}
  H -->|miss| I[conversation_summary table]
  H -->|hit| J[Summary text]
  I --> J
  F --> K[get_profile_for_context]
  K --> L{Redis profile key?}
  L -->|miss| M[user_memory.profile JSON]
  L -->|hit| N[Profile dict]
  M --> N
  F --> O[retrieve_episodic]
  O --> P[extract_tags from current message]
  P --> Q{tags overlap query on episodic_memory?}
  Q -->|rows| R[Episodic strings up to limit]
  Q -->|no hit| S[Fallback last N episodic rows]
  R --> T[MemoryContext + short_term for chat loop]
  S --> T
```

### Memory flow: write path (after a successful turn)

Runs only when the stream **commits** and **`skip_memory`** was not set (`chat/router.py` → `memory/tasks.py`).

```mermaid
flowchart TD
  A[Transaction commit on /chat/stream] --> B{skip_memory set?}
  B -->|yes| Z[No background memory]
  B -->|no| C[BackgroundTasks run_post_chat_memory_work]
  C --> D[apply_long_term_from_message LLM extract + merge user_memory]
  C --> E[store_episodic_memory keyword rules + tags]
  C --> F[maybe_refresh_summary_for_user throttled LLM merge]
  D --> G[session.commit]
  E --> G
  F --> G
  G --> H[invalidate_user_memory_caches]
  H --> I[Delete Redis msgs profile summary keys for user]
```

### Admin / observability flow

Operators use the same API origin as the chat client.

```mermaid
sequenceDiagram
  participant Op as Browser /admin
  participant UI as Next.js admin page
  participant API as FastAPI
  participant PG as PostgreSQL
  Op->>UI: Open /admin
  UI->>API: GET /admin/users
  API->>PG: distinct user_ids
  PG-->>API: rows
  API-->>UI: JSON
  UI->>API: GET /admin/users/{id}/overview
  API->>PG: profile summary episodic messages
  PG-->>API: JSON
  API-->>UI: Messages Memory Profile tabs
  UI->>API: GET/PATCH /admin/prompts
  API->>PG: agent_prompts table
```

---

## How to run it locally (step by step)

### 1. Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for Compose), **or** Python 3.12 + Node 20 for dev servers  
- A **PostgreSQL** URL (e.g. [Neon](https://neon.tech) free tier) **or** use the optional in-Docker Postgres below  
- An **[Upstash Redis](https://upstash.com)** REST database (free tier) — URL + token  
- At least one LLM key: **`OPENAI_API_KEY`** and/or **`GROQ_API_KEY`** (Groq is fallback)

### 2. Server environment

```bash
cp server/.env.example server/.env
```

Edit `server/.env`: set `DATABASE_URL`, `UPSTASH_REDIS_REST_*`, `CORS_ORIGINS` (include `http://localhost:3000`), and your LLM keys. There is **no Anthropic** integration in this repo; use OpenAI and/or Groq.

### 3. UI environment (API base URL)

The UI reads the FastAPI base URL from **`NEXT_PUBLIC_API_URL`** (no trailing slash).

```bash
cd ui
cp .env.example .env.local
# or: cp .env.local.example .env.local
```

Edit `ui/.env.local` if the API is not at `http://localhost:8000`.  
`src/lib/api.ts` uses `process.env.NEXT_PUBLIC_API_URL` with a localhost default.

### 4. Run with Docker Compose (API + UI)

From the **repository root**:

```bash
docker compose up --build
```

- **API:** [http://localhost:8000](http://localhost:8000) (`/docs` for OpenAPI)  
- **UI:** [http://localhost:3000](http://localhost:3000)  

Compose loads **`server/.env`** into the API container. The UI image is built with `NEXT_PUBLIC_API_URL=http://localhost:8000` (see `docker-compose.yml` build args). If you change the API port or use a tunnel, rebuild the UI with the correct build arg or run the UI with `npm run dev` and `.env.local` instead.

**Optional — Postgres only in Docker** (you still configure Upstash + LLM in `server/.env`):

```bash
docker compose -f docker-compose.yml -f docker-compose.localdb.yml up --build
```

This adds a `db` service and sets `DATABASE_URL` for the API to that container. Data persists in the `coach_pg_data` volume.

### 5. Run without Docker (development)

**API**

```bash
cd server
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# server/.env already filled
uvicorn main:app --reload --port 8000
```

**UI**

```bash
cd ui
npm install
# .env.local with NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

---

## Database: migrations and seed

- **Migrations:** There is **no Alembic** (or other migration runner) in this project. On API startup, **`init_db()`** runs **`Base.metadata.create_all()`** so tables match SQLAlchemy models (`server/db/models.py`). For production you may add Alembic later; until then, schema changes require compatible `create_all` or manual SQL.
- **Seed:** **`seed_prompts_if_needed()`** runs at startup (`server/prompts/service.py`). Missing rows in **`agent_prompts`** are filled from defaults in `server/prompts/defaults.py` (coach preamble, intent, question agent, onboarding copy, etc.). **User/chat data is not seeded** — it appears when you use the app.

---

## Environment variables

| Area | File | Important variables |
|------|------|---------------------|
| **API** | `server/.env` (see `server/.env.example`) | `DATABASE_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `CORS_ORIGINS`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL` |
| **UI** | `ui/.env.local` or `ui/.env` (see `ui/.env.example`, `ui/.env.local.example`) | `NEXT_PUBLIC_API_URL` — FastAPI origin the **browser** will call |

Optional guardrail tuning: `GUARDRAIL_MAX_MESSAGE_CHARS`, `GUARDRAIL_RATE_LIMIT_PER_MINUTE`, `GUARDRAIL_JSON_RETRIES` (documented in `.env.example`).

---

## Architecture overview (backend)

See **[System design: HLD, LLD, and flows](#system-design-hld-lld-and-flows)** for diagrams. In one pass: **`chat/router.py`** applies Redis rate limit / dedupe, **`chat/service.py`** orchestrates onboarding vs parallel **intent + `build_memory_context`**, **protocol**, **question UI**, **`build_system_prompt`**, and **streaming**; **`memory/tasks.py`** updates long-term / episodic / summary after commit. **`admin/router.py`** serves user overview and **`agent_prompts`** CRUD.

---

## Design decisions (short)

- **SSE streaming** for perceived latency; tokens arrive incrementally in the UI.  
- **Intent + memory load in parallel** (thread pool) to shave sequential LLM/DB time.  
- **Protocol layer is non-LLM** so emergency and triage hints stay predictable.  
- **Onboarding is mostly deterministic** (goal / conditions / lifestyle via chips and a small state machine) so first-run is fast and stable; results merge into **`user_memory`**.  
- **Long-term profile** is JSON merged with “no clobber from null” and set-union for list fields.  
- **Episodic memory** avoids embeddings: keyword tagging + **`tags && query_keywords`** in SQL, with a small fallback window.  
- **Redis** (Upstash REST) for message list cache, profile/summary cache, rate limit, prompt cache, inflight dedupe — failures degrade to “no cache” or fail-open rate limit where implemented.  
- **OpenAI first, Groq-compatible fallback** (`llm/client.py`, `guardrails/llm_wrapper.py`) for resilience and cost/speed experiments.

---

## LLM: provider and prompting

- **Providers:** Primary **OpenAI** Chat Completions (streaming + JSON-style tasks). **Groq** (OpenAI-compatible HTTP API) when OpenAI is missing or errors. Model names from env (`OPENAI_MODEL`, `GROQ_MODEL`; defaults in `server/config.py` and `.env.example`).  
- **Where the LLM runs:** Intent classification (JSON), question/chip suggestions for some intents, main coach **stream**, background **profile extraction** and **conversation summary** merge.  
- **Prompt assembly:** The live coach uses **`build_system_prompt`** (`chat/prompts.py`): DB-resolved **preamble** (`coach_system_preamble`), optional **goal/conditions/lifestyle** block, structured **profile** JSON, **summary**, **episodic** bullet list, **intent** + **entities**, and **protocol** hint. Agent-specific system text (intent, question, onboarding, etc.) is loaded from **`agent_prompts`** via `prompts/service.py` (seeded defaults, editable in UI).

---

## Trade-offs and “If I had more time…”

- **No Alembic** — fast to ship; production schema evolution should move to migrations.  
- **Upstash REST** — simple hosting, but one HTTP round-trip per Redis command; local TCP Redis would be faster at scale.  
- **No auth on `/admin`** — fine for local demos; needs middleware or network policy before public deploy.  
- **Client-generated `user_id`** — swap for real auth and server-issued IDs when you add accounts.  
- **Embeddings / vector recall** were out of scope; keyword + tag overlap is a deliberate ceiling on recall quality.  
- Could add **E2E tests**, **structured logging**, **per-conversation threads** in the UI, and **cheaper/smaller models** for intent-only calls.

---

## Frontend: chat, admin, prompts, memory

- **`/`** — WhatsApp-style shell; only **Reeba** talks to the API. Streaming text, scales, and quick-reply chips from SSE.  
- **`/admin`** — Two areas: **Users** (pick a `user_id`) and **Agent prompts**.  
  - **Users:** Tabs for **Messages**, **Memory** (episodic list + legacy memory rows), and **Profile** (structured `user_memory`).  
  - **Agent prompts:** List keys, edit body, save — changes apply on the next LLM call that loads that key.  
- **`/health`** — Calls the API health endpoint (DB + Redis).  

All browser calls use **`NEXT_PUBLIC_API_URL`** from env (`@/lib/api`).

---

## Docker notes

- Default API image is built from the repo root: **`Dockerfile.api`** (so `server/requirements.txt` paths resolve).  
- **`server/Dockerfile`** expects build context **`server/`** (e.g. Railway root directory `server`).  
- Details: **[docs/railway.md](docs/railway.md)**.

---

## Reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | DB + Redis checks |
| GET | `/chat/messages` | Paginated history |
| POST | `/chat/stream` | SSE chat |
| PATCH | `/chat/messages/{id}/feedback` | Thumbs up/down |
| GET | `/admin/users`, `/admin/users/{id}/overview` | Admin user inspect |
| GET/PATCH | `/admin/prompts`, `/admin/prompts/{key}` | Prompt manager |

**Guardrails** (`server/guardrails/`): input sanitization, safety keyword short-circuit, output filter, rate limit, LLM retry + fallback.

**Security:** Do not commit `server/.env`. Coach copy is non-diagnostic; protocol layer escalates emergency language.

---

## License

Private / project default — set as needed for your org.
