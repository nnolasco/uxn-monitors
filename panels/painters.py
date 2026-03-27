from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

import config


def draw_sparkline(
    p: QPainter,
    rect: QRectF,
    values: list[float],
    color: str,
    max_val: float | None = None,
    min_val: float = 0.0,
    fill_alpha: int = 40,
):
    """Draw a mini line chart within the given rect."""
    if len(values) < 2:
        p.setPen(QPen(QColor("#666666")))
        p.setFont(QFont(config.FONT_FAMILY, 9))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Waiting...")
        return

    # Determine scale
    hi = max_val if max_val is not None else max(values)
    lo = min_val
    if hi <= lo:
        hi = lo + 1.0

    n = len(values)
    x_step = rect.width() / (n - 1)

    # Build points
    points = []
    for i, v in enumerate(values):
        x = rect.left() + i * x_step
        y = rect.bottom() - ((v - lo) / (hi - lo)) * rect.height()
        y = max(rect.top(), min(rect.bottom(), y))
        points.append(QPointF(x, y))

    # Filled area under the line
    fill_color = QColor(color)
    fill_color.setAlpha(fill_alpha)
    fill_path = QPainterPath()
    fill_path.moveTo(QPointF(rect.left(), rect.bottom()))
    for pt in points:
        fill_path.lineTo(pt)
    fill_path.lineTo(QPointF(rect.right(), rect.bottom()))
    fill_path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.fillPath(fill_path, QBrush(fill_color))

    # Line
    line_path = QPainterPath()
    line_path.moveTo(points[0])
    for pt in points[1:]:
        line_path.lineTo(pt)
    p.setPen(QPen(QColor(color), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(line_path)

    # Dot at last point
    last = points[-1]
    p.setPen(Qt.PenStyle.NoPen)
    dot_color = QColor(color)
    dot_color.setAlpha(180)
    p.setBrush(QBrush(dot_color))
    p.drawEllipse(last, 3, 3)


def draw_dual_sparkline(
    p: QPainter,
    rect: QRectF,
    values1: list[float],
    values2: list[float],
    color1: str,
    color2: str,
    max_val: float | None = None,
):
    """Draw two overlapping sparklines (e.g., network up/down)."""
    all_vals = values1 + values2
    if not all_vals:
        draw_sparkline(p, rect, [], color1)
        return
    auto_max = max(all_vals) if all_vals else 1.0
    effective_max = max_val if max_val is not None else max(auto_max, 1.0)
    draw_sparkline(p, rect, values1, color1, max_val=effective_max, fill_alpha=30)
    draw_sparkline(p, rect, values2, color2, max_val=effective_max, fill_alpha=20)


def draw_graph_box(
    p: QPainter,
    rect: QRectF,
    label: str,
    value_text: str,
    values: list[float],
    color: str,
    max_val: float | None = None,
):
    """Draw a labeled sparkline graph box: label top-left, value top-right, sparkline below."""
    label_h = 18
    pad = 2

    # Background
    bg = QPainterPath()
    bg.addRoundedRect(rect, 6, 6)
    p.fillPath(bg, QBrush(QColor("#222222")))

    # Label
    p.setPen(QPen(QColor("#888888")))
    p.setFont(QFont(config.FONT_FAMILY, 9))
    label_rect = QRectF(rect.left() + 6, rect.top() + 2, rect.width() * 0.6, label_h)
    p.drawText(label_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

    # Value
    p.setPen(QPen(QColor(color)))
    p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
    val_rect = QRectF(rect.left(), rect.top() + 2, rect.width() - 6, label_h)
    p.drawText(val_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value_text)

    # Sparkline area
    spark_rect = QRectF(
        rect.left() + 6,
        rect.top() + label_h + pad,
        rect.width() - 12,
        rect.height() - label_h - pad - 4,
    )
    draw_sparkline(p, spark_rect, values, color, max_val=max_val)


def draw_section_header(p: QPainter, x: float, y: float, width: float, text: str) -> float:
    """Draw a section header with separator. Returns y after header."""
    # Separator line
    p.setPen(QPen(QColor(config.SEPARATOR_COLOR), 1))
    p.drawLine(int(x), int(y), int(x + width), int(y))

    # Title
    p.setPen(QPen(QColor("#888888")))
    p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
    p.drawText(QRectF(x, y + 2, width, 18),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
    return y + 22


def draw_process_row(
    p: QPainter,
    x: float, y: float, width: float,
    name: str, value_text: str, value_color: str,
    rank: int | None = None,
):
    """Draw a single process row: optional rank, name, value."""
    row_h = 17
    p.setFont(QFont(config.FONT_FAMILY, 9))

    # Rank
    offset = 0
    if rank is not None:
        p.setPen(QPen(QColor("#555555")))
        p.drawText(QRectF(x, y, 14, row_h),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{rank}.")
        offset = 18

    # Name (truncated)
    display_name = name[:24] + ".." if len(name) > 26 else name
    p.setPen(QPen(QColor(config.TEXT_COLOR)))
    p.drawText(QRectF(x + offset, y, width * 0.6, row_h),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               display_name)

    # Value
    p.setPen(QPen(QColor(value_color)))
    p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
    p.drawText(QRectF(x, y, width, row_h),
               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
               value_text)


def _gauge_color(usage_pct: float) -> str:
    if usage_pct < 50:
        return config.COLOR_SAFE
    elif usage_pct < 80:
        return config.COLOR_MODERATE
    else:
        return config.COLOR_CRITICAL


def draw_arc_gauge(
    p: QPainter,
    rect: QRectF,
    value_text: str,
    label: str,
    usage_percent: float,
    subtitle: str = "",
):
    """Draw a semicircular arc gauge (270°) with value, label, and subtitle."""
    arc_degrees = 270
    arc_width = 8
    label_space = 40  # space for label + subtitle below arc

    # Compute arc square (centered horizontally in rect)
    arc_side = min(rect.width() - 8, rect.height() - label_space)
    arc_x = rect.left() + (rect.width() - arc_side) / 2
    arc_y = rect.top() + 4
    arc_rect = QRectF(arc_x + arc_width / 2, arc_y + arc_width / 2,
                      arc_side - arc_width, arc_side - arc_width)

    # Angles: 1/16th degree units, start at 7:30 position (225°), sweep 270° CCW
    start_angle = int(225 * 16)
    full_span = int(arc_degrees * 16)
    fill_span = int(arc_degrees * 16 * min(usage_percent / 100.0, 1.0))

    # Background track
    track_pen = QPen(QColor(config.GAUGE_TRACK_COLOR), arc_width)
    track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(track_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(arc_rect, start_angle, full_span)

    # Colored fill
    color = _gauge_color(usage_percent)
    fill_pen = QPen(QColor(color), arc_width)
    fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(fill_pen)
    p.drawArc(arc_rect, start_angle, fill_span)

    # Center value text
    center_y = arc_y + arc_side * 0.45
    p.setPen(QPen(QColor(config.TEXT_COLOR)))
    p.setFont(QFont(config.FONT_FAMILY, 9, QFont.Weight.Bold))
    val_rect = QRectF(rect.left(), center_y, rect.width(), 18)
    p.drawText(val_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
               value_text)

    # Label below
    p.setPen(QPen(QColor("#888888")))
    p.setFont(QFont(config.FONT_FAMILY, 8))
    lbl_y = arc_y + arc_side + 4
    lbl_rect = QRectF(rect.left(), lbl_y, rect.width(), 16)
    p.drawText(lbl_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
               label)

    # Subtitle (total) below label
    if subtitle:
        p.setPen(QPen(QColor("#888888")))
        p.setFont(QFont(config.FONT_FAMILY, 8))
        sub_rect = QRectF(rect.left(), lbl_y + 14, rect.width(), 14)
        p.drawText(sub_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   subtitle)
