"""
fluid_plot.py
─────────────────────────────────────────────────────────────────────────────
Pure drawing primitive — organic fluid blobs + belt connections.

This file knows NOTHING about:
  - window size or position
  - padding / margins
  - data pipelines
  - timers or animation
  - labels or titles

It only knows how to:
  - draw an organic belt between two circles
  - draw a smooth spline through a list of points
  - draw padded blobs and core dots
  - pick a colour per user from USER_PALETTE

USAGE
─────
from fluid_plot import FluidRenderer, USER_PALETTE

# In your widget's paintEvent, after you have computed node positions:
renderer = FluidRenderer(painter, nodes, data, color_map)
renderer.draw()

WHERE:
  painter    = active QPainter
  nodes      = list of (QPointF, radius)  — YOU compute these positions
  data       = list of {"label": str, "value": float, "user": str}
  color_map  = dict  user → (blob QColor, core QColor)
               build with:  build_color_map(data)
"""

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui  import (QPainter, QColor, QPainterPath,
                             QBrush, QPen, Qt)


# ─── Colour palette — only thing fluid_plot decides ──────────────────────────
# (blob_color, core_color) per user, cycled by insertion order

USER_PALETTE = [
    (QColor(254, 197, 110), QColor(193,  52,  40)),   # orange / red
    (QColor(168, 216, 234), QColor( 44,  74, 124)),   # sky    / navy
    (QColor(168, 218, 168), QColor( 46, 125,  50)),   # mint   / forest
    (QColor(220, 160, 220), QColor(120,  30, 120)),   # lilac  / purple
    (QColor(255, 183, 139), QColor(180,  80,  20)),   # peach  / burnt
]


def build_color_map(data: list[dict]) -> dict:
    """
    Returns  { username: (blob QColor, core QColor) }
    Stable — first-seen user gets palette index 0, next gets 1, etc.
    """
    seen = {}
    idx  = 0
    for d in data:
        u = d["user"]
        if u not in seen:
            seen[u] = USER_PALETTE[idx % len(USER_PALETTE)]
            idx += 1
    return seen


# ─── Geometry primitives ─────────────────────────────────────────────────────

def _dyn_pad(r: float) -> float:
    return max(6.0, min(28.0, r * 0.9))


def _outer_tangent_belt(cx1, cy1, r1, cx2, cy2, r2) -> QPainterPath:
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
    mx = (cx1+cx2)/2;  my = (cy1+cy2)/2
    CURVE = 0.25

    def _cp(ta, tb):
        mpx = (ta.x()+tb.x())/2;  mpy = (ta.y()+tb.y())/2
        vx  = mx-mpx;             vy  = my-mpy
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
    a2s = math.degrees(a2_top);  a2e = math.degrees(a2_bot)
    sw2 = (a2e-a2s) % 360
    if sw2 > 180: sw2 -= 360
    path.arcTo(QRectF(cx2-r2, cy2-r2, r2*2, r2*2), -a2s, -sw2)
    path.cubicTo(cp_bot1, cp_bot2, t1_bot)
    a1s = math.degrees(a1_bot);  a1e = math.degrees(a1_top)
    sw1 = (a1e-a1s) % 360
    if sw1 > 180: sw1 -= 360
    path.arcTo(QRectF(cx1-r1, cy1-r1, r1*2, r1*2), -a1s, -sw1)
    path.closeSubpath()
    return path


def _smooth_spline(points: list) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0])
    for i in range(len(points)-1):
        p1 = points[i];  p2 = points[i+1]
        dx = p2.x() - p1.x()
        path.cubicTo(QPointF(p1.x()+dx*0.5, p1.y()),
                     QPointF(p2.x()-dx*0.5, p2.y()), p2)
    return path


# ─── Renderer ────────────────────────────────────────────────────────────────

class FluidRenderer:
    """
    Stateless drawing helper.  Instantiate inside paintEvent, call draw().

    nodes      list of (QPointF, float)   — positions + radii YOU computed
    data       list of {"label", "value", "user"}
    color_map  dict  user → (blob QColor, core QColor)  from build_color_map()
    """

    def __init__(self,
                 painter   : QPainter,
                 nodes     : list,
                 data      : list[dict],
                 color_map : dict):
        self._p   = painter
        self._n   = nodes
        self._d   = data
        self._cm  = color_map

    def draw(self):
        self._draw_splines()
        self._draw_belts()
        self._draw_blobs()
        self._draw_cores()

    # ── internal draw passes ─────────────────────────────────────────

    def _blob_color(self, i):
        return self._cm.get(self._d[i]["user"], USER_PALETTE[0])[0]

    def _core_color(self, i):
        return self._cm.get(self._d[i]["user"], USER_PALETTE[0])[1]

    def _same_user(self, i, j):
        return self._d[i]["user"] == self._d[j]["user"]

    def _draw_splines(self):
        # group nodes by user, draw one spline per group
        groups: dict[str, list] = {}
        for i, (pt, _) in enumerate(self._n):
            u = self._d[i]["user"]
            groups.setdefault(u, []).append(pt)

        for u, pts in groups.items():
            blob, _ = self._cm.get(u, USER_PALETTE[0])
            sc = QColor(blob.red(), blob.green(), blob.blue(), 160)
            pen = QPen(sc, 18, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            self._p.setPen(pen)
            self._p.setBrush(Qt.BrushStyle.NoBrush)
            self._p.drawPath(_smooth_spline(pts))

    def _draw_belts(self):
        self._p.setPen(Qt.PenStyle.NoPen)
        for i in range(len(self._n)-1):
            if not self._same_user(i, i+1):
                continue
            self._p.setBrush(QBrush(self._blob_color(i)))
            p1, r1 = self._n[i];  p2, r2 = self._n[i+1]
            belt = _outer_tangent_belt(p1.x(), p1.y(), r1+_dyn_pad(r1),
                                       p2.x(), p2.y(), r2+_dyn_pad(r2))
            self._p.drawPath(belt)

    def _draw_blobs(self):
        self._p.setPen(Qt.PenStyle.NoPen)
        for i, (pt, r) in enumerate(self._n):
            self._p.setBrush(QBrush(self._blob_color(i)))
            self._p.drawEllipse(pt, r+_dyn_pad(r), r+_dyn_pad(r))

    def _draw_cores(self):
        self._p.setPen(Qt.PenStyle.NoPen)
        for i, (pt, r) in enumerate(self._n):
            self._p.setBrush(QBrush(self._core_color(i)))
            self._p.drawEllipse(pt, r, r)