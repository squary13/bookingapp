from workers import WorkerEntrypoint, Request, Response  # type: ignore

# Register routes by importing modules that use @route
from app.endpoints import meta as _meta  # noqa: F401
from app.endpoints import users as _users  # noqa: F401

from app.router import route, match, split_url  # type: ignore
from app.swagger import openapi_json, swagger_html  # type: ignore


class Default(WorkerEntrypoint):
    async def fetch(self, request: Request, env):
        try:
            # Make env available to handlers (used by D1 helpers)
            if not hasattr(request, "scope"):
                request.scope = {}  # type: ignore[attr-defined]
            request.scope["env"] = env  # type: ignore[index]

            path, _query = split_url(request)
            method = request.method

            # Built-ins
            if path == "/":
                return Response.json({"hello": "world"})
            if path == "/openapi.json":
                return Response.json(openapi_json())
            if path == "/docs":
                return Response(swagger_html(), headers={"content-type": "text/html; charset=utf-8"})

            # Route to handlers
            handler, params, _meta = match(method, path)
            if not handler:
                return Response("Not found", status=404)

            result = await handler(request, **(params or {}))

            if isinstance(result, Response):
                return result
            return Response.json(result)

        except Exception as e:
            # Last-resort error guard
            return Response.json({"error": "Internal Server Error", "detail": str(e)}, status=500)