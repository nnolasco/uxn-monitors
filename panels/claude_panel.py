from datetime import datetime, timezone

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen

import config
from app_service import AppSnapshot
from token_service import TokenStats
from usage_service import UsageData
from system_service import AppGroup, SystemSnapshot, format_memory
from panels.painters import draw_process_row, draw_section_header


def _status_color(pct: float) -> str:
    if pct < 50:
        return config.COLOR_SAFE
    elif pct < 80:
        return config.COLOR_MODERATE
    else:
        return config.COLOR_CRITICAL


class ClaudePanel:
    """Draws the Claude Max usage metrics + process tables in the left panel."""

    def __init__(self, rect: QRectF):
        self.rect = rect

    def paint(self, p: QPainter, usage: UsageData, loading: bool,
              snapshot: SystemSnapshot | None = None,
              app_snapshot: AppSnapshot | None = None,
              token_stats: TokenStats | None = None):
        if loading and usage.error is None and usage.session_utilization == 0.0:
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
            p.setFont(QFont(config.FONT_FAMILY, config.FONT_SIZE))
            p.drawText(self.rect, Qt.AlignmentFlag.AlignCenter, "Loading...")
        elif usage.error:
            self._draw_error(p, usage)
        else:
            y = self._draw_metrics(p, usage)
            if token_stats is not None and token_stats.lifetime_total > 0:
                y = self._draw_token_stats(p, y + 10, token_stats)
            if snapshot is not None:
                y = self._draw_terminals(p, y + 14, snapshot)
                y = self._draw_top_processes(p, y + 10, snapshot)
            if app_snapshot is not None:
                self._draw_app_integrations(p, y + 10, app_snapshot)

    def _draw_error(self, p: QPainter, usage: UsageData):
        p.setPen(QPen(QColor(config.COLOR_CRITICAL)))
        p.setFont(QFont(config.FONT_FAMILY, config.LABEL_FONT_SIZE))
        error_text = usage.error or "Unknown error"
        if len(error_text) > 80:
            error_text = error_text[:77] + "..."
        r = QRectF(self.rect.left() + 14, self.rect.top() + 10,
                   self.rect.width() - 28, 100)
        p.drawText(r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                   | Qt.TextFlag.TextWordWrap, error_text)

    def _draw_metrics(self, p: QPainter, u: UsageData) -> float:
        pad = 14
        x = self.rect.left() + pad
        w = self.rect.width() - pad * 2
        y = self.rect.top() + 12

        # Metric 1: Current Session
        color1 = _status_color(u.session_utilization)
        y = self._draw_metric(
            p, x, y, w,
            label="Current Session",
            value=f"{u.session_utilization:.0f}%",
            subtitle=f"Resets in {u.session_reset_str}",
            pct=u.session_utilization / 100.0,
            color=color1,
        )

        # Metric 2: Weekly Limit
        color2 = _status_color(u.weekly_utilization)
        y = self._draw_metric(
            p, x, y + 10, w,
            label="Weekly Limit (All Models)",
            value=f"{u.weekly_utilization:.0f}%",
            subtitle=f"Resets in {u.weekly_reset_str}",
            pct=u.weekly_utilization / 100.0,
            color=color2,
        )

        # Metric 3: Daily Average
        avg = u.avg_per_day
        avg_val = f"{avg:.1f}%" if avg is not None else "\u2014"
        avg_pct = min(avg / 20.0, 1.0) if avg is not None else 0.0
        y = self._draw_metric(
            p, x, y + 10, w,
            label="Daily Average",
            value=avg_val,
            subtitle=f"~{avg:.1f}%/day over {u.days_elapsed:.1f}d" if avg is not None else "No data yet",
            pct=avg_pct,
            color=config.COLOR_SAFE if avg is not None and avg < 15 else config.COLOR_MODERATE if avg is not None else config.COLOR_SAFE,
        )
        return y

    def _draw_metric(self, p: QPainter, x: float, y: float, w: float,
                     label: str, value: str, subtitle: str,
                     pct: float, color: str) -> float:
        # Label (left) + value (right)
        p.setPen(QPen(QColor(config.TEXT_COLOR)))
        p.setFont(QFont(config.FONT_FAMILY, config.FONT_SIZE))
        p.drawText(QRectF(x, y, w * 0.7, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        p.setFont(QFont(config.FONT_FAMILY, config.FONT_SIZE, QFont.Weight.Bold))
        p.setPen(QPen(QColor(color)))
        p.drawText(QRectF(x, y, w, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value)

        # Subtitle
        p.setPen(QPen(QColor("#666666")))
        p.setFont(QFont(config.FONT_FAMILY, config.FOOTER_FONT_SIZE))
        p.drawText(QRectF(x, y + 18, w, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

        # Progress bar
        bar_y = y + 34
        self._draw_progress_bar(p, x, bar_y, w, pct, color)
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
        fill_w = max(h, width * min(pct, 1.0))
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

    # ── Token Stats ────────────────────────────────────

    def _draw_token_stats(self, p: QPainter, y: float, ts: TokenStats) -> float:
        pad = 14
        x = self.rect.left() + pad
        w = self.rect.width() - pad * 2
        row_h = 17

        y = draw_section_header(p, x, y, w, "Token Usage")

        # Row helper
        def _row(label: str, value: str, color: str = "#888888"):
            nonlocal y
            p.setFont(QFont(config.FONT_FAMILY, 9))
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
            p.drawText(QRectF(x, y, w * 0.6, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QPen(QColor(color)))
            p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
            p.drawText(QRectF(x, y, w, row_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value)
            y += row_h

        _row("Output tokens", ts.lifetime_output_str, config.COLOR_CPU)
        _row("Input tokens", ts.lifetime_input_str, config.COLOR_GPU)
        _row("Cache reads", ts.cache_read_str, config.COLOR_NET_UP)

        if ts.estimated_tokens_today > 0:
            _row("Today (est.)", ts.tokens_today_str, config.COLOR_MODERATE)

        # Staleness note
        if ts.cache_last_computed:
            p.setPen(QPen(QColor("#555555")))
            p.setFont(QFont(config.FONT_FAMILY, 7))
            p.drawText(QRectF(x, y, w, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"Stats cached: {ts.cache_last_computed}")
            y += 14

        return y

    # ── Terminal Processes ──────────────────────────────

    def _draw_terminals(self, p: QPainter, y: float, snap: SystemSnapshot) -> float:
        pad = 14
        x = self.rect.left() + pad
        w = self.rect.width() - pad * 2

        y = draw_section_header(p, x, y, w, "Terminal Processes")

        if not snap.terminals:
            p.setPen(QPen(QColor("#555555")))
            p.setFont(QFont(config.FONT_FAMILY, 8))
            p.drawText(QRectF(x, y, w, 17),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "No terminal processes found")
            return y + 20

        # Column headers
        row_h = 18
        p.setPen(QPen(QColor("#555555")))
        p.setFont(QFont(config.FONT_FAMILY, 8))
        col_name_w = w * 0.40
        col_cnt_w = w * 0.12
        col_cpu_w = w * 0.18
        col_mem_w = w * 0.16
        col_ch_w = w * 0.14
        hdr_y = y
        p.drawText(QRectF(x, hdr_y, col_name_w, row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "NAME")
        p.drawText(QRectF(x + col_name_w, hdr_y, col_cnt_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "CNT")
        p.drawText(QRectF(x + col_name_w + col_cnt_w, hdr_y, col_cpu_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "CPU%")
        p.drawText(QRectF(x + col_name_w + col_cnt_w + col_cpu_w, hdr_y, col_mem_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "MEM")
        p.drawText(QRectF(x + col_name_w + col_cnt_w + col_cpu_w + col_mem_w, hdr_y, col_ch_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "CHLD")
        y = hdr_y + row_h + 2

        for t in snap.terminals[:6]:
            p.setFont(QFont(config.FONT_FAMILY, 9))
            name = t.name[:22] + ".." if len(t.name) > 24 else t.name
            p.setPen(QPen(QColor(config.TEXT_COLOR)))
            p.drawText(QRectF(x, y, col_name_w, row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

            p.setPen(QPen(QColor("#888888")))
            p.drawText(QRectF(x + col_name_w, y, col_cnt_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(t.process_count))

            cpu_color = _status_color(t.cpu_percent) if t.cpu_percent > 5 else "#888888"
            p.setPen(QPen(QColor(cpu_color)))
            p.drawText(QRectF(x + col_name_w + col_cnt_w, y, col_cpu_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{t.cpu_percent:.1f}")

            p.setPen(QPen(QColor("#888888")))
            p.drawText(QRectF(x + col_name_w + col_cnt_w + col_cpu_w, y, col_mem_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, format_memory(t.memory_mb))

            p.setPen(QPen(QColor("#666666")))
            p.drawText(QRectF(x + col_name_w + col_cnt_w + col_cpu_w + col_mem_w, y, col_ch_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(t.child_count))

            y += row_h

        return y

    # ── Top Processes ──────────────────────────────────

    def _draw_top_processes(self, p: QPainter, y: float, snap: SystemSnapshot) -> float:
        pad = 14
        x = self.rect.left() + pad
        w = self.rect.width() - pad * 2

        # Top CPU Apps
        y = draw_section_header(p, x, y, w, "Top CPU Apps")
        for i, grp in enumerate(snap.top_cpu_groups[:5]):
            label = f"{grp.name} ({grp.process_count})"
            color = _status_color(grp.cpu_percent) if grp.cpu_percent > 10 else "#888888"
            draw_process_row(p, x, y, w,
                             label, f"{grp.cpu_percent:.1f}%", color, rank=i + 1)
            y += 19

        # Top Memory Apps
        y = draw_section_header(p, x, y + 10, w, "Top Memory Apps")
        for i, grp in enumerate(snap.top_mem_groups[:5]):
            label = f"{grp.name} ({grp.process_count})"
            draw_process_row(p, x, y, w,
                             label, format_memory(grp.memory_mb), "#60a5fa", rank=i + 1)
            y += 19

        return y

    # ── App Integrations ──────────────────────────────

    def _draw_app_integrations(self, p: QPainter, y: float, app: AppSnapshot):
        pad = 14
        x = self.rect.left() + pad
        w = self.rect.width() - pad * 2
        row_h = 18

        y = draw_section_header(p, x, y, w, "Notifications")

        # Outlook unread emails
        outlook = app.outlook
        if outlook.error:
            p.setPen(QPen(QColor("#555555")))
            p.setFont(QFont(config.FONT_FAMILY, 8))
            p.drawText(QRectF(x, y, w, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "\u2709 Outlook: not connected")
            y += row_h
        else:
            # Unread count
            p.setFont(QFont(config.FONT_FAMILY, 9))
            count_color = config.COLOR_MODERATE if outlook.unread_count > 0 else "#888888"
            p.setPen(QPen(QColor(count_color)))
            p.drawText(QRectF(x, y, w, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"\u2709 {outlook.unread_count} unread emails")
            y += row_h

            # Upcoming appointments
            if outlook.appointments:
                for appt in outlook.appointments[:3]:
                    p.setPen(QPen(QColor("#888888")))
                    p.setFont(QFont(config.FONT_FAMILY, 8))
                    appt_text = f"  \u23F0 {appt.start_time} \u2014 {appt.subject}"
                    p.drawText(QRectF(x, y, w, row_h),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               appt_text)
                    y += row_h
            else:
                p.setPen(QPen(QColor("#555555")))
                p.setFont(QFont(config.FONT_FAMILY, 8))
                p.drawText(QRectF(x, y, w, row_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           "  No upcoming appointments")
                y += row_h

        y += 4

        # Slack unread DMs (per workspace)
        for ws in app.slack_workspaces:
            if ws.error and "not configured" in (ws.error or ""):
                p.setPen(QPen(QColor("#555555")))
                p.setFont(QFont(config.FONT_FAMILY, 8))
                p.drawText(QRectF(x, y, w, row_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           "\U0001F4AC Slack: not configured")
            elif ws.error:
                p.setPen(QPen(QColor("#555555")))
                p.setFont(QFont(config.FONT_FAMILY, 8))
                p.drawText(QRectF(x, y, w, row_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           f"\U0001F4AC {ws.name}: not connected")
            else:
                count_color = config.COLOR_MODERATE if ws.unread_dm_count > 0 else "#888888"
                p.setPen(QPen(QColor(count_color)))
                p.setFont(QFont(config.FONT_FAMILY, 9))
                p.drawText(QRectF(x, y, w, row_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           f"\U0001F4AC {ws.name}: {ws.unread_dm_count} unread DMs")
            y += row_h
