"""
Orchestra Router — /api/v1/orchestra

Manages multi-agent orchestra sessions.  Sessions can be created, queried,
and driven via message injection.

If the sitemap_pro application exposes an orchestra endpoint at
/api/orchestra, this router proxies to it.  Otherwise it maintains sessions
in an in-memory store.

Endpoints
---------
POST /session                          — start a new orchestra session
GET  /session/{session_id}             — get session status and history
POST /session/{session_id}/message     — send a message to the session
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/orchestra", tags=["orchestra"])

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------
_SESSIONS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SessionCreateRequest(BaseModel):
    name: Optional[str] = None
    agents: List[str] = []
    context: Dict[str, Any] = {}


class SessionMessage(BaseModel):
    role: str = "user"  # user | agent | system
    content: str
    agent_id: Optional[str] = None
    timestamp: Optional[str] = None


class SessionMessageRequest(BaseModel):
    content: str
    role: str = "user"
    agent_id: Optional[str] = None


class SessionStatus(BaseModel):
    session_id: str
    name: Optional[str]
    status: str  # active | completed | error
    agents: List[str]
    created_at: str
    updated_at: str
    messages: List[SessionMessage]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _proxy_to_sitemap_pro(path: str, method: str = "GET", payload: Any = None) -> Any:
    """Attempt to proxy an orchestra request to the sitemap_pro server.

    Returns the parsed JSON response, or raises HTTPException on failure.
    This is best-effort; callers fall back to the in-memory store.
    """
    base = settings.flowforge_server_url  # reuse as sitemap_pro base if needed
    url = f"{base.rstrip('/')}/api/orchestra/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.upper() == "POST":
                resp = await client.post(url, json=payload)
            else:
                resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/session",
    response_model=SessionStatus,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new orchestra session",
)
async def create_session(body: SessionCreateRequest) -> SessionStatus:
    """Create a new multi-agent orchestra session.

    An orchestra session coordinates one or more named agents and maintains
    a conversation history that can be driven via POST /session/{id}/message.
    """
    session_id = str(uuid.uuid4())
    now = _now()

    session: Dict[str, Any] = {
        "session_id": session_id,
        "name": body.name or f"session-{session_id[:8]}",
        "status": "active",
        "agents": body.agents or [],
        "context": body.context,
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    _SESSIONS[session_id] = session

    # Attempt proxy to upstream orchestra endpoint (fire-and-forget for now)
    # await _proxy_to_sitemap_pro("session", "POST", body.model_dump())

    return SessionStatus(
        session_id=session_id,
        name=session["name"],
        status=session["status"],
        agents=session["agents"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=[],
    )


@router.get(
    "/session/{session_id}",
    response_model=SessionStatus,
    summary="Get status and message history for a session",
)
def get_session(session_id: str) -> SessionStatus:
    """Return the full state of an orchestra session including all messages.

    Messages are returned in insertion order (oldest first).
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return SessionStatus(
        session_id=session["session_id"],
        name=session.get("name"),
        status=session["status"],
        agents=session.get("agents", []),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=[SessionMessage(**m) for m in session.get("messages", [])],
    )


@router.post(
    "/session/{session_id}/message",
    response_model=SessionStatus,
    summary="Send a message to an orchestra session",
)
async def send_message(
    session_id: str,
    body: SessionMessageRequest,
) -> SessionStatus:
    """Append a message to an orchestra session and return the updated state.

    The message is added with the current UTC timestamp.  Agent-generated
    responses are not yet implemented in this scaffold — the session simply
    stores the message history.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session '{session_id}' is '{session['status']}' and cannot accept messages.",
        )

    now = _now()
    msg: Dict[str, Any] = {
        "role": body.role,
        "content": body.content,
        "agent_id": body.agent_id,
        "timestamp": now,
    }
    session["messages"].append(msg)
    session["updated_at"] = now

    return SessionStatus(
        session_id=session["session_id"],
        name=session.get("name"),
        status=session["status"],
        agents=session.get("agents", []),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=[SessionMessage(**m) for m in session.get("messages", [])],
    )
