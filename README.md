# booking-worker-py-be

Minimal Python (Workers-Python) API on Cloudflare Workers with:
- Tiny router + auto OpenAPI/Swagger (`/docs`, `/openapi.json`)
- D1 database (migrations via Wrangler)
- Users CRUD: `GET/POST/PUT /api/users`, `GET /api/users/{id}`
- Safe error handling (no 1101 Cloudflare error pages)

## Stack

- Cloudflare **Workers** (Python, experimental)
- **D1** (SQLite on Cloudflare)
- **Wrangler** CLI
- No external Python deps at runtime (tiny + fast cold starts)

## Endpoints

- `GET /health` – liveness probe  
- `GET /docs` – Swagger UI  
- `GET /openapi.json` – OpenAPI 3.0  
- `GET /api/db/ping` – quick DB sanity  
- `GET /api/users?limit=&offset=` – list users  
- `POST /api/users` – create
- `GET /api/users/{id}` – fetch by id  
- `PUT /api/users/{id}` – update

## Prereqs

- Node.js 18+  
- `npx` available  
- Cloudflare account (D1 + Workers)  
- `wrangler.toml` already contains:

```toml
name = "booking-worker-py-be"
main = "src/worker.py"
compatibility_date = "2025-08-14"
compatibility_flags = ["python_workers"]
workers_dev = true

[observability.logs]
enabled = true

[[d1_databases]]
binding = "DB"
database_name = "booking-db"
# database_id is optional for local dev; present in deploy env
# database_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"