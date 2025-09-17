from workers import Request  # type: ignore
from ..router import route, respond_json

@route("GET", "/health", summary="Health check", tags=["meta"])
async def health(_req: Request):
    return {"ok": True}