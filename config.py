from pathlib import Path

# Credentials
CLAUDE_CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# API
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA = "oauth-2025-04-20"
USER_AGENT = "claude-code/2.1.5"

# Polling
POLL_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes

# Window
NOTCH_WIDTH = 300
NOTCH_HEIGHT = 260
NOTCH_RADIUS = 16
BACKGROUND_COLOR = "#1a1a1a"
TEXT_COLOR = "#e0e0e0"
SEPARATOR_COLOR = "#2a2a2a"

# Header
HEADER_HEIGHT = 36

# Progress bars
BAR_HEIGHT = 6
BAR_RADIUS = 3
BAR_TRACK_COLOR = "#2a2a2a"

# Status colors
COLOR_SAFE = "#4ade80"       # green - <50%
COLOR_MODERATE = "#fb923c"   # orange - 50-80%
COLOR_CRITICAL = "#f87171"   # red - >80%

# Buttons
BUTTON_COLOR = "#555555"
BUTTON_HOVER_COLOR = "#777777"

# Font
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 11
LABEL_FONT_SIZE = 9
TITLE_FONT_SIZE = 11
FOOTER_FONT_SIZE = 8
