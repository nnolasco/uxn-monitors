# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Windows desktop overlay app shaped like an iPhone notch that displays Claude Max account usage telemetry. Built with Python + PyQt6.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Architecture

- **`main.py`** — Entry point. Creates QApplication and NotchWindow.
- **`notch_window.py`** — PyQt6 frameless, transparent, always-on-top card widget (~300x260px). Custom `paintEvent` draws header (title + refresh/quit buttons), three metric rows (label, subtitle, progress bar), and a footer. Handles drag-to-move, button hit-testing, and QTimer-based polling.
- **`usage_service.py`** — Reads OAuth token from `~/.claude/.credentials.json` (written by `claude login`). Sends a minimal Messages API POST to haiku and parses rate limit headers for usage data.
- **`config.py`** — All constants: API endpoints, colors, dimensions, poll interval.

## How Usage Data Is Obtained

The app makes a minimal `POST https://api.anthropic.com/v1/messages` call (1-token haiku, costs almost nothing) and reads these response headers:

| Header | Meaning |
|--------|---------|
| `anthropic-ratelimit-unified-5h-utilization` | 5-hour session usage (0.0–1.0) |
| `anthropic-ratelimit-unified-5h-reset` | Session reset unix timestamp |
| `anthropic-ratelimit-unified-7d-utilization` | 7-day weekly usage (0.0–1.0) |
| `anthropic-ratelimit-unified-7d-reset` | Weekly reset unix timestamp |

Authentication requires `Authorization: Bearer {token}` + `anthropic-beta: oauth-2025-04-20` headers.
