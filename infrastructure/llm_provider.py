"""
llm_provider.py - Central configuration for LLM mode (offline / online).

Offline: Uses local Phi-3 + LLaVA models (current behaviour).
Online:  Uses Claude API (Anthropic) for both text and vision.
"""
import os
from typing import Literal

# ---------------------------------------------------------------------------
# Global mode state
# ---------------------------------------------------------------------------

_current_mode: Literal["offline", "online"] = "offline"


def get_mode() -> str:
    return _current_mode


def set_mode(mode: str):
    global _current_mode
    if mode not in ("offline", "online"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'offline' or 'online'.")
    _current_mode = mode



# ---------------------------------------------------------------------------
# Claude API helper (lazy-loaded)
# ---------------------------------------------------------------------------

_claude_client = None


def get_claude_client():
    """Returns an Anthropic client, creating it lazily."""
    global _claude_client
    if _claude_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Cannot use online mode."
            )
        import anthropic
        _claude_client = anthropic.Anthropic(api_key=api_key)
    return _claude_client


CLAUDE_MODEL = "claude-sonnet-4-20250514"
