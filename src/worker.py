from workers import WorkerEntrypoint, Request, Response  # type: ignore
from app.router import match, split_url, respond_json
from app.swagger import swagger_page, openapi_json
import traceback

# Импорт эндпоинтов (через @route)
from app.endpoints import meta, users  # noqa: F401

# 🔧 Общие CORS заголовки
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization"
}

def respond_error(status: int, msg: str = "Internal Server Error") -> Response:
    return wrap_with_cors(Response(
        f'{{"error":"{msg}"}}',
        status=status,
        headers={"content-type": "application/json; charset=utf-8"},
    ))

def respond_cors_preflight() -> Response:
    return Response(
        "",
        status=204,
        headers=CORS_HEADERS,
    )

def wrap_with_cors(response: Response) -> Response:
    # Добавляем все нужные заголовки
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response

class Default(WorkerEntrypoint):
    async def fetch(self, request: Request, env):
        try:
            if not isinstance(getattr(request, "scope", None), dict):
                request.scope = {}
            request.scope["env"] = self.env

            # Проверка базы (для отладки)
            try:
                db = self.env.DB
                stmt = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                result = await stmt.first()
                print("🔍 Table 'users' exists:", bool(result))
            except Exception as e:
                print("❌ DB access failed:", e)

        except Exception:
            return respond_error(500)

        try:
            path, _query = split_url(request)
            method = request.method

            # ⚙️ Обработка preflight
            if method == "OPTIONS":
                return respond_cors_preflight()

            if path == "/" or path == "/docs":
                return wrap_with_cors(swagger_page())
            if path == "/openapi.json":
                return wrap_with_cors(openapi_json())

            handler, params, _ = match(method, path)
            if not handler:
                return wrap_with_cors(Response("Not found", status=404))

            result = await handler(request, **(params or {}))
            if isinstance(result, Response):
                return wrap_with_cors(result)
            return wrap_with_cors(respond_json(result))

        except Exception as e:
            print("UNHANDLED ERROR:", e)
            print(traceback.format_exc())
            return respond_error(500)
