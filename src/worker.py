from workers import WorkerEntrypoint, Request, Response  # type: ignore
from app.router import match, split_url, respond_json
from app.swagger import swagger_page, openapi_json

# Import endpoints to register them (side-effect of @route)
from app.endpoints import meta, users  # noqa: F401

def respond_error(status: int, msg: str = "Internal Server Error") -> Response:
    return Response(
        f'{{"error":"{msg}"}}',
        status=status,
        headers={"content-type": "application/json; charset=utf-8"},
    )

class Default(WorkerEntrypoint):
    async def fetch(self, request: Request, env):
        # Make sure handlers can read env via req.scope["env"]
        try:
            scope = getattr(request, "scope", None)
            if not isinstance(scope, dict):
                setattr(request, "scope", {})
            request.scope["env"] = env
        except Exception:
            # If even injecting fails, return 500 rather than throwing 1101
            return respond_error(500)

        try:
            path, _query = split_url(request)
            method = request.method

            if path == "/" or path == "/docs":
                return swagger_page()
            if path == "/openapi.json":
                return openapi_json()

            handler, params, _ = match(method, path)
            if not handler:
                return Response("Not found", status=404)

            result = await handler(request, **(params or {}))
            if isinstance(result, Response):
                return result
            return respond_json(result)
        except Exception:
            # Catch-all: never bubble to 1101
            return respond_error(500)