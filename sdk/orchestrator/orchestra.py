"""
AgentOrchestra — parallel agent orchestration with health-check gating.

Usage::

    orchestra = AgentOrchestra()          # loads agents.json, runs health checks
    result   = orchestra.discuss("topic", "message")
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sdk.orchestrator.backends import AgentBackend
from sdk.orchestrator.client import (
    AgentClient,
    HealthCheckResult,
    get_agent_client,
)

logger = logging.getLogger(__name__)

DEFAULT_AGENT_CONFIG = Path(__file__).with_name("agents.json")


# ---------------------------------------------------------------------------
# AgentSpec
# ---------------------------------------------------------------------------


@dataclass
class AgentSpec:
    """Describes a single agent registered in the orchestra."""

    name: str
    role: str
    backend: AgentBackend
    channel: Optional[str] = None
    supports: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OrchestraHealthError(RuntimeError):
    """Raised when one or more agents fail their health check."""

    def __init__(self, failures: List[HealthCheckResult]) -> None:
        self.failures = failures
        names = ", ".join(f"{f.backend}" for f in failures)
        super().__init__(
            f"Health check failed for {len(failures)} agent(s): {names}"
        )


# ---------------------------------------------------------------------------
# AgentOrchestra
# ---------------------------------------------------------------------------


class AgentOrchestra:
    """Discovers agents, verifies health, and dispatches work in parallel."""

    def __init__(
        self,
        agent_config_path: Optional[Path] = None,
        max_workers: Optional[int] = None,
        *,
        strict_health: bool = True,
    ) -> None:
        self.agent_config_path = agent_config_path or DEFAULT_AGENT_CONFIG
        self.max_workers = max_workers or int(
            os.getenv("ORCHESTRA_MAX_WORKERS", "8")
        )
        self.strict_health = strict_health
        self.agents: Dict[str, AgentSpec] = {}
        self._clients: Dict[str, AgentClient] = {}
        self.discussion_log: List[Dict[str, Any]] = []
        self._health_results: Dict[str, HealthCheckResult] = {}
        self._init_agents()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_agents(self) -> None:
        """Load agent config, create clients, and run parallel health checks.

        If ``strict_health`` is *True* (the default), an
        :class:`OrchestraHealthError` is raised when any agent fails its
        health check.
        """
        # Allow env-var override of config path
        env_path = os.getenv("ORCHESTRA_AGENT_CONFIG")
        if env_path:
            self.agent_config_path = Path(env_path)

        if not self.agent_config_path.exists():
            raise FileNotFoundError(
                f"Missing agent config: {self.agent_config_path}"
            )

        with open(self.agent_config_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        # --- build specs + clients ------------------------------------
        for agent in raw.get("agents", []):
            spec = AgentSpec(
                name=agent["name"],
                role=agent["role"],
                backend=AgentBackend(agent["backend"]),
                channel=agent.get("channel"),
                supports=agent.get("supports", []),
            )
            self.agents[spec.name] = spec
            self._clients[spec.name] = get_agent_client(
                spec.backend, channel=spec.channel
            )

        # --- parallel health checks ----------------------------------
        self._run_health_checks()

    def _run_health_checks(self) -> None:
        """Run health checks for all registered agents in parallel.

        Stores results in ``self._health_results`` and raises
        :class:`OrchestraHealthError` if any check fails and
        ``self.strict_health`` is enabled.
        """
        failures: List[HealthCheckResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_name = {
                pool.submit(client.health_check): name
                for name, client in self._clients.items()
            }
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = HealthCheckResult(
                        backend=self.agents[name].backend,
                        healthy=False,
                        error=str(exc),
                    )
                self._health_results[name] = result
                if result.healthy:
                    logger.info("Agent %s: %s", name, result)
                else:
                    logger.warning("Agent %s: %s", name, result)
                    failures.append(result)

        if failures and self.strict_health:
            raise OrchestraHealthError(failures)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_health_summary(self) -> Dict[str, Any]:
        """Return a JSON-serialisable summary of the last health run."""
        return {
            name: {
                "backend": str(result.backend),
                "healthy": result.healthy,
                "latency_ms": result.latency_ms,
                "error": result.error,
            }
            for name, result in self._health_results.items()
        }

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch_to_agent(
        self,
        spec: AgentSpec,
        topic: str,
        content: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a single request to *spec* and record the exchange."""
        payload: Dict[str, Any] = {
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": {
                "role": spec.role,
                "supports": spec.supports,
            },
            "content": content,
        }
        client = self._clients[spec.name]
        response = client.send(payload, timeout=timeout)
        entry = {
            "agent": spec.name,
            "request": payload,
            "response": response,
        }
        self.discussion_log.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Multi-agent discussion
    # ------------------------------------------------------------------

    def discuss(
        self,
        topic: str,
        message: str,
        *,
        modality: str = "text",
        attachments: Optional[List[Path]] = None,
        timeout: Optional[int] = None,
        agent_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fan-out *message* to matching agents and collect responses.

        Parameters
        ----------
        topic:
            Discussion topic (e.g. ``"code_review"``).
        message:
            The user-facing prompt / question.
        modality:
            Requested modality — agents whose ``supports`` list includes
            this value are selected.  Defaults to ``"text"``.
        attachments:
            Optional file paths to include with the request.
        timeout:
            Per-agent timeout in seconds.
        agent_filter:
            If provided, only agents whose *name* appears in this list are
            contacted.

        Returns
        -------
        list[dict]
            One entry per contacted agent containing ``agent``, ``request``,
            and ``response`` keys.
        """
        content: Dict[str, Any] = {
            "message": message,
            "modality": modality,
        }
        if attachments:
            content["attachments"] = [str(p) for p in attachments]

        # Select agents
        targets = self._select_agents(modality, agent_filter)
        if not targets:
            logger.warning("No agents matched modality=%s filter=%s", modality, agent_filter)
            return []

        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_spec = {
                pool.submit(
                    self._dispatch_to_agent, spec, topic, content, timeout
                ): spec
                for spec in targets
            }
            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    entry = future.result()
                    results.append(entry)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Agent %s dispatch error: %s", spec.name, exc)
                    results.append(
                        {
                            "agent": spec.name,
                            "request": content,
                            "response": {"error": str(exc)},
                        }
                    )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _select_agents(
        self,
        modality: str,
        agent_filter: Optional[List[str]] = None,
    ) -> List[AgentSpec]:
        """Return agents matching *modality* and optional name filter."""
        selected: List[AgentSpec] = []
        for name, spec in self.agents.items():
            if agent_filter and name not in agent_filter:
                continue
            if modality in spec.supports or not spec.supports:
                selected.append(spec)
        return selected
