import sys
import platform
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use('Qt5Agg')

from base_window import BaseMonitorWindow
from scatter_plot import open_scatter_plot_window
from anomaly import open_anomaly_window

# Enable high DPI support for Windows and other platforms
if platform.system() == "Windows":
    # Enable high DPI scaling on Windows
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        pass

# Set matplotlib DPI to be responsive
matplotlib.rcParams['figure.dpi'] = 100
matplotlib.rcParams['savefig.dpi'] = 100
plt.rcParams['figure.dpi'] = 100


class ClickableLabel(QLabel):
    """Custom QLabel that emits a signal when clicked"""
    clicked = Signal()
    
    def mousePressEvent(self, event):
        self.clicked.emit()


class SystemUsageWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="SYSTEM USAGE")
        self.setWindowTitle("System Usage - Critique CLI")
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
                if elem["text"] == "SCATTER PLOT":
                    clickable_label.clicked.connect(lambda: self.switch_tab("SCATTER PLOT"))
                elif elem["text"] == "ANOMALY":
                    clickable_label.clicked.connect(lambda: self.switch_tab("ANOMALY"))
                elif elem["text"] == "SYSTEM USAGE":
                    clickable_label.clicked.connect(lambda: self.switch_tab("SYSTEM USAGE"))
    
    def switch_tab(self, tab_name):
        """Switch to a different tab and update UI"""
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
    
    def paintEvent(self, event):
        """Draw the system usage graph"""
        super().paintEvent(event)
        
        # Get window dimensions for responsive design
        width = self.width()
        height = self.height()
        
        # Calculate scale based on base dimensions
        scale = min(width / self.base_width, height / self.base_height)
        
        # Graph dimensions (base values, will be scaled)
        graph_left = int(50 * scale)
        graph_right = int(650 * scale)
        graph_top = int(150 * scale)
        graph_bottom = int(380 * scale)
        
        painter = QPainter(self)
        
        # Draw horizontal grid lines and Y-axis labels
        y_values = [100, 75, 50, 25, 0]
        for y_val in y_values:
            # Calculate Y position (0% at bottom, 100% at top)
            y_pos = graph_bottom - (graph_bottom - graph_top) * (y_val / 100)
            
            # Draw horizontal line - 40% opacity for all except 0% which is 100%
            pen = QPen(QColor(63, 72, 101))
            if y_val == 0:
                pen.setColor(QColor(63, 72, 101, int(255 * 1.0)))  # 100% opacity for 0% line
            else:
                pen.setColor(QColor(63, 72, 101, int(255 * 0.4)))  # 40% opacity for others
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(int(graph_left), int(y_pos), int(graph_right), int(y_pos))
            
            # Draw Y-axis label with 40% opacity at the START of the line (skip 0%)
            if y_val != 0:  # Don't draw label for 0%
                label_text = f"{y_val}%"
                font_size = int(10 * scale)
                font = QFont("Inter")
                font.setPointSize(font_size)
                painter.setFont(font)
                painter.setPen(QColor(192, 192, 192, int(255 * 0.4)))
                # Position label at the start of the line, inside margin
                label_x = int(graph_left + 5 * scale)
                label_y = int(y_pos - font_size / 2)
                painter.drawText(label_x, label_y, int(40 * scale), font_size, 0, label_text)
        
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
        
        painter.end()


# High DPI support for Windows and other platforms
if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Set application-wide font scaling for better cross-platform compatibility
    if platform.system() == "Windows":
        app.setStyle('Fusion')  # Use Fusion style for better Windows DPI support

    root = SystemUsageWindow()
    root.show()
    sys.exit(app.exec())
