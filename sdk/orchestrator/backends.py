"""
AgentBackend enumeration.

Defines the supported agent backend types for the orchestrator.
Each backend corresponds to a specific AI service or local process.
"""

from enum import Enum


class AgentBackend(str, Enum):
    """Supported agent backend types."""

    GEMINI = "gemini"
    GROK = "grok"
    DEVIN = "devin"
    OPENAI = "openai"
    LOCAL = "local"
    CLAUDE = "claude"

    def __str__(self) -> str:
        return self.value
