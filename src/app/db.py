from workers import Request, Response  # type: ignore
from urllib.parse import parse_qs
from app.router import route
from app.db import d1_all, d1_first, d1_run

# Schema snippets for OpenAPI
user_body_schema = {
    "type": "object",
    "required": ["email", "name"],
    "properties": {
        "email": {"type": "string", "format": "email"},
        "name": {"type": "string", "minLength": 1}
    }
}

@route("GET", "/api/db/ping", summary="D1 ping", tags=["meta"])
async def db_ping(req: Request):
    row = await d1_first(req, "SELECT 1 AS ok;")
    return {"db": "ok" if row and row.get("ok") == 1 else "fail"}

@route("GET", "/api/users", summary="List users", tags=["users"])
async def list_users(req: Request):
    # /api/users?limit=50&offset=0
    url = str(req.url)
    q = parse_qs(url.split("?", 1)[1] if "?" in url else "")
    try:
        limit = int(q.get("limit", ["50"])[0])
        offset = int(q.get("offset", ["0"])[0])
    except Exception:
        limit, offset = 50, 0
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    rows = await d1_all(
        req,
        "SELECT id, email, name, created_at FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
        limit,
        offset,
    )
    return rows

@route("GET", "/api/users/{id}", summary="Get user", tags=["users"],
       responses={"200": {"description": "User found"}, "404": {"description": "Not found"}})
async def get_user(req: Request, id: str):
    row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE id = ?", id)
    if not row:
        return Response.json({"error": "Not found"}, status=404)
    return row

@route("POST", "/api/users", summary="Create user", tags=["users"],
       request_body=user_body_schema,
       responses={"201": {"description": "Created"}, "400": {"description": "Bad request"}})
async def create_user(req: Request):
    import json
    try:
        data = json.loads(getattr(req, "data", b"") or b"{}")
    except Exception:
        data = {}
    email = (data.get("email") or "").strip()
    name = (data.get("name") or "").strip()
    if not email or not name:
        return Response.json({"error": "email and name are required"}, status=400)

    try:
        await d1_run(req, "INSERT INTO users (email, name) VALUES (?, ?)", email, name)
    except Exception as e:
        # uniqueness etc.
        return Response.json({"error": str(e)}, status=400)

    row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE rowid = last_insert_rowid()")
    return Response.json(row, status=201)

@route("PUT", "/api/users/{id}", summary="Update user", tags=["users"],
       request_body={"type": "object", "properties": {
           "email": {"type":"string", "format":"email"},
           "name": {"type":"string", "minLength": 1}
       }})
async def update_user(req: Request, id: str):
    import json
    try:
        data = json.loads(getattr(req, "data", b"") or b"{}")
    except Exception:
        data = {}

    sets = []
    params = []
    if "email" in data and (data["email"] or "").strip():
        sets.append("email = ?")
        params.append(data["email"].strip())
    if "name" in data and (data["name"] or "").strip():
        sets.append("name = ?")
        params.append(data["name"].strip())

    if not sets:
        row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE id = ?", id)
        if not row:
            return Response.json({"error": "Not found"}, status=404)
        return row

    params.append(id)
    await d1_run(req, f"UPDATE users SET {', '.join(sets)} WHERE id = ?", *params)

    row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE id = ?", id)
    if not row:
        return Response.json({"error": "Not found"}, status=404)
    return row