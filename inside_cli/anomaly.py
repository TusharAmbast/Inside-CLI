import sys
import time
import psutil
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QLabel, QFrame, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QWidget
)
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QObject, Slot, QEvent
from PySide6.QtGui import QColor, QFont, QEnterEvent

from base_window import BaseMonitorWindow
import inside_cli.ai_engine as ai_engine


# ==============================================================================
# CLICKABLE LABEL (for tab navigation)
# ==============================================================================

class ClickableLabel(QLabel):
    """Custom QLabel that emits a signal when clicked"""
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()


# ==============================================================================
# HOVER BADGE — shows normal text, switches to action text on hover
# ==============================================================================

class HoverBadge(QLabel):
    """
    A badge label that:
      - shows `normal_text` by default
      - switches to `hover_text` when the mouse enters
      - uses `normal_style` / `hover_style` for visual feedback
    """
    def __init__(self, normal_text: str, hover_text: str,
                 normal_style: str, hover_style: str, parent=None):
        super().__init__(normal_text, parent)
        self._normal_text  = normal_text
        self._hover_text   = hover_text
        self._normal_style = normal_style
        self._hover_style  = hover_style
        self.setStyleSheet(normal_style)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.setText(self._hover_text)
        self.setStyleSheet(self._hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setText(self._normal_text)
        self.setStyleSheet(self._normal_style)
        super().leaveEvent(event)


# ==============================================================================
# BACKGROUND WORKER — anomaly detection only
# ==============================================================================

class AnomalyWorker(QObject):
    """
    Runs in a separate QThread. Collects process data every 500ms,
    checks 3 anomaly conditions, and emits a list of anomalies.
    """
    anomaliesFound = Signal(list)
    killProcess    = Signal(int)

    # How many top CPU processes to watch
    TOP_X = 5
    # How long (seconds) CPU must stay high to count as "sustained"
    SUSTAIN_TIME = 10

    # Expected CPU % per process category
    EXPECTED_CPU = {
        'browser':     30,
        'video':       80,
        'screensaver':  5,
        'default':     20,
    }

    # ------------------------------------------------------------------
    # OPTION 3: Process importance classification
    # ------------------------------------------------------------------

    # Layer 1 — hardcoded whitelist of known critical system processes
    # (cross-platform: covers Linux, macOS, Windows)
    CRITICAL_PROCESSES = {
        # Linux / macOS core
        'systemd', 'launchd', 'kernel_task', 'kthreadd',
        'init', 'kworker', 'ksoftirqd', 'migration',
        'watchdog', 'rcu_sched', 'rcu_bh',
        'sshd', 'cron', 'dbus-daemon', 'networkmanager',
        'wpa_supplicant', 'auditd', 'rsyslogd', 'journald',
        'systemd-journald', 'systemd-udevd', 'systemd-resolved',
        'systemd-logind', 'containerd', 'dockerd',
        # macOS specific
        'WindowServer', 'loginwindow', 'cfprefsd',
        'opendirectoryd', 'configd', 'notifyd',
        'diskarbitrationd', 'powerd', 'coreaudiod',
        # Windows specific
        'svchost.exe', 'lsass.exe', 'csrss.exe',
        'wininit.exe', 'winlogon.exe', 'services.exe',
        'smss.exe', 'System', 'Registry',
        'dwm.exe', 'explorer.exe', 'taskhostw.exe',
        'spoolsv.exe', 'MsMpEng.exe',
    }

    # System-level usernames — processes owned by these are treated as
    # critical if they don't appear in the whitelist (Layer 2 fallback)
    SYSTEM_USERS = {
        # Linux / macOS
        'root', 'daemon', 'nobody', 'messagebus',
        'systemd-network', 'systemd-resolve', 'systemd-timesync',
        '_windowserver', '_coreaudiod', 'www-data',
        # Windows
        'SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE',
        'NT AUTHORITY\\SYSTEM',
        'NT AUTHORITY\\LOCAL SERVICE',
        'NT AUTHORITY\\NETWORK SERVICE',
    }

    def classify_process(self, name: str, username: str, ppid: int) -> str:
        """
        Option 3 importance classifier — three layers:

        Layer 1 — Whitelist check:
            If the process name (case-insensitive) is in CRITICAL_PROCESSES
            → always 'critical', regardless of conditions matched.

        Layer 2 — Ownership check:
            If not on the whitelist but owned by a system user AND has no
            meaningful parent (ppid == 0 or ppid == 1) → 'critical'.

        Layer 3 — Condition-count fallback:
            Used only when layers 1 & 2 don't apply. Passed in as
            `matched_conditions` from the caller.
        """
        name_lower = name.lower().rstrip('.exe')

        # Layer 1: whitelist
        if name_lower in {p.lower().rstrip('.exe') for p in self.CRITICAL_PROCESSES}:
            return 'critical'

        # Layer 2: system ownership + no real parent
        is_system_user = (username or '').strip() in self.SYSTEM_USERS
        is_root_process = ppid in (0, 1)
        if is_system_user and is_root_process:
            return 'critical'

        # Layer 3: caller decides based on condition count
        return 'undecided'

    def __init__(self):
        super().__init__()
        self._monitoring  = False
        self.cpu_history  = {}   # pid -> [(timestamp, cpu_percent), ...]
        self.top_processes = set()

    # ------------------------------------------------------------------
    def get_expected_cpu(self, process_name: str) -> int:
        name = process_name.lower()
        if 'chrome' in name or 'firefox' in name:
            return self.EXPECTED_CPU['browser']
        if 'ffmpeg' in name or 'encoder' in name:
            return self.EXPECTED_CPU['video']
        if 'screen' in name:
            return self.EXPECTED_CPU['screensaver']
        return self.EXPECTED_CPU['default']

    # ------------------------------------------------------------------
    def start_monitoring(self):
        self._monitoring = True
        self._timer = QTimer()
        self._timer.timeout.connect(self._run_cycle)
        self._timer.start(500)

    def stop_monitoring(self):
        self._monitoring = False
        if hasattr(self, '_timer'):
            self._timer.stop()

    # ------------------------------------------------------------------
    def _get_process_data(self) -> pd.DataFrame:
        """Collect CPU usage and lifetime details of all processes."""
        processes = []
        for proc in psutil.process_iter(
            ['pid', 'name', 'cpu_percent', 'username', 'ppid', 'create_time']
        ):
            try:
                info = proc.info
                parent_create_time = None
                try:
                    parent = psutil.Process(info['ppid'])
                    parent_create_time = parent.create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                processes.append({
                    'pid':                info['pid'],
                    'name':               info['name'],
                    'cpu_percent':        info['cpu_percent'],
                    'username':           info['username'],
                    'ppid':               info['ppid'],
                    'create_time':        info['create_time'],
                    'parent_create_time': parent_create_time,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return pd.DataFrame(processes)

    # ------------------------------------------------------------------
    def _run_cycle(self):
        if not self._monitoring:
            return

        try:
            process_df = self._get_process_data()
            if process_df.empty:
                self.anomaliesFound.emit([])
                return

            # Pick top-N CPU consumers
            top_df = (
                process_df
                .sort_values(by='cpu_percent', ascending=False)
                .head(self.TOP_X)
            )
            current_time = time.time()

            # --- Build sustained-high-CPU set ---
            sustained_high = set()
            for _, row in top_df.iterrows():
                pid      = row['pid']
                cpu      = row['cpu_percent']
                expected = self.get_expected_cpu(row['name'])

                if pid not in self.cpu_history:
                    self.cpu_history[pid] = []

                self.cpu_history[pid].append((current_time, cpu))

                # Trim to last SUSTAIN_TIME seconds
                self.cpu_history[pid] = [
                    (t, c) for t, c in self.cpu_history[pid]
                    if current_time - t <= self.SUSTAIN_TIME
                ]

                if (
                    len(self.cpu_history[pid]) > 0
                    and all(c > expected for _, c in self.cpu_history[pid])
                ):
                    sustained_high.add(pid)

            # --- Evaluate each top process ---
            anomalies = []
            for _, row in top_df.iterrows():
                pid      = row['pid']
                expected = self.get_expected_cpu(row['name'])

                # Condition 1: CPU higher than expected
                cpu_abnormal = row['cpu_percent'] > expected

                # Condition 2: Sustained high CPU
                sustained = pid in sustained_high

                # Condition 3: Uptime abnormal vs parent
                uptime_abnormal = False
                if row['parent_create_time'] is not None:
                    proc_uptime   = current_time - row['create_time']
                    parent_uptime = current_time - row['parent_create_time']
                    if proc_uptime > parent_uptime * 1.5:
                        uptime_abnormal = True

                matched = sum([cpu_abnormal, sustained, uptime_abnormal])

                # Flag anomaly if at least 2 conditions match
                if matched >= 2:

                    # --- Option 3 classification ---
                    # Run layers 1 & 2 first
                    importance = self.classify_process(
                        name=row['name'],
                        username=row.get('username', ''),
                        ppid=row['ppid'],
                    )

                    if importance == 'undecided':
                        # Layer 3: ask the LLM to classify by process name
                        # Falls back to 'critical' internally if the call fails
                        importance = ai_engine.classify_process_importance(
                            pid=row['pid'],
                            process_name=row['name'],
                        )

                    anomalies.append({
                        'pid':   row['pid'],
                        'name':  row['name'],
                        'desc':  (
                            "CPU consumption is in unusual range. "
                            "Please check this process."
                        ),
                        'level': importance,
                    })

            self.anomaliesFound.emit(anomalies)

        except Exception as e:
            print(f"[AnomalyWorker] Error: {e}")

    # ------------------------------------------------------------------
    @Slot(int)
    def terminate_process(self, pid: int):
        try:
            psutil.Process(pid).terminate()
            print(f"[AnomalyWorker] Terminated PID {pid}")
        except psutil.NoSuchProcess:
            print(f"[AnomalyWorker] PID {pid} already gone")
        except psutil.AccessDenied:
            print(f"[AnomalyWorker] Access denied for PID {pid}")
        except Exception as e:
            print(f"[AnomalyWorker] Failed to terminate {pid}: {e}")


# ==============================================================================
# MAIN ANOMALY WINDOW
# ==============================================================================

class AnomalyWindow(BaseMonitorWindow):
    def __init__(self):
        super().__init__(active_tab="ANOMALY")
        self.setWindowTitle("Anomaly - Critique CLI")
        self._last_anomalies = []

        # Build the scrollable card container
        self._build_card_area()

        # Make tab labels clickable
        self._setup_clickable_tabs()

        # Start the background anomaly worker
        self._start_worker()

    # ------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------

    def _build_card_area(self):
        """
        QScrollArea — no visible scrollbar, transparent background,
        natural overflow scrolling via mouse wheel / trackpad.
        """
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea                     { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)

        self.card_container = QWidget()
        self.card_container.setStyleSheet("background: transparent;")

        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(2, 6, 2, 6)
        self.card_layout.setSpacing(12)
        self.card_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.card_container)
        self._position_scroll_area()

    def _position_scroll_area(self):
        """Fit the scroll area between the tab bar and the bottom stats row."""
        w = self.width()
        h = self.height()
        sx = w / self.base_width
        sy = h / self.base_height

        pad_h  = int(50 * sx)          # left/right margin
        top    = int(90 * sy)           # below tab labels + gap under "Inside Cli"
        bottom = int(48 * sy)           # just above the stats labels

        self.scroll_area.setGeometry(
            pad_h,
            top,
            w - pad_h * 2,
            h - top - bottom,
        )

    def _setup_clickable_tabs(self):
        """Replace static tab QLabels with ClickableLabel instances."""
        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                old = elem["label"]
                new = ClickableLabel(elem["text"], self)
                new.setFont(old.font())
                new.setStyleSheet(old.styleSheet())
                new.move(old.pos())
                new.adjustSize()
                new.show()
                old.hide()
                elem["label"] = new
                tab = elem["text"]
                new.clicked.connect(lambda _=False, t=tab: self.switch_tab(t))

    # ------------------------------------------------------------------
    # WORKER THREAD
    # ------------------------------------------------------------------

    def _start_worker(self):
        self.worker        = AnomalyWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker.anomaliesFound.connect(self._update_anomaly_cards)
        self.worker.killProcess.connect(self.worker.terminate_process)
        self.worker_thread.started.connect(self.worker.start_monitoring)
        self.worker_thread.start()

    def _stop_worker(self):
        self.worker.stop_monitoring()
        self.worker_thread.quit()
        self.worker_thread.wait()

    def closeEvent(self, event):
        self._stop_worker()
        event.accept()

    # ------------------------------------------------------------------
    # ANOMALY CARD RENDERING
    # ------------------------------------------------------------------

    @Slot(list)
    def _update_anomaly_cards(self, anomalies: list):
        """Rebuild the card list every time the worker emits new anomalies."""
        self._last_anomalies = anomalies
        self._clear_layout(self.card_layout)

        if not anomalies:
            empty = QLabel("No anomalies detected.")
            empty.setFont(QFont("Inter", 11))
            empty.setStyleSheet("color: rgba(63, 72, 101, 0.45); background: transparent;")
            empty.setAlignment(Qt.AlignCenter)
            self.card_layout.addWidget(empty)
            return

        for anomaly in anomalies:
            self.card_layout.addWidget(self._make_card(anomaly))

        self.card_layout.addStretch()

    def _make_card(self, anomaly: dict) -> QFrame:
        """
        Anomaly process card — redesigned per spec:

        ┌─────────────────────────────────────────────────────────────────┐
        │  process name  (Inter SemiBold 13px)       ┌──────────────────┐ │
        │  details text  (Inter Regular  13px)        │ hover badge      │ │
        │                                             └──────────────────┘ │
        └─────────────────────────────────────────────────────────────────┘

        Card border : rgb(63, 72, 101) 1px
        Card bg     : rgb(245, 242, 233)
        Padding     : left/right 50*scale  top 100*scale  bottom 60*scale

        Hover badge (safe)     : "Process is not important…"  → hover → "END TASK"
        Hover badge (critical) : "Process is important…"      → hover → "CAN'T END TASK"
        """
        is_safe = anomaly["level"] == "safe"

        # ── scale factor from the window geometry ─────────────────────────
        sx = self.width()  / self.base_width
        sy = self.height() / self.base_height
        scale = (sx + sy) / 2.0          # single uniform scale for padding

        pad_lr  = int(50  * scale)
        pad_top = int(10  * scale)
        pad_bot = int(10  * scale)

        # ── colour scheme ─────────────────────────────────────────────────
        CARD_BG     = "rgb(245, 242, 233)"
        CARD_BORDER = "rgb(63, 72, 101)"

        BADGE_BORDER = "rgb(63, 72, 101)"
        BADGE_TEXT   = "rgb(254, 243, 215)"

        if is_safe:
            badge_color      = "rgb(56, 171, 142)"
            hover_text       = "END TASK"
            normal_badge_txt = "Process is not important\ncan be removed for\nCPU RELAXATION"
        else:
            badge_color      = "rgb(222, 96, 58)"
            hover_text       = "CAN'T END TASK"
            normal_badge_txt = "Process is important\ncannot be removed for\nCPU RELAXATION"

        # ── card frame ────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("anomalyCard")
        card.setFixedHeight(int(70 * scale))
        card.setStyleSheet(f"""
            QFrame#anomalyCard {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}
        """)

        body = QHBoxLayout(card)
        body.setContentsMargins(pad_lr, pad_top, pad_lr, pad_bot)
        body.setSpacing(int(16 * scale))

        # ── left: name + description ──────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(int(4 * scale))
        left.setContentsMargins(0, 0, 0, 0)

        name_font_size = max(1, int(13 * scale))
        name_lbl = QLabel(anomaly["name"])
        name_font = QFont("Inter", name_font_size)
        name_font.setWeight(QFont.Weight.DemiBold)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet(
            f"color: {CARD_BORDER}; background: transparent; border: none;"
        )

        desc_font_size = max(1, int(13 * scale))
        desc_lbl = QLabel(anomaly["desc"])
        desc_lbl.setFont(QFont("Inter", desc_font_size, QFont.Weight.Normal))
        desc_lbl.setStyleSheet(
            "color: rgba(63, 72, 101, 0.65); background: transparent; border: none;"
        )
        desc_lbl.setWordWrap(True)

        left.addWidget(name_lbl)
        left.addWidget(desc_lbl)
        left.addStretch()

        # ── right: hover badge ────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(0)
        right.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        right.setContentsMargins(0, 0, 0, 0)

        badge_font_size        = max(1, int(11 * scale))
        badge_font_size_hover  = max(1, int(13 * scale))
        badge_radius           = max(1, int(10 * scale))
        badge_pad              = max(1, int(8 * scale))
        badge_width            = max(1, int(170 * scale))
        badge_height           = max(1, int(52  * scale))

        normal_style = f"""
            QLabel {{
                background-color: {badge_color};
                color: {BADGE_TEXT};
                border-radius: {badge_radius}px;
                border: 1px solid {BADGE_BORDER};
                padding: {badge_pad}px {badge_pad}px {badge_pad}px {badge_pad}px;
                font-family: Inter;
                font-size: {badge_font_size}px;
                font-weight: 600;
            }}
        """
        hover_style = f"""
            QLabel {{
                background-color: {badge_color};
                color: {BADGE_TEXT};
                border-radius: {badge_radius}px;
                border: 1px solid {BADGE_BORDER};
                padding: {badge_pad}px {badge_pad}px {badge_pad}px {badge_pad}px;
                font-family: Inter;
                font-size: {badge_font_size_hover}px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """

        badge = HoverBadge(
            normal_text=normal_badge_txt,
            hover_text=hover_text,
            normal_style=normal_style,
            hover_style=hover_style,
        )
        badge.setFixedWidth(badge_width)
        badge.setFixedHeight(badge_height)
        badge.setFont(QFont("Inter", badge_font_size, QFont.Weight.DemiBold))

        if is_safe:
            badge.setCursor(Qt.PointingHandCursor)
            badge.mousePressEvent = (
                lambda _, pid=anomaly["pid"]:
                self.worker.killProcess.emit(pid)
            )

        right.addWidget(badge, 0, Qt.AlignRight)

        body.addLayout(left,  3)
        body.addLayout(right, 1)

        return card

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def switch_tab(self, tab_name: str):
        if self.active_tab == tab_name:
            return
        self.active_tab = tab_name
        for elem in self.elements:
            if elem["text"] in ["SYSTEM USAGE", "SCATTER PLOT", "ANOMALY"]:
                elem["opacity"] = 1.0 if elem["text"] == tab_name else 0.4
        self.update_layout()
        self.update()

    # ------------------------------------------------------------------
    # RESIZE — reposition the scroll area when window resizes
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_scroll_area()
        if hasattr(self, '_last_anomalies') and self._last_anomalies:
            self._update_anomaly_cards(self._last_anomalies)

    # ------------------------------------------------------------------
    # paintEvent — no graph, just let BaseMonitorWindow draw its chrome
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)   # draws background + tab labels + stats


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def open_anomaly_window():
    window = AnomalyWindow()
    window.show()
    return window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnomalyWindow()
    window.show()

    # ── FAKE ANOMALIES for UI testing ─────────────────────────────────────
    FAKE_ANOMALIES = [
        {
            "pid":   1001,
            "name":  "chrome.exe",
            "desc":  "CPU consumption is in unusual range. Please check this process.",
            "level": "safe",
        },
        {
            "pid":   1002,
            "name":  "systemd",
            "desc":  "CPU consumption is in unusual range. Please check this process.",
            "level": "critical",
        },
        {
            "pid":   1003,
            "name":  "ffmpeg",
            "desc":  "CPU consumption is in unusual range. Please check this process.",
            "level": "safe",
        },
        {
            "pid":   1004,
            "name":  "svchost.exe",
            "desc":  "CPU consumption is in unusual range. Please check this process.",
            "level": "critical",
        },
        {
            "pid":   1005,
            "name":  "lsass.exe",
            "desc":  "CPU consumption is in unusual range. Please check this process.",
            "level": "critical",
        },
        {
            "pid":   1006,
            "name":  "kernel_task",
            "desc":  "CPU consumption is in unusual range. Please check this process.",
            "level": "critical",
        },
    ]
    # Inject after a short delay so the window has fully rendered
    QTimer.singleShot(300, lambda: window._update_anomaly_cards(FAKE_ANOMALIES))
    # ─────────────────────────────────────────────────────────────────────

    sys.exit(app.exec())