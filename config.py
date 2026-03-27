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
DEFAULT_WIDTH = 850
MIN_WIDTH = 600
TOTAL_HEIGHT = 780
DEFAULT_LEFT_WIDTH = 400
MIN_LEFT_WIDTH = 250
MIN_RIGHT_WIDTH = 250
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

# System monitoring
SYSTEM_POLL_INTERVAL_MS = 1000   # 1 second for graphs
APP_POLL_INTERVAL_MS = 60_000    # 60 seconds for app integrations
PROCESS_POLL_INTERVAL_MS = 2000  # 2 seconds for process lists
SPARKLINE_HISTORY_SIZE = 120     # 2 minutes of samples

# Graph colors
COLOR_CPU = "#60a5fa"        # blue
COLOR_GPU = "#a78bfa"        # purple
COLOR_NET_DOWN = "#60a5fa"   # blue
COLOR_NET_UP = "#34d399"     # teal
COLOR_DISK_IO = "#fbbf24"    # amber

# Gauges
GAUGE_SECTION_HEIGHT = 160
GAUGE_TRACK_COLOR = "#2a2a2a"
