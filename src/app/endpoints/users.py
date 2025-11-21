import json
from workers import Request, Response  # type: ignore
from urllib.parse import urlsplit, parse_qs
from app.router import route, json_body
from app.db import d1_run, d1_first, d1_all
from typing import Callable, Any
from datetime import datetime, timedelta

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

# ---------------- USERS ----------------

@route("GET", "/api/users")
async def list_or_query_users(req: Request):
    telegram_id = get_query_param(req, "telegram_id")
    phone = get_query_param(req, "phone")
    if telegram_id:
        rows = await d1_all(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE telegram_id = ?", telegram_id)
    elif phone:
        rows = await d1_all(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE phone = ?", phone)
    else:
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

    existing = await d1_first(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE telegram_id = ? OR phone = ?", telegram_id, phone)
    if existing:
        return respond_json(existing.to_py(), status=200)

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

# ---------------- BOOKINGS ----------------

@route("GET", "/api/bookings/by-user/{telegram_id}")
async def get_bookings_by_telegram(req: Request, telegram_id: int):
    user = await d1_first(req, "SELECT id FROM users WHERE telegram_id = ?", telegram_id)
    if not user:
        return respond_json({"error": "User not found"}, status=404)
    user_id = user.to_py()["id"]
    rows = await d1_all(req, "SELECT id, date, time FROM bookings WHERE user_id = ? ORDER BY date DESC, time DESC", user_id)
    return respond_json([row.to_py() for row in rows])

@route("POST", "/api/bookings")
async def create_booking(req: Request):
    data = await json_body(req) or {}
    user_id = data.get("user_id")
    date = data.get("date")
    time = data.get("time")

    if user_id is None or date is None or time is None:
        return respond_json({"error": "All fields are required"}, status=400)

    # Проверка существования пользователя
    user = await d1_first(req, "SELECT id FROM users WHERE id = ?", user_id)
    if not user:
        return respond_json({"error": "User not found"}, status=404)

    # Ищем свободный слот (у админа)
    admin = await d1_first(req, "SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    if not admin:
        return respond_json({"error": "No admin found"}, status=400)
    admin_id = admin.to_py()["id"] if hasattr(admin, "to_py") else admin["id"]

    slot = await d1_first(
        req,
        "SELECT id FROM bookings WHERE user_id = ? AND date = ? AND time = ?",
        admin_id, date, time
    )
    if not slot:
        return respond_json({"error": "Slot not available"}, status=404)

    # Обновляем слот: назначаем его пользователю
    await d1_run(req, "UPDATE bookings SET user_id = ? WHERE id = ?", user_id, slot.to_py()["id"])

    # Возвращаем обновлённую запись
    row = await d1_first(req, "SELECT id, user_id, date, time FROM bookings WHERE id = ?", slot.to_py()["id"])
    return respond_json(row.to_py(), status=200)


@route("DELETE", "/api/bookings/{id}")
async def delete_booking(req: Request, id: int):
    existing = await d1_first(req, "SELECT id FROM bookings WHERE id = ?", id)
    if not existing:
        return respond_json({"error": "Booking not found"}, status=404)
    await d1_run(req, "DELETE FROM bookings WHERE id = ?", id)
    return respond_json({"ok": True}, status=200)

# ---------------- DATES ----------------

@route("GET", "/api/available-dates")
async def get_available_dates(req: Request):
    # Возвращаем уникальные даты, где есть хоть одна запись
    rows = await d1_all(req, "SELECT DISTINCT date FROM bookings ORDER BY date ASC")
    # D1 возвращает объекты с .to_py(), но на всякий случай поддержим словари
    def get_date(row):
        return row.to_py()["date"] if hasattr(row, "to_py") else row["date"]
    dates = [get_date(row) for row in rows]
    return respond_json({"dates": dates})


@route("POST", "/api/generate-slots")
async def generate_slots(req: Request):
    # Параметры генерации (необязательные): дней вперёд и список слотов
    body = await json_body(req) or {}
    days_ahead = int(body.get("days", 30))  # по умолчанию 30 дней
    times = body.get("times") or ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]

    today = datetime.today()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]

    # Нужен админ — слоты создаются на него, чтобы отличать админские открытия
    admin = await d1_first(req, "SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    if not admin:
        return respond_json({"error": "Нет администратора"}, status=400)
    user_id = admin.to_py()["id"] if hasattr(admin, "to_py") else admin["id"]

    generated = 0
    skipped_weekend = 0
    skipped_existing = 0

    for date in dates:
        # Пропускаем выходные (суббота/воскресенье)
        if datetime.strptime(date, "%Y-%m-%d").weekday() >= 5:
            skipped_weekend += 1
            continue

        for time in times:
            # Защита от дублей: если уже есть запись (для любого пользователя), не добавляем
            exists = await d1_first(
                req,
                "SELECT id FROM bookings WHERE date = ? AND time = ?",
                date, time
            )
            if exists:
                skipped_existing += 1
                continue

            await d1_run(
                req,
                "INSERT INTO bookings (user_id, date, time) VALUES (?, ?, ?)",
                user_id, date, time
            )
            generated += 1

    return respond_json({
        "ok": True,
        "generated": generated,
        "skipped_weekend_days": skipped_weekend,
        "skipped_existing_slots": skipped_existing,
        "days_considered": days_ahead,
        "times_used": times
    }, status=200)
