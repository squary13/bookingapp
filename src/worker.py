from workers import WorkerEntrypoint, Request, Response

class Default(WorkerEntrypoint):
    async def fetch(self, request: Request):
        # Super cheap handler to avoid startup CPU
        if request.url.pathname == "/":
            return Response.json({"hello": "world"})
        return Response("Not found", status=404)