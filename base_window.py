import os
import sys
import psutil
from PySide6.QtWidgets import QMainWindow, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase


class BaseMonitorWindow(QMainWindow):
    def __init__(self, active_tab="SYSTEM USAGE"):
        super().__init__()

        
        self.setGeometry(100, 100, 900, 560)
        self.setMinimumSize(750, 450)  # Prevent layout collapse when resizing small

        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        self.setStyleSheet("background-color: #FEF3D7; QMainWindow { background-color: #FEF3D7; }")

        
        self.base_width = 900
        self.base_height = 560

        self.active_tab = active_tab

        # Load fonts
        script_dir = os.path.dirname(os.path.abspath(__file__))
        abril_path = os.path.join(script_dir, "Fonts/Abril Fatface/AbrilFatface-Regular.ttf")
        QFontDatabase.addApplicationFont(abril_path)

        inter_path = os.path.join(script_dir, "Fonts/Inter Font Family/Inter-ExtraBold.otf")
        QFontDatabase.addApplicationFont(inter_path)

        inter_semibold_path = os.path.join(script_dir, "Fonts/Inter Font Family/Inter-SemiBold.otf")
        QFontDatabase.addApplicationFont(inter_semibold_path)

        self.elements = [
            {
                "text": "Inside Cli",
                "font_name": "Abril Fatface",
                "base_font_size": 40,
                "base_pos": (650, 4),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0,
                "label": None,
                "align_right": True,
                "right_margin": 50
            },
            {
                "text": "SYSTEM USAGE",
                "font_name": "Inter",
                "base_font_size": 14,
                "base_pos": (39, 28),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "SYSTEM USAGE" else 0.4,
                "label": None,
                "is_extra_bold": True
            },
            {
                "text": "SCATTER PLOT",
                "font_name": "Inter",
                "base_font_size": 14,
                "base_pos": (210, 28),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "SCATTER PLOT" else 0.4,
                "label": None,
                "is_extra_bold": True
            },
            {
                "text": "ANOMALY",
                "font_name": "Inter",
                "base_font_size": 14,
                "base_pos": (370, 28),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "ANOMALY" else 0.4,
                "label": None,
                "is_extra_bold": True
            }
        ]

        for elem in self.elements:
            label = QLabel(elem["text"], self)
            elem["label"] = label

        self.add_bottom_stats()

        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

        self.update_layout()

    def add_bottom_stats(self):
        """Add CPU, RAM, and DISK stats at the bottom with live updates"""
        self.stat_labels = {}

        
        stats = [
            {
                "key": "cpu",
                "text": "CPU: --.--%",
                "font_name": "Inter",
                "base_font_size": 16,
                "base_pos": (50, 510),
                "color": "rgb(255, 170, 30)",
                "is_semibold": True,
            },
            {
                "key": "ram",
                "text": "RAM: --.--%",
                "font_name": "Inter",
                "base_font_size": 16,
                "base_pos": (230, 510),
                "color": "rgb(57, 171, 142)",
                "is_semibold": True,
            },
            {
                "key": "disk",
                "text": "DISK: --.--%",
                "font_name": "Inter",
                "base_font_size": 16,
                "base_pos": (430, 510),
                "color": "rgb(222, 96, 58)",
                "is_semibold": True,
            }
        ]

        for stat in stats:
            self.elements.append({
                "text": stat["text"],
                "font_name": stat["font_name"],
                "base_font_size": stat["base_font_size"],
                "base_pos": stat["base_pos"],
                "color": stat["color"],
                "is_semibold": True,
                "opacity": 1.0,
                "label": None,
                "is_dynamic": True
            })
            label = QLabel(stat["text"], self)
            self.elements[-1]["label"] = label
            self.stat_labels[stat["key"]] = label

    def update_stats(self):
        """Update live CPU, RAM, and DISK stats"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent

            self.stat_labels["cpu"].setText(f"CPU: {cpu_percent:.1f}%")
            self.stat_labels["ram"].setText(f"RAM: {ram_percent:.1f}%")
            self.stat_labels["disk"].setText(f"DISK: {disk_percent:.1f}%")

           
            self.update_layout()
        except Exception as e:
            print(f"Error updating stats: {e}")

    def update_layout(self):
        """Update positions and font sizes based on current window dimensions"""
        current_width = self.width()
        current_height = self.height()

        scale_x = current_width / self.base_width
        scale_y = current_height / self.base_height

        for elem in self.elements:
            label = elem["label"]

            # Scale font size with a minimum so it never hits 0
            scaled_font_size = max(8, int(elem["base_font_size"] * min(scale_x, scale_y)))
            font = QFont(elem["font_name"], scaled_font_size)
            label.setFont(font)

            
            if elem.get("is_semibold"):
                color = elem.get("color", "rgb(63, 72, 101)")
                label.setStyleSheet(f"color: {color};")
            else:
                label.setStyleSheet(f"color: rgba(63, 72, 101, {elem['opacity']});")

            
            label.adjustSize()

            # Now position is calculated with accurate label dimensions
            if elem.get("align_right"):
                right_margin = int(elem.get("right_margin", 50) * min(scale_x, scale_y))
                scaled_x = current_width - right_margin - label.width()
                scaled_y = int(elem["base_pos"][1] * scale_y)
            else:
                scaled_x = int(elem["base_pos"][0] * scale_x)
                scaled_y = int(elem["base_pos"][1] * scale_y)

            label.move(scaled_x, scaled_y)
            label.show()

    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        self.update_layout()