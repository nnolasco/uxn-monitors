from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen

import config
from system_service import (
    SystemMonitor, SystemSnapshot, format_bytes_rate,
)
from panels.painters import (
    draw_arc_gauge, draw_dual_sparkline, draw_graph_box, draw_sparkline,
)


def _status_color(pct: float) -> str:
    if pct < 50:
        return config.COLOR_SAFE
    elif pct < 80:
        return config.COLOR_MODERATE
    else:
        return config.COLOR_CRITICAL


class SystemPanel:
    """Draws 5 full-width graph rows in the right panel."""

    def __init__(self, rect: QRectF):
        self.rect = rect

    def paint(self, p: QPainter, snapshot: SystemSnapshot, monitor: SystemMonitor):
        pad = 10
        x = self.rect.left() + pad
        w = self.rect.width() - pad * 2
        gap = 6

        # Layout: 4 sparklines + gauge section at bottom
        gauge_h = config.GAUGE_SECTION_HEIGHT
        sparkline_area = self.rect.height() - gauge_h - gap
        graph_h = (sparkline_area - gap * 3) / 4  # 3 gaps between 4 rows
        y = self.rect.top()

        # 1. CPU
        cpu_rect = QRectF(x, y, w, graph_h)
        draw_graph_box(
            p, cpu_rect, "CPU", f"{snapshot.cpu_percent:.0f}%",
            monitor.cpu_history.values(), config.COLOR_CPU, max_val=100.0,
        )
        y += graph_h + gap

        # 2. GPU
        gpu_rect = QRectF(x, y, w, graph_h)
        if snapshot.gpu_percent is not None:
            draw_graph_box(
                p, gpu_rect, "GPU", f"{snapshot.gpu_percent:.0f}%",
                monitor.gpu_history.values(), config.COLOR_GPU, max_val=100.0,
            )
        else:
            self._draw_na_box(p, gpu_rect, "GPU")
        y += graph_h + gap

        # 3. Network (dual sparkline: down + up)
        net_rect = QRectF(x, y, w, graph_h)
        net_parts = []
        if snapshot.net_rate_down > 0 or snapshot.net_rate_up > 0:
            net_parts.append(f"\u2193{format_bytes_rate(snapshot.net_rate_down)}")
            net_parts.append(f"\u2191{format_bytes_rate(snapshot.net_rate_up)}")
        net_val = "  ".join(net_parts) if net_parts else "0 B/s"
        self._draw_net_graph(p, net_rect, net_val, monitor)
        y += graph_h + gap

        # 4. Disk I/O (dual sparkline: read + write)
        disk_rect = QRectF(x, y, w, graph_h)
        disk_rate = snapshot.disk_read_rate + snapshot.disk_write_rate
        disk_val = format_bytes_rate(disk_rate)
        self._draw_disk_graph(p, disk_rect, disk_val, monitor)
        y += graph_h + gap

        # 5. Gauges: drives + RAM
        gauge_rect = QRectF(x, y, w, gauge_h)
        self._draw_gauges(p, gauge_rect, snapshot)

    def _draw_net_graph(self, p: QPainter, rect: QRectF, value_text: str,
                        mon: SystemMonitor):
        label_h = 18
        pad = 2

        bg = QPainterPath()
        bg.addRoundedRect(rect, 6, 6)
        p.fillPath(bg, QBrush(QColor("#222222")))

        p.setPen(QPen(QColor("#888888")))
        p.setFont(QFont(config.FONT_FAMILY, 9))
        p.drawText(QRectF(rect.left() + 6, rect.top() + 2, 60, label_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Network")

        p.setPen(QPen(QColor(config.COLOR_NET_DOWN)))
        p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
        p.drawText(QRectF(rect.left(), rect.top() + 2, rect.width() - 6, label_h),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value_text)

        spark_rect = QRectF(
            rect.left() + 6,
            rect.top() + label_h + pad,
            rect.width() - 12,
            rect.height() - label_h - pad - 4,
        )
        draw_dual_sparkline(
            p, spark_rect,
            mon.net_down_history.values(),
            mon.net_up_history.values(),
            config.COLOR_NET_DOWN,
            config.COLOR_NET_UP,
        )

    def _draw_disk_graph(self, p: QPainter, rect: QRectF, value_text: str,
                         mon: SystemMonitor):
        label_h = 18
        pad = 2

        bg = QPainterPath()
        bg.addRoundedRect(rect, 6, 6)
        p.fillPath(bg, QBrush(QColor("#222222")))

        p.setPen(QPen(QColor("#888888")))
        p.setFont(QFont(config.FONT_FAMILY, 9))
        p.drawText(QRectF(rect.left() + 6, rect.top() + 2, 60, label_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Disk I/O")

        p.setPen(QPen(QColor(config.COLOR_DISK_IO)))
        p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
        p.drawText(QRectF(rect.left(), rect.top() + 2, rect.width() - 6, label_h),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value_text)

        spark_rect = QRectF(
            rect.left() + 6,
            rect.top() + label_h + pad,
            rect.width() - 12,
            rect.height() - label_h - pad - 4,
        )
        draw_dual_sparkline(
            p, spark_rect,
            mon.disk_read_history.values(),
            mon.disk_write_history.values(),
            config.COLOR_DISK_IO,
            "#e87f3a",
        )

    def _draw_na_box(self, p: QPainter, rect: QRectF, label: str):
        bg = QPainterPath()
        bg.addRoundedRect(rect, 6, 6)
        p.fillPath(bg, QBrush(QColor("#222222")))

        p.setPen(QPen(QColor("#888888")))
        p.setFont(QFont(config.FONT_FAMILY, 7))
        p.drawText(QRectF(rect.left() + 6, rect.top() + 2, rect.width(), 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        p.setPen(QPen(QColor("#555555")))
        p.setFont(QFont(config.FONT_FAMILY, 9))
        inner = QRectF(rect.left(), rect.top() + 14, rect.width(), rect.height() - 14)
        p.drawText(inner, Qt.AlignmentFlag.AlignCenter, "N/A")

    def _draw_gauges(self, p: QPainter, rect: QRectF, snapshot: SystemSnapshot):
        """Draw arc gauges for each drive + RAM."""
        items = []
        for drive in snapshot.drives:
            items.append({
                "label": f"{drive.label} Drive",
                "value_text": f"{drive.free_gb:.0f} GB",
                "usage_percent": drive.usage_percent,
            })
        if snapshot.memory:
            items.append({
                "label": "RAM",
                "value_text": f"{snapshot.memory.available_gb:.1f} GB",
                "usage_percent": snapshot.memory.usage_percent,
            })

        if not items:
            return

        gauge_w = rect.width() / len(items)
        for i, item in enumerate(items):
            gauge_rect = QRectF(rect.left() + i * gauge_w, rect.top(),
                                gauge_w, rect.height())
            draw_arc_gauge(p, gauge_rect, item["value_text"],
                           item["label"], item["usage_percent"])
