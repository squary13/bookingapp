# src/worker.py
from workers import WorkerEntrypoint, Request, Response
import asgi  # CF's ASGI adapter

# Global cache for the FastAPI app, but DO NOT import fastapi at module load.
_fastapi_app = None

async def get_app():
    global _fastapi_app
    if _fastapi_app is None:
        # Lazy imports to avoid startup CPU
        from fastapi import FastAPI
        from jinja2 import Environment

        app = FastAPI(
            title="Hello Python Worker",
            # keep docs off initially to reduce import cost; re-enable later
            docs_url=None, redoc_url=None, openapi_url=None
        )

        jinja_env = Environment()

        @app.get("/hi/{name}")
        async def say_hi(name: str):
            tmpl = jinja_env.from_string("Hello, {{ name }}!")
            return {"message": tmpl.render(name=name)}

        @app.get("/env")
        async def env(req: Request):
            cf_env = req.scope["env"]
            return {"message": f"env MESSAGE: {cf_env.MESSAGE}"}

        _fastapi_app = app
    return _fastapi_app

class Default(WorkerEntrypoint):
    async def fetch(self, request: Request):
        # ultra-cheap health route handled without importing FastAPI
        url = request.url
        if url.pathname == "/" or url.pathname == "/api/health":
            return Response.json({"ok": True})

        # For anything else, lazy-init FastAPI and delegate via ASGI
        app = await get_app()
        return await asgi.fetch(app, request, self.env)