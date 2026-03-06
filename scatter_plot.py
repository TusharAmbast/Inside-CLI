import sys
from PySide6.QtWidgets import QApplication
from base_window import BaseMonitorWindow


class ScatterPlotWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="SCATTER PLOT")
        self.setWindowTitle("Scatter Plot - Critique CLI")


def open_scatter_plot_window():
    """Function to open Scatter Plot window"""
    window = ScatterPlotWindow()
    window.show()
    return window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScatterPlotWindow()
    window.show()
    sys.exit(app.exec())
