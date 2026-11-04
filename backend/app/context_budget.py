"""Conservative estimates, not model-tokenizer counts. No extra model calls."""
import math
import os
from .config import OLLAMA_NUM_CTX

# Zero keeps the automatic budget. A positive value can only reduce it.
ROOM_CONTEXT_BUDGET = max(0, int(os.getenv("JST_ROOM_CONTEXT_BUDGET", "0")))


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / 3) if text else 0


def message_tokens(messages) -> int:
    return sum(estimate_tokens(m.get("content", "")) + 8 for m in messages if m.get("content", "").strip())


def context_policy(system_text: str):
    limit = max(1, OLLAMA_NUM_CTX)
    system = estimate_tokens(system_text) + 256 + 3000  # Bounded user evidence plus optional older continuation summary.
    sources = min(2048, limit // 4)
    reply = min(1024, max(1, limit // 8))
    automatic = max(0, limit - system - sources - reply)
    room_budget = min(automatic, ROOM_CONTEXT_BUDGET) if ROOM_CONTEXT_BUDGET else automatic
    return {"limit": limit, "systemReserve": system, "sourceReserve": sources,
            "replyReserve": reply, "roomBudget": room_budget,
            "estimated": True}


def room_fits(messages, question, policy):
    return message_tokens(messages) + estimate_tokens(question) + 8 < policy["roomBudget"]
