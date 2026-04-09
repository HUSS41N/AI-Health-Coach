# Deploying on Railway

## Docker build: `requirements.txt` not found

Railway often uses the **git repository root** as the Docker build context. The API’s `requirements.txt` lives under **`server/`**, so `COPY requirements.txt` in `server/Dockerfile` fails unless the service **Root Directory** is `server`.

**Fix (pick one):**

1. **Root Directory = `server`**  
   Service → Settings → **Root Directory** → `server`  
   Dockerfile: default `Dockerfile` (same as `server/Dockerfile`).

2. **Root Directory = empty (repo root)**  
   Set **Dockerfile path** to **`Dockerfile.api`** at the **repository root**. That file runs `COPY server/requirements.txt` and `COPY server/`.

Local **`docker compose`** uses **`Dockerfile.api`** from the repo root so it matches option 2.

---

## Services and env

- **API** (`server/` or root + `Dockerfile.api`): `DATABASE_URL`, Upstash Redis vars, `CORS_ORIGINS`, `OPENAI_*`, `GROQ_*`, etc. See `server/.env.example` and `server/railway.variables.template.json`.
- **UI** (`ui/`): set **`NEXT_PUBLIC_API_URL`** to the API’s **public HTTPS URL** before build (Next bakes it in).
- **`CORS_ORIGINS`** on the API must include your **exact** UI origin(s), no trailing slash.

---

## Health checks

- API: `GET /health` (see `server/railway.toml` when root is `server`).
- UI: `GET /` (see `ui/railway.toml`).

---

## Security

`/admin` is unauthenticated in this repo—protect it before a public launch.
