"""
FlowForge Proxy Router — /api/v1/flowforge

Transparent reverse-proxy to the FlowForge rendering server (Node/TS).
All requests are forwarded using httpx, preserving headers, query params,
and request bodies.

Endpoints
---------
GET  /status         — check FlowForge server health
ANY  /{path}         — catch-all proxy to flowforge_server_url
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from app.core.config import settings

router = APIRouter(prefix="/flowforge", tags=["flowforge"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOP_BY_HOP = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-encoding",
        "content-length",
        "host",
    ]
)


def _forward_headers(request: Request) -> dict:
    """Build a cleaned header dict suitable for forwarding to FlowForge."""
    return {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }


async def _proxy_request(request: Request, path: str) -> Response:
    """Forward *request* to the FlowForge server at the given sub-path."""
    base = settings.flowforge_server_url.rstrip("/")
    target_url = f"{base}/{path.lstrip('/')}"

    # Preserve query string
    qs = request.url.query
    if qs:
        target_url = f"{target_url}?{qs}"

    body = await request.body()
    headers = _forward_headers(request)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True,
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"FlowForge server at {settings.flowforge_server_url} is unreachable. "
                "Ensure it is running."
            ),
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="FlowForge server did not respond in time.",
        )

    # Strip hop-by-hop headers from the upstream response
    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    summary="Check FlowForge server health",
    response_model=None,
)
async def flowforge_status() -> Any:
    """Probe the FlowForge server's health endpoint.

    Tries GET /health on the FlowForge server.  Returns the response body
    on success, or a structured error if the server is unreachable.
    """
    base = settings.flowforge_server_url.rstrip("/")
    health_url = f"{base}/health"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(health_url)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return {"status": "ok", "raw": resp.text}
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unreachable",
                "url": settings.flowforge_server_url,
                "hint": "Start FlowForge with: cd apps/flowforge && npm run dev",
            },
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={"status": "error", "message": exc.response.text},
        ) from exc


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    summary="Catch-all proxy to FlowForge server",
    include_in_schema=True,
)
async def proxy_to_flowforge(request: Request, path: str) -> Response:
    """Forward any request under /api/v1/flowforge/{path} transparently to
    the FlowForge rendering server.

    This allows the ICC frontend to reach FlowForge APIs through a single
    origin without CORS configuration on the FlowForge side.
    """
    return await _proxy_request(request, path)
