from workers import Request, Response  # type: ignore
import json, re
from urllib.parse import urlsplit, parse_qs
from typing import Callable, Any

# -------------------------------
# Minimal router + OpenAPI registry
# -------------------------------
_routes: list[tuple[str, str, re.Pattern[str], list[str], Callable[..., Any], dict]] = []

def route(method: str, path: str, *, summary: str = "", request_body: dict | None = None,
          responses: dict | None = None, tags: list[str] | None = None):
    """
    Register endpoint and OpenAPI metadata. Path params are {name}.
    """
    def decorator(fn: Callable[..., Any]):
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

def match(method: str, pathname: str):
    for m, path, regex, params, fn, meta in _routes:
        mobj = (m == method) and regex.match(pathname)
        if mobj:
            return fn, mobj.groupdict(), meta
    return None, None, None

# -------------------------------
# Helpers
# -------------------------------
def split_url(request: Request) -> tuple[str, str]:
    parts = urlsplit(str(request.url))
    return (parts.path or "/"), (parts.query or "")

async def json_body(req):
    try:
        return await req.json()
    except Exception:
        return None



def respond_json(obj: Any, status: int = 200) -> Response:
    # Convert JsProxy to dict if needed
    if hasattr(obj, "to_py"):
        obj = obj.to_py()
    return Response(json.dumps(obj), status=status,
                    headers={"content-type": "application/json; charset=utf-8",
                             "Access-Control-Allow-Origin": "*"})

