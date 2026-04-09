# Deploying on Railway

This app is **two services**: **FastAPI** (`server/`) and **Next.js** (`ui/`). You also need **PostgreSQL**, **Redis (Upstash)**, and **LLM keys** (OpenAI and/or Groq).

---

## 1. Create the project

1. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub** (or empty project + connect repo).
2. You will add **three** pieces: **Postgres** (optional if you keep Neon), **API**, **UI**.

---

## 2. Database

**Option A — Railway PostgreSQL**

1. Project → **New** → **Database** → **PostgreSQL**.
2. Open the Postgres service → **Variables** → copy **`DATABASE_URL`** (or connect Postgres to the API service and use Railway’s **Reference Variable** so `DATABASE_URL` is injected into the API).

**Option B — Neon (or other hosted Postgres)**

- Keep your existing Neon URL. Add it to the API service as **`DATABASE_URL`** (include `?sslmode=require` if your provider requires it).

The API runs `create_all` on startup, so tables are created automatically.

---

## 3. API service (`server/`)

1. **New** → **GitHub Repo** → same repo → **Add variables** (see below).
2. Service **Settings**:
   - **Root Directory**: `server`
   - **Builder**: Dockerfile (repo includes `server/railway.toml` pointing at `Dockerfile`).
3. **Networking** → **Generate Domain** (e.g. `https://your-api.up.railway.app`). You will use this URL in CORS and in the UI build.

### API — required variables

| Variable | Notes |
|----------|--------|
| `DATABASE_URL` | From Railway Postgres (reference) or Neon. |
| `UPSTASH_REDIS_REST_URL` | Upstash REST URL. |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash token. |
| `CORS_ORIGINS` | Comma-separated **exact** browser origins that may call the API. Include your **UI** public URL(s), e.g. `https://your-ui.up.railway.app` and local dev if needed: `http://localhost:3000`. **No trailing slashes.** |
| `OPENAI_API_KEY` | If using OpenAI as primary. |
| `GROQ_API_KEY` | If using Groq as fallback (or primary if OpenAI unset). |

### API — optional / defaults

| Variable | Default / notes |
|----------|-----------------|
| `OPENAI_MODEL` | e.g. `gpt-4.1-mini` |
| `GROQ_MODEL` | e.g. `llama-3.3-70b-versatile` |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |
| `GUARDRAIL_*` | See `server/.env.example` |

Railway sets **`PORT`** automatically; the API Dockerfile uses **`${PORT:-8000}`** so it binds correctly.

### API — health check

`server/railway.toml` sets **`/health`**. Ensure Postgres and Redis are reachable or `/health` returns `degraded` until fixed.

---

## 4. UI service (`ui/`)

Next.js **bakes** `NEXT_PUBLIC_API_URL` into the client at **build** time. You must set it **before** the Docker build runs.

1. **New** → same repo → second service.
2. **Settings** → **Root Directory**: `ui`
3. **Variables**:
   - Add **`NEXT_PUBLIC_API_URL`** = your API’s **public** URL, e.g. `https://your-api.up.railway.app` (**no trailing slash**).
4. In Railway, for Docker builds, ensure this variable is available **during build** (Railway usually exposes service variables to the build; if the UI build still shows `localhost`, use **Railway → UI service → Settings → Build →** add the same var as a **build argument** or redeploy after setting the variable).

5. **Networking** → **Generate Domain** for the UI.

6. Update the **API** service **`CORS_ORIGINS`** to include the new UI URL, then **redeploy the API**.

### UI Dockerfile build arg

The `ui/Dockerfile` expects:

```dockerfile
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
```

Railway: set `NEXT_PUBLIC_API_URL` in the UI service; in **Dockerfile** builds Railway typically passes matching env into the build. If not, add a custom build command in the UI service that passes `--build-arg NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL`.

---

## 5. Checklist (order matters)

1. Deploy **Postgres** (or wire **Neon**).
2. Deploy **API** → set env vars → generate **API** public URL.
3. Set **`CORS_ORIGINS`** on API to include the **UI** URL you will use (you can add UI URL after step 4 and redeploy API).
4. Deploy **UI** with **`NEXT_PUBLIC_API_URL`** = API public URL → build → generate **UI** URL.
5. Set **`CORS_ORIGINS`** on API to include the real **UI** URL → **redeploy API**.
6. Open the **UI** URL in the browser and smoke-test chat and `/health`.

---

## 6. Common issues

| Issue | Fix |
|-------|-----|
| Browser CORS error | Add the **exact** UI origin (scheme + host + port) to **`CORS_ORIGINS`** on the API; redeploy API. |
| UI calls `localhost:8000` in production | Rebuild UI with correct **`NEXT_PUBLIC_API_URL`**; env is compile-time for Next. |
| `DATABASE_URL` SSL errors | Append `?sslmode=require` (or provider-specific params). |
| Redis failures | Confirm Upstash URL/token; `/health` shows Redis status. |
| Cold start timeouts | Increase health check timeout in `railway.toml` or Railway UI. |

---

## 7. Security (production)

- **`/admin`** has **no auth** in this repo. Do **not** expose the API broadly without adding auth or restricting `/admin` (IP allowlist, separate internal service, or remove the router).
- Keep **`server/.env`** and Railway secrets **private**.
- Prefer **HTTPS** only (Railway provides TLS for `*.up.railway.app`).

---

## 8. Local vs Railway

| | Local | Railway |
|---|--------|---------|
| API URL | `http://localhost:8000` | `https://<api>.up.railway.app` |
| UI env | `ui/.env` | Service variable `NEXT_PUBLIC_API_URL` |
| CORS | `localhost:3000` | Your real UI origin(s) |

---

## 9. Optional: single custom domain

Point **DNS** to Railway, attach **custom domains** on both API and UI services, then set **`CORS_ORIGINS`** and **`NEXT_PUBLIC_API_URL`** to those HTTPS origins and rebuild the UI.
