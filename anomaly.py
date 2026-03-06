import sys
import psutil
from collections import deque
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPolygon, QPoint
from base_window import BaseMonitorWindow


class ClickableLabel(QLabel):
    """Custom QLabel that emits a signal when clicked"""
    clicked = Signal()
    
    def mousePressEvent(self, event):
        self.clicked.emit()


class AnomalyWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="ANOMALY")
        self.setWindowTitle("Anomaly - Critique CLI")
        
        # Initialize data storage for plots (max 30 data points)
        self.cpu_data = deque(maxlen=30)
        self.ram_data = deque(maxlen=30)
        self.disk_data = deque(maxlen=30)
        
        # Setup data collection timer
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.collect_usage_data)
        self.data_timer.start(1000)  # Collect data every 1 second
        
        # Setup clickable buttons after layout is initialized
        self.after_layout_setup()
    
    def after_layout_setup(self):
        """Setup clickable tab buttons after initial layout"""
        # Find the tab button elements and make them clickable
        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                old_label = elem["label"]
                
                # Create new clickable label
                clickable_label = ClickableLabel(elem["text"], self)
                clickable_label.setFont(old_label.font())
                clickable_label.setStyleSheet(old_label.styleSheet())
                clickable_label.move(old_label.pos())
                clickable_label.adjustSize()
                clickable_label.show()
                
                # Update element with new clickable label
                old_label.hide()
                elem["label"] = clickable_label
                
                # Connect click signals
                if elem["text"] == "SYSTEM USAGE":
                    clickable_label.clicked.connect(lambda: self.switch_tab("SYSTEM USAGE"))
                elif elem["text"] == "SCATTER PLOT":
                    clickable_label.clicked.connect(lambda: self.switch_tab("SCATTER PLOT"))
                elif elem["text"] == "ANOMALY":
                    clickable_label.clicked.connect(lambda: self.switch_tab("ANOMALY"))
    
    def collect_usage_data(self):
        """Collect CPU, RAM, and DISK usage data"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0)
            ram_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            self.cpu_data.append(cpu_percent)
            self.ram_data.append(ram_percent)
            self.disk_data.append(disk_percent)
            
            self.update()  # Trigger repaint
        except Exception as e:
            print(f"Error collecting usage data: {e}")
    
    def switch_tab(self, tab_name):
        """Switch to a different tab and update UI"""
        if self.active_tab == tab_name:
            return
            
        self.active_tab = tab_name
        
        # Update opacity of all tab buttons
        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                if elem["text"] == tab_name:
                    elem["opacity"] = 1.0  # Active tab
                else:
                    elem["opacity"] = 0.4  # Inactive tabs
        
        # Redraw the layout to update button appearances
        self.update_layout()
        self.update()  # Trigger repaint to show new content
    
    def draw_usage_plots(self, painter, graph_left, graph_right, graph_top, graph_bottom):
        """Draw CPU, RAM, and DISK usage plots"""
        if len(self.cpu_data) < 2:
            return  # Need at least 2 points to draw a line
        
        graph_width = graph_right - graph_left
        graph_height = graph_bottom - graph_top
        
        # Helper function to convert data value to Y position
        def value_to_y(value):
            return graph_bottom - (graph_height * (value / 100))
        
        # Helper function to convert data index to X position
        def index_to_x(index):
            # Index 0 is 30 seconds ago, latest index is now (0 seconds ago)
            x_progress = index / 29.0  # 0 to 1
            return graph_left + (graph_width * x_progress)
        
        # Draw CPU plot (filled area + line, rgb(225, 170, 30), opacity 0.6)
        points = []
        for i, value in enumerate(self.cpu_data):
            x = index_to_x(i)
            y = value_to_y(value)
            points.append((int(x), int(y)))
        
        # Create filled polygon for CPU
        polygon_points = points + [(p[0], int(graph_bottom)) for p in reversed(points)]
        if len(polygon_points) > 2:
            polygon = QPolygon([QPoint(p[0], p[1]) for p in polygon_points])
            painter.setBrush(QBrush(QColor(225, 170, 30, int(255 * 0.6))))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(polygon)
        
        # Draw CPU line on top
        pen = QPen(QColor(225, 170, 30, int(255 * 0.6)))
        pen.setWidth(2)
        painter.setPen(pen)
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        
        # Draw RAM plot (filled area + line, rgb(59, 169, 144), opacity 0.6)
        points = []
        for i, value in enumerate(self.ram_data):
            x = index_to_x(i)
            y = value_to_y(value)
            points.append((int(x), int(y)))
        
        # Create filled polygon for RAM
        polygon_points = points + [(p[0], int(graph_bottom)) for p in reversed(points)]
        if len(polygon_points) > 2:
            polygon = QPolygon([QPoint(p[0], p[1]) for p in polygon_points])
            painter.setBrush(QBrush(QColor(59, 169, 144, int(255 * 0.6))))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(polygon)
        
        # Draw RAM line on top
        pen = QPen(QColor(59, 169, 144, int(255 * 0.6)))
        pen.setWidth(2)
        painter.setPen(pen)
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        
        # Draw DISK plot (dashed line, rgb(222, 96, 58), width 2px)
        pen = QPen(QColor(222, 96, 58))
        pen.setWidth(2)
        pen.setDashPattern([5, 5])  # Dashed pattern
        painter.setPen(pen)
        
        points = []
        for i, value in enumerate(self.disk_data):
            x = index_to_x(i)
            y = value_to_y(value)
            points.append((int(x), int(y)))
        
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
    
    def paintEvent(self, event):
        """Draw the anomaly graph"""
        super().paintEvent(event)
        
        # Get window dimensions for responsive design
        width = self.width()
        height = self.height()
        
        # Calculate scale based on base dimensions
        scale = min(width / self.base_width, height / self.base_height)
        
        # Fixed margins that scale with window
        margin_left = int(50 * scale)
        margin_right = int(50 * scale)
        margin_top = int(100 * scale)
        margin_bottom = int(60 * scale)
        
        # Calculate graph dimensions to center it with maintained margins
        graph_left = margin_left
        graph_right = width - margin_right
        graph_top = margin_top
        graph_bottom = height - margin_bottom
        
        painter = QPainter(self)
        
        # Define consistent opacity for labels and lines
        label_opacity = 0.6
        line_opacity = 0.6
        
        # Draw horizontal grid lines and Y-axis labels
        y_values = [100, 75, 50, 25]
        for y_val in y_values:
            # Calculate Y position (0% at bottom, 100% at top)
            y_pos = graph_bottom - (graph_bottom - graph_top) * (y_val / 100) 
            
            # Draw horizontal line with consistent opacity
            pen = QPen(QColor(63, 72, 101))
            pen.setColor(QColor(63, 72, 101, int(255 * line_opacity)))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(int(graph_left)+28, int(y_pos), int(graph_right), int(y_pos))
            
            # Draw Y-axis label with consistent opacity and semi-bold font
            label_text = f"{y_val}%"
            font_size = int(10 * scale)
            font = QFont("Inter")
            font.setPointSize(font_size)
            font.setWeight(QFont.Weight.DemiBold)  # Semi-bold
            painter.setFont(font)
            painter.setPen(QColor(63, 72, 101, int(255 * label_opacity)))
            # Position label at the start of the line, left-aligned to margin
            label_x = int(graph_left)
            label_y = int(y_pos - font_size / 2)
            painter.drawText(label_x, label_y, int(40 * scale), font_size, 0, label_text)
        
        # Draw 0% line outside the loop with 100% opacity
        y_pos = graph_bottom  # 0% is at the bottom
        pen = QPen(QColor(63, 72, 101))
        pen.setColor(QColor(63, 72, 101, int(255 * 1.0)))  # 100% opacity for 0% line
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(int(graph_left), int(y_pos), int(graph_right), int(y_pos))
        
        # Draw X-axis and tick marks
        x_values = list(range(30, -5, -5))  # [30, 25, 20, 15, 10, 5] - removed 0
        tick_height = int(5 * scale)
        
        for i, x_val in enumerate(x_values):
            # Calculate X position
            x_pos = graph_left + (graph_right - graph_left) * ((30 - x_val) / 30)
            
            # Draw small upward tick mark (5px height)
            pen = QPen(QColor(63, 72, 101, 255))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(int(x_pos), int(graph_bottom), int(x_pos), int(graph_bottom - tick_height))
            
            # Draw X-axis label ABOVE the tick marks with 100% opacity, centered at vertical indicator
            label_text = str(x_val)
            font_size = int(8 * scale)
            font = QFont("Inter")
            font.setPointSize(font_size)
            painter.setFont(font)
            painter.setPen(QColor(63, 72, 101, 255))
            # Center the label at x_pos
            label_width = int(20 * scale)
            label_x = int((x_pos - label_width / 2)+6)
            # Position label above the tick marks
            label_y = int(graph_bottom - tick_height - font_size - 3 * scale)
            painter.drawText(label_x, label_y, label_width, font_size, 0, label_text)
        
        # Draw usage plots inside the graph area
        self.draw_usage_plots(painter, graph_left, graph_right, graph_top, graph_bottom)
        
        painter.end()


def open_anomaly_window():
    """Function to open Anomaly window"""
    window = AnomalyWindow()
    window.show()
    return window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnomalyWindow()
    window.show()
    sys.exit(app.exec())
