import sys
from PySide6.QtWidgets import QApplication
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
    app = QApplication(sys.argv)
    window = AnomalyWindow()
    window.show()
    sys.exit(app.exec())
