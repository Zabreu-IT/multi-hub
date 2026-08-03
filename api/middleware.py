import os
import time
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse

_hits: dict[str, deque[float]] = defaultdict(deque)


async def request_context(request: Request, call_next):
    request.state.raw_body = await request.body()
    limit, now, ip = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120")), time.monotonic(), request.client.host if request.client else "unknown"
    hits = _hits[ip]
    while hits and hits[0] <= now - 60: hits.popleft()
    if len(hits) >= limit: return JSONResponse({"detail": "Rate limit exceeded"}, 429)
    hits.append(now)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "")
    return response
