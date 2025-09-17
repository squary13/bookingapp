from workers import WorkerEntrypoint, Response
import asgi  # Cloudflare's ASGI adapter

_app = None  # lazy-initialized FastAPI app

def _build_app():
    # Lazy import to avoid startup CPU on cold boot
    from fastapi import FastAPI

    app = FastAPI(
        title="Booking API (Python Workers)",
        version="0.0.1",
        # If you hit startup CPU errors again, temporarily set these to None:
        docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.get("/health", tags=["meta"])
    async def health():
        return {"ok": True}

    return app

class Default(WorkerEntrypoint):
    async def fetch(self, request, env):
        # cheap root route (no FastAPI import)
        if request.url.pathname == "/":
            return Response.json({"hello": "world"})

        # lazily create FastAPI app only when needed
        global _app
        if _app is None:
            _app = _build_app()

        # delegate to FastAPI via ASGI adapter (this injects env into scope)
        return await asgi.fetch(_app, request, env)