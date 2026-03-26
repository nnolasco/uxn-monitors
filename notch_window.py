from datetime import datetime, timezone

import threading

from PyQt6.QtCore import QPointF, QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget

import config
from usage_service import UsageData, fetch_usage


def _status_color(pct: float) -> str:
    if pct < 50:
        return config.COLOR_SAFE
    elif pct < 80:
        return config.COLOR_MODERATE
    else:
        return config.COLOR_CRITICAL


class NotchWindow(QWidget):
    _fetch_done = pyqtSignal(UsageData)

    def __init__(self):
        super().__init__()
        self._drag_pos: QPointF | None = None
        self._usage: UsageData = UsageData()
        self._loading = False
        self._hover_btn: str | None = None  # "refresh" | "quit" | None

        # Button hit-test rects (set during paint)
        self._refresh_btn_rect = QRectF()
        self._quit_btn_rect = QRectF()

        self._fetch_done.connect(self._on_fetch_done)

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
        self.setFixedSize(config.NOTCH_WIDTH, config.NOTCH_HEIGHT)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y()
            self.move(x, y)

    def _setup_polling(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(config.POLL_INTERVAL_MS)

    def _setup_footer_timer(self):
        self._footer_timer = QTimer(self)
        self._footer_timer.timeout.connect(self.update)
        self._footer_timer.start(30_000)  # repaint every 30s to keep "Updated Xm ago" fresh

    def _refresh(self):
        if self._loading:
            return  # already fetching
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

    # ── Paint ──────────────────────────────────────────

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

        if self._loading and self._usage.error is None:
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
            p.setFont(QFont(config.FONT_FAMILY, config.FONT_SIZE))
            p.drawText(QRectF(0, 0, self.width(), self.height()),
                       Qt.AlignmentFlag.AlignCenter, "Loading...")
        elif self._usage.error:
            self._draw_error(p)
        else:
            self._draw_metrics(p)

        self._draw_footer(p)
        p.end()

    def _draw_header(self, p: QPainter):
        pad = 14
        y_center = config.HEADER_HEIGHT / 2

        # Title
        p.setPen(QPen(QColor(config.TEXT_COLOR)))
        title_font = QFont(config.FONT_FAMILY, config.TITLE_FONT_SIZE, QFont.Weight.Bold)
        p.setFont(title_font)
        p.drawText(QRectF(pad, 0, 200, config.HEADER_HEIGHT),
                   Qt.AlignmentFlag.AlignVCenter, "Claude Max Monitor")

        # Refresh button (↻)
        btn_size = 22
        btn_y = (config.HEADER_HEIGHT - btn_size) / 2
        refresh_x = self.width() - pad - btn_size * 2 - 6
        self._refresh_btn_rect = QRectF(refresh_x, btn_y, btn_size, btn_size)

        btn_font = QFont(config.FONT_FAMILY, 12)
        p.setFont(btn_font)

        # Highlight on hover
        if self._hover_btn == "refresh":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#333333")))
            p.drawRoundedRect(self._refresh_btn_rect, 4, 4)
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
        else:
            p.setPen(QPen(QColor(config.BUTTON_COLOR)))
        p.drawText(self._refresh_btn_rect, Qt.AlignmentFlag.AlignCenter, "\u21bb")

        # Quit button (✕)
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

        # Separator line under header
        p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
        p.drawLine(int(pad), int(config.HEADER_HEIGHT),
                   int(self.width() - pad), int(config.HEADER_HEIGHT))

    def _draw_error(self, p: QPainter):
        p.setPen(QPen(QColor(config.COLOR_CRITICAL)))
        p.setFont(QFont(config.FONT_FAMILY, config.LABEL_FONT_SIZE))
        error_text = self._usage.error or "Unknown error"
        if len(error_text) > 80:
            error_text = error_text[:77] + "..."
        r = QRectF(14, config.HEADER_HEIGHT + 10, self.width() - 28, 100)
        p.drawText(r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                   | Qt.TextFlag.TextWordWrap, error_text)

    def _draw_metrics(self, p: QPainter):
        u = self._usage
        pad = 14
        y = config.HEADER_HEIGHT + 12
        section_h = 62

        # Metric 1: Current Session
        color1 = _status_color(u.session_utilization)
        y = self._draw_metric(
            p, y, pad,
            label="Current Session",
            value=f"{u.session_utilization:.0f}%",
            subtitle=f"Resets in {u.session_reset_str}",
            pct=u.session_utilization / 100.0,
            color=color1,
        )

        # Metric 2: Weekly Limit
        color2 = _status_color(u.weekly_utilization)
        y = self._draw_metric(
            p, y + 10, pad,
            label="Weekly Limit (All Models)",
            value=f"{u.weekly_utilization:.0f}%",
            subtitle=f"Resets in {u.weekly_reset_str}",
            pct=u.weekly_utilization / 100.0,
            color=color2,
        )

        # Metric 3: Daily Average
        avg = u.avg_per_day
        avg_val = f"{avg:.1f}%" if avg is not None else "\u2014"
        avg_pct = min(avg / 20.0, 1.0) if avg is not None else 0.0  # scale: 20%/day = full bar
        avg_color = _status_color(avg * (7.0 / max(u.days_elapsed or 1, 1))) if avg is not None else config.COLOR_SAFE
        self._draw_metric(
            p, y + 10, pad,
            label="Daily Average",
            value=avg_val,
            subtitle=f"~{avg:.1f}%/day over {u.days_elapsed:.1f}d" if avg is not None else "No data yet",
            pct=avg_pct,
            color=config.COLOR_SAFE if avg is not None and avg < 15 else config.COLOR_MODERATE if avg is not None else config.COLOR_SAFE,
        )

    def _draw_metric(self, p: QPainter, y: float, pad: float,
                     label: str, value: str, subtitle: str,
                     pct: float, color: str) -> float:
        w = self.width() - pad * 2

        # Label (left) + value (right)
        p.setPen(QPen(QColor(config.TEXT_COLOR)))
        label_font = QFont(config.FONT_FAMILY, config.FONT_SIZE)
        p.setFont(label_font)
        p.drawText(QRectF(pad, y, w * 0.7, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        value_font = QFont(config.FONT_FAMILY, config.FONT_SIZE, QFont.Weight.Bold)
        p.setFont(value_font)
        p.setPen(QPen(QColor(color)))
        p.drawText(QRectF(pad, y, w, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value)

        # Subtitle
        p.setPen(QPen(QColor("#666666")))
        sub_font = QFont(config.FONT_FAMILY, config.FOOTER_FONT_SIZE)
        p.setFont(sub_font)
        p.drawText(QRectF(pad, y + 18, w, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

        # Progress bar
        bar_y = y + 34
        self._draw_progress_bar(p, pad, bar_y, w, pct, color)

        return bar_y + config.BAR_HEIGHT + 4

    def _draw_progress_bar(self, p: QPainter, x: float, y: float,
                           width: float, pct: float, color: str):
        h = config.BAR_HEIGHT
        r = config.BAR_RADIUS

        # Track
        track = QPainterPath()
        track.addRoundedRect(QRectF(x, y, width, h), r, r)
        p.fillPath(track, QBrush(QColor(config.BAR_TRACK_COLOR)))

        # Fill
        fill_w = max(h, width * min(pct, 1.0))  # at least pill-width so it looks good
        if pct > 0.001:
            fill = QPainterPath()
            fill.addRoundedRect(QRectF(x, y, fill_w, h), r, r)
            p.fillPath(fill, QBrush(QColor(color)))

            # Glow dot at fill edge
            dot_r = h / 2 + 1
            dot_x = x + fill_w - dot_r
            dot_y = y + h / 2
            p.setPen(Qt.PenStyle.NoPen)
            glow = QColor(color)
            glow.setAlpha(120)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

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

        # Poll interval
        poll_min = config.POLL_INTERVAL_MS // 60000
        p.drawText(QRectF(self.width() - pad - 60, footer_y, 60, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{poll_min}m poll")

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

        # Hover tracking for buttons
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
