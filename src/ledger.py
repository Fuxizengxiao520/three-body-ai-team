"""庄颜，记录每次调用的 token 与估算成本。"""

from __future__ import annotations

from pathlib import Path

from .models import append_jsonl, read_jsonl, timestamp

# 谷时基准价，单位 美元 / 1M tokens，快照日期与来源见 README
PRICING = {
    "deepseek-flash": {"input": 0.15, "output": 0.60, "cache_hit": 0.003},
    "deepseek-v4-pro": {"input": 0.66, "output": 1.98, "cache_hit": 0.022},
    "mock-local": {"input": 0.0, "output": 0.0, "cache_hit": 0.0},
}


class Ledger:
    def __init__(self, path: Path, peak: bool = False):
        self.path = path
        self.peak = peak

    def record(self, role: str, model: str, reply, note: str = "") -> float:
        price = PRICING.get(model, PRICING["deepseek-flash"])
        multiplier = 2.0 if self.peak else 1.0
        cached = min(reply.cached_input_tokens, reply.input_tokens)
        fresh = max(0, reply.input_tokens - cached)
        cost = (
            fresh * price["input"]
            + cached * price["cache_hit"]
            + reply.output_tokens * price["output"]
        ) / 1_000_000 * multiplier
        append_jsonl(
            self.path,
            {
                "ts": timestamp(),
                "role": role,
                "model": model,
                "input_tokens": reply.input_tokens,
                "cached_input_tokens": reply.cached_input_tokens,
                "output_tokens": reply.output_tokens,
                "cost_usd": round(cost, 6),
                "peak": self.peak,
                "simulated": reply.simulated,
                "note": note,
            },
        )
        return cost

    def summary(self) -> dict:
        rows = read_jsonl(self.path)
        return {
            "calls": len(rows),
            "input_tokens": sum(row["input_tokens"] for row in rows),
            "output_tokens": sum(row["output_tokens"] for row in rows),
            "cost_usd": round(sum(row["cost_usd"] for row in rows), 6),
            "simulated_only": (
                all(row.get("simulated", False) for row in rows) if rows else True
            ),
        }
