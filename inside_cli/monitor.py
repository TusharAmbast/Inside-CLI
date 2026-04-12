import sys
import numpy as np
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSizePolicy)
from PySide6.QtGui import QFont, QFontDatabase, QColor, QPainter
from PySide6.QtCore import Qt
import pyqtgraph as pg

# Configuration & Colors
BG_COLOR = "#FDF5E2"
TEXT_COLOR = "#2D3447"
CPU_COLOR = "#F5B951"  # Yellowish
RAM_COLOR = "#6FB085"  # Greenish
DISK_COLOR = "#E65C39" # Reddish (Dashed)

class InsideCliApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inside Cli - System Monitor")
        self.resize(1000, 600)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        
        # Load Fonts (Placeholder logic - assumes fonts are installed or in folder)
        # QFontDatabase.addApplicationFont("fonts/Inter-Bold.ttf")
        # QFontDatabase.addApplicationFont("fonts/AbrilFatface-Regular.ttf")
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(0)

        # --- HEADER ---
        header_layout = QHBoxLayout()
        
        # Mac-style traffic lights
        traffic_lights = QHBoxLayout()
        for color in ["#FF5F56", "#FFBD2E", "#27C93F"]:
            dot = QFrame()
            dot.setFixedSize(15, 15)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 7px;")
            traffic_lights.addWidget(dot)
        traffic_lights.addSpacing(20)
        header_layout.addLayout(traffic_lights)

        # Tabs
        self.tabs = []
        tab_names = ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]
        for i, name in enumerate(tab_names):
            btn = QPushButton(name)
            btn.setFlat(True)
            # System Usage starts at 100% opacity, others at 40%
            opacity = "1.0" if i == 0 else "0.4"
            btn.setStyleSheet(f"""
                QPushButton {{
                    color: {TEXT_COLOR};
                    font-family: 'Inter', sans-serif;
                    font-weight: bold;
                    font-size: 18px;
                    border: none;
                    padding: 0 15px;
                    opacity: {opacity};
                }}
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, b=btn: self.handle_tab_click(b))
            header_layout.addWidget(btn)
            self.tabs.append(btn)

        header_layout.addStretch()

        # Logo
        logo = QLabel("Inside Cli")
        logo.setStyleSheet(f"color: {TEXT_COLOR}; font-family: 'Abril Fatface', serif; font-size: 42px;")
        header_layout.addWidget(logo)
        
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(40)

        # --- GRAPH AREA ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()
        
        # Remove borders
        self.plot_widget.showAxis('left', False)
        self.plot_widget.showAxis('bottom', True)
        
        self.setup_graph()
        main_layout.addWidget(self.plot_widget)

        # --- FOOTER ---
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 20, 0, 0)
        
        stats = [
            ("CPU : 69%", CPU_COLOR),
            ("RAM : 69%", RAM_COLOR),
            ("DISK : 69%", DISK_COLOR)
        ]
        
        for text, color in stats:
            label = QLabel(text)
            label.setStyleSheet(f"color: {color}; font-family: 'Inter'; font-weight: bold; font-size: 24px;")
            footer_layout.addWidget(label)
            footer_layout.addSpacing(40)
            
        footer_layout.addStretch()
        main_layout.addLayout(footer_layout)

    def setup_graph(self):
        # Synthetic Data
        x = np.linspace(0, 30, 100)
        y_cpu = 40 + 30 * np.sin(x/3) + 10 * np.random.normal(size=100)
        y_ram = 30 + 20 * np.cos(x/4) + 5 * np.random.normal(size=100)
        y_disk = 50 + 10 * np.sin(x/5)

        # Styling the Grid
        styles = {'color': '#C7C1B1', 'font-size': '14px', 'font-family': 'Inter'}
        self.plot_widget.getAxis('bottom').setLabel('Time', **styles)
        self.plot_widget.getAxis('bottom').setPen('#C7C1B1')
        self.plot_widget.getAxis('bottom').setTickSpacing(5, 5)

        # Grid Lines (Horizontal)
        self.plot_widget.showGrid(x=False, y=True, alpha=0.3)

        # Plot CPU (Area)
        cpu_curve = self.plot_widget.plot(x, y_cpu, pen=None)
        cpu_fill = pg.FillBetweenItem(cpu_curve, pg.PlotDataItem(x, np.zeros(100)), brush=QColor(245, 185, 81, 178)) # 178 = 70% opacity
        self.plot_widget.addItem(cpu_fill)

        # Plot RAM (Area)
        ram_curve = self.plot_widget.plot(x, y_ram, pen=None)
        ram_fill = pg.FillBetweenItem(ram_curve, pg.PlotDataItem(x, np.zeros(100)), brush=QColor(111, 176, 133, 178))
        self.plot_widget.addItem(ram_fill)

        # Plot DISK (Dashed Line)
        pen = pg.mkPen(color=DISK_COLOR, width=3, style=Qt.DashLine)
        self.plot_widget.plot(x, y_disk, pen=pen)

        # Fix Y Axis Scale
        self.plot_widget.setYRange(0, 100)
        self.plot_widget.setXRange(30, 0) # Reverse x-axis as per design (30 on left, 0 on right)

    def handle_tab_click(self, clicked_btn):
        for btn in self.tabs:
            if btn == clicked_btn:
                btn.setStyleSheet(btn.styleSheet().replace("opacity: 0.4", "opacity: 1.0"))
            else:
                btn.setStyleSheet(btn.styleSheet().replace("opacity: 1.0", "opacity: 0.4"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InsideCliApp()
    window.show()
    sys.exit(app.exec())