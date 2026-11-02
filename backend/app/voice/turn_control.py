"""Fast deterministic stop-speaking commands for real-time voice sessions.

These controls must never be routed to the paid LLM or stored as an
unanswered chat turn. Match only short, direct commands; instructional
questions about stopping a service must still reach the model.
"""
from __future__ import annotations

import re
import unicodedata


_COMMANDS = frozenset({
    "stop", "stop talking", "stop speaking", "stop now",
    "please stop", "stop please", "be quiet", "quiet please",
    "enough", "that's enough", "that's fine stop",
    "থামো", "থাম", "থেমে যাও", "এখন থামো",
    "চুপ করো", "আর বলো না", "কথা বলা বন্ধ করো",
    "thamo", "tham", "ekhon thamo", "chup koro",
    "ar bolo na", "kotha bola bondho koro",
    "やめて", "止めて", "止まって", "もういい", "話すのをやめて",
})


def is_stop_speaking_command(transcript: str) -> bool:
    """Recognize an explicit stop command in English, Bangla or Japanese."""
    normalized = unicodedata.normalize("NFKC", transcript).casefold()
    normalized = re.sub(r"[.,!?;:।。！？、，…]+", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized or len(normalized) > 64:
        return False
    return normalized in _COMMANDS
