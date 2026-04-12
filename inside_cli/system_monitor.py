import sys
import os
import psutil
import pandas as pd
import numpy as np
import time
import platform 
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.interpolate import make_interp_spline
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.ticker import FormatStrFormatter
import inside_cli.ai_engine as ai_engine  # Import our new file
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, QTimer, QThread, QObject, Signal, Slot
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QMessageBox 

# --- Force Matplotlib Backend ---
# This is the correct backend for PySide6/PyQt
os.environ['MPLBACKEND'] = 'QtAgg'
import matplotlib
matplotlib.use('QtAgg', force=True)

# --- Matplotlib Style (Your settings) ---
# We set the facecolor to transparent so it shows the
# rounded-corner widget background
plt.style.use('dark_background')
plt.rcParams.update({
    'figure.dpi': 100,
    'savefig.dpi': 100,
    'figure.figsize': (8, 4),
    'axes.edgecolor': 'black',
    'axes.linewidth': 2,
    'lines.linewidth': 2.5,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    
    # Key change for PySide6 integration:
    'figure.facecolor': 'none', 
    'axes.facecolor': 'none', 
    'savefig.facecolor': 'none',
})

from PySide6.QtWidgets import QTextEdit, QScrollArea

class ExplanationPanel(QFrame):
    """A side panel for displaying AI explanations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #E8E8E8;
                border-radius: 10px;
                border: 2px solid #B0B0B0;
            }
        """)
        self.setFixedWidth(280)  # Fixed width for side panel
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Title
        self.title_label = QLabel("AI Process Analysis")
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.title_label)
        
        # Process name label
        self.process_label = QLabel("Select a process")
        self.process_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.process_label.setStyleSheet("color: #333333;")
        self.process_label.setWordWrap(True)
        layout.addWidget(self.process_label)
        
        # Status label (for "Loading..." etc)
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Arial", 9))
        self.status_label.setStyleSheet("color: #666666; font-style: italic;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        #Explanation text area (scrollable)
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                padding: 10px;
                color: #000000;
                font-size: 10pt;
            }
        """)
        self.text_area.setText("Click on a process in the scatter plot to see AI analysis...")
        layout.addWidget(self.text_area)
        
        # Initially hidden
        self.hide()
    
    def show_loading(self, process_name):
        """Show loading state"""
        self.process_label.setText(f"Process: {process_name}")
        self.status_label.setText("⏳ Analyzing...")
        self.text_area.setText("Loading AI explanation...\n\nThis may take a few seconds.")
        self.show()  # Make panel visible
    
    def show_explanation(self, process_name, explanation):
        """Show the AI explanation"""
        self.process_label.setText(f"Process: {process_name}")
        self.status_label.setText("✓ Analysis complete")
        self.text_area.setText(explanation)
        self.show()  # Ensure panel is visible
    
    def show_error(self, error_message):
        """Show error state"""
        self.status_label.setText("❌ Error")
        self.text_area.setText(f"Could not generate explanation:\n\n{error_message}")
        self.show()
# ==============================================================================
# STEP 1: THE DATA WORKER (MOVED TO A QTHREAD)
# ==============================================================================

class SystemDataWorker(QObject):
    """
    Runs in a separate thread to collect system data without
    blocking the main GUI.
    """
    # Define signals that will carry the new data
    dataUpdated = Signal(dict, pd.DataFrame)
    processDataUpdated = Signal(pd.DataFrame)
    systemInfoUpdated = Signal(dict)
    anomaliesFound = Signal(list)
    networkInfoUpdated = Signal(dict)
    killProcess = Signal(int)
    
    def __init__(self, max_history=60):
        super().__init__()
        self.data = pd.DataFrame(columns=['timestamp', 'cpu', 'ram', 'disk'])
        self.max_history = max_history
        self.monitoring = False

    # --- Store network baseline ---
        self.last_net_io = psutil.net_io_counters()
        
        # --- Get system info once ---
        self.system_info = {
            'hostname': platform.node(),
            'os': f"{platform.system()} {platform.release()}",
            'kernel': platform.version().split(' ')[0] # Gets kernel version
        }

        self.TOP_X = 5
        self.top_processes = set()

        # CPU history for sustained usage check
        self.cpu_history = {}   # pid -> [(timestamp, cpu), ...]

        # Sustained CPU window (seconds)
        self.SUSTAIN_TIME = 10

        self.expected_cpu = {
            'browser': 30,
            'video': 80,
            'screensaver': 5,
            'default': 20
        }
    
    def get_expected_cpu(self, process_name):
        name = process_name.lower()
        if 'chrome' in name or 'firefox' in name:
            return self.expected_cpu['browser']
        if 'ffmpeg' in name or 'encoder' in name:
            return self.expected_cpu['video']
        if 'screen' in name:
            return self.expected_cpu['screensaver']
        return self.expected_cpu['default']

    def start_monitoring(self):
        """Starts the monitoring loop."""
        self.monitoring = True
        
        # --- Timer to control update frequency ---
        # We use a QTimer *inside* the thread for stable timing
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_monitor_cycle)
        self.timer.start(500) # Update every 500ms

    def stop_monitoring(self):
        """Stops the monitoring loop."""
        self.monitoring = False
        if hasattr(self, 'timer'):
            self.timer.stop()

    def run_monitor_cycle(self):
        """
        This is the main loop of the worker. It collects data
        and emits signals.
        """
        if not self.monitoring:
            return
            
        try:
            # 1. Collect system metrics
            metrics = self.collect_metrics()
            timestamp = time.time()
            new_data = {'timestamp': timestamp, **metrics}

            if self.data.empty:
                self.data = pd.DataFrame([new_data])
            else:
                new_row = pd.DataFrame([new_data])
                self.data = pd.concat([self.data, new_row], ignore_index=True)
                
            if len(self.data) > self.max_history:
                self.data = self.data.iloc[-self.max_history:]
            
            # EMIT SIGNAL 1
            self.dataUpdated.emit(metrics, self.data.copy())

            # 2. Collect process data
            process_df = self.get_process_data()

            if not process_df.empty:
                top_df = process_df.sort_values(
                    by='cpu_percent', ascending=False
                ).head(self.TOP_X)
                self.top_processes = set(top_df['pid'].tolist())
            else:
                top_df = pd.DataFrame()
                self.top_processes = set()
            
            # EMIT SIGNAL 2
            self.processDataUpdated.emit(process_df)

            current_time = time.time()
            sustained_high = set()

            for _, row in top_df.iterrows():
                pid = row['pid']
                cpu = row['cpu_percent']
                expected = self.get_expected_cpu(row['name'])

                if pid not in self.cpu_history:
                    self.cpu_history[pid] = []

                self.cpu_history[pid].append((current_time, cpu))

                # Keep only last 10 seconds
                self.cpu_history[pid] = [
                    (t, c) for t, c in self.cpu_history[pid]
                    if current_time - t <= self.SUSTAIN_TIME
                ]

                # Check sustained high CPU
                if (
                    len(self.cpu_history[pid]) > 0 and
                    all(c > expected for _, c in self.cpu_history[pid])
                ):
                    sustained_high.add(pid)         
            
            anomalies = []

            for _, row in top_df.iterrows():
                pid = row['pid']

                # ---------------- Condition flags ----------------

                # Condition 1: CPU higher than expected
                expected = self.get_expected_cpu(row['name'])
                cpu_abnormal = row['cpu_percent'] > expected

                # Condition 2: Sustained high CPU
                sustained = pid in sustained_high

                # Condition 3: Uptime abnormal vs parent
                uptime_abnormal = False
                if row['parent_create_time'] is not None:
                    proc_uptime = current_time - row['create_time']
                    parent_uptime = current_time - row['parent_create_time']
                    if proc_uptime > parent_uptime * 1.5:
                        uptime_abnormal = True

                # ---------------- K-out-of-N decision ----------------

                matched_conditions = sum([
                    cpu_abnormal,
                    sustained,
                    uptime_abnormal
                ])

                # Flag anomaly if ANY 2 conditions match
                if matched_conditions >= 2:
                    anomalies.append({
                        'pid': row['pid'],        # 👈 REQUIRED
                        'name': row['name'],
                        'desc': (
                            f"Anomaly detected: "
                            f"CPU abnormal={cpu_abnormal}, "
                            f"Sustained CPU={sustained}, "
                            f"Uptime abnormal={uptime_abnormal}"
                        ),
                        'level': 'safe' if matched_conditions == 2 else 'critical'
                    })

            # --- 3. ADD NETWORK DATA COLLECTION ---
            new_net_io = psutil.net_io_counters()
            network_stats = {
                'sent_rate': new_net_io.bytes_sent - self.last_net_io.bytes_sent,
                'recv_rate': new_net_io.bytes_recv - self.last_net_io.bytes_recv
            }
            self.last_net_io = new_net_io # Update baseline for next cycle

            # EMIT SIGNAL 3 (New)
            self.networkInfoUpdated.emit(network_stats)

            # --- 4. CHECK FOR ANOMALIES (PLACEHOLDER) ---
            self.anomaliesFound.emit(anomalies)

        except Exception as e:
            print(f"Monitoring error: {e}")

    # --- Your data collection methods, unchanged ---
    def collect_metrics(self):
        """Collect real-time system metrics."""
        cpu = psutil.cpu_percent(interval=None) # No interval for non-blocking
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        return {'cpu': cpu, 'ram': ram, 'disk': disk}
    
    def get_process_data(self):
        """Collect CPU usage and lifetime details of all processes."""
        processes = []

        for proc in psutil.process_iter([
            'pid', 'name', 'cpu_percent', 'username', 'ppid', 'create_time'
        ]):
            try:
                info = proc.info

                # Get parent create time safely
                parent_create_time = None
                try:
                    parent = psutil.Process(info['ppid'])
                    parent_create_time = parent.create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                processes.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'cpu_percent': info['cpu_percent'],
                    'username': info['username'],
                    'ppid': info['ppid'],
                    'create_time': info['create_time'],
                    'parent_create_time': parent_create_time
                })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return pd.DataFrame(processes)
    
    @Slot(int)
    def terminate_process(self, pid):
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            print(f"Terminated process {pid}")
        except psutil.NoSuchProcess:
            print(f"Process {pid} already exited")
        except psutil.AccessDenied:
            print(f"Access denied to terminate {pid}")
        except Exception as e:
            print(f"Failed to terminate {pid}: {e}")

class AIWorker(QThread):
    """Runs the AI explanation in the background"""
    finished = Signal(str)  # Signal to send text back to GUI

    def __init__(self, pid, name):
        super().__init__()
        self.pid = pid
        self.name = name

    def run(self):
        # This runs in a separate thread
        explanation = ai_engine.explain_process_by_pid(self.pid, self.name)
        self.finished.emit(explanation)



# ==============================================================================
# STEP 2: THE PYSIXDE6 GUI SHELL
# ==============================================================================

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.display_time_window = 30 # From your original code
        
        # --- Fonts ---
        self.nav_font_bold = QFont("Arial", 15, QFont.Weight.Bold)
        self.nav_font_normal = QFont("Arial", 15)
        self.legend_font = QFont("Arial", 16)
        
        self.init_ui()
        self.init_worker_thread()
        
        # Set initial view
        self.switch_view(0)

        self.ai_label = QLabel("Click a process in the Scatter Plot to see AI explanation...")
        self.ai_label.setWordWrap(True) # Allow text to go to next line
        self.ai_label.setStyleSheet("color: #00ff00; font-size: 14px; padding: 10px; border: 1px solid #333;")

    def init_ui(self):
        """Create the main GUI layout."""
        
        self.setWindowTitle("System Monitor (PySide6)")
        self.setGeometry(100, 100, 700, 450)
        self.setMinimumSize(700, 450)
        
        # Set main window background color
        self.setStyleSheet("background-color: #212121;")

        # --- Main Central Widget & Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Custom Navigation Header ---
        nav_frame = QFrame(self)
        nav_frame.setFixedHeight(60)
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(25, 15, 25, 15)
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.usage_button = QPushButton("SYSTEM USAGE")
        self.scatter_button = QPushButton("SCATTER PLOT")
        self.anomaly_button = QPushButton("ANOMALY")

        # Connect buttons to the switch_view slot
        self.usage_button.clicked.connect(lambda: self.switch_view(0))
        self.scatter_button.clicked.connect(lambda: self.switch_view(1))
        self.anomaly_button.clicked.connect(lambda: self.switch_view(2))

        # Apply stylesheet for buttons (replaces configure)
        button_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0;
                margin-right: 20px;
            }
        """
        self.usage_button.setStyleSheet(button_style)
        self.scatter_button.setStyleSheet(button_style)
        self.anomaly_button.setStyleSheet(button_style)

        nav_layout.addWidget(self.usage_button)
        nav_layout.addWidget(self.scatter_button)
        nav_layout.addWidget(self.anomaly_button)
        
        main_layout.addWidget(nav_frame)

        # --- Main Content Area (QStackedWidget) ---
        # This is the proper way to switch between views
        self.plot_stack = QStackedWidget()
        main_layout.addWidget(self.plot_stack)
        
        # --- Plot 1: Line Plot ---
        self.line_plot_widget = QWidget()
        line_layout = QVBoxLayout(self.line_plot_widget)
        line_layout.setContentsMargins(20, 5, 20, 5) # padx, pady
        
        # This is the rounded-corner frame (the "why")
        self.line_plot_frame = QFrame()
        self.line_plot_frame.setStyleSheet("background-color: #F0F0F0; border-radius: 20px;")
        line_layout.addWidget(self.line_plot_frame)
        
        plot_layout = QVBoxLayout(self.line_plot_frame)
        plot_layout.setContentsMargins(15, 15, 15, 15)
        
        self.line_fig, self.line_ax = plt.subplots()
        self.line_canvas = FigureCanvasQTAgg(self.line_fig)
        plot_layout.addWidget(self.line_canvas)
        
        self.plot_stack.addWidget(self.line_plot_widget)
        
        # --- Plot 2: Scatter Plot ---
        self.scatter_plot_widget = QWidget()
        scatter_layout = QVBoxLayout(self.scatter_plot_widget)
        scatter_layout.setContentsMargins(20, 5, 20, 5)

        # Create a horizontal layout to hold scatter plot + side panel
        scatter_main_layout = QHBoxLayout()
        scatter_layout.addLayout(scatter_main_layout)

        # Left side: Scatter plot frame (takes most space)
        self.scatter_plot_frame = QFrame()
        self.scatter_plot_frame.setStyleSheet("background-color: #F0F0F0; border-radius: 20px;")
        scatter_main_layout.addWidget(self.scatter_plot_frame, 3)  # 3/4 of the space

        scatter_plot_layout = QVBoxLayout(self.scatter_plot_frame)
        scatter_plot_layout.setContentsMargins(15, 15, 15, 15)

        self.scatter_fig, self.scatter_ax = plt.subplots()

        self.scatter_fig.patch.set_facecolor('#F0F0F0')  # Match the QFrame background
        self.scatter_ax.patch.set_facecolor('#F0F0F0')   # Match the QFrame background
        # This makes the background OPAQUE so clicks register
        self.scatter_canvas = FigureCanvasQTAgg(self.scatter_fig)
        scatter_plot_layout.addWidget(self.scatter_canvas)
        
        self.pick_cid = self.scatter_canvas.mpl_connect('pick_event', self.on_scatter_pick)

        def test_click(event):
            print(f"🖱️ CANVAS CLICKED! x={event.xdata}, y={event.ydata}")

        def test_pick(event):
            print(f"🎯 PICK EVENT FIRED! ind={event.ind}")

        self.scatter_canvas.mpl_connect('button_press_event', test_click)
        self.scatter_canvas.mpl_connect('pick_event', test_pick)
        # Right side: Explanation panel (1/4 of space)
        self.explanation_panel = ExplanationPanel()
        scatter_main_layout.addWidget(self.explanation_panel, 1)
        self.plot_stack.addWidget(self.scatter_plot_widget)

        # --- Page 3: Anomaly List ---
        self.anomaly_page_widget = QWidget()
        anomaly_page_layout = QVBoxLayout(self.anomaly_page_widget)
        anomaly_page_layout.setContentsMargins(20, 5, 20, 5)

        # This is the main gray rounded frame
        self.anomaly_frame = QFrame()
        self.anomaly_frame.setStyleSheet("background-color: #F0F0F0; border-radius: 20px;")
        anomaly_page_layout.addWidget(self.anomaly_frame)

        # We will put all anomaly "cards" inside this layout
        self.anomaly_card_container_layout = QVBoxLayout(self.anomaly_frame)
        self.anomaly_card_container_layout.setContentsMargins(15, 15, 15, 15)
        self.anomaly_card_container_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # New cards stack from top

        # Add a placeholder label for now
        self.no_anomalies_label = QLabel("No anomalies detected.")
        self.no_anomalies_label.setFont(QFont("Arial", 12))
        self.no_anomalies_label.setStyleSheet("color: #888888;")
        self.no_anomalies_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anomaly_card_container_layout.addWidget(self.no_anomalies_label)

        # Add this new page to the stack
        self.plot_stack.addWidget(self.anomaly_page_widget)
        
        # --- Footer Area (SysInfo, Legend, Network) ---
        footer_frame = QFrame(self)
        footer_frame.setFixedHeight(80) # Made it a bit taller
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(25, 10, 25, 10) # Added horizontal margin

        # --- 1. System Info Panel (Left) ---
        sys_info_frame = QFrame()
        sys_info_layout = QVBoxLayout(sys_info_frame)
        sys_info_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        sys_title = QLabel("SYSTEM INFORMATION")
        sys_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sys_title.setStyleSheet("color: #FFFFFF; padding-bottom: 5px;")
        
        self.hostname_label = QLabel("Hostname: ...")
        self.os_label = QLabel("OS: ...")
        self.kernel_label = QLabel("Kernel: ...")
        
        sys_info_layout.addWidget(sys_title)
        for label in [self.hostname_label, self.os_label, self.kernel_label]:
            label.setFont(QFont("Arial", 9))
            label.setStyleSheet("color: #A0A0A0;")
            sys_info_layout.addWidget(label)

        # --- 2. Legend (Center) ---
        # This is your existing QStackedWidget for the legends
        self.line_legend_stack = QStackedWidget()
        self.line_legend_stack.setStyleSheet("background-color: transparent;")

        # --- Line Plot Legend (Page 1 of stack) ---
        self.line_legend_frame = QFrame()
        line_legend_layout = QHBoxLayout(self.line_legend_frame)
        line_legend_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.cpu_label_line = self.create_legend_item(line_legend_layout, "#E53935", "CPU : 0%")
        self.ram_label_line = self.create_legend_item(line_legend_layout, "#43A047", "RAM : 0%")
        self.disk_label_line = self.create_legend_item(line_legend_layout, "#1E88E5", "DISK : 0%")
        self.line_legend_stack.addWidget(self.line_legend_frame)

        # --- Scatter Plot Legend (Page 2 of stack) ---
        self.scatter_legend_frame = QFrame()
        scatter_legend_layout = QHBoxLayout(self.scatter_legend_frame)
        scatter_legend_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.cpu_label_scatter = QLabel("CPU : 0%")
        self.ram_label_scatter = QLabel("RAM : 0%")
        self.disk_label_scatter = QLabel("DISK : 0%")
        
        for label in [self.cpu_label_scatter, self.ram_label_scatter, self.disk_label_scatter]:
            label.setFont(self.legend_font)
            label.setStyleSheet("color: #FFFFFF; padding: 0 20px;")
            scatter_legend_layout.addWidget(label)
        self.line_legend_stack.addWidget(self.scatter_legend_frame)
        
        # --- Anomaly Legend (Page 3 of stack) ---
        self.anomaly_legend_frame = QFrame()
        self.line_legend_stack.addWidget(self.anomaly_legend_frame)
        
        # --- 3. Network Panel (Right) ---
        net_info_frame = QFrame()
        net_info_layout = QVBoxLayout(net_info_frame)
        net_info_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        net_title = QLabel("NETWORK (per 0.5s)")
        net_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        net_title.setStyleSheet("color: #FFFFFF; padding-bottom: 5px;")
        
        self.sent_label = QLabel("Sent: ...")
        self.recv_label = QLabel("Recv: ...")
        
        net_info_layout.addWidget(net_title)
        for label in [self.sent_label, self.recv_label]:
            label.setFont(QFont("Arial", 9))
            label.setStyleSheet("color: #A0A0A0;")
            net_info_layout.addWidget(label)

        # --- Add all three panels to the footer layout ---
        footer_layout.addWidget(sys_info_frame, 1, Qt.AlignmentFlag.AlignLeft)
        footer_layout.addWidget(self.line_legend_stack, 2, Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(net_info_frame, 1, Qt.AlignmentFlag.AlignRight)

        main_layout.addWidget(footer_frame)

    def create_legend_item(self, layout, color, text):
        """Helper to create the dotted legend items."""
        item_frame = QFrame()
        item_layout = QHBoxLayout(item_frame)
        item_layout.setContentsMargins(0, 0, 0, 0)
        
        color_dot = QFrame()
        color_dot.setFixedSize(15, 15)
        color_dot.setStyleSheet(f"background-color: {color}; border-radius: 7px;")
        
        label = QLabel(text)
        label.setFont(self.legend_font)
        label.setStyleSheet("color: #FFFFFF; padding-left: 10px; padding-right: 20px;")
        
        item_layout.addWidget(color_dot)
        item_layout.addWidget(label)
        layout.addWidget(item_frame)
        return label

    def init_worker_thread(self):
        """Create, connect, and start the background data thread."""
        
        # 1. Create the worker and thread
        self.worker = SystemDataWorker()
        self.thread = QThread()
        
        # 2. Move worker to thread
        self.worker.moveToThread(self.thread)
        
        # ======================================================================
        # STEP 3: CONNECT SIGNALS AND SLOTS
        # ======================================================================
        
        # Connect worker signals to GUI slots
        self.worker.dataUpdated.connect(self.update_line_plot)
        self.worker.processDataUpdated.connect(self.update_scatter_plot)
        self.worker.systemInfoUpdated.connect(self.update_system_info)
        self.worker.networkInfoUpdated.connect(self.update_network_info)
        self.worker.anomaliesFound.connect(self.update_anomaly_tab)
        self.worker.killProcess.connect(self.worker.terminate_process)

        # Connect thread started signal to worker's start method
        self.thread.started.connect(self.worker.start_monitoring)
        
        # Connect window's close event to stop the thread
        self.destroyed.connect(self.stop_worker)
        
        # 3. Start the thread
        self.thread.start()

    def stop_worker(self):
        """Safely stop the worker and thread."""
        print("Stopping worker...")
        self.worker.stop_monitoring()
        self.thread.quit()
        self.thread.wait() # Wait for thread to finish
        print("Worker stopped.")
        
    def closeEvent(self, event):
        """Override close event to stop the thread."""
        self.stop_worker()
        event.accept()
        
    def format_bytes(self, size):
        """Helper to format byte rates into readable strings."""
        if size < 1024:
            return f"{size} B/s"
        elif size < 1024**2:
            return f"{size/1024:.1f} KB/s"
        else:
            return f"{size/1024**2:.1f} MB/s"
        
    # ==========================================================================
    # --- GUI UPDATE SLOTS (These receive the data) ---
    # ==========================================================================
    
    @Slot(dict)
    def update_system_info(self, info):
        """Receives system info (hostname, os, etc.) ONCE."""
        self.hostname_label.setText(f"Hostname: {info['hostname']}")
        self.os_label.setText(f"OS: {info['os']}")
        self.kernel_label.setText(f"Kernel: {info['kernel']}")

    @Slot(dict)
    def update_network_info(self, net_stats):
        """Receives network data every cycle."""
        # We multiply by 2 because our interval is 500ms (0.5s)
        sent_per_sec = net_stats['sent_rate'] * 2
        recv_per_sec = net_stats['recv_rate'] * 2
        
        self.sent_label.setText(f"Sent: {self.format_bytes(sent_per_sec)}")
        self.recv_label.setText(f"Recv: {self.format_bytes(recv_per_sec)}")

    @Slot(dict, pd.DataFrame)
    def update_line_plot(self, metrics, data):
        """
        This function is now a SLOT. It only runs when the
        worker sends new data. It ONLY does drawing.
        """
        
        # Update labels in BOTH legends
        for label in [self.cpu_label_line, self.cpu_label_scatter]:
            label.setText(f"CPU : {metrics['cpu']:.0f}%")
        for label in [self.ram_label_line, self.ram_label_scatter]:
            label.setText(f"RAM : {metrics['ram']:.0f}%")
        for label in [self.disk_label_line, self.disk_label_scatter]:
            label.setText(f"DISK : {metrics['disk']:.0f}%")
            
        # --- Update Line Plot (Your logic, moved here) ---
        self.line_ax.clear()
        
        if not data.empty:
            current_time = data['timestamp'].iloc[-1]
            time_window_ago = current_time - self.display_time_window
            recent_data = data[data['timestamp'] >= time_window_ago].copy()
            times = (recent_data['timestamp'] - current_time).values
            
            if not recent_data.empty:
                first_cpu = recent_data['cpu'].iloc[0]
                first_ram = recent_data['ram'].iloc[0]
                first_disk = recent_data['disk'].iloc[0]
                first_time = times[0]
                
                if first_time > -self.display_time_window:
                    baseline_times = [-self.display_time_window, first_time]
                    self.line_ax.plot(baseline_times, [first_cpu, first_cpu], color='#E53935', 
                                    linewidth=1.5, alpha=0.4, linestyle='--', label='CPU Baseline')
                    self.line_ax.plot(baseline_times, [first_ram, first_ram], color='#43A047', 
                                    linewidth=1.5, alpha=0.4, linestyle='--', label='RAM Baseline')
                    self.line_ax.plot(baseline_times, [first_disk, first_disk], color='#1E88E5', 
                                    linewidth=1.5, alpha=0.4, linestyle='--', label='DISK Baseline')
        else:
            recent_data = data
            times = []
            baseline_times = [-self.display_time_window, 0]
            self.line_ax.plot(baseline_times, [0, 0], color='#E53935', linewidth=1, alpha=0.3, linestyle='--')
            self.line_ax.plot(baseline_times, [0, 0], color='#43A047', linewidth=1, alpha=0.3, linestyle='--')
            self.line_ax.plot(baseline_times, [0, 0], color='#1E88E5', linewidth=1, alpha=0.3, linestyle='--')
        
        if len(times) > 5:
            try:
                times_smooth = np.linspace(times.min(), times.max(), len(times) + 10)
                cpu_spline = make_interp_spline(times, recent_data['cpu'], k=2)
                cpu_smooth = cpu_spline(times_smooth)
                self.line_ax.plot(times_smooth, cpu_smooth, color='#E53935', linewidth=2.5, 
                                alpha=0.8, label='CPU')
                ram_spline = make_interp_spline(times, recent_data['ram'], k=2)
                ram_smooth = ram_spline(times_smooth)
                self.line_ax.plot(times_smooth, ram_smooth, color='#43A047', linewidth=2.5, 
                                alpha=0.8, label='RAM')
                disk_spline = make_interp_spline(times, recent_data['disk'], k=2)
                disk_smooth = disk_spline(times_smooth)
                self.line_ax.plot(times_smooth, disk_smooth, color='#1E88E5', linewidth=2.5, 
                                alpha=0.8, label='DISK')
                
                self.line_ax.fill_between(times_smooth, cpu_smooth, alpha=0.1, color='#E53935')
                self.line_ax.fill_between(times_smooth, ram_smooth, alpha=0.1, color='#43A047')
                self.line_ax.fill_between(times_smooth, disk_smooth, alpha=0.1, color='#1E88E5')
                
                self.line_ax.scatter(times, recent_data['cpu'], color='#E53935', s=15, alpha=0.6, zorder=5)
                self.line_ax.scatter(times, recent_data['ram'], color='#43A047', s=15, alpha=0.6, zorder=5)
                self.line_ax.scatter(times, recent_data['disk'], color='#1E88E5', s=15, alpha=0.6, zorder=5)
                
            except Exception:
                self.line_ax.plot(times, recent_data['cpu'], color='#E53935', linewidth=2, alpha=0.8)
                self.line_ax.plot(times, recent_data['ram'], color='#43A047', linewidth=2, alpha=0.8)
                self.line_ax.plot(times, recent_data['disk'], color='#1E88E5', linewidth=2, alpha=0.8)
                self.line_ax.fill_between(times, recent_data['cpu'], alpha=0.1, color='#E53935')
                self.line_ax.fill_between(times, recent_data['ram'], alpha=0.1, color='#43A047')
                self.line_ax.fill_between(times, recent_data['disk'], alpha=0.1, color='#1E88E5')
        elif len(times) > 1:
            self.line_ax.plot(times, recent_data['cpu'], color='#E53935', linewidth=2, 
                            marker='o', markersize=3, alpha=0.8)
            self.line_ax.plot(times, recent_data['ram'], color='#43A047', linewidth=2, 
                            marker='s', markersize=3, alpha=0.8)
            self.line_ax.plot(times, recent_data['disk'], color='#1E88E5', linewidth=2, 
                            marker='^', markersize=3, alpha=0.8)
            self.line_ax.fill_between(times, recent_data['cpu'], alpha=0.1, color='#E53935')
            self.line_ax.fill_between(times, recent_data['ram'], alpha=0.1, color='#43A047')
            self.line_ax.fill_between(times, recent_data['disk'], alpha=0.1, color='#1E88E5')
        elif len(times) == 1:
            self.line_ax.scatter(times, recent_data['cpu'], color='#E53935', s=25, alpha=0.8, zorder=5)
            self.line_ax.scatter(times, recent_data['ram'], color='#43A047', s=25, alpha=0.8, zorder=5)
            self.line_ax.scatter(times, recent_data['disk'], color='#1E88E5', s=25, alpha=0.8, zorder=5)
            
            point_width = self.display_time_window * 0.02
            self.line_ax.fill_between([times[0] - point_width, times[0] + point_width], 
                                    [recent_data['cpu'].iloc[0], recent_data['cpu'].iloc[0]], 
                                    alpha=0.1, color='#E53935')
            self.line_ax.fill_between([times[0] - point_width, times[0] + point_width], 
                                    [recent_data['ram'].iloc[0], recent_data['ram'].iloc[0]], 
                                    alpha=0.1, color='#43A047')
            self.line_ax.fill_between([times[0] - point_width, times[0] + point_width], 
                                    [recent_data['disk'].iloc[0], recent_data['disk'].iloc[0]], 
                                    alpha=0.1, color='#1E88E5')
        
        self.line_ax.set_xlim(-self.display_time_window, 0)
        self.line_ax.set_xlabel("Timeline", color='black', fontsize=12)
        self.line_ax.set_ylabel("Usage (%)", color='black', fontsize=12)
        self.line_ax.set_ylim(0, 100)
        for spine in ['top', 'right']: self.line_ax.spines[spine].set_visible(False)
        self.line_ax.spines['bottom'].set_color('black')
        self.line_ax.spines['left'].set_color('black') # Make left spine visible
        self.line_ax.tick_params(axis='y', colors='black')
        self.line_ax.tick_params(axis='x', colors='black')
        
        # Set all plot text/lines to black
        for text in self.line_ax.get_xticklabels() + self.line_ax.get_yticklabels():
            text.set_color('black')
        self.line_ax.xaxis.label.set_color('black')
        self.line_ax.yaxis.label.set_color('black')
        
        self.line_fig.tight_layout(pad=0.5)
        self.line_canvas.draw()

    @Slot(pd.DataFrame)
    def update_scatter_plot(self, process_df):
        """Updates the scatter plot."""
        
        self.scatter_ax.clear()
        
        if not process_df.empty:
            # Filter logic (same as before)
            user_cpu_summary = process_df.groupby('username')['cpu_percent'].sum().reset_index()
            relevant_users = user_cpu_summary[user_cpu_summary['cpu_percent'] > 1.0]['username'].tolist()
            filtered_df = process_df[process_df['username'].isin(relevant_users)].copy()
            filtered_df = filtered_df[filtered_df['cpu_percent'] >= 0.5]

            if not filtered_df.empty:
                # 1. CRITICAL: Save the dataframe so clicks map to the right process
                filtered_df = filtered_df.sort_values(by=['username', 'cpu_percent'], ascending=[True, False]).reset_index(drop=True)
                self.df = filtered_df 
                
                # ... (Color/Size calculation logic - same as before) ...
                users = filtered_df['username'].unique()
                x_vals, y_vals, colors, sizes, x_tick_labels, process_names = [], [], [], [], [], []
                user_colors = ['#E53935', '#43A047', '#1E88E5', '#FF9800', '#9C27B0', '#00BCD4', '#795548', '#607D8B']
                background_colors = ['#FFEBEE', '#E8F5E8', '#E3F2FD', '#FFF3E0', '#F3E5F5', '#E0F2F1', '#EFEBE9', '#ECEFF1']
                current_x_offset = 0

                for i, user in enumerate(users):
                    user_procs = filtered_df[filtered_df['username'] == user]
                    user_color = user_colors[i % len(user_colors)]
                    bg_color = background_colors[i % len(background_colors)]
                    
                    user_x_indices = list(range(current_x_offset, current_x_offset + len(user_procs)))
                    x_vals.extend(user_x_indices)
                    y_vals.extend(user_procs['cpu_percent'].tolist())
                    process_names.extend(user_procs['name'].tolist())
                    
                    for cpu_val in user_procs['cpu_percent']:
                        colors.append(user_color)
                        size = max(20, min(100, cpu_val * 3))
                        sizes.append(size)
                    
                    if not user_procs.empty:
                        center_x_pos = current_x_offset + (len(user_procs) - 1) / 2
                        x_tick_labels.append((center_x_pos, user))
                        # Background rectangles
                        rect = mpatches.Rectangle((current_x_offset - 0.5, 0), len(user_procs), 100,
                                            facecolor=bg_color, edgecolor='none', alpha=0.3, zorder=0)
                        self.scatter_ax.add_patch(rect)
                    current_x_offset += len(user_procs) + 1

                # 2. DRAW THE DOTS 
                self.sc = self.scatter_ax.scatter(
                    x_vals, y_vals, c=colors, s=sizes, alpha=0.7, 
                    edgecolors='white', linewidth=0.5, zorder=2, picker=True 
                )

                if hasattr(self, 'pick_cid'):
                    self.scatter_canvas.mpl_disconnect(self.pick_cid)
                self.pick_cid = self.scatter_canvas.mpl_connect('pick_event', self.on_scatter_pick)

                # Label Logic
                for j, (x, y) in enumerate(zip(x_vals, y_vals)):
                    name = process_names[j][:9] + '...' if len(process_names[j]) > 12 else process_names[j]
                    y_offset = 8 if y > 50 else -15
                    v_align = 'bottom' if y > 50 else 'top'
                    self.scatter_ax.annotate(name, (x, y), textcoords="offset points",
                                            xytext=(0, y_offset), ha='center', va=v_align,
                                            fontsize=6, color='black', alpha=0.8, weight='bold')

                max_cpu = max(y_vals) if y_vals else 0
                self.scatter_ax.set_ylim(0, max(max_cpu * 1.3, 10))
                tick_positions = [pos for pos, _ in x_tick_labels]
                tick_labels_text = [label for _, label in x_tick_labels]
                self.scatter_ax.set_xticks(tick_positions)
                self.scatter_ax.set_xticklabels(tick_labels_text, rotation=0, ha="center", fontsize=9, color='black')
                
        # Final cleanup
        self.scatter_ax.tick_params(axis='y', colors='black')
        for spine in ['top', 'right']: self.scatter_ax.spines[spine].set_visible(False)
        self.scatter_ax.spines['bottom'].set_color('black')
        self.scatter_ax.spines['left'].set_color('black')
        self.scatter_ax.grid(True, alpha=0.3, linestyle='--', color='gray', zorder=1)
        for text in self.scatter_ax.get_xticklabels() + self.scatter_ax.get_yticklabels():
            text.set_color('black')
        self.scatter_fig.tight_layout(pad=0.5)
        self.scatter_canvas.draw()

    # --- GUI Control Slots ---

    @Slot()
    def switch_view(self, index):
        """Switches the main view and legend."""
        self.plot_stack.setCurrentIndex(index)
        self.line_legend_stack.setCurrentIndex(index)
        
        # Reset all buttons to normal
        self.usage_button.setFont(self.nav_font_normal)
        self.usage_button.setStyleSheet(self.usage_button.styleSheet() + "color: #A0A0A0;")
        self.scatter_button.setFont(self.nav_font_normal)
        self.scatter_button.setStyleSheet(self.scatter_button.styleSheet() + "color: #A0A0A0;")
        self.anomaly_button.setFont(self.nav_font_normal)
        self.anomaly_button.setStyleSheet(self.anomaly_button.styleSheet() + "color: #A0A0A0;")

        # Set the active button to bold/white
        if index == 0:
            # "Usage" view
            self.usage_button.setFont(self.nav_font_bold)
            self.usage_button.setStyleSheet(self.usage_button.styleSheet() + "color: #FFFFFF;")
        elif index == 1:
            # "Scatter" view
            self.scatter_button.setFont(self.nav_font_bold)
            self.scatter_button.setStyleSheet(self.scatter_button.styleSheet() + "color: #FFFFFF;")
        elif index == 2:
            # "Anomaly" view
            self.anomaly_button.setFont(self.nav_font_bold)
            self.anomaly_button.setStyleSheet(self.anomaly_button.styleSheet() + "color: #FFFFFF;")
    
    

    def clear_layout(self, layout):
        """Removes all widgets from a layout."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                self.clear_layout(item.layout())
    

    @Slot(list)
    def update_anomaly_tab(self, anomalies):
        """Receives the list of anomalies and updates the UI."""

        # Clear all old anomaly cards
        self.clear_layout(self.anomaly_card_container_layout)

        if not anomalies:
            # Show the "No anomalies" label if the list is empty
            self.no_anomalies_label = QLabel("No anomalies detected.")
            self.no_anomalies_label.setFont(QFont("Arial", 12))
            self.no_anomalies_label.setStyleSheet("color: #888888;")
            self.no_anomalies_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.anomaly_card_container_layout.addWidget(self.no_anomalies_label)
            return

        # --- Styles for the cards ---
        card_style_sheet = """
            QFrame {
                background-color: #DCDCDC;
                border-radius: 10px;
                border: 1px solid #C0C0C0;
            }
        """
        title_font = QFont("Arial", 12, QFont.Weight.Bold)
        desc_font = QFont("Arial", 10)

        box_font = QFont("Arial", 8, QFont.Weight.Bold)
        safe_box_style = "background-color: #C8E6C9; color: #2E7D32; border-radius: 5px; padding: 8px;"
        critical_box_style = "background-color: #FFCDD2; color: #C62828; border-radius: 5px; padding: 8px;"

        # --- Create a card for each anomaly ---
        for anomaly in anomalies:
            # Main card frame
            card_frame = QFrame()
            card_frame.setStyleSheet(card_style_sheet)
            card_frame.setFixedHeight(100)

            card_layout = QHBoxLayout(card_frame)
            card_layout.setContentsMargins(15, 10, 15, 10)

            # Left side (text)
            text_layout = QVBoxLayout()
            text_layout.setSpacing(5)

            title_label = QLabel(anomaly['name'])
            title_label.setFont(title_font)
            title_label.setStyleSheet("color: #000000;")

            desc_label = QLabel(anomaly['desc'])
            desc_label.setFont(desc_font)
            desc_label.setStyleSheet("color: #333333;")

            text_layout.addWidget(title_label)
            text_layout.addWidget(desc_label)
            text_layout.addStretch() # Pushes text to the top

            # Right side (status box)
            box_layout = QVBoxLayout()
            box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            status_box = QLabel()
            status_box.setFont(box_font)
            status_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_box.setWordWrap(True)
            status_box.setFixedWidth(120)

            if anomaly['level'] == 'safe':
                status_box.setText("Process is not important can be removed for CPU RELAXATION")
                status_box.setStyleSheet(safe_box_style)
            else: # 'critical'
                status_box.setText("Process is important can not be removed for CPU RELAXATION")
                status_box.setStyleSheet(critical_box_style)

            box_layout.addWidget(status_box)

            if anomaly['level'] == 'safe':
                kill_button = QPushButton("End Task")
                kill_button.setStyleSheet("""
                    QPushButton {
                        background-color: #E53935;
                        color: white;
                        border-radius: 6px;
                        padding: 6px;
                    }
                    QPushButton:hover {
                        background-color: #C62828;
                    }
                """)
                kill_button.setFixedWidth(120)

                # Connect button → worker signal
                kill_button.clicked.connect(
                    lambda _, pid=anomaly['pid']: self.worker.killProcess.emit(pid)
                )

                box_layout.addWidget(kill_button)
            

            # Add layouts to card
            card_layout.addLayout(text_layout, 3) # Give text 3/4 of the space
            card_layout.addLayout(box_layout, 1)  # Give box 1/4 of the space

            # Add the finished card to the main container
            self.anomaly_card_container_layout.addWidget(card_frame)

        # Add a final "stretch" to push all cards to the top
        self.anomaly_card_container_layout.addStretch()

    # ==========================================
    # --- FIXED HELPER FUNCTIONS ---
    # ==========================================

    def on_scatter_pick(self, event):
        """Handle clicks on the scatter plot points"""
        if not hasattr(event, 'ind') or len(event.ind) == 0:
            return
    
        ind = event.ind[0]
    
        # Check if we have the dataframe
        if not hasattr(self, 'df') or self.df is None or self.df.empty:
            self.explanation_panel.show_error("No process data available")
            return
    
        # Check if index is valid
        if ind >= len(self.df):
            self.explanation_panel.show_error(f"Invalid process index")
            return
    
        try:
            pid = int(self.df.iloc[ind]['pid'])
            name = str(self.df.iloc[ind]['name'])

            print(f"🤖 Clicked {name} ({pid}). Requesting AI...")

            # IMMEDIATE FEEDBACK: Show loading state right away
            self.explanation_panel.show_loading(name)

            # Then start the AI processing
            self.trigger_ai_explanation(pid, name)
        
        except Exception as e:
            print(f"Error picking point: {e}")
            self.explanation_panel.show_error(str(e))

    def trigger_ai_explanation(self, pid, name):
        """Start the background worker safely"""
        # 1. Check if a thread is already running to prevent overlap crashes
        if hasattr(self, 'ai_thread') and self.ai_thread.isRunning():
            print("AI is busy, ignoring click.")
            return

        # 2. Create and start thread
        self.ai_thread = AIWorker(pid, name)
        self.ai_thread.finished.connect(self.update_ai_explanation)
        self.ai_thread.start()

    @Slot(str)
    def update_ai_explanation(self, text):
        """Receive the text and update the side panel"""
        print(f"AI Response received: {text[:100]}...")
    
        # Get the process name from the panel
        process_name = self.explanation_panel.process_label.text().replace("Process: ", "")
    
        # Update the panel with the explanation
        if text and text.strip():
            self.explanation_panel.show_explanation(process_name, text)
        else:
            self.explanation_panel.show_error("No explanation available")

# ==============================================================================
# --- APPLICATION ENTRY POINT ---
# ==============================================================================

if __name__ == "__main__":
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()