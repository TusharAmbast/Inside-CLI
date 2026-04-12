import sys
import math
import time
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout
)
from PySide6.QtGui import QPainter, QPen, QColor, QBrush
from PySide6.QtCore import Qt, QTimer, QPoint, QTime

class AnalogClock(QWidget):
    """
    A custom PySide6 widget that renders an analog clock.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        
        # --- The PySide6 way to handle updates ---
        # 1. Create a QTimer
        self.timer = QTimer(self)
        
        # 2. Connect its 'timeout' signal to the widget's 'update' slot
        # The 'update' slot automatically triggers a 'paintEvent'
        self.timer.timeout.connect(self.update)
        
        # 3. Start the timer (1000 ms = 1 second)
        self.timer.start(1000)

    def paintEvent(self, event):
        """
        This event is called automatically whenever the widget needs to be
        repainted (e.g., on resize, when update() is called, or on first show).
        """
        
        # --- Get current time ---
        current_time = QTime.currentTime()
        hours = current_time.hour() % 12
        minutes = current_time.minute()
        seconds = current_time.second()
        
        # --- Setup Painter ---
        painter = QPainter(self)
        
        # This is crucial for smooth, non-pixelated lines (solves one of your issues)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Center point and radius
        side = min(self.width(), self.height())
        cx = self.width() // 2
        cy = self.height() // 2
        r = (side // 2) - 10  # Radius with a 10px padding
        
        # --- Draw Clock Face ---
        painter.setPen(QPen(QColor("black"), 2))
        painter.setBrush(QBrush(QColor("#F0F0F0")))
        painter.drawEllipse(QPoint(cx, cy), r, r)

        # --- Draw Hour Marks ---
        painter.setPen(QPen(QColor("black"), 3))
        for i in range(12):
            angle = math.radians(i * 30 - 90)
            x1 = cx + r * 0.85 * math.cos(angle)
            y1 = cy + r * 0.85 * math.sin(angle)
            x2 = cx + r * 0.95 * math.cos(angle)
            y2 = cy + r * 0.95 * math.sin(angle)
            painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))

        # --- Draw Hands ---
        
        # Angles in radians
        sec_angle = math.radians(seconds * 6 - 90)
        min_angle = math.radians(minutes * 6 - 90)
        hour_angle = math.radians((hours * 30) + (minutes * 0.5) - 90)

        # Second hand (Red, thin)
        x_sec = cx + r * 0.9 * math.cos(sec_angle)
        y_sec = cy + r * 0.9 * math.sin(sec_angle)
        painter.setPen(QPen(QColor("red"), 1.5))
        painter.drawLine(QPoint(cx, cy), QPoint(int(x_sec), int(y_sec)))
        
        # Minute hand (Black, medium)
        x_min = cx + r * 0.75 * math.cos(min_angle)
        y_min = cy + r * 0.75 * math.sin(min_angle)
        painter.setPen(QPen(QColor("black"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPoint(cx, cy), QPoint(int(x_min), int(y_min)))
        
        # Hour hand (Black, thick)
        x_hour = cx + r * 0.5 * math.cos(hour_angle)
        y_hour = cy + r * 0.5 * math.sin(hour_angle)
        painter.setPen(QPen(QColor("black"), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPoint(cx, cy), QPoint(int(x_hour), int(y_hour)))
        
        # --- End Painting ---
        painter.end()


# --- Main Application Setup ---
if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    
    # --- Main Window ---
    # We use a base QWidget as the main window
    window = QWidget()
    window.setWindowTitle("Analog Clock in Curved Frame (PySide6)")
    window.setGeometry(100, 100, 400, 400) # x, y, width, height
    
    # --- Styling (The "Rounded Corners" fix) ---
    # This is PySide6's "CSS" stylesheet system.
    # It applies to the 'window' QWidget itself.
    window.setStyleSheet("""
        QWidget {
            background-color: #F0F0F0;
            border: 2px solid #A0A0A0;
            border-radius: 50px; 
        }
    """)
    
    # We must set this attribute to make the background-color "clip"
    # to the border-radius, otherwise, we get a white square behind our round frame.
    window.setAttribute(Qt.WA_TranslucentBackground)
    
    # Optional: Makes the window frameless (no title bar)
    # window.setWindowFlag(Qt.FramelessWindowHint) 
    

    # --- Layout ---
    # We use a QVBoxLayout to center the clock widget inside the main window
    layout = QVBoxLayout(window)
    layout.setContentsMargins(20, 20, 20, 20) # This replaces your 'padx' and 'pady'
    
    # --- Add Clock ---
    clock_widget = AnalogClock()
    layout.addWidget(clock_widget)
    
    window.setLayout(layout)
    window.show()
    
    sys.exit(app.exec())