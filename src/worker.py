from workers import WorkerEntrypoint, Request, Response
import json, re
from urllib.parse import parse_qs

# -------------------------------
# Minimal router + OpenAPI builder
# -------------------------------

_routes = []  # registry of (method, path, pattern, param_names, handler, meta)

def route(method: str, path: str, *, summary: str = "", request_body: dict | None = None, responses: dict | None = None, tags: list[str] | None = None):
    """
    Register an endpoint and its OpenAPI metadata.
    Path params use {name} (e.g., /users/{id})
    """
    def decorator(fn):
        # convert /users/{id} -> ^/users/(?P<id>[^/]+)$
        param_names = re.findall(r"{(\w+)}", path)
        pattern_str = "^" + re.sub(r"{(\w+)}", r"(?P<\1>[^/]+)", path) + "$"
        pattern = re.compile(pattern_str)
        meta = {
            "summary": summary or fn.__name__,
            "requestBody": request_body,
            "responses": responses or {"200": {"description": "OK"}},
            "tags": tags or [],
        }
        _routes.append((method.upper(), path, pattern, param_names, fn, meta))
        return fn
    return decorator

def _match(method: str, pathname: str):
    for m, path, regex, params, fn, meta in _routes:
        if m == method and (m := regex.match(pathname)):
            return fn, m.groupdict(), meta
    return None, None, None

def _parse_json_body(req: Request):
    try:
        return json.loads(req.data or b"")
    except Exception:
        return None

# ---------------
# OpenAPI (auto)
# ---------------
def _openapi():
    paths = {}
    for method, path, _regex, _params, _fn, meta in _routes:
        if path not in paths:
            paths[path] = {}
        op = {
            "summary": meta["summary"],
            "responses": meta["responses"],
        }
        if meta["requestBody"]:
            op["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": meta["requestBody"]}},
            }
        if meta["tags"]:
            op["tags"] = meta["tags"]
        paths[path][method.lower()] = op

    return {
        "openapi": "3.0.3",
        "info": {"title": "Python Worker API", "version": "1.0.0"},
        "paths": paths,
    }

_SWAGGER_HTML = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Swagger UI</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css"/>
  </head>
  <body>
    <div id="swagger"></div>
    <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
    <script>
      SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger' });
    </script>
  </body>
</html>
"""

# -----------------------
# Example API endpoints
# -----------------------

@route("GET", "/health", summary="Health check", tags=["meta"])
async def health(_req: Request):
    return {"ok": True}

@route("GET", "/hello", summary="Say hello", tags=["demo"])
async def hello(req: Request):
    # query: /hello?name=Sergejs
    q = parse_qs(req.url.search[1:] if req.url.search else "")
    name = q.get("name", ["world"])[0]
    return {"message": f"Hello, {name}!"}

@route("GET", "/users/{id}", summary="Get user by id", tags=["users"],
       responses={"200": {"description": "User found"}, "404": {"description": "Not found"}})
async def get_user(_req: Request, id: str):
    # demo only; no DB here yet
    if id == "1":
        return {"id": 1, "email": "demo@example.com", "name": "Demo User"}
    return Response.json({"error": "Not found"}, status=404)

@route("POST", "/users", summary="Create user", tags=["users"],
       request_body={"type": "object", "required": ["email", "name"], "properties": {
           "email": {"type": "string", "format": "email"},
           "name": {"type": "string", "minLength": 1}
       }},
       responses={"201": {"description": "Created"}, "400": {"description": "Bad request"}})
async def create_user(req: Request):
    data = _parse_json_body(req) or {}
    email = data.get("email")
    name = data.get("name")
    if not email or not name:
        return Response.json({"error": "email and name are required"}, status=400)
    # demo only; would INSERT into D1 here
    return Response.json({"id": 123, "email": email, "name": name}, status=201)

# -------------
# Worker entry
# -------------
class Default(WorkerEntrypoint):
    async def fetch(self, request: Request, env):
        path = request.url.pathname
        method = request.method

        # cheap routes first (no registry scan)
        if path == "/":
            return Response.json({"hello": "world"})
        if path == "/openapi.json":
            return Response.json(_openapi())
        if path == "/docs":
            return Response(_SWAGGER_HTML, headers={"content-type": "text/html; charset=utf-8"})

        # route matching
        handler, params, _meta = _match(method, path)
        if not handler:
            return Response("Not found", status=404)

        # call endpoint
        result = await handler(request, **(params or {}))

        # If handler returned a ready Response, pass through.
        if isinstance(result, Response):
            return result
        # Otherwise JSON-ify
        return Response.json(result)