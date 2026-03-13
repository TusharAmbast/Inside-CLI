import os
import psutil
from PySide6.QtWidgets import QMainWindow, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
import sys

class BaseMonitorWindow(QMainWindow):
    def __init__(self, active_tab="SYSTEM USAGE"):
        super().__init__()
        self.setGeometry(100, 100, 700, 450)

        if sys.platform == "darwin":
            # Mac: removes title bar TEXT but keeps traffic light buttons natively
            self.setWindowFlags(
                Qt.Window |
                Qt.CustomizeWindowHint |
                Qt.WindowCloseButtonHint |
                Qt.WindowMinimizeButtonHint |
                Qt.WindowMaximizeButtonHint
            )
        else:
            # Windows: keep standard title bar behavior
            self.setWindowFlags(
                Qt.Window |
                Qt.WindowCloseButtonHint |
                Qt.WindowMinimizeButtonHint |
                Qt.WindowMaximizeButtonHint
            )       
        self.setStyleSheet("background-color: #FEF3D7; QMainWindow { background-color: #FEF3D7; }")
        
        # Base dimensions for ratio calculations
        self.base_width = 750
        self.base_height = 450
        
        if sys.platform == "darwin":
            self._title_bar_offset = 0   # Mac traffic lights don't eat into content
        else:
            self._title_bar_offset = 10  # Windows title bar is slightly taller
            
        # Track which tab is active
        self.active_tab = active_tab
        
        if sys.platform == "darwin":
            font_size = 14
            cli_font_size = 40
            self.stat_size=16
        else:
            font_size = 12
            cli_font_size = 36
            self.stat_size = 14

        # Load fonts
        script_dir = os.path.dirname(os.path.abspath(__file__))
        abril_path = os.path.join(script_dir, "Fonts/Abril Fatface/AbrilFatface-Regular.ttf")
        QFontDatabase.addApplicationFont(abril_path)
        
        inter_path = os.path.join(script_dir, "Fonts/Inter Font Family/Inter-ExtraBold.otf")
        QFontDatabase.addApplicationFont(inter_path)
        
        inter_semibold_path = os.path.join(script_dir, "Fonts/Inter Font Family/Inter-SemiBold.otf")
        QFontDatabase.addApplicationFont(inter_semibold_path)
        
        # Element definitions with base font sizes and positions
        self.elements = [
            {
                "text": "Inside Cli",
                "font_name": "Abril Fatface",
                "base_font_size": cli_font_size,
                "base_pos": (650, 22),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0,
                "label": None,
                "align_right": True,
                "right_margin": 50
            },
            {
                "text": "SYSTEM USAGE",
                "font_name": "Inter",
                "base_font_size": font_size,
                "base_pos": (39, 56),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "SYSTEM USAGE" else 0.4,
                "label": None,
                "is_extra_bold": True
            },
            {
                "text": "SCATTER PLOT",
                "font_name": "Inter",
                "base_font_size": font_size,
                "base_pos": (196, 56),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "SCATTER PLOT" else 0.4,
                "label": None,
                "is_extra_bold": True
            },
            {
                "text": "ANOMALY",
                "font_name": "Inter",
                "base_font_size": font_size,
                "base_pos": (349, 56),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "ANOMALY" else 0.4,
                "label": None,
                "is_extra_bold": True
            }
        ]
        
        # Create all labels
        for elem in self.elements:
            label = QLabel(elem["text"], self)
            elem["label"] = label
        
        # Add bottom stats
        self.add_bottom_stats()

        self._last_disk_io = psutil.disk_io_counters()
        
        # Setup timer for live stats updates
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)  # Update every 1 second
        
        self.update_layout()
    

    def add_bottom_stats(self):
        """Add CPU, RAM, and DISK stats at the bottom with live updates"""
        self.stat_labels = {}
        
        stats = [
            {
                "key": "cpu",
                "text": "CPU :             ",
                "font_name": "Inter",
                "base_font_size": self.stat_size,
                "base_pos": (50, 410),
                "color": "rgb(255, 170, 30)",
                "is_semibold": True,
                "bottom_margin": 20
            },
            {
                "key": "ram",
                "text": "RAM :             ",
                "font_name": "Inter",
                "base_font_size": self.stat_size,
                "base_pos": (180, 410),
                "color": "rgb(57, 171, 142)",
                "is_semibold": True,
                "bottom_margin": 20
            },
            {
                "key": "disk",
                "text": "DISK :              ",
                "font_name": "Inter",
                "base_font_size": self.stat_size ,
                "base_pos": (310, 410),
                "color": "rgb(222, 96, 58)",
                "is_semibold": True,
                "bottom_margin": 20
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
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Get RAM usage
            ram = psutil.virtual_memory()
            ram_percent = ram.percent
            
            # Get DISK usage
            current_io = psutil.disk_io_counters()
            bytes_delta = (current_io.read_bytes + current_io.write_bytes) - \
                        (self._last_disk_io.read_bytes + self._last_disk_io.write_bytes)
            disk_percent = min(bytes_delta / (500 * 1024 * 1024) * 100, 100)
            self._last_disk_io = current_io
            disk_percent = disk_percent
            
            # Update labels with actual values
            self.stat_labels["cpu"].setText(f"CPU: {cpu_percent:.1f}%")
            self.stat_labels["ram"].setText(f"RAM: {ram_percent:.1f}%")
            self.stat_labels["disk"].setText(f"DISK: {disk_percent:.1f}%")
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
            
            # Scale font size
            scaled_font_size = int(elem["base_font_size"] * min(scale_x, scale_y))
            font = QFont(elem["font_name"], scaled_font_size)
            label.setFont(font)
            
            # Handle right-aligned elements
            if elem.get("align_right"):
                label.adjustSize()  # Get the width of the label
                right_margin = int(elem.get("right_margin", 50) * min(scale_x, scale_y))
                scaled_x = current_width - right_margin - label.width()
                scaled_y = int(elem["base_pos"][1] * scale_y)
            else:
                # Scale position normally
                scaled_x = int(elem["base_pos"][0] * scale_x)
                scaled_y = int(elem["base_pos"][1] * scale_y)
            
            label.move(scaled_x, scaled_y)
            
            # Set color with opacity
            if "is_semibold" in elem and elem.get("is_semibold"):
                color = elem.get("color", "rgb(63, 72, 101)")
                label.setStyleSheet(f"color: {color};")
            else:
                opacity_percent = int(elem["opacity"] * 100)
                color = elem.get("color", "rgb(63, 72, 101)")
                label.setStyleSheet(f"color: rgba(63, 72, 101, {elem['opacity']});")
            
            label.adjustSize()
            label.show()
    
    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        self.update_layout()