import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config


def _format_tokens(n: int) -> str:
    """Format token count to human-readable string."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    else:
        return str(n)


@dataclass
class TokenStats:
    # From stats-cache.json (historical)
    lifetime_input: int = 0
    lifetime_output: int = 0
    lifetime_cache_read: int = 0
    lifetime_cache_create: int = 0
    daily_tokens: list[dict] = field(default_factory=list)
    cache_last_computed: str = ""
    total_messages: int = 0
    total_sessions: int = 0

    # From history.jsonl (live estimate)
    messages_today: int = 0
    estimated_tokens_today: int = 0

    error: str | None = None

    @property
    def lifetime_total(self) -> int:
        return self.lifetime_input + self.lifetime_output

    @property
    def lifetime_total_str(self) -> str:
        return _format_tokens(self.lifetime_total)

    @property
    def lifetime_output_str(self) -> str:
        return _format_tokens(self.lifetime_output)

    @property
    def lifetime_input_str(self) -> str:
        return _format_tokens(self.lifetime_input)

    @property
    def cache_read_str(self) -> str:
        return _format_tokens(self.lifetime_cache_read)

    @property
    def tokens_today_str(self) -> str:
        return f"~{_format_tokens(self.estimated_tokens_today)}"


def load_token_stats() -> TokenStats:
    """Load token stats from Claude Code's local files."""
    stats = TokenStats()

    # Source 1: stats-cache.json
    try:
        cache_path = config.STATS_CACHE_PATH
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            stats.cache_last_computed = data.get("lastComputedDate", "")
            stats.total_messages = data.get("totalMessages", 0)
            stats.total_sessions = data.get("totalSessions", 0)

            # Aggregate model usage across all models
            model_usage = data.get("modelUsage", {})
            for model, usage in model_usage.items():
                stats.lifetime_input += usage.get("inputTokens", 0)
                stats.lifetime_output += usage.get("outputTokens", 0)
                stats.lifetime_cache_read += usage.get("cacheReadInputTokens", 0)
                stats.lifetime_cache_create += usage.get("cacheCreationInputTokens", 0)

            # Daily token breakdown (last 14 days)
            daily = data.get("dailyModelTokens", [])
            stats.daily_tokens = [
                {
                    "date": entry["date"],
                    "tokens": sum(entry.get("tokensByModel", {}).values()),
                }
                for entry in daily[-14:]
            ]
    except Exception as e:
        stats.error = f"Stats cache: {e}"

    # Source 2: history.jsonl — estimate today's tokens
    try:
        history_path = config.HISTORY_PATH
        if history_path.exists():
            today = datetime.now().strftime("%Y-%m-%d")
            messages_today = 0
            chars_today = 0

            with open(history_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "")
                        if ts.startswith(today):
                            messages_today += 1
                            display = entry.get("display", "")
                            if isinstance(display, str):
                                chars_today += len(display)
                            elif isinstance(display, list):
                                for item in display:
                                    if isinstance(item, dict):
                                        chars_today += len(item.get("text", ""))
                                    elif isinstance(item, str):
                                        chars_today += len(item)
                    except (json.JSONDecodeError, KeyError):
                        continue

            stats.messages_today = messages_today
            # Rough estimate: ~4 characters per token
            stats.estimated_tokens_today = chars_today // 4
    except Exception:
        pass  # Non-critical, just skip

    return stats
