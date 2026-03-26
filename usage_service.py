import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

import config


@dataclass
class UsageData:
    # 5-hour session window
    session_utilization: float = 0.0  # 0-100%
    session_reset: datetime | None = None

    # 7-day weekly window
    weekly_utilization: float = 0.0  # 0-100%
    weekly_reset: datetime | None = None

    # Derived
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None

    @property
    def session_remaining(self) -> float:
        return max(0.0, 100.0 - self.session_utilization)

    @property
    def weekly_remaining(self) -> float:
        return max(0.0, 100.0 - self.weekly_utilization)

    @property
    def days_left(self) -> float | None:
        if self.weekly_reset is None:
            return None
        delta = self.weekly_reset - datetime.now(timezone.utc)
        return max(0.0, delta.total_seconds() / 86400)

    @property
    def days_elapsed(self) -> float | None:
        if self.days_left is None:
            return None
        return max(0.001, 7.0 - self.days_left)

    @property
    def avg_per_day(self) -> float | None:
        if self.days_elapsed is None:
            return None
        return self.weekly_utilization / self.days_elapsed

    @property
    def session_reset_str(self) -> str:
        if self.session_reset is None:
            return "—"
        delta = self.session_reset - datetime.now(timezone.utc)
        secs = max(0, int(delta.total_seconds()))
        h, m = secs // 3600, (secs % 3600) // 60
        return f"{h}h {m}m"

    @property
    def weekly_reset_str(self) -> str:
        if self.days_left is None:
            return "—"
        d = self.days_left
        days = int(d)
        hours = int((d - days) * 24)
        return f"{days}d {hours}h"


def read_oauth_token(credentials_path: Path | None = None) -> str:
    path = credentials_path or config.CLAUDE_CREDENTIALS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Claude credentials not found at {path}. Run 'claude login' first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))

    # The credentials file may have different structures
    # Try common patterns
    if "claudeAiOauth" in data:
        oauth = data["claudeAiOauth"]
        if isinstance(oauth, dict) and "accessToken" in oauth:
            return oauth["accessToken"]
    if "accessToken" in data:
        return data["accessToken"]
    if "oauthAccessToken" in data:
        return data["oauthAccessToken"]

    raise ValueError(
        f"Could not find OAuth token in {path}. "
        "Expected 'claudeAiOauth.accessToken', 'accessToken', or 'oauthAccessToken' key."
    )


def fetch_usage(credentials_path: Path | None = None) -> UsageData:
    try:
        token = read_oauth_token(credentials_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        return UsageData(error=str(e))

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": config.USER_AGENT,
        "anthropic-beta": config.ANTHROPIC_BETA,
        "anthropic-version": config.ANTHROPIC_VERSION,
    }

    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }

    try:
        resp = requests.post(
            config.ANTHROPIC_MESSAGES_URL,
            headers=headers,
            json=body,
            timeout=30,
        )
    except requests.RequestException as e:
        return UsageData(error=f"Network error: {e}")

    if resp.status_code not in (200, 201):
        return UsageData(error=f"API error {resp.status_code}: {resp.text[:200]}")

    return _parse_rate_limit_headers(resp.headers)


def _parse_rate_limit_headers(headers: dict) -> UsageData:
    def get_float(name: str) -> float | None:
        val = headers.get(name)
        if val is not None:
            try:
                return float(val)
            except ValueError:
                pass
        return None

    # Session (5h)
    session_util_raw = get_float("anthropic-ratelimit-unified-5h-utilization") or 0.0
    session_pct = session_util_raw * 100.0
    session_reset_ts = get_float("anthropic-ratelimit-unified-5h-reset")
    session_reset = (
        datetime.fromtimestamp(session_reset_ts, tz=timezone.utc)
        if session_reset_ts and session_reset_ts > 0
        else None
    )

    # If session window expired, reset to 0
    if session_reset and session_reset < datetime.now(timezone.utc):
        session_pct = 0.0

    # Weekly (7d)
    weekly_util_raw = get_float("anthropic-ratelimit-unified-7d-utilization") or 0.0
    weekly_pct = weekly_util_raw * 100.0
    weekly_reset_ts = get_float("anthropic-ratelimit-unified-7d-reset")
    weekly_reset = (
        datetime.fromtimestamp(weekly_reset_ts, tz=timezone.utc)
        if weekly_reset_ts and weekly_reset_ts > 0
        else None
    )

    return UsageData(
        session_utilization=session_pct,
        session_reset=session_reset,
        weekly_utilization=weekly_pct,
        weekly_reset=weekly_reset,
        last_updated=datetime.now(timezone.utc),
    )
