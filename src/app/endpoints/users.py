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

@route("GET", "/api/users", summary="List users", tags=["users"])
async def list_users(req: Request):
    env = req.scope["env"]
    db = D1(env)
    rows = await db.all("SELECT id, email, name, created_at FROM users ORDER BY id DESC")
    return rows

@route("GET", "/api/users/{id}", summary="Get user by id", tags=["users"],
       responses={"200": {"description": "OK"}, "404": {"description": "Not found"}})
async def get_user(req: Request, id: str):
    env = req.scope["env"]; db = D1(env)
    row = await db.first("SELECT id, email, name, created_at FROM users WHERE id = ?", id)
    if not row:
        return respond_json({"error": "Not found"}, status=404)
    return row

@route("POST", "/api/users", summary="Create user", tags=["users"],
       request_body=user_body_schema,
       responses={"201": {"description": "Created"}, "400": {"description": "Bad request"}})
async def create_user(req: Request):
    env = req.scope["env"]; db = D1(env)
    data = json_body(req) or {}
    email = data.get("email"); name = data.get("name")
    if not email or not name:
        return respond_json({"error": "email and name are required"}, status=400)

    try:
        await db.run("INSERT INTO users (email, name) VALUES (?, ?)", email, name)
    except Exception as e:
        # uniqueness etc.
        return respond_json({"error": str(e)}, status=400)

    row = await db.first("SELECT id, email, name, created_at FROM users WHERE email = ?", email)
    return respond_json(row, status=201)

@route("PUT", "/api/users/{id}", summary="Update user", tags=["users"],
       request_body={"type": "object", "properties": {
           "email": {"type":"string", "format":"email"},
           "name": {"type":"string", "minLength": 1}
       }})
async def update_user(req: Request, id: str):
    env = req.scope["env"]; db = D1(env)
    data = json_body(req) or {}
    sets = []; params = []

    if "email" in data and data["email"]:
        sets.append("email = ?"); params.append(data["email"])
    if "name" in data and data["name"]:
        sets.append("name = ?"); params.append(data["name"])

    # No fields to update → just return current user (or 404)
    if not sets:
        row = await db.first("SELECT id, email, name, created_at FROM users WHERE id = ?", id)
        if not row: return respond_json({"error": "Not found"}, status=404)
        return row

    params.append(id)
    await db.run(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", *params)
    row = await db.first("SELECT id, email, name, created_at FROM users WHERE id = ?", id)
    if not row: return respond_json({"error": "Not found"}, status=404)
    return row