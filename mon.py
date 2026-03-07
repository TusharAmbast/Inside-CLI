import sys
import platform
import psutil
from collections import deque
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Signal, Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPolygon



from base_window import BaseMonitorWindow
from scatter_plot import ScatterPlotWidget, ProcessDataProcessor


class ClickableLabel(QLabel):
    """Custom QLabel that emits a signal when clicked"""
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()


class SystemUsageWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="SYSTEM USAGE")
        self.setWindowTitle("System Usage - Critique CLI")

        

        self.cpu_data  = deque(maxlen=30)
        self.ram_data  = deque(maxlen=30)
        self.disk_data = deque(maxlen=30)

        self._scatter = ScatterPlotWidget(parent=self)
        self._scatter.hide()

        self._scatter_timer = QTimer(self)
        self._scatter_timer.timeout.connect(self._refresh_scatter)
        self._scatter_timer.start(2000)

        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.collect_usage_data)
        self.data_timer.start(1000)

        self.after_layout_setup()

    # ── scatter data ──────────────────────────────────────────────────────────

    def _refresh_scatter(self):
        try:
            processed  = ProcessDataProcessor.process_pipeline()
            fluid_data = ProcessDataProcessor.to_fluid_data(processed)
            if fluid_data:
                self._scatter.set_data(fluid_data)
        except Exception as e:
            print(f"[scatter refresh] {e}")

    # ── tab geometry helpers ──────────────────────────────────────────────────

    def _get_margin_top(self):
        
        tab_texts = ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]
        tab_bottom = 0
        for elem in self.elements:
            if elem["text"] in tab_texts and elem["label"]:
                lbl = elem["label"]
                bottom = lbl.y() + lbl.height()
                tab_bottom = max(tab_bottom, bottom)

        scale = min(self.width() / self.base_width, self.height() / self.base_height)
        padding = int(40 * scale)

        # Fall back to scaled default if labels aren't positioned yet
        return tab_bottom + padding if tab_bottom > 0 else int(100 * scale)

    def _plot_rect(self) -> QRect:
        w, h  = self.width(), self.height()
        scale = min(w / self.base_width, h / self.base_height)
        ml = int(50 * scale)
        mr = int(50 * scale)
        mt = self._get_margin_top()   # uses dynamic margin now
        mb = int(60 * scale)
        return QRect(ml, mt, w - ml - mr, h - mt - mb)

    def _reposition_scatter(self):
        self._scatter.setGeometry(self._plot_rect())

    # ── tab switching ─────────────────────────────────────────────────────────

    def after_layout_setup(self):
        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                old_label = elem["label"]
                clickable_label = ClickableLabel(elem["text"], self)
                clickable_label.setFont(old_label.font())
                clickable_label.setStyleSheet(old_label.styleSheet())
                clickable_label.move(old_label.pos())
                clickable_label.adjustSize()
                clickable_label.show()
                old_label.hide()
                elem["label"] = clickable_label

                if elem["text"] == "SCATTER PLOT":
                    clickable_label.clicked.connect(
                        lambda: self.switch_tab("SCATTER PLOT"))
                elif elem["text"] == "ANOMALY":
                    clickable_label.clicked.connect(
                        lambda: self.switch_tab("ANOMALY"))
                elif elem["text"] == "SYSTEM USAGE":
                    clickable_label.clicked.connect(
                        lambda: self.switch_tab("SYSTEM USAGE"))

    def switch_tab(self, tab_name):
        if self.active_tab == tab_name:
            return
        self.active_tab = tab_name
        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                elem["opacity"] = 1.0 if elem["text"] == tab_name else 0.4

        if tab_name == "SCATTER PLOT":
            self._reposition_scatter()
            self._scatter.show()
            self._scatter.raise_()
            if not self._scatter._data:
                self._refresh_scatter()
        else:
            self._scatter.hide()

        self.update_layout()
        self.update()

    # ── system data collection ────────────────────────────────────────────────

    def collect_usage_data(self):
        try:
            self.cpu_data.append(psutil.cpu_percent(interval=0))
            self.ram_data.append(psutil.virtual_memory().percent)
            self.disk_data.append(psutil.disk_usage('/').percent)
            self.update()
        except Exception as e:
            print(f"Error collecting usage data: {e}")

    # ── resize ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.active_tab == "SCATTER PLOT":
            self._reposition_scatter()

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw_usage_plots(self, painter, graph_left, graph_right,
                         graph_top, graph_bottom):
        if len(self.cpu_data) < 2:
            return

        graph_width  = graph_right - graph_left
        graph_height = graph_bottom - graph_top

        def value_to_y(value):
            return graph_bottom - (graph_height * (value / 100))

        def index_to_x(index):
            
            total = max(len(self.cpu_data) - 1, 1)
            return graph_left + (graph_width * (index / total))

        

        # CPU — filled + line
        points = [(int(index_to_x(i)), int(value_to_y(v)))
                  for i, v in enumerate(self.cpu_data)]
        if len(points) >= 2:
            poly = [QPoint(points[0][0], int(graph_bottom))]  # bottom-left anchor
            poly += [QPoint(p[0], p[1]) for p in points]      # data line
            poly += [QPoint(points[-1][0], int(graph_bottom))] # bottom-right anchor
            painter.setBrush(QBrush(QColor(225, 170, 30, int(255 * 0.6))))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygon(poly))
        pen = QPen(QColor(225, 170, 30, int(255 * 0.6)))
        pen.setWidth(2)
        painter.setPen(pen)
        for i in range(len(points) - 1):
            painter.drawLine(*points[i], *points[i+1])

        # RAM — filled + line
        points = [(int(index_to_x(i)), int(value_to_y(v)))
                  for i, v in enumerate(self.ram_data)]
        if len(points) >= 2:
            poly = [QPoint(points[0][0], int(graph_bottom))]
            poly += [QPoint(p[0], p[1]) for p in points]
            poly += [QPoint(points[-1][0], int(graph_bottom))]
            painter.setBrush(QBrush(QColor(59, 169, 144, int(255 * 0.6))))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygon(poly))
        pen = QPen(QColor(59, 169, 144, int(255 * 0.6)))
        pen.setWidth(2)
        painter.setPen(pen)
        for i in range(len(points) - 1):
            painter.drawLine(*points[i], *points[i+1])

        # DISK — dashed line only (no fill)
        pen = QPen(QColor(222, 96, 58))
        pen.setWidth(2)
        pen.setDashPattern([5, 5])
        painter.setPen(pen)
        points = [(int(index_to_x(i)), int(value_to_y(v)))
                  for i, v in enumerate(self.disk_data)]
        for i in range(len(points) - 1):
            painter.drawLine(*points[i], *points[i+1])

    def paintEvent(self, event):
        super().paintEvent(event)

        width  = self.width()
        height = self.height()
        scale  = min(width / self.base_width, height / self.base_height)

        margin_left   = int(50 * scale)
        margin_right  = int(50 * scale)
        margin_top    = self._get_margin_top()  # FIX 10: dynamic, not hardcoded
        margin_bottom = int(60 * scale)

        graph_left   = margin_left
        graph_right  = width  - margin_right
        graph_top    = margin_top
        graph_bottom = height - margin_bottom

        painter = QPainter(self)

        if self.active_tab == "SYSTEM USAGE":
            label_opacity = 0.6
            line_opacity  = 0.6

            # Y-axis grid + labels
            for y_val in [100, 75, 50, 25]:
                y_pos = graph_bottom - (graph_bottom - graph_top) * (y_val / 100)
                pen = QPen(QColor(63, 72, 101, int(255 * line_opacity)))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawLine(int(graph_left) + 28, int(y_pos),
                                 int(graph_right), int(y_pos))

                
                font_size = max(8, int(10 * scale))
                font = QFont("Inter")
                font.setPointSize(font_size)
                font.setWeight(QFont.Weight.DemiBold)
                painter.setFont(font)
                painter.setPen(QColor(63, 72, 101, int(255 * label_opacity)))
                painter.drawText(int(graph_left), int(y_pos - font_size),
                                 int(40 * scale), font_size * 2, 0, f"{y_val}%")

            # 0% baseline
            pen = QPen(QColor(63, 72, 101))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(int(graph_left), int(graph_bottom),
                             int(graph_right), int(graph_bottom))

            # X-axis ticks + labels
            tick_height = int(5 * scale)
            for x_val in range(30, -5, -5):
                x_pos = graph_left + (graph_right - graph_left) * ((30 - x_val) / 30)
                pen = QPen(QColor(63, 72, 101, 255))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawLine(int(x_pos), int(graph_bottom),
                                 int(x_pos), int(graph_bottom - tick_height))

                font_size = max(7, int(8 * scale))
                font = QFont("Inter")
                font.setPointSize(font_size)
                painter.setFont(font)
                painter.setPen(QColor(63, 72, 101, 255))
                lw = int(24 * scale)   # slightly wider label box
                lx = int(x_pos - lw / 2 + 6)
                ly = graph_bottom - tick_height - font_size*2 - 4  # below the baseline
                painter.drawText(lx, ly, lw, font_size * 2, 0, str(x_val))

            self.draw_usage_plots(painter, graph_left, graph_right,
                                  graph_top, graph_bottom)

        elif self.active_tab == "ANOMALY":
            painter.setPen(QColor(63, 72, 101))
            font = QFont("Inter")
            font.setPointSize(int(16 * scale))
            painter.setFont(font)
            painter.drawText(graph_left, graph_top,
                             graph_right - graph_left, graph_bottom - graph_top,
                             Qt.AlignCenter, "ANOMALY\n(To be implemented)")

        painter.end()


if __name__ == "__main__":
    
    if platform.system() == "Windows":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        except Exception:
            pass  # Silently ignore if it fails (older Windows versions)

    app = QApplication(sys.argv)
    root = SystemUsageWindow()
    root.show()
    sys.exit(app.exec())