from operator import index
import sys
import psutil
from collections import deque
from PySide6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QFrame, QScrollArea
)
from PySide6.QtCore import Signal, Qt, QTimer, QThread, QPoint, QRect, Slot
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPolygon

from base_window import BaseMonitorWindow
from scatter_plot import ScatterPlotElement, ProcessDataProcessor
from anomaly import AnomalyWorker, HoverBadge


class ClickableLabel(QLabel):
    """Custom QLabel that emits a signal when clicked"""
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()

disk_path = 'C:\\' if sys.platform == 'win32' else '/'


class SystemUsageWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="SYSTEM USAGE")
        self.setWindowTitle("System Usage - Critique CLI")
        self.resize(700, 450)

        # Initialize data storage for plots (max 30 data points)
        self.cpu_data  = deque(maxlen=30)
        self.ram_data  = deque(maxlen=30)
        self.disk_data = deque(maxlen=30)
        self._last_disk_io = psutil.disk_io_counters()

        # ── Scatter element (not a widget — draws onto our painter) ───
        self._scatter = ScatterPlotElement(parent=self)

        # Data refresh timer for scatter (every 2 s)
        self._scatter_timer = QTimer(self)
        self._scatter_timer.timeout.connect(self._refresh_scatter)
        self._scatter_timer.start(2000)

        # Setup data collection timer (system usage)
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.collect_usage_data)
        self.data_timer.start(1000)

        # ── Anomaly scroll area (child widget, shown on ANOMALY tab) ──
        self._last_anomalies = []
        self._build_anomaly_area()
        self._start_anomaly_worker()

        self.after_layout_setup()

    # ── scatter data ─────────────────────────────────────────────────

    def _refresh_scatter(self):
        try:
            processed  = ProcessDataProcessor.process_pipeline()
            fluid_data = ProcessDataProcessor.to_fluid_data(processed)
            if fluid_data:
                px, py, pw, ph = self._scatter_rect_tuple()
                self._scatter.set_data(fluid_data, px, py, pw, ph)
        except Exception as e:
            print(f"[scatter refresh] {e}")

    # ── plot rect helper ──────────────────────────────────────────────

    def _plot_rect_tuple(self):
        """Returns (px, py, pw, ph) — the plot area in window coordinates."""
        w, h  = self.width(), self.height()
        scale = min(w / self.base_width, h / self.base_height)
        ml = int(50 * scale)
        mr = int(50 * scale)
        mt = int((100 + self._title_bar_offset) * scale)
        mb = int(60 * scale)
        return ml, mt, w - ml - mr, h - mt - mb

    def _scatter_rect_tuple(self):
        """Returns (px, py, pw, ph) for the scatter plot — wider side margins."""
        w, h  = self.width(), self.height()
        scale = min(w / self.base_width, h / self.base_height)
        ml = int(50 * scale)
        mr = int(50 * scale)
        mt = int((100 + self._title_bar_offset) * scale)
        mb = int(85 * scale)
        return ml, mt, w - ml - mr, h - mt - mb

    # ── anomaly area setup ────────────────────────────────────────────

    def _build_anomaly_area(self):
        """Build the scrollable card container for the ANOMALY tab."""
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea                     { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)

        self.card_container = QWidget()
        self.card_container.setStyleSheet("background: transparent;")

        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(2, 6, 2, 6)
        self.card_layout.setSpacing(12)
        self.card_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.card_container)
        self.scroll_area.hide()
        self._position_anomaly_area()

    def _position_anomaly_area(self):
        """Fit the scroll area exactly inside the plot rect."""
        px, py, pw, ph = self._plot_rect_tuple()
        self.scroll_area.setGeometry(px, py, pw, ph)

    # ── anomaly worker ────────────────────────────────────────────────

    def _start_anomaly_worker(self):
        self._anomaly_worker        = AnomalyWorker()
        self._anomaly_worker_thread = QThread()
        self._anomaly_worker.moveToThread(self._anomaly_worker_thread)
        self._anomaly_worker.anomaliesFound.connect(self._update_anomaly_cards)
        self._anomaly_worker.killProcess.connect(
            self._anomaly_worker.terminate_process)
        self._anomaly_worker_thread.started.connect(
            self._anomaly_worker.start_monitoring)
        self._anomaly_worker_thread.start()

    def _stop_anomaly_worker(self):
        self._anomaly_worker.stop_monitoring()
        self._anomaly_worker_thread.quit()
        self._anomaly_worker_thread.wait()

    def closeEvent(self, event):
        self._stop_anomaly_worker()
        event.accept()

    # ── anomaly card rendering ────────────────────────────────────────

    @Slot(list)
    def _update_anomaly_cards(self, anomalies: list):
        self._last_anomalies = anomalies
        self._clear_card_layout()
            
        if not anomalies:
            empty = QLabel("No anomalies detected.")
            empty.setFont(QFont("Inter", 11))
            empty.setStyleSheet(
                "color: rgba(63, 72, 101, 0.45); background: transparent;")
            empty.setAlignment(Qt.AlignCenter)
            self.card_layout.addWidget(empty)
            return

        for anomaly in anomalies:
            self.card_layout.addWidget(self._make_anomaly_card(anomaly))

        self.card_layout.addStretch()

    def _make_anomaly_card(self, anomaly: dict) -> QFrame:
        is_safe = anomaly["level"] == "safe"

        sx    = self.width()  / self.base_width
        sy    = self.height() / self.base_height
        scale = (sx + sy) / 2.0

        pad_lr  = int(16  * scale)
        pad_top = int(10  * scale)
        pad_bot = int(10  * scale)

        CARD_BG      = "rgb(245, 242, 233)"
        CARD_BORDER  = "rgb(63, 72, 101)"
        BADGE_BORDER = "rgb(63, 72, 101)"
        BADGE_TEXT   = "rgb(254, 243, 215)"

        if is_safe:
            badge_color      = "rgb(56, 171, 142)"
            hover_text       = "END TASK"
            normal_badge_txt = "Process is not important\ncan be removed for\nCPU RELAXATION"
        else:
            badge_color      = "rgb(222, 96, 58)"
            hover_text       = "CAN'T END TASK"
            normal_badge_txt = "Process is important\ncannot be removed for\nCPU RELAXATION"

        card = QFrame()
        card.setObjectName("anomalyCard")
        card.setFixedHeight(int(70 * scale))
        card.setStyleSheet(f"""
            QFrame#anomalyCard {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}
        """)

        body = QHBoxLayout(card)
        body.setContentsMargins(pad_lr, pad_top, pad_lr, pad_bot)
        body.setSpacing(int(16 * scale))

        # left: name + description
        left = QVBoxLayout()
        left.setSpacing(int(4 * scale))
        left.setContentsMargins(0, 0, 0, 0)

        name_font_size = max(1, int(13 * scale))
        name_lbl = QLabel(anomaly["name"])
        name_font = QFont("Inter", name_font_size)
        name_font.setWeight(QFont.Weight.DemiBold)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet(
            f"color: {CARD_BORDER}; background: transparent; border: none;")

        desc_font_size = max(1, int(11 * scale))
        desc_lbl = QLabel(anomaly["desc"])
        desc_lbl.setFont(QFont("Inter", desc_font_size, QFont.Weight.Normal))
        desc_lbl.setStyleSheet(
            "color: rgba(63, 72, 101, 0.65); background: transparent; border: none;")
        desc_lbl.setWordWrap(True)

        left.addWidget(name_lbl)
        left.addWidget(desc_lbl)
        left.addStretch()

        # right: hover badge
        right = QVBoxLayout()
        right.setSpacing(0)
        right.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        right.setContentsMargins(0, 0, 0, 0)

        badge_font_size       = max(1, int(11 * scale))
        badge_font_size_hover = max(1, int(13 * scale))
        badge_radius          = max(1, int(10 * scale))
        badge_pad             = max(1, int(8  * scale))
        badge_width           = max(1, int(170 * scale))
        badge_height          = max(1, int(52  * scale))

        normal_style = f"""
            QLabel {{
                background-color: {badge_color};
                color: {BADGE_TEXT};
                border-radius: {badge_radius}px;
                border: 1px solid {BADGE_BORDER};
                padding: {badge_pad}px;
                font-family: Inter;
                font-size: {badge_font_size}px;
                font-weight: 600;
            }}
        """
        hover_style = f"""
            QLabel {{
                background-color: {badge_color};
                color: {BADGE_TEXT};
                border-radius: {badge_radius}px;
                border: 1px solid {BADGE_BORDER};
                padding: {badge_pad}px;
                font-family: Inter;
                font-size: {badge_font_size_hover}px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """

        badge = HoverBadge(
            normal_text=normal_badge_txt,
            hover_text=hover_text,
            normal_style=normal_style,
            hover_style=hover_style,
        )
        badge.setFixedWidth(badge_width)
        badge.setFixedHeight(badge_height)
        badge.setFont(QFont("Inter", badge_font_size, QFont.Weight.DemiBold))

        if is_safe:
            badge.setCursor(Qt.PointingHandCursor)
            badge.mousePressEvent = (
                lambda _, pid=anomaly["pid"]:
                self._anomaly_worker.killProcess.emit(pid)
            )

        right.addWidget(badge, 0, Qt.AlignRight)
        body.addLayout(left,  3)
        body.addLayout(right, 1)

        return card

    def _clear_card_layout(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_nested_layout(item.layout())

    def _clear_nested_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_nested_layout(item.layout())

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

                tab = elem["text"]
                clickable_label.clicked.connect(
                    lambda _=False, t=tab: self.switch_tab(t))

    def switch_tab(self, tab_name):
        if self.active_tab == tab_name:
            return

        self.active_tab = tab_name

        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                elem["opacity"] = 1.0 if elem["text"] == tab_name else 0.4

        if tab_name == "SCATTER PLOT":
            self.scroll_area.hide()
            if not self._scatter._data:
                self._refresh_scatter()
        elif tab_name == "ANOMALY":
            self._position_anomaly_area()
            self.scroll_area.show()
            self.scroll_area.raise_()
            if self._last_anomalies:
                self._update_anomaly_cards(self._last_anomalies)
        else:
            self.scroll_area.hide()

        self.update_layout()
        self.update()

    # ── system data collection ────────────────────────────────────────

    def collect_usage_data(self):
        try:
            self.cpu_data.append(psutil.cpu_percent(interval=None))
            self.ram_data.append(psutil.virtual_memory().percent)
            current_io = psutil.disk_io_counters()
            last_io = self._last_disk_io
            bytes_delta = (current_io.read_bytes + current_io.write_bytes) - \
                        (last_io.read_bytes + last_io.write_bytes)
            disk_activity = min(bytes_delta / (500 * 1024 * 1024) * 100, 100)
            self.disk_data.append(disk_activity)
            self._last_disk_io = current_io
            self.update()
        except Exception as e:
            print(f"Error collecting usage data: {e}")

    # ── resize ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.active_tab == "SCATTER PLOT":
            px, py, pw, ph = self._scatter_rect_tuple()
            self._scatter.on_resize(px, py, pw, ph)
        elif self.active_tab == "ANOMALY":
            self._position_anomaly_area()
            if self._last_anomalies:
                self._update_anomaly_cards(self._last_anomalies)

    # ── mouse ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self.active_tab == "SCATTER PLOT":
            mx = event.position().x()
            my = event.position().y()
            px, py, pw, ph = self._scatter_rect_tuple()
            self._scatter.handle_click(mx, my, px, py, pw, ph)
        else:
            super().mousePressEvent(event)

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
            n = len(self.cpu_data)
            slot_width = graph_width / 29.0
            return graph_right - (n - 1 - index) * slot_width

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
        graph_width  = graph_right  - graph_left
        graph_height = graph_bottom - graph_top

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

        elif self.active_tab == "SCATTER PLOT":
            sx, sy, sw, sh = self._scatter_rect_tuple()
            self._scatter.draw(painter, sx, sy, sw, sh)

        # ANOMALY tab has no painter drawing — the scroll_area child widget
        # handles all rendering when visible

        painter.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    root = SystemUsageWindow()
    root.show()
    sys.exit(app.exec())