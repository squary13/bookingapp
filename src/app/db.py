from workers import Request  # type: ignore

# ---- D1 helpers (no imports from app.db to avoid circular imports) ----

def _db(req: Request):
    # Attach env in worker before calling handlers: request.scope["env"] = env
    env = getattr(req, "scope", {}).get("env") if hasattr(req, "scope") else None
    if env is None:
        # Fallback for older workers runtime shapes
        env = getattr(req, "env", None)
    if env is None or not hasattr(env, "DB"):
        raise RuntimeError("D1 binding not available on request.env / request.scope['env']")
    return env.DB

async def d1_all(req: Request, sql: str, *params):
    stmt = _db(req).prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    res = await stmt.all()
    # Cloudflare returns an object with .results
    return getattr(res, "results", res)

async def d1_first(req: Request, sql: str, *params):
    rows = await d1_all(req, sql, *params)
    return rows[0] if rows else None

async def d1_run(req: Request, sql: str, *params):
    stmt = _db(req).prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    # We don't need results for mutations
    return await stmt.run()