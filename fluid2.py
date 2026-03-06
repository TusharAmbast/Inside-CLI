"""
fluid_plot.py
─────────────────────────────────────────────────────────────────────────────
A reusable, data-driven fluid graph widget.

USAGE
─────
from fluid_plot import FluidPlotWidget

# Minimal — just pass a list of (label, value) tuples
widget = FluidPlotWidget()
widget.set_data([
    ("chrome",  45.2),
    ("python",  18.7),
    ("Xorg",     9.1),
    ("systemd",  3.4),
])

# Full control — override colors, title, axis label
widget = FluidPlotWidget(
    color_core=QColor(182, 52, 42),
    color_blob=QColor(254, 197, 110),
    color_bg  =QColor(253, 246, 227),
    title="CPU Usage",
    y_label="% CPU",
)
widget.set_data(data_points)

DATA FORMAT
───────────
Each data point is a dict OR a 2-tuple:
  {"label": str, "value": float}   ← dict form
  ("label", float)                 ← tuple form

Values are mapped to:
  • node radius  (size of the blob)
  • node Y pos   (height on chart, higher value = higher up)
  • X pos        is evenly distributed left-to-right

The widget self-animates. Call set_data() at any time to feed new data;
nodes will LERP smoothly to the new positions/sizes.
"""

import math
import random

from PySide6.QtWidgets import QWidget
from PySide6.QtCore    import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui     import (QPainter, QColor, QPainterPath,
                                QBrush, QPen, QFont, QFontMetrics)


# ─── Geometry helpers (unchanged from fluid2.py) ─────────────────────────────

def _outer_tangent_belt(cx1, cy1, r1, cx2, cy2, r2):
    dx   = cx2 - cx1
    dy   = cy2 - cy1
    dist = math.hypot(dx, dy)

    if dist < abs(r1 - r2) + 1:
        path = QPainterPath()
        path.addEllipse(QPointF(cx1, cy1), r1, r1)
        path.addEllipse(QPointF(cx2, cy2), r2, r2)
        return path.simplified()

    angle = math.atan2(dy, dx)
    sin_a = max(-1.0, min(1.0, (r1 - r2) / dist))
    alpha = math.asin(sin_a)

    a1_top = angle + math.pi/2 - alpha
    a2_top = angle + math.pi/2 - alpha
    a1_bot = angle - math.pi/2 + alpha
    a2_bot = angle - math.pi/2 + alpha

    t1_top = QPointF(cx1 + r1*math.cos(a1_top), cy1 + r1*math.sin(a1_top))
    t2_top = QPointF(cx2 + r2*math.cos(a2_top), cy2 + r2*math.sin(a2_top))
    t1_bot = QPointF(cx1 + r1*math.cos(a1_bot), cy1 + r1*math.sin(a1_bot))
    t2_bot = QPointF(cx2 + r2*math.cos(a2_bot), cy2 + r2*math.sin(a2_bot))

    tlen = math.hypot(t2_top.x()-t1_top.x(), t2_top.y()-t1_top.y()) or 1.0
    mx = (cx1 + cx2) / 2
    my = (cy1 + cy2) / 2
    CURVE = 0.25

    def _cp(ta, tb):
        mpx = (ta.x()+tb.x())/2;  mpy = (ta.y()+tb.y())/2
        vx  = mx - mpx;           vy  = my - mpy
        vl  = math.hypot(vx, vy) or 1.0
        off = tlen * CURVE
        return (
            QPointF(ta.x()+(tb.x()-ta.x())/3 + vx/vl*off*0.5,
                    ta.y()+(tb.y()-ta.y())/3 + vy/vl*off*0.5),
            QPointF(ta.x()+2*(tb.x()-ta.x())/3 + vx/vl*off*0.5,
                    ta.y()+2*(tb.y()-ta.y())/3 + vy/vl*off*0.5),
        )

    cp_top1, cp_top2 = _cp(t1_top, t2_top)
    cp_bot1, cp_bot2 = _cp(t2_bot, t1_bot)

    path = QPainterPath()
    path.moveTo(t1_top)
    path.cubicTo(cp_top1, cp_top2, t2_top)

    arc2_start = math.degrees(a2_top)
    arc2_end   = math.degrees(a2_bot)
    sweep2 = (arc2_end - arc2_start) % 360
    if sweep2 > 180: sweep2 -= 360
    path.arcTo(QRectF(cx2-r2, cy2-r2, r2*2, r2*2), -arc2_start, -sweep2)

    path.cubicTo(cp_bot1, cp_bot2, t1_bot)

    arc1_start = math.degrees(a1_bot)
    arc1_end   = math.degrees(a1_top)
    sweep1 = (arc1_end - arc1_start) % 360
    if sweep1 > 180: sweep1 -= 360
    path.arcTo(QRectF(cx1-r1, cy1-r1, r1*2, r1*2), -arc1_start, -sweep1)

    path.closeSubpath()
    return path


def _smooth_spline(nodes):
    path = QPainterPath()
    if not nodes:
        return path
    path.moveTo(nodes[0][0])
    for i in range(len(nodes)-1):
        p1 = nodes[i][0];   p2 = nodes[i+1][0]
        dx = p2.x() - p1.x()
        path.cubicTo(
            QPointF(p1.x()+dx*0.5, p1.y()),
            QPointF(p2.x()-dx*0.5, p2.y()),
            p2
        )
    return path


def _dyn_pad(r):
    return max(6.0, min(28.0, r * 0.9))


# ─── Data normalisation ───────────────────────────────────────────────────────

def _normalise(raw):
    """
    Accept list of dicts {"label":…,"value":…} or 2-tuples (label, value).
    Returns list of {"label": str, "value": float}.
    """
    out = []
    for item in raw:
        if isinstance(item, dict):
            out.append({"label": str(item["label"]), "value": float(item["value"])})
        else:
            out.append({"label": str(item[0]), "value": float(item[1])})
    return out


def _data_to_nodes(data, width, height,
                   margin_x=80, margin_y=80,
                   r_min=10, r_max=40):
    """
    Map normalised data → list of (QPointF, radius) nodes.

    • X  : evenly spaced left→right in order
    • Y  : value mapped so HIGH value = HIGH on screen (low pixel Y)
    • r  : value mapped to [r_min, r_max]
    """
    n = len(data)
    if n == 0:
        return []

    values = [d["value"] for d in data]
    v_min, v_max = min(values), max(values)
    v_range = v_max - v_min or 1.0

    uw = width  - 2*margin_x
    uh = height - 2*margin_y

    nodes = []
    for i, d in enumerate(data):
        t = (d["value"] - v_min) / v_range          # 0..1, 1 = highest value

        x = margin_x + uw * (i / max(n-1, 1))
        # high value → low pixel-y (top of screen)
        y = margin_y + uh * (1.0 - t)
        # add a tiny random vertical jitter so equal values don't stack
        y += random.uniform(-6, 6)

        r = r_min + (r_max - r_min) * t

        nodes.append((QPointF(x, y), r))

    return nodes


# ─── Widget ───────────────────────────────────────────────────────────────────

class FluidPlotWidget(QWidget):
    """
    Drop-in fluid graph widget.

    Parameters
    ──────────
    color_core  QColor  colour of the inner dot          default red
    color_blob  QColor  colour of the outer blob/belt    default orange
    color_bg    QColor  background colour                default cream
    title       str     chart title drawn top-right
    y_label     str     label on the left Y axis
    show_labels bool    draw process/data labels below each node
    lerp_speed  float   animation smoothness 0.01(slow)…0.15(snappy)
    """

    def __init__(self,
                 parent=None,
                 color_core=None,
                 color_blob=None,
                 color_bg  =None,
                 title     ="",
                 y_label   ="",
                 show_labels=True,
                 lerp_speed =0.06):
        super().__init__(parent)
        self.setMinimumSize(640, 320)

        # ── Colors ────────────────────────────────────────────────────
        self._c_core = color_core or QColor(182, 52, 42)
        self._c_blob = color_blob or QColor(254, 197, 110)
        self._c_bg   = color_bg   or QColor(253, 246, 227)
        self._c_spline = QColor(self._c_blob.red(),
                                self._c_blob.green(),
                                self._c_blob.blue(), 150)
        self._c_grid   = QColor(190, 178, 155, 80)

        # ── Meta ──────────────────────────────────────────────────────
        self._title       = title
        self._y_label     = y_label
        self._show_labels = show_labels
        self._lerp_speed  = lerp_speed

        # ── State ─────────────────────────────────────────────────────
        self._data: list[dict] = []
        self._current_nodes: list = []
        self._target_nodes:  list = []

        # ── Timers ────────────────────────────────────────────────────
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._step)
        self._anim_timer.start(16)          # ~60 fps

    # ── Public API ────────────────────────────────────────────────────

    def set_data(self, raw_data):
        """
        Feed new data.  Nodes LERP smoothly to new positions.

        raw_data : list of {"label":str,"value":float}  OR  (label, value)
        """
        self._data = _normalise(raw_data)
        self._rebuild_targets()

    def set_colors(self, core=None, blob=None, bg=None):
        if core: self._c_core = core
        if blob:
            self._c_blob = blob
            self._c_spline = QColor(blob.red(), blob.green(), blob.blue(), 150)
        if bg:   self._c_bg = bg
        self.update()

    def set_title(self, title):
        self._title = title
        self.update()

    # ── Internal ──────────────────────────────────────────────────────

    def _rebuild_targets(self):
        w = max(self.width(),  640)
        h = max(self.height(), 320)
        new_targets = _data_to_nodes(self._data, w, h)

        # If node count changed, reset current nodes too (no lerp from wrong count)
        if len(new_targets) != len(self._current_nodes):
            self._current_nodes = [(QPointF(n[0].x(), n[0].y()), n[1])
                                   for n in new_targets]
        self._target_nodes = new_targets
        self.update()

    def _step(self):
        if len(self._current_nodes) != len(self._target_nodes):
            return
        moved = False
        s = self._lerp_speed
        for i in range(len(self._current_nodes)):
            cp, cr = self._current_nodes[i]
            tp, tr = self._target_nodes[i]
            nx = cp.x() + (tp.x()-cp.x())*s
            ny = cp.y() + (tp.y()-cp.y())*s
            nr = cr     + (tr - cr)*s
            self._current_nodes[i] = (QPointF(nx, ny), nr)
            if abs(tp.x()-nx)>0.4 or abs(tp.y()-ny)>0.4 or abs(tr-nr)>0.05:
                moved = True
        if moved:
            self.update()

    def resizeEvent(self, event):
        self._rebuild_targets()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        # Click triggers a gentle re-jitter of Y positions
        self._rebuild_targets()

    # ── Paint ─────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, self._c_bg)

        # Horizontal grid lines
        painter.setPen(QPen(self._c_grid, 1))
        for i in range(1, 11):
            painter.drawLine(0, int(i*h/11), w, int(i*h/11))

        nodes = self._current_nodes
        if not nodes:
            # Empty state hint
            painter.setPen(QColor(160, 140, 100, 120))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            return

        # ── Spline skeleton ───────────────────────────────────────────
        spline = _smooth_spline(nodes)
        pen = QPen(self._c_spline, 20,
                   Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(spline)

        # ── Belts ─────────────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._c_blob))
        for i in range(len(nodes)-1):
            p1, r1 = nodes[i];    p2, r2 = nodes[i+1]
            pr1 = r1 + _dyn_pad(r1);  pr2 = r2 + _dyn_pad(r2)
            belt = _outer_tangent_belt(p1.x(), p1.y(), pr1,
                                       p2.x(), p2.y(), pr2)
            painter.drawPath(belt)

        # ── Padded node blobs ─────────────────────────────────────────
        for pt, r in nodes:
            painter.drawEllipse(pt, r+_dyn_pad(r), r+_dyn_pad(r))

        # ── Core dots ─────────────────────────────────────────────────
        painter.setBrush(QBrush(self._c_core))
        for pt, r in nodes:
            painter.drawEllipse(pt, r, r)

        # ── Data labels ───────────────────────────────────────────────
        if self._show_labels and self._data:
            painter.setPen(QColor(80, 60, 30, 200))
            painter.setFont(QFont("Georgia", 8))
            fm = QFontMetrics(painter.font())
            for (pt, r), d in zip(nodes, self._data):
                lbl = d["label"][:14]
                tw  = fm.horizontalAdvance(lbl)
                pr  = r + _dyn_pad(r)
                # Draw label below blob
                lx = int(pt.x() - tw/2)
                ly = int(pt.y() + pr + 14)
                painter.drawText(lx, ly, lbl)

                # Draw value above blob
                val_str = f"{d['value']:.1f}"
                vw = fm.horizontalAdvance(val_str)
                painter.drawText(int(pt.x()-vw/2), int(pt.y()-pr-4), val_str)

        # ── Y-axis label ──────────────────────────────────────────────
        if self._y_label:
            painter.save()
            painter.setPen(QColor(140, 120, 80, 180))
            painter.setFont(QFont("Georgia", 9, QFont.Weight.Bold))
            painter.translate(16, h//2)
            painter.rotate(-90)
            painter.drawText(-50, 0, self._y_label)
            painter.restore()

        # ── Title ─────────────────────────────────────────────────────
        if self._title:
            painter.setPen(QColor(80, 60, 30, 180))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Bold))
            painter.drawText(w-200, 24, self._title)

        # ── Hint ──────────────────────────────────────────────────────
        painter.setPen(QColor(160, 140, 100, 120))
        painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal, True))
        painter.drawText(10, h-10, "click to re-jitter positions")