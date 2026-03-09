import sys
import psutil
from collections import deque
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
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
        self.resize(700, 450)

        # Initialize data storage for plots (max 30 data points)
        self.cpu_data  = deque(maxlen=30)
        self.ram_data  = deque(maxlen=30)
        self.disk_data = deque(maxlen=30)

        # ── Scatter plot widget ───────────────────────────────────────
        # scatter_plot.py shim sets embedded=True — zero internal padding.
        # mon.py owns the geometry via _reposition_scatter().
        self._scatter = ScatterPlotWidget(parent=self, embedded=True)
        self._scatter.hide()

        # Data refresh timer for scatter (every 2 s)
        self._scatter_timer = QTimer(self)
        self._scatter_timer.timeout.connect(self._refresh_scatter)
        self._scatter_timer.start(2000)

        # Setup data collection timer (system usage)
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.collect_usage_data)
        self.data_timer.start(1000)

        self.after_layout_setup()

    # ── scatter data ─────────────────────────────────────────────────

    def _refresh_scatter(self):
        try:
            processed  = ProcessDataProcessor.process_pipeline()
            fluid_data = ProcessDataProcessor.to_fluid_data(processed)
            if fluid_data:
                self._scatter.set_data(fluid_data)
        except Exception as e:
            print(f"[scatter refresh] {e}")

    # ── tab geometry helpers ──────────────────────────────────────────

    def _plot_rect(self) -> QRect:
        """
        Returns the QRect of the plot area using the same margin logic
        as paintEvent, so the child widget sits exactly inside it.
        """
        w, h  = self.width(), self.height()
        scale = min(w / self.base_width, h / self.base_height)
        ml = int(50 * scale)
        mr = int(50 * scale)
        mt = int(100 * scale)
        mb = int(60 * scale)
        return QRect(ml, mt, w - ml - mr, h - mt - mb)

    def _reposition_scatter(self):
        """Move/resize the scatter widget to fill the current plot area."""
        r = self._plot_rect()
        self._scatter.setGeometry(r)

    # ── tab switching ─────────────────────────────────────────────────

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

    # ── system data collection ────────────────────────────────────────

    def collect_usage_data(self):
        try:
            self.cpu_data.append(psutil.cpu_percent(interval=0))
            self.ram_data.append(psutil.virtual_memory().percent)
            self.disk_data.append(psutil.disk_usage('/').percent)
            self.update()
        except Exception as e:
            print(f"Error collecting usage data: {e}")

    # ── resize ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.active_tab == "SCATTER PLOT":
            self._reposition_scatter()

    # ── drawing ───────────────────────────────────────────────────────

    def draw_usage_plots(self, painter, graph_left, graph_right,
                         graph_top, graph_bottom):
        if len(self.cpu_data) < 2:
            return

        graph_width  = graph_right - graph_left
        graph_height = graph_bottom - graph_top

        def value_to_y(value):
            return graph_bottom - (graph_height * (value / 100))

        def index_to_x(index):
            return graph_left + (graph_width * (index / 29.0))

        # CPU — filled + line
        points = [(int(index_to_x(i)), int(value_to_y(v)))
                  for i, v in enumerate(self.cpu_data)]
        poly_pts = points + [(p[0], int(graph_bottom)) for p in reversed(points)]
        if len(poly_pts) > 2:
            painter.setBrush(QBrush(QColor(225, 170, 30, int(255 * 0.6))))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygon([QPoint(*p) for p in poly_pts]))
        pen = QPen(QColor(225, 170, 30, int(255 * 0.6)))
        pen.setWidth(2)
        painter.setPen(pen)
        for i in range(len(points)-1):
            painter.drawLine(*points[i], *points[i+1])

        # RAM — filled + line
        points = [(int(index_to_x(i)), int(value_to_y(v)))
                  for i, v in enumerate(self.ram_data)]
        poly_pts = points + [(p[0], int(graph_bottom)) for p in reversed(points)]
        if len(poly_pts) > 2:
            painter.setBrush(QBrush(QColor(59, 169, 144, int(255 * 0.6))))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygon([QPoint(*p) for p in poly_pts]))
        pen = QPen(QColor(59, 169, 144, int(255 * 0.6)))
        pen.setWidth(2)
        painter.setPen(pen)
        for i in range(len(points)-1):
            painter.drawLine(*points[i], *points[i+1])

        # DISK — dashed line
        pen = QPen(QColor(222, 96, 58))
        pen.setWidth(2)
        pen.setDashPattern([5, 5])
        painter.setPen(pen)
        points = [(int(index_to_x(i)), int(value_to_y(v)))
                  for i, v in enumerate(self.disk_data)]
        for i in range(len(points)-1):
            painter.drawLine(*points[i], *points[i+1])

    def paintEvent(self, event):
        super().paintEvent(event)

        width  = self.width()
        height = self.height()
        scale  = min(width / self.base_width, height / self.base_height)

        margin_left   = int(50 * scale)
        margin_right  = int(50 * scale)
        margin_top    = int((100 + self._title_bar_offset) * scale)
        margin_bottom = int(60 * scale)

        graph_left   = margin_left
        graph_right  = width  - margin_right
        graph_top    = margin_top
        graph_bottom = height - margin_bottom

        if sys.platform == "darwin":
            divvv = 2
            scall = 40
            ftttt = 1
            mkc = 0
        else:
            divvv = 1
            scall = 50
            ftttt = 3
            mkc = 4

        painter = QPainter(self)
        if self.active_tab == "SYSTEM USAGE":
            label_opacity = 0.6
            line_opacity  = 0.6

            for y_val in [100, 75, 50, 25]:
                y_pos = graph_bottom - (graph_bottom - graph_top) * (y_val / 100)
                pen = QPen(QColor(63, 72, 101, int(255 * line_opacity)))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawLine(int(graph_left)+28, int(y_pos),
                                 int(graph_right),   int(y_pos))
                font_size = int(10 * scale)
                font = QFont("Inter")
                font.setPointSize(font_size)
                font.setWeight(QFont.Weight.DemiBold)
                painter.setFont(font)
                painter.setPen(QColor(63, 72, 101, int(255 * label_opacity)))
                painter.drawText(int(graph_left), int(y_pos - font_size/divvv),
                                 int(scall*scale), font_size*ftttt, 0, f"{y_val}%")

            pen = QPen(QColor(63, 72, 101))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(int(graph_left), int(graph_bottom),
                             int(graph_right), int(graph_bottom))

            tick_height = int(5 * scale)
            for x_val in range(30, -5, -5):
                x_pos = graph_left + (graph_right-graph_left) * ((30-x_val)/30)
                pen = QPen(QColor(63, 72, 101, 255))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawLine(int(x_pos), int(graph_bottom),
                                 int(x_pos), int(graph_bottom-tick_height))
                font_size = int(8 * scale)
                font = QFont("Inter")
                font.setPointSize(font_size)
                painter.setFont(font)
                painter.setPen(QColor(63, 72, 101, 255))
                lw = int(20 * scale)
                lx = int(x_pos - lw/2 + 6)
                ly = int((graph_bottom - tick_height - font_size - 3*scale)-mkc)
                painter.drawText(lx, ly, lw, (font_size*ftttt), 0, str(x_val))

            self.draw_usage_plots(painter, graph_left, graph_right,
                                  graph_top, graph_bottom)

        elif self.active_tab == "ANOMALY":
            painter.setPen(QColor(63, 72, 101))
            font = QFont("Inter")
            font.setPointSize(int(16 * scale))
            painter.setFont(font)
            painter.drawText(graph_left, graph_top,
                             graph_right-graph_left, graph_bottom-graph_top,
                             Qt.AlignCenter, "ANOMALY\n(To be implemented)")

        painter.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    root = SystemUsageWindow()
    root.show()
    sys.exit(app.exec())