"""
Fluid Graph Visualization — PySide6
Approach: paint many overlapping filled circles along the Catmull-Rom spine,
with varying radius (wide at nodes, slim between). Because circles always
union cleanly, there are ZERO self-intersections or artifacts.
"""

import sys
import math
import random
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPainterPath, QBrush, QPen, QFont


# ─── Catmull-Rom sampler ──────────────────────────────────────────────────────

def catmull_rom_point(p0, p1, p2, p3, t):
    t2, t3 = t*t, t*t*t
    return QPointF(
        0.5*((2*p1.x()) + (-p0.x()+p2.x())*t
             + (2*p0.x()-5*p1.x()+4*p2.x()-p3.x())*t2
             + (-p0.x()+3*p1.x()-3*p2.x()+p3.x())*t3),
        0.5*((2*p1.y()) + (-p0.y()+p2.y())*t
             + (2*p0.y()-5*p1.y()+4*p2.y()-p3.y())*t2
             + (-p0.y()+3*p1.y()-3*p2.y()+p3.y())*t3),
    )


# Padding scales with dot radius: smaller dots get less, bigger get more.
# PADDING_RATIO controls how much padding relative to the node radius.
PADDING_RATIO = 0.55   # padding = node_radius * PADDING_RATIO
PADDING_MIN   = 6      # minimum padding (px) for very small dots
PADDING_MAX   = 28     # maximum padding (px) for very large dots

def dynamic_padding(r):
    """Return padding for a dot of radius r — scales proportionally."""
    return max(PADDING_MIN, min(PADDING_MAX, r * PADDING_RATIO))


def sample_spine(nodes, steps_per_seg=60):
    """
    Returns list of (QPointF, radius) sampled densely along the spine.
    Radius uses a smooth sin-valley: full node radius at nodes,
    dips to MIN_RATIO in the middle of each segment.
    Padding at each sample is interpolated from the two endpoint paddings.
    """
    pts   = [n[0] for n in nodes]
    radii = [n[1] for n in nodes]
    n     = len(pts)
    MIN_RATIO = 0.10        # slim part = 10% of the interpolated node radius

    samples = []
    for seg in range(n - 1):
        p0 = pts[max(seg-1, 0)]
        p1 = pts[seg]
        p2 = pts[seg+1]
        p3 = pts[min(seg+2, n-1)]
        r1, r2   = radii[seg], radii[seg+1]
        pad1, pad2 = dynamic_padding(r1), dynamic_padding(r2)

        total = steps_per_seg + (1 if seg == n-2 else 0)
        for step in range(total):
            t   = step / steps_per_seg
            pos = catmull_rom_point(p0, p1, p2, p3, t)

            # smooth valley: wide at nodes, slim at midpoint
            valley    = math.sin(t * math.pi)           # 0→1→0
            r_interp  = r1 + (r2 - r1) * t
            pad_interp = pad1 + (pad2 - pad1) * t       # interpolate padding too
            r_scaled  = r_interp * (1.0 - (1.0 - MIN_RATIO) * valley)
            samples.append((pos, r_scaled + pad_interp))

    return samples


# ─── Node generator ───────────────────────────────────────────────────────────

def generate_nodes(width, height, count=8):
    margin_x, margin_y = 70, 80
    uw = width  - 2*margin_x
    uh = height - 2*margin_y
    col_w = uw / count
    nodes = []
    for i in range(count):
        x = margin_x + col_w*i + random.uniform(col_w*0.1, col_w*0.85)
        y = margin_y + random.uniform(0, uh)
        r = random.uniform(14, 40)
        nodes.append((QPointF(x, y), r))
    nodes.sort(key=lambda nd: nd[0].x())
    return nodes


# ─── Colors ───────────────────────────────────────────────────────────────────

ORANGE = QColor(254, 197, 110, 178)   # 70% opacity
RED    = QColor(182, 52, 42)
BG     = QColor(253, 246, 227)
LINES  = QColor(190, 178, 155, 80)


# ─── Widget ───────────────────────────────────────────────────────────────────

class FluidGraphWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(860, 440)
        self._nodes = []
        self._regenerate()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._regen_update)
        self._timer.start(4500)

    def _regenerate(self):
        w = max(self.width(), 860)
        h = max(self.height(), 440)
        self._nodes = generate_nodes(w, h, count=random.randint(6, 10))

    def _regen_update(self):
        self._regenerate(); self.update()

    def resizeEvent(self, event):
        self._regenerate(); super().resizeEvent(event)

    def mousePressEvent(self, event):
        self._regen_update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, BG)

        # Ruled lines
        painter.setPen(QPen(LINES, 1))
        for i in range(1, 11):
            painter.drawLine(0, int(i*h/11), w, int(i*h/11))

        if not self._nodes:
            return

        # ── Orange blob: just paint every spine circle ──────────────────────
        # Because overlapping same-colour filled circles union perfectly,
        # there are zero artifacts regardless of how sharp the bends are.
        samples = sample_spine(self._nodes, steps_per_seg=60)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(ORANGE))

        # Add a circle at each node with dynamic padding based on its radius
        node_circles = [(nd[0], nd[1] + dynamic_padding(nd[1])) for nd in self._nodes]

        for pos, r in samples + node_circles:
            painter.drawEllipse(pos, r, r)

        # ── Red dots ────────────────────────────────────────────────────────
        painter.setBrush(QBrush(RED))
        painter.setPen(Qt.PenStyle.NoPen)
        for pt, r in self._nodes:
            painter.drawEllipse(pt, r, r)

        # Hint
        painter.setPen(QColor(160, 140, 100, 120))
        painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
        painter.drawText(10, h-10, "click or wait to regenerate")


# ─── Main ─────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fluid Graph")
        self.resize(1100, 560)
        self.setCentralWidget(FluidGraphWidget())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())