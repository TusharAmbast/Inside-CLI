import sys
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use('Qt5Agg')

from base_window import BaseMonitorWindow
from scatter_plot import open_scatter_plot_window
from anomaly import open_anomaly_window


class ClickableLabel(QLabel):
    """Custom QLabel that emits a signal when clicked"""
    clicked = Signal()
    
    def mousePressEvent(self, event):
        self.clicked.emit()


class SystemUsageWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="SYSTEM USAGE")
        self.setWindowTitle("System Usage - Critique CLI")
        
        # Create and embed matplotlib figure
        self.create_matplotlib_graph()
        
        # Setup clickable buttons after layout is initialized
        self.after_layout_setup()
    
    def create_matplotlib_graph(self):
        """Create and embed a matplotlib graph with system usage data"""
        # Create figure with transparent background
        fig = Figure(figsize=(9, 4), dpi=100, facecolor='#FEF3D7', edgecolor='none')
        self.canvas = FigureCanvas(fig)
        
        # Create axis
        ax = fig.add_subplot(111)
        
        # Set axis colors and styling
        axis_color = '#1C2951'
        
        # Configure matplotlib rc params for fonts
        plt.rcParams['font.sans-serif'] = ['Helvetica', 'Arial']
        plt.rcParams['font.size'] = 8
        
        # Draw Y-axis grid lines and labels at 20%, 60%, 100%
        y_values = [20, 60, 100]
        for y_val in y_values:
            # Draw horizontal grid line with 40% opacity
            ax.axhline(y=y_val, color=axis_color, linewidth=0.8, alpha=0.4)
        
        # Set Y-axis ticks and labels
        ax.set_yticks(y_values)
        ax.set_yticklabels([f'{y}%' for y in y_values], fontsize=10, fontfamily='sans-serif')
        
        # Style Y-axis labels - 10px, 40% opacity
        for label in ax.get_yticklabels():
            label.set_color(axis_color)
            label.set_alpha(0.4)
            label.set_fontsize(10)
        
        # Remove Y-axis tick marks
        ax.tick_params(axis='y', length=0, width=0)
        
        # Set X-axis (time axis from 30 to 0, right to left)
        x_values = list(range(0, 31, 5))  # [0, 5, 10, 15, 20, 25, 30]
        ax.set_xlim(30, 0)  # Reverse to make 30 on left, 0 on right
        ax.set_xticks(x_values)
        ax.set_xticklabels([str(x) for x in x_values], fontsize=8, fontfamily='sans-serif')
        
        # Style X-axis labels - 8px, 100% opacity
        for label in ax.get_xticklabels():
            label.set_color(axis_color)
            label.set_alpha(1.0)
            label.set_fontsize(8)
        
        # Configure X-axis tick marks - 5px upward lines
        ax.tick_params(axis='x', direction='out', length=5, width=0.8, colors=axis_color)
        
        # Draw X-axis baseline at y=0
        ax.axhline(y=0, color=axis_color, linewidth=0.9, alpha=1.0)
        
        # Set Y-axis limits
        ax.set_ylim(0, 120)
        
        # Add some sample data (can be replaced with real CPU usage data)
        x_data = list(range(30, -1, -1))  # 30 data points
        y_data = [50 + i % 20 for i in range(31)]  # Sample data
        ax.plot(x_data, y_data, color='#3F4865', linewidth=1.5, alpha=0.8)
        
        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        # Style remaining spines
        ax.spines['bottom'].set_color(axis_color)
        ax.spines['bottom'].set_linewidth(0.9)
        ax.spines['left'].set_color(axis_color)
        
        # Set background
        ax.set_facecolor('#FEF3D7')
        
        # Tight layout
        fig.tight_layout()
        
        # Embed canvas in window
        self.canvas.setGeometry(50, 150, 600, 230)
        self.canvas.setParent(self)
        self.canvas.show()
    
    def resizeEvent(self, event):
        """Handle window resize - also resize matplotlib canvas"""
        super().resizeEvent(event)
        
        # Resize matplotlib canvas proportionally
        scale_x = self.width() / self.base_width
        scale_y = self.height() / self.base_height
        
        canvas_x = int(50 * scale_x)
        canvas_y = int(150 * scale_y)
        canvas_w = int(600 * scale_x)
        canvas_h = int(230 * scale_y)
        
        self.canvas.setGeometry(canvas_x, canvas_y, canvas_w, canvas_h)
    
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

app = QApplication(sys.argv)
root = SystemUsageWindow()
root.show()
sys.exit(app.exec())