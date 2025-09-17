from workers import WorkerEntrypoint, Request, Response  # type: ignore
from app.router import match, split_url, respond_json
from app.swagger import swagger_page, openapi_json

# Import endpoints to register them with the router (side-effects of @route)
from app.endpoints import meta, users 

class Default(WorkerEntrypoint):
    async def fetch(self, request: Request, env):
        path, _query = split_url(request)
        method = request.method

        # super-cheap root
        if path == "/docs" or path == "/":
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