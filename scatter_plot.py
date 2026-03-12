"""
scatter_plot.py
─────────────────────────────────────────────────────────────────────────────
Owns layout, padding, animation, data pipeline, labels.
Delegates blob/belt drawing to FluidRenderer from fluid_plot.py.

Fixes applied
─────────────
1. CLIPPING  — plot area is inset by R_MAX + max_pad so the first/last
               blob never clips against the margin edge.
2. STABLE X  — each process name is assigned a fixed X slot on first seen.
               On refresh, only Y and radius update (LERP). Nodes never
               jump or re-randomize their horizontal position.
3. NO SPLINE — skeleton line removed from FluidRenderer entirely.

ScatterPlotElement
──────────────────
A non-widget element that can be drawn directly onto any QPainter.
mon.py owns the geometry and calls:
  - element.set_data(fluid_data)
  - element.draw(painter, px, py, pw, ph)
  - element.handle_click(mx, my, px, py, pw, ph)
  - element.handle_resize(px, py, pw, ph)
"""

import sys
import psutil
from collections import defaultdict

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from PySide6.QtCore    import Qt, QTimer, QPointF, QObject
from PySide6.QtGui     import QPainter, QColor, QPen, QFont, QFontMetrics

from base_window      import BaseMonitorWindow
from fluid_plot       import FluidRenderer, build_color_map, _dyn_pad
from scatter_details  import draw_detail_box, BOX_W, BOX_GAP, box_rect


# ─── Layout constants ────────────────────────────────────────────────────────

WIN_W      = 700
WIN_H      = 450
PAD_TOP    = 100
PAD_BOTTOM =  60
PAD_LEFT   =  50
PAD_RIGHT  =  50

R_MAX        = 30
_BLOB_MAX    = int(R_MAX + _dyn_pad(R_MAX))
_EDGE_INSET  = _BLOB_MAX + 5

USER_GROUP_GAP = 50
R_MIN = 12

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
    def filter_active_users(user_data, cpu_threshold=1.0):
        return {u: d for u, d in user_data.items()
                if d['total_cpu'] > cpu_threshold}

    @staticmethod
    def filter_and_sort_processes(user_data, process_cpu_threshold=0.5):
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
        Flatten pipeline → [{"label", "value", "user"}, …]
        Within each user, processes are sorted ALPHABETICALLY by name.
        X positions are therefore stable — a process always occupies the
        same horizontal slot. Only Y and radius change with CPU usage.
        """
        flat = []
        for user, procs in sorted(processed.items()):
            for p in sorted(procs, key=lambda x: x['name'].lower()):
                flat.append({
                    "label": p['name'][:12],
                    "value": p['cpu_percent'],
                    "user" : user,
                })
        return flat


# ─── Node layout ─────────────────────────────────────────────────────────────

def _value_to_radius(t: float) -> float:
    return R_MIN + (R_MAX - R_MIN) * t


def _assign_x_slots(data: list[dict], plot_x: int, plot_w: int) -> dict:
    user_order: list[str]            = []
    groups:     dict[str, list[str]] = {}

    for d in data:
        u, lbl = d["user"], d["label"]
        if u not in groups:
            groups[u] = []
            user_order.append(u)
        if lbl not in groups[u]:
            groups[u].append(lbl)

    for u in user_order:
        groups[u].sort(key=str.lower)

    ordered = []
    values  = [d["value"] for d in data]
    v_min   = min(values);  v_max = max(values)
    v_range = v_max - v_min or 1.0

    val_map = {(d["user"], d["label"]): d["value"] for d in data}

    for u in user_order:
        for lbl in groups[u]:
            ordered.append((u, lbl))

    n = len(ordered)
    if n == 0:
        return {}

    def _outer(key):
        v = val_map.get(key, 0)
        t = (v - v_min) / v_range
        r = _value_to_radius(t)
        return r + _dyn_pad(r)

    x_start = plot_x + _outer(ordered[0]) + 5
    x_end   = plot_x + plot_w - _outer(ordered[-1]) - 5

    n_gaps   = len(user_order) - 1
    usable_w = x_end - x_start - n_gaps * USER_GROUP_GAP
    step     = usable_w / max(n - 1, 1)

    slots    = {}
    x_cursor = x_start
    for u_idx, u in enumerate(user_order):
        for local_i, lbl in enumerate(groups[u]):
            slots[(u, lbl)] = x_cursor + local_i * step
        x_cursor += len(groups[u]) * step + USER_GROUP_GAP

    return slots


def _compute_targets(data: list[dict], x_slots: dict,
                     plot_y: int, plot_h: int) -> list[tuple]:
    if not data:
        return []

    values  = [d["value"] for d in data]
    v_min   = min(values);  v_max = max(values)
    v_range = v_max - v_min or 1.0

    nodes = []
    for d in data:
        t  = (d["value"] - v_min) / v_range
        r  = _value_to_radius(t)
        pr = r + _dyn_pad(r)

        x = x_slots.get((d["user"], d["label"]), plot_y)

        y_top = plot_y  + pr + 5
        y_bot = plot_y  + plot_h - pr - 5
        y = y_top + (y_bot - y_top) * (1.0 - t)

        nodes.append((QPointF(x, y), r))

    return nodes


# ─── ScatterPlotElement ──────────────────────────────────────────────────────

class ScatterPlotElement(QObject):
    """
    A non-widget scatter plot element.

    mon.py owns the geometry. This class holds all state and exposes:
      draw(painter, px, py, pw, ph)        — paint onto mon.py's painter
      handle_click(mx, my, px, py, pw, ph) — forward mouse events
      handle_resize(px, py, pw, ph)        — call on window resize
      set_data(fluid_data)                 — update data

    The animation timer calls parent.update() so mon.py repaints.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._parent = parent

        self._data          : list[dict] = []
        self._color_map     : dict       = {}
        self._x_slots       : dict       = {}
        self._current_nodes : list       = []
        self._target_nodes  : list       = []

        # Detail panel state
        self._panel_open    : bool = False
        self._panel_proc    : str  = ""
        self._panel_parent  : str  = ""

        # Animation timer — triggers parent repaint at ~60 fps
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)
        self._anim.start(16)

    # ── public API ───────────────────────────────────────────────────

    def set_data(self, data: list[dict], px: int, py: int,
                 pw: int, ph: int):
        self._data      = data
        self._color_map = build_color_map(data)
        blob_pw         = self._blob_plot_w(pw)
        new_slots = _assign_x_slots(data, px, blob_pw)
        for key, x in new_slots.items():
            if key not in self._x_slots:
                self._x_slots[key] = x
        self._rebuild_targets(px, py, pw, ph)

    def handle_resize(self, px: int, py: int, pw: int, ph: int):
        if self._data:
            self._rebuild_targets(px, py, pw, ph)

    def handle_click(self, mx: float, my: float,
                     px: int, py: int, pw: int, ph: int):
        if self._panel_open:
            bx, by, bw, bh = box_rect(px, py, pw, ph)
            if bx <= mx <= bx + bw and by <= my <= by + bh:
                return   # click inside panel — ignore
            self._panel_open = False
            self._rebuild_targets(px, py, pw, ph)
            self._request_update()
            return

        idx = self._hit_node(mx, my)
        if 0 <= idx < len(self._data):
            d = self._data[idx]
            self._panel_proc   = d["label"]
            self._panel_parent = self._get_parent_name(d["label"])
            self._panel_open   = True
            self._rebuild_targets(px, py, pw, ph)
            self._request_update()

    def draw(self, painter: QPainter, px: int, py: int,
             pw: int, ph: int):
        """
        Paint the full scatter plot into the given plot rect.
        Called from mon.py's paintEvent when active_tab == "SCATTER PLOT".
        """
        plot_bottom = py + ph

        # Background — fill only the plot area
        painter.fillRect(px, py, pw, ph, BG_COLOR)

        # Horizontal ruled lines
        painter.setPen(QPen(GRID_COLOR, 1))
        for i in range(11):
            gy = int(py + ph * i / 10)
            painter.drawLine(px, gy, px + pw, gy)

        # Top / bottom dividers
        painter.setPen(QPen(DIVIDER, 1))
        painter.drawLine(px, py,          px + pw, py)
        painter.drawLine(px, plot_bottom, px + pw, plot_bottom)

        nodes = self._current_nodes
        if not nodes:
            painter.setPen(QColor(160, 140, 100, 120))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(px, py, pw, ph,
                             Qt.AlignmentFlag.AlignCenter, "No data")
            return

        # Fluid blobs + belts
        FluidRenderer(painter, nodes, self._data, self._color_map).draw()

        # Username labels centred under each user group
        painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
        fm = QFontMetrics(painter.font())
        label_y = plot_bottom + 26

        groups: dict[str, list] = {}
        for i, (pt, _) in enumerate(nodes):
            groups.setdefault(self._data[i]["user"], []).append(pt.x())

        for u, xs in groups.items():
            blob, _ = self._color_map.get(u, (QColor(254, 197, 110),
                                              QColor(193, 52, 40)))
            mid = (min(xs) + max(xs)) / 2
            uw  = fm.horizontalAdvance(u)
            painter.setPen(blob.darker(160))
            painter.drawText(int(mid - uw / 2), label_y, u)

        # Process name above each blob
        painter.setFont(QFont("Georgia", 7))
        fm2 = QFontMetrics(painter.font())
        painter.setPen(QColor(90, 70, 40, 150))
        for i, (pt, r) in enumerate(nodes):
            lbl = self._data[i]["label"]
            pr  = r + _dyn_pad(r)
            tw  = fm2.horizontalAdvance(lbl)
            painter.drawText(int(pt.x() - tw / 2), int(pt.y() - pr - 4), lbl)

        # CPU % in white at centre of each blob
        for i, (pt, r) in enumerate(nodes):
            val = self._data[i]["value"]
            if r < 10:
                continue
            txt       = f"{val:.0f}%"
            font_size = max(6, min(int(r * 0.55), 11))
            font      = QFont("Georgia", font_size, QFont.Weight.Bold)
            painter.setFont(font)
            fm3 = QFontMetrics(font)
            tw  = fm3.horizontalAdvance(txt)
            th  = fm3.ascent()
            painter.setPen(QColor(255, 255, 255, 220))
            painter.drawText(int(pt.x() - tw / 2), int(pt.y() + th / 2), txt)

        # Detail panel — drawn last so it's always on top
        if self._panel_open:
            draw_detail_box(painter, px, py, pw, ph,
                            self._panel_proc, self._panel_parent)

    # ── internal ─────────────────────────────────────────────────────

    def _blob_plot_w(self, plot_w: int) -> int:
        if self._panel_open:
            return plot_w - BOX_W - BOX_GAP
        return plot_w

    def _rebuild_targets(self, px: int, py: int, pw: int, ph: int):
        blob_pw        = self._blob_plot_w(pw)
        self._x_slots  = _assign_x_slots(self._data, px, blob_pw)
        targets = _compute_targets(self._data, self._x_slots, py, ph)
        if len(targets) != len(self._current_nodes):
            self._current_nodes = [(QPointF(p.x(), p.y()), r)
                                   for p, r in targets]
        self._target_nodes = targets
        self._request_update()

    def _step(self):
        if len(self._current_nodes) != len(self._target_nodes):
            return
        moved = False
        s = 0.06
        for i in range(len(self._current_nodes)):
            cp, cr = self._current_nodes[i]
            tp, tr = self._target_nodes[i]
            nx = cp.x() + (tp.x() - cp.x()) * s
            ny = cp.y() + (tp.y() - cp.y()) * s
            nr = cr     + (tr - cr) * s
            self._current_nodes[i] = (QPointF(nx, ny), nr)
            if abs(tp.x()-nx) > 0.4 or abs(tp.y()-ny) > 0.4 or abs(tr-nr) > 0.05:
                moved = True
        if moved:
            self._request_update()

    def _request_update(self):
        """Ask the parent window to repaint."""
        if self._parent is not None:
            self._parent.update()

    def _hit_node(self, mx: float, my: float) -> int:
        for i, (pt, r) in enumerate(self._current_nodes):
            pr = r + _dyn_pad(r)
            dx = mx - pt.x();  dy = my - pt.y()
            if dx*dx + dy*dy <= pr*pr:
                return i
        return -1

    @staticmethod
    def _get_parent_name(proc_name: str) -> str:
        try:
            for proc in psutil.process_iter(['name', 'ppid']):
                if proc.info['name'] == proc_name:
                    ppid = proc.info['ppid']
                    if ppid:
                        try:
                            return psutil.Process(ppid).name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            return "—"
        except Exception:
            pass
        return "—"


# ─── Standalone window (unchanged) ───────────────────────────────────────────

class ScatterPlotWidget(QWidget):
    """
    Kept for ScatterPlotWindow standalone use.
    Not used by mon.py anymore — mon.py uses ScatterPlotElement instead.
    """

    def __init__(self, parent=None, embedded: bool = False):
        super().__init__(parent)

        self._embedded      = embedded
        self._data          : list[dict] = []
        self._color_map     : dict       = {}
        self._x_slots       : dict       = {}
        self._current_nodes : list       = []
        self._target_nodes  : list       = []

        self._panel_open    : bool = False
        self._panel_proc    : str  = ""
        self._panel_parent  : str  = ""

        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)
        self._anim.start(16)

    def set_data(self, data: list[dict]):
        self._data      = data
        self._color_map = build_color_map(data)
        px, py, pw, ph  = self._plot_rect()
        blob_pw         = self._blob_plot_w(pw)
        new_slots = _assign_x_slots(data, px, blob_pw)
        for key, x in new_slots.items():
            if key not in self._x_slots:
                self._x_slots[key] = x
        self._rebuild_targets()

    def _plot_rect(self):
        w, h = self.width(), self.height()
        if self._embedded:
            return (0, 0, w, h)
        return (PAD_LEFT, PAD_TOP,
                w - PAD_LEFT - PAD_RIGHT,
                h - PAD_TOP  - PAD_BOTTOM)

    def _blob_plot_w(self, plot_w: int) -> int:
        if self._panel_open:
            return plot_w - BOX_W - BOX_GAP
        return plot_w

    def _rebuild_targets(self):
        px, py, pw, ph = self._plot_rect()
        blob_pw        = self._blob_plot_w(pw)
        self._x_slots  = _assign_x_slots(self._data, px, blob_pw)
        targets = _compute_targets(self._data, self._x_slots, py, ph)
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
            nx = cp.x() + (tp.x() - cp.x()) * s
            ny = cp.y() + (tp.y() - cp.y()) * s
            nr = cr     + (tr - cr) * s
            self._current_nodes[i] = (QPointF(nx, ny), nr)
            if abs(tp.x()-nx) > 0.4 or abs(tp.y()-ny) > 0.4 or abs(tr-nr) > 0.05:
                moved = True
        if moved:
            self.update()

    def _hit_node(self, mx: float, my: float) -> int:
        for i, (pt, r) in enumerate(self._current_nodes):
            pr = r + _dyn_pad(r)
            dx = mx - pt.x();  dy = my - pt.y()
            if dx*dx + dy*dy <= pr*pr:
                return i
        return -1

    def _panel_rect(self):
        if not self._panel_open:
            return None
        px, py, pw, ph = self._plot_rect()
        return box_rect(px, py, pw, ph)

    @staticmethod
    def _get_parent_name(proc_name: str) -> str:
        try:
            for proc in psutil.process_iter(['name', 'ppid']):
                if proc.info['name'] == proc_name:
                    ppid = proc.info['ppid']
                    if ppid:
                        try:
                            return psutil.Process(ppid).name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            return "—"
        except Exception:
            pass
        return "—"

    def mousePressEvent(self, event):
        mx, my = event.position().x(), event.position().y()
        if self._panel_open:
            pr = self._panel_rect()
            if pr:
                bx, by, bw, bh = pr
                if bx <= mx <= bx + bw and by <= my <= by + bh:
                    return
            self._panel_open = False
            self._rebuild_targets()
            self.update()
            return
        idx = self._hit_node(mx, my)
        if 0 <= idx < len(self._data):
            d = self._data[idx]
            self._panel_proc   = d["label"]
            self._panel_parent = self._get_parent_name(d["label"])
            self._panel_open   = True
            self._rebuild_targets()
            self.update()

    def resizeEvent(self, e):
        if self._data:
            self._rebuild_targets()
        super().resizeEvent(e)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        px, py, pw, ph = self._plot_rect()
        plot_bottom    = py + ph
        painter.fillRect(0, 0, w, h, BG_COLOR)
        painter.setPen(QPen(GRID_COLOR, 1))
        for i in range(11):
            gy = int(py + ph * i / 10)
            painter.drawLine(px, gy, px + pw, gy)
        painter.setPen(QPen(DIVIDER, 1))
        painter.drawLine(px, py,          px + pw, py)
        painter.drawLine(px, plot_bottom, px + pw, plot_bottom)
        nodes = self._current_nodes
        if not nodes:
            painter.setPen(QColor(160, 140, 100, 120))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            return
        FluidRenderer(painter, nodes, self._data, self._color_map).draw()
        painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
        fm = QFontMetrics(painter.font())
        label_y = plot_bottom + 26
        groups: dict[str, list] = {}
        for i, (pt, _) in enumerate(nodes):
            groups.setdefault(self._data[i]["user"], []).append(pt.x())
        for u, xs in groups.items():
            blob, _ = self._color_map.get(u, (QColor(254, 197, 110),
                                              QColor(193, 52, 40)))
            mid = (min(xs) + max(xs)) / 2
            uw  = fm.horizontalAdvance(u)
            painter.setPen(blob.darker(160))
            painter.drawText(int(mid - uw / 2), label_y, u)
        painter.setFont(QFont("Georgia", 7))
        fm2 = QFontMetrics(painter.font())
        painter.setPen(QColor(90, 70, 40, 150))
        for i, (pt, r) in enumerate(nodes):
            lbl = self._data[i]["label"]
            pr  = r + _dyn_pad(r)
            tw  = fm2.horizontalAdvance(lbl)
            painter.drawText(int(pt.x() - tw / 2), int(pt.y() - pr - 4), lbl)
        for i, (pt, r) in enumerate(nodes):
            val = self._data[i]["value"]
            if r < 10:
                continue
            txt       = f"{val:.0f}%"
            font_size = max(6, min(int(r * 0.55), 11))
            font      = QFont("Georgia", font_size, QFont.Weight.Bold)
            painter.setFont(font)
            fm3 = QFontMetrics(font)
            tw  = fm3.horizontalAdvance(txt)
            th  = fm3.ascent()
            painter.setPen(QColor(255, 255, 255, 220))
            painter.drawText(int(pt.x() - tw / 2), int(pt.y() + th / 2), txt)
        if self._panel_open:
            draw_detail_box(painter, px, py, pw, ph,
                            self._panel_proc, self._panel_parent)


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

        self._plot = ScatterPlotWidget(embedded=False)
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


def open_scatter_plot_window() -> ScatterPlotWindow:
    w = ScatterPlotWindow()
    w.show()
    return w


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ScatterPlotWindow()
    win.show()
    sys.exit(app.exec())