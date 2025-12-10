"""Agent definitions and personas."""
from .base import Agent
from .republican import REPUBLICAN_AGENTS
from .democrat import DEMOCRAT_AGENTS

__all__ = [
    "Agent",
    "REPUBLICAN_AGENTS",
    "DEMOCRAT_AGENTS",
]
