from workers import Request, Response  # type: ignore
from urllib.parse import parse_qs
from app.router import route, respond_json, json_body
from app.db import d1_run, d1_first, d1_all

# OpenAPI schema for user creation
user_body_schema = {
    "type": "object",
    "required": ["email", "name", "phone"],
    "properties": {
        "email": {"type": "string", "format": "email"},
        "name": {"type": "string", "minLength": 1},
        "phone": {"type": "string"}
    }
}

@route("GET", "/api/users", summary="List users", tags=["users"])
async def list_users(req: Request):
    rows = await d1_all(req, "SELECT id, email, name, created_at FROM users ORDER BY id DESC")
    return respond_json(rows)

@route("GET", "/api/users/{id}", summary="Get user by id", tags=["users"],
       responses={"200": {"description": "OK"}, "404": {"description": "Not found"}})
async def get_user(req: Request, id: str):
    row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE id = ?", id)
    if not row:
        return respond_json({"error": "Not found"}, status=404)
    return respond_json(row)

@route("POST", "/api/users", summary="Create user", tags=["users"],
       request_body=user_body_schema,
       responses={"201": {"description": "Created"}, "400": {"description": "Bad request"}})
async def create_user(req: Request):
    data = json_body(req) or {}
    print("Incoming JSON:", data)

    email = data.get("email")
    name = data.get("name")
    phone = data.get("phone")  
    print("Parsed email:", email, "| name:", name, "| phone:", phone)

    if not email or not name:
        print("Missing required fields")
        return respond_json({"error": "email and name are required"}, status=400)

    try:
        if phone:
            await d1_run(req, "INSERT INTO users (email, name, phone) VALUES (?, ?, ?)", email, name, phone)
        else:
            await d1_run(req, "INSERT INTO users (email, name) VALUES (?, ?)", email, name)
        print("✅ User inserted successfully:", email)
    except Exception as e:
        print("SQL insert error:", str(e))
        return respond_json({"error": str(e)}, status=400)

    row = await d1_first(req, "SELECT id, email, name, phone, created_at FROM users WHERE email = ?", email)
    print("Fetched user row:", row)
    return respond_json(row, status=201)


@route("PUT", "/api/users/{id}", summary="Update user", tags=["users"],
       request_body={"type": "object", "properties": {
           "email": {"type": "string", "format": "email"},
           "name": {"type": "string", "minLength": 1}
       }})
async def update_user(req: Request, id: str):
    data = json_body(req) or {}
    sets = []; params = []

    if "email" in data and data["email"]:
        sets.append("email = ?"); params.append(data["email"])
    if "name" in data and data["name"]:
        sets.append("name = ?"); params.append(data["name"])

    if not sets:
        row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE id = ?", id)
        if not row:
            return respond_json({"error": "Not found"}, status=404)
        return respond_json(row)

    params.append(id)
    await d1_run(req, f"UPDATE users SET {', '.join(sets)} WHERE id = ?", *params)
    row = await d1_first(req, "SELECT id, email, name, created_at FROM users WHERE id = ?", id)
    if not row:
        return respond_json({"error": "Not found"}, status=404)
    return respond_json(row)

@route("OPTIONS", "/api/users", summary="CORS preflight", tags=["meta"])
async def options_users(req: Request):
    return Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@route("GET", "/api/slots", summary="Available time slots", tags=["bookings"])
async def get_slots(req: Request):
    date = parse_qs(req.scope["query"]).get("date", [""])[0]
    if not date:
        return respond_json({"error": "Missing date"}, status=400)

    all_slots = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    booked = await d1_all(req, "SELECT time FROM bookings WHERE date = ?", date)
    booked_times = [row["time"] for row in booked]

    available = [t for t in all_slots if t not in booked_times]
    return respond_json({"date": date, "available": available})
