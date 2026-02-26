"""
Agent client abstraction with health check support.

Each backend gets a concrete client that knows how to:
  - perform a health check (connectivity + simple request)
  - send a payload and return a response
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from sdk.orchestrator.backends import AgentBackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Health check result
# ---------------------------------------------------------------------------


@dataclass
class HealthCheckResult:
    """Structured result of a single agent health check."""

    backend: AgentBackend
    healthy: bool
    latency_ms: float = 0.0
    status_code: Optional[int] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        tag = "OK" if self.healthy else "FAIL"
        lat = f"{self.latency_ms:.0f}ms"
        err = f" error={self.error}" if self.error else ""
        return f"[{tag}] {self.backend} {lat}{err}"


# ---------------------------------------------------------------------------
# Abstract base client
# ---------------------------------------------------------------------------


class AgentClient:
    """Base class for backend-specific agent clients."""

    def __init__(
        self,
        backend: AgentBackend,
        *,
        channel: Optional[str] = None,
        timeout: int = 10,
    ) -> None:
        self.backend = backend
        self.channel = channel
        self.timeout = timeout

    # -- public API --------------------------------------------------------

    def health_check(self) -> HealthCheckResult:
        """Verify connectivity and responsiveness of the backend."""
        raise NotImplementedError

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send *payload* to the agent and return the response dict."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete clients
# ---------------------------------------------------------------------------


class GeminiClient(AgentClient):
    """Client for Google Gemini API."""

    def __init__(self, *, channel: Optional[str] = None, timeout: int = 10) -> None:
        super().__init__(AgentBackend.GEMINI, channel=channel, timeout=timeout)
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def health_check(self) -> HealthCheckResult:
        if not self.api_key:
            return HealthCheckResult(
                backend=self.backend,
                healthy=False,
                error="GEMINI_API_KEY not configured",
            )
        url = f"{self.base_url}/models"
        return _http_health_probe(self.backend, url, self.timeout, headers={
            "x-goog-api-key": self.api_key,
        })

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        # Placeholder – real implementation would call Gemini generateContent
        return {"status": "accepted", "backend": str(self.backend)}


class GrokClient(AgentClient):
    """Client for xAI Grok API."""

    def __init__(self, *, channel: Optional[str] = None, timeout: int = 10) -> None:
        super().__init__(AgentBackend.GROK, channel=channel, timeout=timeout)
        self.api_key = os.getenv("GROK_API_KEY", "")
        self.base_url = "https://api.x.ai/v1"

    def health_check(self) -> HealthCheckResult:
        if not self.api_key:
            return HealthCheckResult(
                backend=self.backend,
                healthy=False,
                error="GROK_API_KEY not configured",
            )
        url = f"{self.base_url}/models"
        return _http_health_probe(self.backend, url, self.timeout, headers={
            "Authorization": f"Bearer {self.api_key}",
        })

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        return {"status": "accepted", "backend": str(self.backend)}


class DevinClient(AgentClient):
    """Client for Devin API."""

    def __init__(self, *, channel: Optional[str] = None, timeout: int = 10) -> None:
        super().__init__(AgentBackend.DEVIN, channel=channel, timeout=timeout)
        self.api_key = os.getenv("DEVIN_API_KEY", "")
        self.base_url = os.getenv("DEVIN_BASE_URL", "https://api.devin.ai/v1")

    def health_check(self) -> HealthCheckResult:
        if not self.api_key:
            return HealthCheckResult(
                backend=self.backend,
                healthy=False,
                error="DEVIN_API_KEY not configured",
            )
        url = f"{self.base_url}/sessions?limit=1"
        return _http_health_probe(self.backend, url, self.timeout, headers={
            "Authorization": f"Bearer {self.api_key}",
        })

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        return {"status": "accepted", "backend": str(self.backend)}


class OpenAIClient(AgentClient):
    """Client for OpenAI API."""

    def __init__(self, *, channel: Optional[str] = None, timeout: int = 10) -> None:
        super().__init__(AgentBackend.OPENAI, channel=channel, timeout=timeout)
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = "https://api.openai.com/v1"

    def health_check(self) -> HealthCheckResult:
        if not self.api_key:
            return HealthCheckResult(
                backend=self.backend,
                healthy=False,
                error="OPENAI_API_KEY not configured",
            )
        url = f"{self.base_url}/models"
        return _http_health_probe(self.backend, url, self.timeout, headers={
            "Authorization": f"Bearer {self.api_key}",
        })

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        return {"status": "accepted", "backend": str(self.backend)}


class ClaudeClient(AgentClient):
    """Client for Anthropic Claude API."""

    def __init__(self, *, channel: Optional[str] = None, timeout: int = 10) -> None:
        super().__init__(AgentBackend.CLAUDE, channel=channel, timeout=timeout)
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1"

    def health_check(self) -> HealthCheckResult:
        if not self.api_key:
            return HealthCheckResult(
                backend=self.backend,
                healthy=False,
                error="ANTHROPIC_API_KEY not configured",
            )
        url = f"{self.base_url}/models"
        return _http_health_probe(self.backend, url, self.timeout, headers={
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        })

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        return {"status": "accepted", "backend": str(self.backend)}


class LocalClient(AgentClient):
    """Client for a locally-running agent process."""

    def __init__(self, *, channel: Optional[str] = None, timeout: int = 10) -> None:
        super().__init__(AgentBackend.LOCAL, channel=channel, timeout=timeout)
        self.base_url = channel or os.getenv(
            "LOCAL_AGENT_URL", "http://localhost:8000"
        )

    def health_check(self) -> HealthCheckResult:
        url = f"{self.base_url}/health"
        return _http_health_probe(self.backend, url, self.timeout)

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        return {"status": "accepted", "backend": str(self.backend)}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_CLIENT_MAP: Dict[AgentBackend, type] = {
    AgentBackend.GEMINI: GeminiClient,
    AgentBackend.GROK: GrokClient,
    AgentBackend.DEVIN: DevinClient,
    AgentBackend.OPENAI: OpenAIClient,
    AgentBackend.CLAUDE: ClaudeClient,
    AgentBackend.LOCAL: LocalClient,
}


def get_agent_client(
    backend: AgentBackend,
    *,
    channel: Optional[str] = None,
    timeout: int = 10,
) -> AgentClient:
    """Return a concrete :class:`AgentClient` for *backend*."""
    cls = _CLIENT_MAP.get(backend)
    if cls is None:
        raise ValueError(f"Unsupported backend: {backend}")
    return cls(channel=channel, timeout=timeout)


# ---------------------------------------------------------------------------
# Shared HTTP probe helper
# ---------------------------------------------------------------------------


def _http_health_probe(
    backend: AgentBackend,
    url: str,
    timeout: int,
    *,
    headers: Optional[Dict[str, str]] = None,
) -> HealthCheckResult:
    """Perform a lightweight HTTP GET and return a :class:`HealthCheckResult`."""
    start = time.monotonic()
    try:
        req = Request(url, method="GET")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        with urlopen(req, timeout=timeout) as resp:
            status_code: int = resp.status
            latency = (time.monotonic() - start) * 1000
            healthy = 200 <= status_code < 400
            return HealthCheckResult(
                backend=backend,
                healthy=healthy,
                latency_ms=latency,
                status_code=status_code,
                error=None if healthy else f"HTTP {status_code}",
            )
    except URLError as exc:
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            backend=backend,
            healthy=False,
            latency_ms=latency,
            error=str(exc.reason),
        )
    except Exception as exc:  # noqa: BLE001
        latency = (time.monotonic() - start) * 1000
        return HealthCheckResult(
            backend=backend,
            healthy=False,
            latency_ms=latency,
            error=str(exc),
        )
