# src/worker.py
from workers import WorkerEntrypoint, Request
import asgi  # Cloudflare's ASGI adapter
from fastapi import FastAPI

app = FastAPI(
    title="Hello Python Worker",
    # keep docs on; if you still hit CPU limit, set docs_url=None, redoc_url=None
)

@app.get("/")
async def root():
    return {"message": "hello from FastAPI on Python Workers"}

# Lazy Jinja import so it doesn't run at module import time
_jinja_env = None
def get_jinja_env():
    global _jinja_env
    if _jinja_env is None:
        from jinja2 import Environment
        _jinja_env = Environment()
    return _jinja_env

@app.get("/hi/{name}")
async def say_hi(name: str):
    tmpl = get_jinja_env().from_string("Hello, {{ name }}!")
    return {"message": tmpl.render(name=name)}

@app.get("/env")
async def env(req: Request):
    # asgi.fetch() will inject `env` into ASGI scope
    cf_env = req.scope["env"]
    return {"message": f"env MESSAGE: {cf_env.MESSAGE}"}

class Default(WorkerEntrypoint):
    async def fetch(self, request: Request):
        # IMPORTANT: pass `request`, not request.js_object
        return await asgi.fetch(app, request, self.env)