import json
from workers import Request, Response  # type: ignore
from urllib.parse import urlsplit, parse_qs
from app.router import route, respond_json, json_body
from app.db import d1_run, d1_first, d1_all

# OpenAPI schema for user creation
user_body_schema = {
    "type": "object",
    "required": ["telegram_id", "phone", "name", "role"],
    "properties": {
        "telegram_id": {"type": "integer"},
        "phone": {"type": "string"},
        "name": {"type": "string", "minLength": 1},
        "role": {"type": "string", "enum": ["admin", "user"]}
    }
}


@route("GET", "/api/users", summary="List users", tags=["users"])
async def list_users(req: Request):
    rows = await d1_all(req, """
        SELECT id, telegram_id, phone, name, role, created_at
        FROM users
        ORDER BY id DESC
    """)
    return respond_json([row.to_py() for row in rows])



@route("GET", "/api/users/{telegram_id}", summary="Get user by telegram_id", tags=["users"])
async def get_user(req: Request, telegram_id: int):
    row = await d1_first(req, """
        SELECT id, telegram_id, phone, name, role, created_at
        FROM users
        WHERE telegram_id = ?
    """, telegram_id)
    if not row:
        return respond_json({"error": "Not found"}, status=404)
    return respond_json(row.to_py())




@route("POST", "/api/users", summary="Create user", tags=["users"],
       request_body=user_body_schema,
       responses={"201": {"description": "Created"}, "400": {"description": "Bad request"}})
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

    await d1_run(req, "INSERT INTO users (telegram_id, phone, name, role) VALUES (?, ?, ?, ?)",
                 telegram_id, phone, name, role)

    row = await d1_first(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE telegram_id = ?", telegram_id)
    return respond_json(row, status=201)

@route("PUT", "/api/users/{id}", summary="Update user", tags=["users"],
       request_body={
           "type": "object",
           "properties": {
               "name": {"type": "string", "minLength": 1},
               "phone": {"type": "string"},
               "role": {"type": "string", "enum": ["admin", "user"]}
           }
       },
       responses={
           "200": {"description": "User updated"},
           "400": {"description": "Bad request"},
           "404": {"description": "User not found"}
       })
async def update_user(req: Request, id: str):
    data = await json_body(req) or {}
    sets = []; params = []

    # Проверка на существование пользователя
    existing = await d1_first(req, "SELECT id FROM users WHERE id = ?", id)
    if not existing:
        return respond_json({"error": "User not found"}, status=404)

    # Обновляем name
    if "name" in data and data["name"]:
        sets.append("name = ?"); params.append(data["name"])

    # Обновляем phone с проверкой уникальности
    if "phone" in data and data["phone"]:
        conflict = await d1_first(req, "SELECT id FROM users WHERE phone = ? AND id != ?", data["phone"], id)
        if conflict:
            return respond_json({"error": "Phone already in use"}, status=400)
        sets.append("phone = ?"); params.append(data["phone"])

    # Обновляем role
    if "role" in data and data["role"]:
        sets.append("role = ?"); params.append(data["role"])

    if not sets:
        return respond_json({"error": "No fields to update"}, status=400)

    # Выполняем обновление
    params.append(id)
    await d1_run(req, f"UPDATE users SET {', '.join(sets)} WHERE id = ?", *params)

    # Возвращаем обновлённого пользователя
    row = await d1_first(req, "SELECT id, telegram_id, phone, name, role, created_at FROM users WHERE id = ?", id)
    return respond_json(row.to_py(), status=200)


@route("OPTIONS", "/api/users", summary="CORS preflight", tags=["meta"])
async def options_users(req: Request):
    return Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@route("GET", "/api/slots", summary="Available time slots", tags=["bookings"])
async def get_slots(req: Request):
    query = parse_qs(urlsplit(str(req.url)).query)
    date = query.get("date", [None])[0]

    if not date and req.method == "POST":
        body = await json_body(req) or {}
        date = body.get("date")

    if not date:
        return respond_json({"error": "Missing date"}, status=400)

    all_slots = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    booked_rows = await d1_all(req, "SELECT time FROM bookings WHERE date = ?", date)
    booked_times = [row.to_py()["time"] for row in booked_rows] if booked_rows else []
    available = [slot for slot in all_slots if slot not in booked_times]

    return respond_json({"date": date, "available": available})

@route("GET", "/api/bookings", summary="Get user bookings", tags=["bookings"],
       query_params={
           "user_id": {"type": "integer", "required": True}
       },
       responses={
           "200": {"description": "List of bookings"},
           "400": {"description": "Missing user_id"},
           "500": {"description": "Internal server error"}
       })
async def get_bookings(req: Request):
    try:
        user_id = req.query.get("user_id")
        if not user_id:
            return respond_json({"error": "user_id is required"}, status=400)

        rows = await d1_all(req,
            "SELECT id, date, time FROM bookings WHERE user_id = ? ORDER BY date, time",
            int(user_id)
        )
        return respond_json([row.to_py() for row in rows])

    except Exception as e:
        print(f"❌ Error in get_bookings: {e}")
        return respond_json({"error": "Internal server error"}, status=500)

@route("POST", "/api/bookings", summary="Create booking", tags=["bookings"],
       request_body={
           "type": "object",
           "required": ["user_id", "date", "time"],
           "properties": {
               "user_id": {"type": "integer"},
               "date": {"type": "string"},
               "time": {"type": "string"}
           }
       },
       responses={
           "201": {"description": "Created"},
           "400": {"description": "Bad request"},
           "500": {"description": "Internal server error"}
       })
async def create_booking(req: Request):
    try:
        data = await json_body(req) or {}
        user_id = data.get("user_id")
        date = data.get("date")
        time = data.get("time")

        if not user_id or not date or not time:
            return respond_json({"error": "All fields required"}, status=400)

        # Проверка: пользователь уже записан на этот день
        user_has_booking = await d1_first(
            req,
            "SELECT id FROM bookings WHERE user_id = ? AND date = ?",
            user_id, date
        )
        if user_has_booking:
            return respond_json({"error": "Вы уже записаны на этот день"}, status=400)

        # Проверка: слот занят другим пользователем
        slot_taken = await d1_first(
            req,
            "SELECT id FROM bookings WHERE date = ? AND time = ?",
            date, time
        )
        if slot_taken:
            return respond_json({"error": "Слот уже занят"}, status=400)

        # Создание записи
        await d1_run(req,
            "INSERT INTO bookings (user_id, date, time) VALUES (?, ?, ?)",
            user_id, date, time
        )

        # Возврат созданной записи
        row = await d1_first(req,
            "SELECT * FROM bookings WHERE user_id = ? AND date = ? AND time = ?",
            user_id, date, time
        )
        return respond_json(row.to_py(), status=201)

    except Exception as e:
        print(f"❌ Error in create_booking: {e}")
        return respond_json({"error": "Internal server error"}, status=500)




@route("GET", "/api/bookings", summary="List bookings", tags=["bookings"])
async def list_bookings(req: Request):
    query = parse_qs(urlsplit(str(req.url)).query)
    user_id = query.get("user_id", [None])[0]

    if not user_id:
        return respond_json({"error": "Missing user_id"}, status=400)

    rows = await d1_all(req, """
        SELECT id, user_id, date, time, created_at
        FROM bookings
        WHERE user_id = ?
        ORDER BY date, time
    """, user_id)

    return respond_json([row.to_py() for row in rows])

@route("DELETE", "/api/bookings/{id}", summary="Cancel booking", tags=["bookings"],
       responses={
           "200": {"description": "Booking cancelled"},
           "404": {"description": "Booking not found"}
       })
async def cancel_booking(req: Request, id: str):
    row = await d1_first(req, "SELECT id FROM bookings WHERE id = ?", id)
    if not row:
        return respond_json({"error": "Booking not found"}, status=404)

    await d1_run(req, "DELETE FROM bookings WHERE id = ?", id)
    return respond_json({"ok": True}, status=200)


@route("OPTIONS", "/api/bookings", summary="CORS preflight", tags=["meta"])
async def options_bookings(req: Request):
    return Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })