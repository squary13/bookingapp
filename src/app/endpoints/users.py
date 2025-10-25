import json
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

# BOOKINGS

@route("GET", "/api/slots")
async def get_slots(req: Request):
    try:
        date = get_query_param(req, "date", required=True)
    except ValueError as e:
        return respond_json({"error": str(e)}, status=400)

    all_slots = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    booked_rows = await d1_all(req, "SELECT time FROM bookings WHERE date = ?", date)
    booked_times = [row.to_py()["time"] for row in booked_rows] if booked_rows else []
    available = [slot for slot in all_slots if slot not in booked_times]

    return respond_json({"date": date, "available": available})

@route("GET", "/api/bookings")
async def get_bookings(req: Request):
    try:
        user_id = get_query_param(req, "user_id", required=True, cast=int)
        rows = await d1_all(req, "SELECT id, date, time FROM bookings WHERE user_id = ? ORDER BY date, time", user_id)
        return respond_json([row.to_py() for row in rows])
    except ValueError as e:
        return respond_json({"error": str(e)}, status=400)
    except Exception as e:
        print(f"❌ Error in get_bookings: {e}")
        return respond_json({"error": "Internal server error"}, status=500)

@route("POST", "/api/bookings")
async def create_booking(req: Request):
    try:
        data = await json_body(req) or {}
        user_id = data.get("user_id")
        date = data.get("date")
        time = data.get("time")

        if not user_id or not date or not time:
            return respond_json({"error": "All fields required"}, status=400)

        user_has_booking = await d1_first(req, "SELECT id FROM bookings WHERE user_id = ? AND date = ?", user_id, date)
        if user_has_booking:
            return respond_json({"error": "Вы уже записаны на этот день"}, status=400)

        slot_taken = await d1_first(req, "SELECT id FROM bookings WHERE date = ? AND time = ?", date, time)
        if slot_taken:
            return respond_json({"error": "Слот уже занят"}, status=400)

        await d1_run(req, "INSERT INTO bookings (user_id, date, time) VALUES (?, ?, ?)", user_id, date, time)
        row = await d1_first(req, "SELECT * FROM bookings WHERE user_id = ? AND date = ? AND time = ?", user_id, date, time)
        return respond_json(row.to_py(), status=201)
    except Exception as e:
        print(f"❌ Error in create_booking: {e}")
        return respond_json({"error": "Internal server error"}, status=500)

@route("DELETE", "/api/bookings/{id}")
async def cancel_booking(req: Request, id: str):
    row = await d1_first(req, "SELECT id FROM bookings WHERE id = ?", id)
    if not row:
        return respond_json({"error": "Booking not found"}, status=404)

    await d1_run(req, "DELETE FROM bookings WHERE id = ?", id)
    return respond_json({"ok": True}, status=200)
