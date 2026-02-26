"""
Tests for agent health checks and orchestra initialization.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from sdk.orchestrator.backends import AgentBackend
from sdk.orchestrator.client import (
    AgentClient,
    HealthCheckResult,
    get_agent_client,
)
from sdk.orchestrator.orchestra import (
    AgentOrchestra,
    AgentSpec,
    OrchestraHealthError,
)


# -----------------------------------------------------------------------
# AgentBackend
# -----------------------------------------------------------------------


class TestAgentBackend:
    def test_enum_values(self) -> None:
        assert AgentBackend.GEMINI.value == "gemini"
        assert AgentBackend.GROK.value == "grok"
        assert AgentBackend.DEVIN.value == "devin"
        assert AgentBackend.LOCAL.value == "local"
        assert AgentBackend.OPENAI.value == "openai"
        assert AgentBackend.CLAUDE.value == "claude"

    def test_str_conversion(self) -> None:
        assert str(AgentBackend.GEMINI) == "gemini"

    def test_from_string(self) -> None:
        assert AgentBackend("gemini") is AgentBackend.GEMINI


# -----------------------------------------------------------------------
# HealthCheckResult
# -----------------------------------------------------------------------


class TestHealthCheckResult:
    def test_healthy_str(self) -> None:
        r = HealthCheckResult(
            backend=AgentBackend.GEMINI, healthy=True, latency_ms=42.5
        )
        assert "[OK]" in str(r)
        assert "gemini" in str(r)

    def test_unhealthy_str(self) -> None:
        r = HealthCheckResult(
            backend=AgentBackend.GROK,
            healthy=False,
            latency_ms=100.0,
            error="timeout",
        )
        assert "[FAIL]" in str(r)
        assert "timeout" in str(r)


# -----------------------------------------------------------------------
# get_agent_client factory
# -----------------------------------------------------------------------


class TestGetAgentClient:
    def test_returns_correct_type_for_each_backend(self) -> None:
        for backend in AgentBackend:
            client = get_agent_client(backend)
            assert isinstance(client, AgentClient)
            assert client.backend is backend

    def test_unsupported_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported backend"):
            get_agent_client("nonexistent")  # type: ignore[arg-type]


# -----------------------------------------------------------------------
# Stub client for orchestra tests
# -----------------------------------------------------------------------


class _StubClient(AgentClient):
    """Deterministic stub for testing orchestra logic."""

    def __init__(
        self,
        backend: AgentBackend,
        *,
        healthy: bool = True,
        channel: Optional[str] = None,
    ) -> None:
        super().__init__(backend, channel=channel)
        self._healthy = healthy

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            backend=self.backend,
            healthy=self._healthy,
            latency_ms=1.0,
            error=None if self._healthy else "stub failure",
        )

    def send(
        self, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        return {"echo": payload, "backend": str(self.backend)}


def _make_config(agents: list[dict[str, Any]]) -> Path:
    """Write a temporary agents.json and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    )
    json.dump({"agents": agents}, tmp)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


# -----------------------------------------------------------------------
# AgentOrchestra
# -----------------------------------------------------------------------


class TestAgentOrchestra:
    """Test orchestra initialisation and health-check gating."""

    SINGLE_AGENT = [
        {
            "name": "test-agent",
            "role": "implementer",
            "backend": "local",
            "supports": ["text"],
        }
    ]

    MULTI_AGENT = [
        {
            "name": "agent-a",
            "role": "implementer",
            "backend": "local",
            "supports": ["text", "code"],
        },
        {
            "name": "agent-b",
            "role": "verifier",
            "backend": "local",
            "supports": ["text"],
        },
    ]

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _patch_factory(healthy: bool = True):
        """Return a mock for ``get_agent_client`` that yields stubs."""
        def _factory(
            backend: AgentBackend,
            *,
            channel: Optional[str] = None,
            timeout: int = 10,
        ) -> AgentClient:
            return _StubClient(backend, healthy=healthy, channel=channel)

        return patch(
            "sdk.orchestrator.orchestra.get_agent_client", side_effect=_factory
        )

    # -- config loading ------------------------------------------------

    def test_missing_config_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Missing agent config"):
            AgentOrchestra(agent_config_path=tmp_path / "nope.json")

    def test_loads_agents_from_config(self) -> None:
        cfg = _make_config(self.SINGLE_AGENT)
        with self._patch_factory(healthy=True):
            orch = AgentOrchestra(agent_config_path=cfg)
        assert "test-agent" in orch.agents
        spec = orch.agents["test-agent"]
        assert spec.role == "implementer"
        assert spec.backend is AgentBackend.LOCAL

    # -- health checks -------------------------------------------------

    def test_healthy_agents_pass(self) -> None:
        cfg = _make_config(self.MULTI_AGENT)
        with self._patch_factory(healthy=True):
            orch = AgentOrchestra(agent_config_path=cfg)
        summary = orch.get_health_summary()
        assert all(v["healthy"] for v in summary.values())

    def test_unhealthy_agents_raise_in_strict_mode(self) -> None:
        cfg = _make_config(self.SINGLE_AGENT)
        with self._patch_factory(healthy=False):
            with pytest.raises(OrchestraHealthError):
                AgentOrchestra(agent_config_path=cfg, strict_health=True)

    def test_unhealthy_agents_warn_in_lenient_mode(self) -> None:
        cfg = _make_config(self.SINGLE_AGENT)
        with self._patch_factory(healthy=False):
            orch = AgentOrchestra(
                agent_config_path=cfg, strict_health=False
            )
        summary = orch.get_health_summary()
        assert not summary["test-agent"]["healthy"]

    # -- dispatch / discuss -------------------------------------------

    def test_dispatch_records_log(self) -> None:
        cfg = _make_config(self.SINGLE_AGENT)
        with self._patch_factory(healthy=True):
            orch = AgentOrchestra(agent_config_path=cfg)
        spec = orch.agents["test-agent"]
        entry = orch._dispatch_to_agent(spec, "ping", {"msg": "hello"})
        assert entry["agent"] == "test-agent"
        assert "response" in entry
        assert len(orch.discussion_log) == 1

    def test_discuss_fans_out(self) -> None:
        cfg = _make_config(self.MULTI_AGENT)
        with self._patch_factory(healthy=True):
            orch = AgentOrchestra(agent_config_path=cfg)
        results = orch.discuss("topic", "hello", modality="text")
        assert len(results) == 2

    def test_discuss_filters_by_modality(self) -> None:
        cfg = _make_config(self.MULTI_AGENT)
        with self._patch_factory(healthy=True):
            orch = AgentOrchestra(agent_config_path=cfg)
        results = orch.discuss("topic", "hello", modality="code")
        # Only agent-a supports "code"
        assert len(results) == 1
        assert results[0]["agent"] == "agent-a"

    def test_discuss_filters_by_name(self) -> None:
        cfg = _make_config(self.MULTI_AGENT)
        with self._patch_factory(healthy=True):
            orch = AgentOrchestra(agent_config_path=cfg)
        results = orch.discuss(
            "topic", "hello", agent_filter=["agent-b"]
        )
        assert len(results) == 1
        assert results[0]["agent"] == "agent-b"

    def test_env_override_config_path(self, tmp_path: Path) -> None:
        cfg = _make_config(self.SINGLE_AGENT)
        with (
            self._patch_factory(healthy=True),
            patch.dict("os.environ", {"ORCHESTRA_AGENT_CONFIG": str(cfg)}),
        ):
            orch = AgentOrchestra(
                agent_config_path=tmp_path / "ignored.json"
            )
        assert "test-agent" in orch.agents


# -----------------------------------------------------------------------
# AgentSpec
# -----------------------------------------------------------------------


class TestAgentSpec:
    def test_defaults(self) -> None:
        spec = AgentSpec(name="x", role="y", backend=AgentBackend.LOCAL)
        assert spec.channel is None
        assert spec.supports == []
