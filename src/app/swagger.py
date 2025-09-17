from workers import Response  # type: ignore
import json
from .router import _routes, respond_json

def openapi_schema():
    paths: dict = {}
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

SWAGGER_HTML = """<!DOCTYPE html>
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

def swagger_page() -> Response:
    return Response(SWAGGER_HTML, headers={"content-type": "text/html; charset=utf-8"})

def openapi_json() -> Response:
    return Response(json.dumps(openapi_schema()),
                    headers={"content-type": "application/json; charset=utf-8"})