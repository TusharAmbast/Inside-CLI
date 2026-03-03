import sys
import platform
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from base_window import BaseMonitorWindow


class AnomalyWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="ANOMALY")
        self.setWindowTitle("Anomaly - Critique CLI")


def open_anomaly_window():
    """Function to open Anomaly window"""
    window = AnomalyWindow()
    window.show()
    return window


if __name__ == "__main__":
    # High DPI support for Windows and other platforms
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Set application-wide font scaling for better cross-platform compatibility
    if platform.system() == "Windows":
        app.setStyle('Fusion')  # Use Fusion style for better Windows DPI support
    
    window = AnomalyWindow()
    window.show()
    sys.exit(app.exec())
