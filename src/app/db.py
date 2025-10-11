# src/app/db.py
from workers import Request  # type: ignore

def get_env(req: Request):
    scope = getattr(req, "scope", None)
    print("🔍 scope in get_env:", scope)
    return scope.get("env") if isinstance(scope, dict) else None



async def d1_all(req: Request, sql: str, *params):
    env = get_env(req)
    stmt = env.DB.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    res = await stmt.all()
    # Cloudflare's Python D1 returns an object with `.results`
    return res.results

async def d1_run(req: Request, sql: str, *params):
    """
    Execute a statement where we don't need rows back.
    Some drivers support `.run()`. If not present, `.all()` still executes.
    """
    env = get_env(req)
    env = get_env(req)
    print("🔍 env in create_user:", env)
    print("🔍 env.DB in create_user:", getattr(env, "DB", None))

    stmt = env.DB.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    run = getattr(stmt, "run", None)
    if callable(run):
        return await run()
    else:
        # Fallback: force execution
        return await stmt.all()

async def d1_first(req: Request, sql: str, *params):
    rows = await d1_all(req, sql, *params)
    return rows[0] if rows else None