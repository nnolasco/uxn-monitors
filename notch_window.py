import threading
from datetime import datetime, timezone

from PyQt6.QtCore import QPointF, QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget

import config
from panels.claude_panel import ClaudePanel
from panels.system_panel import SystemPanel
from app_service import AppSnapshot, collect_apps
from system_service import SystemMonitor, SystemSnapshot
from usage_service import UsageData, fetch_usage


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

        # System monitoring
        self._system_monitor = SystemMonitor()
        self._snapshot = SystemSnapshot()
        self._sys_collecting = False

        # App integrations
        self._app_snapshot = AppSnapshot()
        self._app_collecting = False

        # Panels
        header_h = config.HEADER_HEIGHT
        footer_h = 28
        body_top = header_h
        body_h = config.TOTAL_HEIGHT - header_h - footer_h

        self._claude_panel = ClaudePanel(
            QRectF(0, body_top, config.LEFT_PANEL_WIDTH, body_h)
        )
        self._system_panel = SystemPanel(
            QRectF(config.LEFT_PANEL_WIDTH, body_top,
                   config.RIGHT_PANEL_WIDTH, body_h)
        )

        # Signals
        self._fetch_done.connect(self._on_fetch_done)
        self._sys_done.connect(self._on_sys_done)
        self._app_done.connect(self._on_app_done)

        self._setup_window()
        self._center_on_screen()
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
        self.setFixedSize(config.TOTAL_WIDTH, config.TOTAL_HEIGHT)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y()
            self.move(x, y)

    def _setup_polling(self):
        # Claude API polling (5 min)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(config.POLL_INTERVAL_MS)

        # System metrics polling (1 sec)
        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._collect_system)
        self._sys_timer.start(config.SYSTEM_POLL_INTERVAL_MS)

        # App integrations polling (60 sec)
        self._app_timer = QTimer(self)
        self._app_timer.timeout.connect(self._collect_apps)
        self._app_timer.start(config.APP_POLL_INTERVAL_MS)
        self._collect_apps()  # initial fetch

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

        # Header
        self._draw_header(p)

        # Vertical separator
        sep_x = config.LEFT_PANEL_WIDTH
        p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
        p.drawLine(int(sep_x), int(config.HEADER_HEIGHT),
                   int(sep_x), int(self.height() - 28))

        # Left panel: Claude metrics + process tables + notifications
        self._claude_panel.paint(p, self._usage, self._loading, self._snapshot, self._app_snapshot)

        # Right panel: System metrics
        self._system_panel.paint(p, self._snapshot, self._system_monitor)

        # Footer
        self._draw_footer(p)
        p.end()

    def _draw_header(self, p: QPainter):
        pad = 14
        # Title
        p.setPen(QPen(QColor(config.TEXT_COLOR)))
        title_font = QFont(config.FONT_FAMILY, config.TITLE_FONT_SIZE, QFont.Weight.Bold)
        p.setFont(title_font)
        p.drawText(QRectF(pad, 0, 200, config.HEADER_HEIGHT),
                   Qt.AlignmentFlag.AlignVCenter, "Claude Max Monitor")

        # Refresh button
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

        # Quit button
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

        # Separator under header
        p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
        p.drawLine(int(pad), int(config.HEADER_HEIGHT),
                   int(self.width() - pad), int(config.HEADER_HEIGHT))

    def _draw_footer(self, p: QPainter):
        pad = 14
        footer_y = self.height() - 28

        # Separator
        p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
        p.drawLine(int(pad), int(footer_y - 4),
                   int(self.width() - pad), int(footer_y - 4))

        p.setPen(QPen(QColor("#666666")))
        p.setFont(QFont(config.FONT_FAMILY, config.FOOTER_FONT_SIZE))

        # "Updated Xm ago"
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

        # System info on right side of footer
        mem = self._snapshot.memory
        if mem:
            footer_info = f"CPU: {self._snapshot.cpu_percent:.0f}%  RAM: {mem.usage_percent:.0f}%"
        else:
            footer_info = f"CPU: {self._snapshot.cpu_percent:.0f}%"
        p.drawText(QRectF(self.width() - pad - 200, footer_y, 200, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   footer_info)

    # ── Mouse events ──────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            if self._refresh_btn_rect.contains(pos):
                self._refresh()
                return
            if self._quit_btn_rect.contains(pos):
                QApplication.quit()
                return
            self._drag_pos = event.globalPosition() - QPointF(self.x(), self.y())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition() - self._drag_pos
            self.move(int(new_pos.x()), int(new_pos.y()))
            event.accept()
            return

        pos = event.position()
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
        if self._hover_btn is not None:
            self._hover_btn = None
            self.update()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
