import os
import psutil
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QFontDatabase, QColor, QPainter, QPainterPath, QBrush, QPen
import sys

# ─────────────────────────────────────────────────────────────────
#  Shared constants
# ─────────────────────────────────────────────────────────────────
BG     = "#FEF3D7"   # window background colour
RADIUS = 12          # window corner radius (px)


# ─────────────────────────────────────────────────────────────────
#  macOS traffic-light button
# ─────────────────────────────────────────────────────────────────
class _MacButton(QWidget):
    MAC_BTN_SIZE = 13

    def __init__(self, color, hover_color, action, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.MAC_BTN_SIZE, self.MAC_BTN_SIZE)
        self._color       = QColor(color)
        self._hover_color = QColor(hover_color)
        self._hovered     = False
        self._action      = action

    def enterEvent(self, e):  self._hovered = True;  self.update()
    def leaveEvent(self, e):  self._hovered = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._action:
            self._action()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._hover_color if self._hovered else self._color)
        p.drawEllipse(0, 0, self.MAC_BTN_SIZE, self.MAC_BTN_SIZE)


# ─────────────────────────────────────────────────────────────────
#  Windows-style button  (─  □  ✕)
# ─────────────────────────────────────────────────────────────────
class _WinButton(QWidget):
    WIN_BTN_W = 58
    WIN_BTN_H = 40
    WIN_BTN_FONT      = "Inter"
    WIN_BTN_FONT_SIZE = 12
    WIN_BTN_SYMBOL_COLOR       = "#3f4865"
    WIN_BTN_HOVER_SYMBOL_COLOR = "#ffffff"

    def __init__(self, symbol, hover_bg, action, is_close=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WIN_BTN_W, self.WIN_BTN_H)
        self._symbol   = symbol
        self._hover_bg = QColor(hover_bg)
        self._action   = action
        self._is_close = is_close
        self._hovered  = False

    def enterEvent(self, e):  self._hovered = True;  self.update()
    def leaveEvent(self, e):  self._hovered = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._action:
            self._action()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        if self._hovered:
            if self._is_close:
                path = QPainterPath()
                path.addRoundedRect(0, 0, self.width(), self.height(), 0, 0)
                p.setBrush(self._hover_bg)
                p.drawPath(path)
            else:
                p.setBrush(self._hover_bg)
                p.drawRect(0, 0, self.width(), self.height())

        p.setPen(QColor(self.WIN_BTN_SYMBOL_COLOR)
                 if not (self._is_close and self._hovered)
                 else QColor(self.WIN_BTN_HOVER_SYMBOL_COLOR))
        font = QFont(self.WIN_BTN_FONT, self.WIN_BTN_FONT_SIZE)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, self._symbol)


# ─────────────────────────────────────────────────────────────────
#  Animated OS toggle switch
# ─────────────────────────────────────────────────────────────────
class OsToggle(QWidget):
    """
    A pill-shaped toggle.  Left = macOS (dark pill, white thumb + apple).
    Right = Windows (light pill, dark thumb + win-logo).
    """
    def __init__(self, on_toggle, parent=None):
        super().__init__(parent)
        self.setFixedSize(110, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._mac_mode  = True
        self._on_toggle = on_toggle
        self._thumb_x   = 4

    def _get_thumb_x(self): return self._thumb_x
    def _set_thumb_x(self, v):
        self._thumb_x = v
        self.update()
    thumb_x = Property(int, _get_thumb_x, _set_thumb_x)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._mac_mode = not self._mac_mode

        anim = QPropertyAnimation(self, b"thumb_x", self)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(self._thumb_x)
        anim.setEndValue(4 if self._mac_mode else self.width() - 28 - 4)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._anim = anim

        if self._on_toggle:
            self._on_toggle(self._mac_mode)

    def paintEvent(self, e):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pill_color = QColor("#3f4865") if self._mac_mode else QColor("#d6cbb0")
        p.setPen(Qt.NoPen)
        p.setBrush(pill_color)
        p.drawRoundedRect(0, 0, w, h, h // 2, h // 2)

        label_font = QFont("Inter", 8) if sys.platform == "darwin" else QFont("Inter", 8)
        label_font.setBold(True)
        p.setFont(label_font)

        mac_alpha = 230 if self._mac_mode else 100
        p.setPen(QColor(255, 255, 255, mac_alpha))
        p.drawText(QRect(0, 0, w // 2, h), Qt.AlignCenter, "MAC")

        win_alpha = 230 if not self._mac_mode else 100
        win_color = QColor(63, 72, 101, win_alpha) if not self._mac_mode else QColor(255, 255, 255, win_alpha)
        p.setPen(win_color)
        p.drawText(QRect(w // 2, 0, w // 2, h), Qt.AlignCenter, "WIN")

        thumb_size = 24
        thumb_y    = (h - thumb_size) // 2
        thumb_color = QColor("#ffffff") if self._mac_mode else QColor("#3f4865")
        p.setPen(Qt.NoPen)
        p.setBrush(thumb_color)
        p.drawEllipse(self._thumb_x, thumb_y, thumb_size, thumb_size)

        icon_font = QFont("Apple Color Emoji" if sys.platform == "darwin" else "Segoe UI Symbol", 10)
        p.setFont(icon_font)
        icon_color = QColor("#3f4865") if self._mac_mode else QColor("#ffffff")
        p.setPen(icon_color)
        icon = "" if self._mac_mode else "⊞"
        p.drawText(
            QRect(self._thumb_x, thumb_y, thumb_size, thumb_size),
            Qt.AlignCenter, icon
        )


# ─────────────────────────────────────────────────────────────────
#  Title bar
# ─────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    HEIGHT = 40

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setFixedHeight(self.HEIGHT)
        self._drag_pos  = None
        self._win       = window
        self._mac_mode  = True

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._mac_group = QWidget(self)
        self._mac_group.setStyleSheet("background: transparent;")
        mac_row = QHBoxLayout(self._mac_group)
        mac_row.setContentsMargins(14, 0, 0, 0)
        mac_row.setSpacing(8)
        mac_row.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self._m_close = _MacButton(
            "#FF5F56", "#e04a44",
            window.close, self._mac_group)
        self._m_min   = _MacButton(
            "#FFBD2E", "#e0a228",
            window.showMinimized, self._mac_group)
        self._m_max   = _MacButton(
            "#27C93F", "#1fb534",
            lambda: window.showNormal() if window.isMaximized() else window.showMaximized(),
            self._mac_group)
        mac_row.addWidget(self._m_close)
        mac_row.addWidget(self._m_min)
        mac_row.addWidget(self._m_max)

        self._win_group = QWidget(self)
        self._win_group.setStyleSheet("background: transparent;")
        self._win_group.hide()
        win_row = QHBoxLayout(self._win_group)
        win_row.setContentsMargins(0, 0, 0, 0)
        win_row.setSpacing(0)
        win_row.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        self._w_min   = _WinButton(
            "─", "#d6cbb0",
            window.showMinimized, parent=self._win_group)
        self._w_max   = _WinButton(
            "□", "#d6cbb0",
            lambda: window.showNormal() if window.isMaximized() else window.showMaximized(),
            parent=self._win_group)
        self._w_close = _WinButton(
            "✕", "#e81123",
            window.close, is_close=True, parent=self._win_group)
        win_row.addWidget(self._w_min)
        win_row.addWidget(self._w_max)
        win_row.addWidget(self._w_close)

        self._toggle = OsToggle(on_toggle=self._on_os_switched, parent=self)

        row.addWidget(self._mac_group,  0)
        row.addStretch(1)
        row.addWidget(self._toggle,     0, Qt.AlignVCenter)
        row.addStretch(1)
        row.addWidget(self._win_group,  0)

    def _on_os_switched(self, mac_mode: bool):
        self._mac_mode = mac_mode
        self._mac_group.setVisible(mac_mode)
        self._win_group.setVisible(not mac_mode)
        self.update()
        # Notify parent window of OS switch
        if hasattr(self._win, 'on_os_switched'):
            self._win.on_os_switched(mac_mode)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self._win.move(e.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG))
        path = QPainterPath()
        r    = RADIUS
        w, h = self.width(), self.height()
        path.moveTo(r, 0)
        path.lineTo(w - r, 0)
        path.quadTo(w, 0, w, r)
        path.lineTo(w, h)
        path.lineTo(0, h)
        path.lineTo(0, r)
        path.quadTo(0, 0, r, 0)
        path.closeSubpath()
        p.drawPath(path)


class BaseMonitorWindow(QWidget):
    def __init__(self, active_tab="SYSTEM USAGE"):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 700, 450)

        # Load Inter-Regular font for Windows buttons
        script_dir = os.path.dirname(os.path.abspath(__file__))
        inter_regular_path = os.path.join(script_dir, "Fonts/Inter Font Family/Inter-Regular.otf")
        QFontDatabase.addApplicationFont(inter_regular_path)

        # Main layout with title bar
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add custom title bar and connect OS switch callback
        self.title_bar = TitleBar(self)
        self._current_os_mode = "mac"  # Track current OS mode
        main_layout.addWidget(self.title_bar)

        # Content widget
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent;")
        main_layout.addWidget(self.content_widget, 1)

        # Base dimensions for ratio calculations
        self.base_width = 750
        self.base_height = 450
        
        # Title bar offset is now 0 since it's part of our frameless window
        self._title_bar_offset = 0
            
        # Track which tab is active
        self.active_tab = active_tab
        
        # ── initialise disk I/O baseline BEFORE the stats timer starts ───
        self._last_disk_io = psutil.disk_io_counters()

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
        
        # Element definitions with base font sizes and positions (MAC mode)
        # Windows mode positions will be calculated dynamically
        self.elements = [
            {
                "text": "Inside Cli",
                "font_name": "Abril Fatface",
                "base_font_size": cli_font_size,
                "base_pos_mac": (650, 22),
                "base_pos_win": (50, 22),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0,
                "label": None,
                "align_right_mac": True,
                "align_right_win": False,
                "right_margin": 50
            },
            {
                "text": "SYSTEM USAGE",
                "font_name": "Inter",
                "base_font_size": font_size,
                "base_pos_mac": (39, 56),
                "base_pos_win": (330, 56),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "SYSTEM USAGE" else 0.4,
                "label": None,
                "is_extra_bold": True,
                "align_right_mac": False,
                "align_right_win": False,
                "right_margin": 90
            },
            {
                "text": "SCATTER PLOT",
                "font_name": "Inter",
                "base_font_size": font_size,
                "base_pos_mac": (196, 56),
                "base_pos_win": (487, 56),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "SCATTER PLOT" else 0.4,
                "label": None,
                "is_extra_bold": True,
                "align_right_mac": False,
                "align_right_win": False,
                "right_margin": 180
            },
            {
                "text": "ANOMALY",
                "font_name": "Inter",
                "base_font_size": font_size,
                "base_pos_mac": (349, 56),
                "base_pos_win": (640, 56),
                "color": "rgb(63, 72, 101)",
                "opacity": 1.0 if active_tab == "ANOMALY" else 0.4,
                "label": None,
                "is_extra_bold": True,
                "align_right_mac": False,
                "align_right_win": False,
                "right_margin": 270
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
                "text": "CPU :                 ",
                "font_name": "Inter",
                "base_font_size": self.stat_size,
                "base_pos": (50, 410),
                "color": "rgb(255, 170, 30)",
                "is_semibold": True,
                "bottom_margin": 20
            },
            {
                "key": "ram",
                "text": "RAM :                 ",
                "font_name": "Inter",
                "base_font_size": self.stat_size,
                "base_pos": (180, 410),
                "color": "rgb(57, 171, 142)",
                "is_semibold": True,
                "bottom_margin": 20
            },
            {
                "key": "disk",
                "text": "DISK :                  ",
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
    
    def on_os_switched(self, mac_mode: bool):
        """Called by TitleBar when OS mode is switched"""
        self._current_os_mode = "mac" if mac_mode else "windows"
        self.update_layout()
    
    def update_layout(self):
        """Update positions and font sizes based on current window dimensions and OS mode"""
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
            
            # Determine which position and alignment to use based on OS mode
            if self._current_os_mode == "mac":
                base_pos = elem.get("base_pos_mac", elem.get("base_pos", (0, 0)))
                align_right = elem.get("align_right_mac", elem.get("align_right", False))
            else:
                base_pos = elem.get("base_pos_win", elem.get("base_pos", (0, 0)))
                align_right = elem.get("align_right_win", elem.get("align_right", False))
            
            # Handle right-aligned elements
            if align_right:
                label.adjustSize()  # Get the width of the label
                right_margin = int(elem.get("right_margin", 50) * min(scale_x, scale_y))
                scaled_x = current_width - right_margin - label.width()
                scaled_y = int(base_pos[1] * scale_y)
            else:
                # Scale position normally
                scaled_x = int(base_pos[0] * scale_x)
                scaled_y = int(base_pos[1] * scale_y)
            
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

    def paintEvent(self, e):
        """Paint the whole window with full rounded corners"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        path = QPainterPath()
        path.addRoundedRect(self.rect(), RADIUS, RADIUS)
        p.setBrush(QColor(BG))
        p.drawPath(path)

        # Thin border so the window edge is crisp against any desktop
        border_path = QPainterPath()
        border_path.addRoundedRect(
            self.rect().adjusted(1, 1, -1, -1), RADIUS - 1, RADIUS - 1
        )
        p.setPen(QPen(QColor(0, 0, 0, 30), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(border_path)