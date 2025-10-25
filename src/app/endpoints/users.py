import json
import os
from workers import Request, Response  # type: ignore
from urllib.parse import urlsplit, parse_qs
from app.router import route, json_body
from app.db import d1_run, d1_first, d1_all
from typing import Callable, Any

def respond_json(data, status=200):
    return Response(json.dumps(data), status=status, headers={
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

def get_query_param(req: Request, name: str, required: bool = False, cast: Callable = str) -> Any:
    query = parse_qs(urlsplit(str(req.url)).query)
    value = query.get(name, [None])[0]

    if required and value is None:
        raise ValueError(f"Missing required query parameter: {name}")

    try:
        return cast(value) if value is not None else None
    except Exception:
        raise ValueError(f"Invalid value for query parameter '{name}': {value}")

def serve_static(filename: str) -> Response:
    path = os.path.join("src", "app", "mini-app", filename)
    if not os.path.exists(path):
        return Response("File not found", status=404)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    content_type = "text/html" if filename.endswith(".html") else "text/javascript"
    return Response(content, status=200, headers={"Content-Type": content_type})

@route("OPTIONS", "/{any}")
async def options_all(req: Request, any: str):
    return Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

# USERS

@route("GET", "/api/users")
async def list_users(req: Request):
    rows = await d1_all(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users ORDER BY id DESC")
    return respond_json([row.to_py() for row in rows])

@route("GET", "/api/users/{telegram_id}")
async def get_user(req: Request, telegram_id: int):
    row = await d1_first(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE telegram_id = ?", telegram_id)
    if not row:
        return respond_json({"error": "Not found"}, status=404)
    return respond_json(row.to_py())

@route("POST", "/api/users")
async def create_user(req: Request):
    data = await json_body(req) or {}
    telegram_id = data.get("telegram_id")
    phone = data.get("phone")
    name = data.get("name")
    role = data.get("role")

    if telegram_id is None or phone is None or name is None or role is None:
        return respond_json({"error": "All fields are required"}, status=400)

    exists = await d1_first(req, "SELECT id FROM users WHERE telegram_id = ? OR phone = ?", telegram_id, phone)
    if exists:
        return respond_json({"error": "User with this telegram_id or phone already exists"}, status=400)

    await d1_run(req, "INSERT INTO users (telegram_id, phone, name, role) VALUES (?, ?, ?, ?)", telegram_id, phone, name, role)
    row = await d1_first(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE telegram_id = ?", telegram_id)
    return respond_json(row.to_py(), status=201)

@route("PUT", "/api/users/{id}")
async def update_user(req: Request, id: str):
    data = await json_body(req) or {}
    sets = []; params = []

    existing = await d1_first(req, "SELECT id FROM users WHERE id = ?", id)
    if not existing:
        return respond_json({"error": "User not found"}, status=404)

    if "name" in data and data["name"]:
        sets.append("name = ?"); params.append(data["name"])

    if "phone" in data and data["phone"]:
        conflict = await d1_first(req, "SELECT id FROM users WHERE phone = ? AND id != ?", data["phone"], id)
        if conflict:
            return respond_json({"error": "Phone already in use"}, status=400)
        sets.append("phone = ?"); params.append(data["phone"])

    if "role" in data and data["role"]:
        sets.append("role = ?"); params.append(data["role"])

    if not sets:
        return respond_json({"error": "No fields to update"}, status=400)

    params.append(id)
    await d1_run(req, f"UPDATE users SET {', '.join(sets)} WHERE id = ?", *params)
    row = await d1_first(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE id = ?", id)
    return respond_json(row.to_py(), status=200)

@route("DELETE", "/api/users/{telegram_id}")
async def delete_user(req: Request, telegram_id: int):
    user = await d1_first(req, "SELECT id FROM users WHERE telegram_id = ?", telegram_id)
    if not user:
        return respond_json({"error": "User not found"}, status=404)

    user_id = user.to_py()["id"]
    await d1_run(req, "DELETE FROM bookings WHERE user_id = ?", user_id)
    await d1_run(req, "DELETE FROM users WHERE id = ?", user_id)

    return respond_json({"ok": True}, status=200)

@route("GET", "/api/bookings/by-user/{telegram_id}")
async def get_bookings_by_telegram(req: Request, telegram_id: int):
    user = await d1_first(req, "SELECT id FROM users WHERE telegram_id = ?", telegram_id)
    if not user:
        return respond_json({"error": "User not found"}, status=404)

    user_id = user.to_py()["id"]
    rows = await d1_all(req, "SELECT id, date, time FROM bookings WHERE user_id = ? ORDER BY date DESC, time DESC", user_id)
    return respond_json([row.to_py() for row in rows])

@route("GET", "/admin")
async def serve_admin(req: Request):
    token = get_query_param(req, "key")
    if token != "adminsecret":
        return Response("Unauthorized", status=403)
    return await serve_static("admin.html")
