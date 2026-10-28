from collections import deque
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound actual bytes even when Content-Length is missing or dishonest."""
    def __init__(self, app, maximum_bytes: int):
        self.app = app
        self.maximum_bytes = maximum_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        messages = deque()
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.maximum_bytes:
                return await JSONResponse({"detail": "Request exceeds the upload limit."}, status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return messages.popleft() if messages else await receive()
        await self.app(scope, replay, send)
