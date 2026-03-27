import threading
from datetime import datetime, timezone

from PyQt6.QtCore import QByteArray, QPointF, QRectF, QSettings, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget

import config
from panels.claude_panel import ClaudePanel
from panels.system_panel import SystemPanel
from app_service import AppSnapshot, collect_apps
from system_service import SystemMonitor, SystemSnapshot
from token_service import TokenStats, load_token_stats
from usage_service import UsageData, fetch_usage

RESIZE_ZONE = 8    # pixels from right edge for resize handle
DIVIDER_ZONE = 6   # pixels each side of divider for hit-test


class NotchWindow(QWidget):
    _fetch_done = pyqtSignal(UsageData)
    _sys_done = pyqtSignal(SystemSnapshot)
    _app_done = pyqtSignal(AppSnapshot)

    def __init__(self):
        super().__init__()
        self._drag_pos: QPointF | None = None
        self._usage: UsageData = UsageData()
        self._loading = False
        self._hover_btn: str | None = None

        # Button hit-test rects
        self._refresh_btn_rect = QRectF()
        self._quit_btn_rect = QRectF()

        # Divider & resize state
        self._left_width: float = config.DEFAULT_LEFT_WIDTH
        self._dragging_divider = False
        self._resizing = False
        self._resize_start_x: float = 0
        self._resize_start_w: int = 0
        self._hover_zone: str | None = None  # "divider" | "resize" | None

        # System monitoring
        self._system_monitor = SystemMonitor()
        self._snapshot = SystemSnapshot()
        self._sys_collecting = False

        # App integrations
        self._app_snapshot = AppSnapshot()
        self._app_collecting = False

        # Token stats
        self._token_stats = TokenStats()

        # Persistence
        self._settings = QSettings("UXNMonitors", "ClaudeMaxMonitor")

        # Panels (will be rebuilt after restore)
        self._claude_panel = ClaudePanel(QRectF())
        self._system_panel = SystemPanel(QRectF())

        # Signals
        self._fetch_done.connect(self._on_fetch_done)
        self._sys_done.connect(self._on_sys_done)
        self._app_done.connect(self._on_app_done)

        self._setup_window()
        self._restore_state()
        self._rebuild_panels()
        self._setup_polling()
        self._setup_footer_timer()
        self._refresh()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(config.MIN_WIDTH, config.TOTAL_HEIGHT)
        self.setMaximumHeight(config.TOTAL_HEIGHT)
        self.resize(config.DEFAULT_WIDTH, config.TOTAL_HEIGHT)

    def _restore_state(self):
        """Restore window geometry and divider position from settings."""
        geometry = self._settings.value("geometry")
        if geometry and isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        else:
            self._center_on_screen()

        saved_divider = self._settings.value("divider_x")
        if saved_divider is not None:
            try:
                self._left_width = float(saved_divider)
            except (ValueError, TypeError):
                pass
        self._clamp_divider()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y()
            self.move(x, y)

    def _save_state(self):
        """Persist window geometry and divider position."""
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("divider_x", self._left_width)

    def _rebuild_panels(self):
        """Recalculate panel rects based on current width and divider position."""
        header_h = config.HEADER_HEIGHT
        footer_h = 28
        body_top = header_h
        body_h = self.height() - header_h - footer_h
        right_width = self.width() - self._left_width
        self._claude_panel.rect = QRectF(0, body_top, self._left_width, body_h)
        self._system_panel.rect = QRectF(self._left_width, body_top, right_width, body_h)

    def _clamp_divider(self):
        """Ensure divider stays within min bounds."""
        max_left = self.width() - config.MIN_RIGHT_WIDTH
        self._left_width = max(config.MIN_LEFT_WIDTH, min(self._left_width, max_left))

    def _setup_polling(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(config.POLL_INTERVAL_MS)

        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._collect_system)
        self._sys_timer.start(config.SYSTEM_POLL_INTERVAL_MS)

        self._app_timer = QTimer(self)
        self._app_timer.timeout.connect(self._collect_apps)
        self._app_timer.start(config.APP_POLL_INTERVAL_MS)
        self._collect_apps()

    def _setup_footer_timer(self):
        self._footer_timer = QTimer(self)
        self._footer_timer.timeout.connect(self.update)
        self._footer_timer.start(30_000)

    # ── Claude API fetch ──────────────────────────────

    def _refresh(self):
        if self._loading:
            return
        self._loading = True
        self.update()
        threading.Thread(target=self._do_fetch, daemon=True).start()
        self._collect_apps()

    def _do_fetch(self):
        result = fetch_usage()
        self._fetch_done.emit(result)

    def _on_fetch_done(self, data: UsageData):
        self._usage = data
        self._loading = False
        self.update()

    # ── System metrics fetch ──────────────────────────

    def _collect_system(self):
        if self._sys_collecting:
            return
        self._sys_collecting = True
        threading.Thread(target=self._do_collect_system, daemon=True).start()

    def _do_collect_system(self):
        snapshot = self._system_monitor.collect()
        self._sys_done.emit(snapshot)

    def _on_sys_done(self, snapshot: SystemSnapshot):
        self._snapshot = snapshot
        self._sys_collecting = False
        self.update()

    # ── App integrations fetch ────────────────────────

    def _collect_apps(self):
        if self._app_collecting:
            return
        self._app_collecting = True
        threading.Thread(target=self._do_collect_apps, daemon=True).start()

    def _do_collect_apps(self):
        snapshot = collect_apps()
        self._app_done.emit(snapshot)

    def _on_app_done(self, snapshot: AppSnapshot):
        self._app_snapshot = snapshot
        self._token_stats = load_token_stats()
        self._app_collecting = False
        self.update()

    # ── Paint ─────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Card background
        card = QPainterPath()
        rect = QRectF(0, 0, self.width(), self.height())
        card.addRoundedRect(rect, config.NOTCH_RADIUS, config.NOTCH_RADIUS)
        p.fillPath(card, QBrush(QColor(config.BACKGROUND_COLOR)))
        p.setPen(QPen(QColor("#333333"), 1))
        p.drawPath(card)

        self._draw_header(p)

        # Vertical divider
        sep_x = self._left_width
        divider_color = "#444444" if self._hover_zone == "divider" else config.SEPARATOR_COLOR
        divider_width = 2 if self._hover_zone == "divider" else 1
        p.setPen(QPen(QColor(divider_color), divider_width))
        p.drawLine(int(sep_x), int(config.HEADER_HEIGHT),
                   int(sep_x), int(self.height() - 28))

        # Grip dots on divider when hovering
        if self._hover_zone == "divider" or self._dragging_divider:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#666666")))
            mid_y = self.height() / 2
            for dy in [-12, 0, 12]:
                p.drawEllipse(QPointF(sep_x, mid_y + dy), 2, 2)

        # Panels
        self._claude_panel.paint(p, self._usage, self._loading, self._snapshot, self._app_snapshot, self._token_stats)
        self._system_panel.paint(p, self._snapshot, self._system_monitor)

        self._draw_footer(p)
        p.end()

    def _draw_header(self, p: QPainter):
        pad = 14
        p.setPen(QPen(QColor(config.TEXT_COLOR)))
        title_font = QFont(config.FONT_FAMILY, config.TITLE_FONT_SIZE, QFont.Weight.Bold)
        p.setFont(title_font)
        p.drawText(QRectF(pad, 0, 200, config.HEADER_HEIGHT),
                   Qt.AlignmentFlag.AlignVCenter, "Claude Max Monitor")

        btn_size = 22
        btn_y = (config.HEADER_HEIGHT - btn_size) / 2
        refresh_x = self.width() - pad - btn_size * 2 - 6
        self._refresh_btn_rect = QRectF(refresh_x, btn_y, btn_size, btn_size)

        btn_font = QFont(config.FONT_FAMILY, 12)
        p.setFont(btn_font)

        if self._hover_btn == "refresh":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#333333")))
            p.drawRoundedRect(self._refresh_btn_rect, 4, 4)
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
        else:
            p.setPen(QPen(QColor(config.BUTTON_COLOR)))
        p.drawText(self._refresh_btn_rect, Qt.AlignmentFlag.AlignCenter, "\u21bb")

        quit_x = self.width() - pad - btn_size
        self._quit_btn_rect = QRectF(quit_x, btn_y, btn_size, btn_size)

        if self._hover_btn == "quit":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#333333")))
            p.drawRoundedRect(self._quit_btn_rect, 4, 4)
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
        else:
            p.setPen(QPen(QColor(config.BUTTON_COLOR)))
        p.drawText(self._quit_btn_rect, Qt.AlignmentFlag.AlignCenter, "\u2715")

        p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
        p.drawLine(int(pad), int(config.HEADER_HEIGHT),
                   int(self.width() - pad), int(config.HEADER_HEIGHT))

    def _draw_footer(self, p: QPainter):
        pad = 14
        footer_y = self.height() - 28

        p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
        p.drawLine(int(pad), int(footer_y - 4),
                   int(self.width() - pad), int(footer_y - 4))

        p.setPen(QPen(QColor("#666666")))
        p.setFont(QFont(config.FONT_FAMILY, config.FOOTER_FONT_SIZE))

        u = self._usage
        if u.last_updated:
            delta = (datetime.now(timezone.utc) - u.last_updated).total_seconds()
            if delta < 60:
                ago = "just now"
            else:
                ago = f"{int(delta // 60)}m ago"
            p.drawText(QRectF(pad, footer_y, 150, 20),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"Updated {ago}")

        mem = self._snapshot.memory
        if mem:
            footer_info = f"CPU: {self._snapshot.cpu_percent:.0f}%  RAM: {mem.usage_percent:.0f}%"
        else:
            footer_info = f"CPU: {self._snapshot.cpu_percent:.0f}%"
        p.drawText(QRectF(self.width() - pad - 200, footer_y, 200, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   footer_info)

    # ── Hit-test helpers ──────────────────────────────

    def _is_in_divider_zone(self, pos: QPointF) -> bool:
        return (abs(pos.x() - self._left_width) <= DIVIDER_ZONE
                and config.HEADER_HEIGHT < pos.y() < self.height() - 28)

    def _is_in_resize_zone(self, pos: QPointF) -> bool:
        return pos.x() >= self.width() - RESIZE_ZONE

    # ── Mouse events ──────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()

            # Buttons
            if self._refresh_btn_rect.contains(pos):
                self._refresh()
                return
            if self._quit_btn_rect.contains(pos):
                QApplication.quit()
                return

            # Divider drag
            if self._is_in_divider_zone(pos):
                self._dragging_divider = True
                event.accept()
                return

            # Right-edge resize
            if self._is_in_resize_zone(pos):
                self._resizing = True
                self._resize_start_x = event.globalPosition().x()
                self._resize_start_w = self.width()
                event.accept()
                return

            # Window drag
            self._drag_pos = event.globalPosition() - QPointF(self.x(), self.y())
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position()

        # Divider dragging
        if self._dragging_divider and event.buttons() & Qt.MouseButton.LeftButton:
            self._left_width = pos.x()
            self._clamp_divider()
            self._rebuild_panels()
            self.update()
            return

        # Right-edge resizing
        if self._resizing and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().x() - self._resize_start_x
            new_w = max(config.MIN_WIDTH, int(self._resize_start_w + delta))
            self.resize(new_w, self.height())
            self._clamp_divider()
            self._rebuild_panels()
            self.update()
            return

        # Window dragging
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition() - self._drag_pos
            self.move(int(new_pos.x()), int(new_pos.y()))
            event.accept()
            return

        # Hover detection (no button pressed)
        old_zone = self._hover_zone
        if self._is_in_divider_zone(pos):
            self._hover_zone = "divider"
            self.setCursor(Qt.CursorShape.SplitHCursor)
        elif self._is_in_resize_zone(pos):
            self._hover_zone = "resize"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self._hover_zone = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if self._hover_zone != old_zone:
            self.update()

        # Button hover
        old = self._hover_btn
        if self._refresh_btn_rect.contains(pos):
            self._hover_btn = "refresh"
        elif self._quit_btn_rect.contains(pos):
            self._hover_btn = "quit"
        else:
            self._hover_btn = None
        if self._hover_btn != old:
            self.update()

    def leaveEvent(self, event):
        changed = False
        if self._hover_btn is not None:
            self._hover_btn = None
            changed = True
        if self._hover_zone is not None:
            self._hover_zone = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            changed = True
        if changed:
            self.update()

    def mouseReleaseEvent(self, event):
        if self._dragging_divider or self._resizing or self._drag_pos is not None:
            self._save_state()
        self._drag_pos = None
        self._dragging_divider = False
        self._resizing = False

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

    def resizeEvent(self, event):
        self._clamp_divider()
        self._rebuild_panels()
        super().resizeEvent(event)
