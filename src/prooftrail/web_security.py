"""Shared request caps and response protections for the two independent apps."""

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware


def protect_app(app: FastAPI):
    default_hosts = "127.0.0.1,localhost,testserver"
    if os.getenv("RENDER") == "true" and os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        default_hosts += "," + os.environ["RENDER_EXTERNAL_HOSTNAME"]
    if os.getenv("VERCEL") == "1":
        for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
            if os.getenv(name):
                default_hosts += "," + os.environ[name]
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv("PROOFTRAIL_ALLOWED_HOSTS", default_hosts).split(","),
    )

    @app.middleware("http")
    async def headers_and_limits(request: Request, call_next):
        max_size = 4 * 1024 * 1024
        declared = request.headers.get("content-length", "0")
        if not declared.isdigit() or int(declared) > max_size:
            return JSONResponse({"detail": "请求超过 4 MB 限制"}, status_code=413)
        if request.method == "POST":
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_size:
                    return JSONResponse({"detail": "请求超过 4 MB 限制"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'"
        )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response
