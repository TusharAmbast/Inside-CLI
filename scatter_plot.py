"""
scatter_plot_window.py
─────────────────────────────────────────────────────────────────────────────
Owns everything except the fluid drawing primitive:
  - window size (700 × 450)
  - padding (top=100, bottom=60, left=50, right=50)
  - data pipeline (psutil → nodes)
  - LERP animation
  - background, grid, dividers, labels, title
  - calls FluidRenderer to draw blobs/belts

To call from mon.py:
    from scatter_plot_window import open_scatter_plot_window
    win = open_scatter_plot_window()
    win.show()
"""

import sys
import random
import psutil
from collections import defaultdict

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from PySide6.QtCore    import Qt, QTimer, QPointF
from PySide6.QtGui     import QPainter, QColor, QPen, QFont, QFontMetrics, QBrush

from base_window import BaseMonitorWindow
from fluid_plot  import FluidRenderer, build_color_map


# ─── Window / layout constants ───────────────────────────────────────────────

WIN_W      = 700
WIN_H      = 450
PAD_TOP    = 100
PAD_BOTTOM =  60
PAD_LEFT   =  50
PAD_RIGHT  =  50

# Pixel gap inserted between different user groups along X
USER_GROUP_GAP = 60

# Node radius range (mapped from cpu %)
R_MIN = 12
R_MAX = 44

# ─── Colors ──────────────────────────────────────────────────────────────────

BG_COLOR   = QColor(253, 243, 215)
GRID_COLOR = QColor(180, 168, 140, 90)
DIVIDER    = QColor(160, 150, 120, 160)


# ─── Data pipeline ───────────────────────────────────────────────────────────

class ProcessDataProcessor:

    @staticmethod
    def get_process_data():
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent']):
            try:
                processes.append({
                    'name'       : proc.info['name'],
                    'username'   : proc.info['username'] or 'system',
                    'cpu_percent': proc.info['cpu_percent'] or 0.0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    @staticmethod
    def aggregate_by_username(processes):
        user_data = defaultdict(lambda: {'total_cpu': 0.0, 'processes': []})
        for p in processes:
            user_data[p['username']]['processes'].append(p)
            user_data[p['username']]['total_cpu'] += p['cpu_percent']
        return user_data

    @staticmethod
    def filter_active_users(user_data, cpu_threshold=1.5):
        return {u: d for u, d in user_data.items()
                if d['total_cpu'] > cpu_threshold}

    @staticmethod
    def filter_and_sort_processes(user_data, process_cpu_threshold=1.0):
        result = {}
        for user, data in user_data.items():
            filtered = [p for p in data['processes']
                        if p['cpu_percent'] >= process_cpu_threshold]
            result[user] = sorted(filtered,
                                  key=lambda x: x['cpu_percent'], reverse=True)
        return result

    @staticmethod
    def process_pipeline():
        raw       = ProcessDataProcessor.get_process_data()
        agg       = ProcessDataProcessor.aggregate_by_username(raw)
        active    = ProcessDataProcessor.filter_active_users(agg)
        processed = ProcessDataProcessor.filter_and_sort_processes(active)
        return processed

    @staticmethod
    def to_fluid_data(processed: dict) -> list[dict]:
        """
        Flatten pipeline output → [{"label", "value", "user"}, …]
        Nodes stay grouped by user so belts connect within each group.
        """
        flat = []
        for user, procs in sorted(processed.items()):
            for p in procs:
                flat.append({
                    "label": p['name'][:12],
                    "value": p['cpu_percent'],
                    "user" : user,
                })
        return flat


# ─── Node position calculator ────────────────────────────────────────────────

def _compute_nodes(data: list[dict], plot_w: int, plot_h: int,
                   plot_x: int, plot_y: int) -> list[tuple]:
    """
    Map data → (QPointF, radius) list.

    X : users laid out left→right with USER_GROUP_GAP between groups.
        nodes within a group are evenly spaced.
    Y : high value = high on screen (low pixel-Y).
    r : mapped from value to [R_MIN, R_MAX].
    """
    if not data:
        return []

    # group indices by user (first-seen order)
    user_order = []
    groups: dict[str, list[int]] = {}
    for i, d in enumerate(data):
        u = d["user"]
        if u not in groups:
            groups[u] = []
            user_order.append(u)
        groups[u].append(i)

    n_total = len(data)
    n_gaps  = len(user_order) - 1
    node_space = plot_w - n_gaps * USER_GROUP_GAP
    node_step  = node_space / max(n_total - 1, 1)

    values  = [d["value"] for d in data]
    v_min   = min(values);  v_max = max(values)
    v_range = v_max - v_min or 1.0

    nodes = [None] * n_total
    x_cursor = plot_x

    for u_idx, u in enumerate(user_order):
        idxs = groups[u]
        for local_i, global_i in enumerate(idxs):
            d = data[global_i]
            t = (d["value"] - v_min) / v_range
            x = x_cursor + local_i * node_step
            y = plot_y + plot_h * (1.0 - t) + random.uniform(-5, 5)
            r = R_MIN + (R_MAX - R_MIN) * t
            nodes[global_i] = (QPointF(x, y), r)

        x_cursor += len(idxs) * node_step + USER_GROUP_GAP

    return nodes


# ─── Plot widget ─────────────────────────────────────────────────────────────

class ScatterPlotWidget(QWidget):
    """
    The actual plot canvas.
    Handles animation, background, grid, labels.
    Delegates blob/belt drawing to FluidRenderer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._data         : list[dict] = []
        self._color_map    : dict       = {}
        self._current_nodes: list       = []
        self._target_nodes : list       = []

        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)
        self._anim.start(16)   # ~60 fps

    # ── public ───────────────────────────────────────────────────────

    def set_data(self, data: list[dict]):
        self._data      = data
        self._color_map = build_color_map(data)
        self._rebuild_targets()

    # ── internal ─────────────────────────────────────────────────────

    def _plot_rect(self):
        """Returns (plot_x, plot_y, plot_w, plot_h) based on current widget size."""
        w, h = self.width(), self.height()
        px = PAD_LEFT
        py = PAD_TOP
        pw = w - PAD_LEFT - PAD_RIGHT
        ph = h - PAD_TOP  - PAD_BOTTOM
        return px, py, pw, ph

    def _rebuild_targets(self):
        px, py, pw, ph = self._plot_rect()
        targets = _compute_nodes(self._data, pw, ph, px, py)
        if len(targets) != len(self._current_nodes):
            self._current_nodes = [(QPointF(p.x(), p.y()), r)
                                   for p, r in targets]
        self._target_nodes = targets
        self.update()

    def _step(self):
        if len(self._current_nodes) != len(self._target_nodes):
            return
        moved = False
        s = 0.06
        for i in range(len(self._current_nodes)):
            cp, cr = self._current_nodes[i]
            tp, tr = self._target_nodes[i]
            nx = cp.x() + (tp.x()-cp.x())*s
            ny = cp.y() + (tp.y()-cp.y())*s
            nr = cr     + (tr-cr)*s
            self._current_nodes[i] = (QPointF(nx, ny), nr)
            if abs(tp.x()-nx)>0.4 or abs(tp.y()-ny)>0.4 or abs(tr-nr)>0.05:
                moved = True
        if moved:
            self.update()

    def resizeEvent(self, e):
        self._rebuild_targets()
        super().resizeEvent(e)

    def mousePressEvent(self, _):
        self._rebuild_targets()

    # ── paint ────────────────────────────────────────────────────────

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        px, py, pw, ph = self._plot_rect()
        plot_bottom = py + ph

        # ── background ───────────────────────────────────────────────
        painter.fillRect(0, 0, w, h, BG_COLOR)

        # ── horizontal ruled lines ────────────────────────────────────
        painter.setPen(QPen(GRID_COLOR, 1))
        for i in range(11):
            y = int(py + ph * i / 10)
            painter.drawLine(px, y, px + pw, y)

        # ── top / bottom dividers ─────────────────────────────────────
        painter.setPen(QPen(DIVIDER, 1))
        painter.drawLine(px, py,           px + pw, py)
        painter.drawLine(px, plot_bottom,  px + pw, plot_bottom)

        nodes = self._current_nodes
        if not nodes:
            painter.setPen(QColor(160, 140, 100, 120))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            return

        # ── fluid blobs + belts ───────────────────────────────────────
        FluidRenderer(painter, nodes, self._data, self._color_map).draw()

        # ── username labels (centred under each user group) ───────────
        painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
        fm = QFontMetrics(painter.font())
        label_y = plot_bottom + 26

        groups: dict[str, list] = {}
        for i, (pt, _) in enumerate(nodes):
            u = self._data[i]["user"]
            groups.setdefault(u, []).append(pt.x())

        for u, xs in groups.items():
            blob, _ = self._color_map.get(u, (QColor(254, 197, 110),
                                              QColor(193, 52, 40)))
            mid = (min(xs) + max(xs)) / 2
            uw  = fm.horizontalAdvance(u)
            painter.setPen(blob.darker(160))
            painter.drawText(int(mid - uw/2), label_y, u)

        # ── process name labels (small, above each blob) ──────────────
        painter.setFont(QFont("Georgia", 7))
        fm2 = QFontMetrics(painter.font())
        painter.setPen(QColor(90, 70, 40, 150))
        for i, (pt, r) in enumerate(nodes):
            from fluid_plot import _dyn_pad
            lbl = self._data[i]["label"]
            pr  = r + _dyn_pad(r)
            tw  = fm2.horizontalAdvance(lbl)
            painter.drawText(int(pt.x()-tw/2), int(pt.y()-pr-4), lbl)


# ─── Window ──────────────────────────────────────────────────────────────────

class ScatterPlotWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="SCATTER PLOT")
        self.setWindowTitle("Scatter Plot - Critique CLI")
        self.resize(WIN_W, WIN_H)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._plot = ScatterPlotWidget()
        layout.addWidget(self._plot)

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _refresh(self):
        try:
            processed  = ProcessDataProcessor.process_pipeline()
            fluid_data = ProcessDataProcessor.to_fluid_data(processed)
            if fluid_data:
                self._plot.set_data(fluid_data)
        except Exception as e:
            print(f"[ScatterPlotWindow] {e}")


# ─── Entry points for mon.py ─────────────────────────────────────────────────

def open_scatter_plot_window() -> ScatterPlotWindow:
    """
    from scatter_plot_window import open_scatter_plot_window
    win = open_scatter_plot_window()
    win.show()
    """
    w = ScatterPlotWindow()
    w.show()
    return w


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ScatterPlotWindow()
    win.show()
    sys.exit(app.exec())