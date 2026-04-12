import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPen, QFont


# ─────────────────────────────────────────────────────────────────
#  Shared constants
# ─────────────────────────────────────────────────────────────────
BG     = "#FEF3D7"   # ← change this to set the whole window background colour
RADIUS = 12          # ← window corner radius (px) — applies to all four corners


# ─────────────────────────────────────────────────────────────────
#  macOS traffic-light button
# ─────────────────────────────────────────────────────────────────
class _MacButton(QWidget):
    # ── macOS button sizes ────────────────────────────────────────────────
    MAC_BTN_SIZE = 13   # ← diameter of each traffic-light circle (px)

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
    # ── Windows button sizes ──────────────────────────────────────────────
    # WIN_BTN_W  : width of each button (px)  — increase for wider buttons
    # WIN_BTN_H  : height of each button (px) — should match TitleBar.HEIGHT
    WIN_BTN_W = 58   # ← change button width here
    WIN_BTN_H = 40   # ← change button height here (keep equal to TitleBar.HEIGHT)

    # ── Windows button symbol font ────────────────────────────────────────
    # Change the font name or size to adjust how  ─  □  ✕  look
    WIN_BTN_FONT      = "Inter"  # ← font for the button symbols (Inter-Regular)
    WIN_BTN_FONT_SIZE = 20                 # ← symbol font size (pt)

    # ── Windows button colours ────────────────────────────────────────────
    WIN_BTN_SYMBOL_COLOR       = "#3f4865"  # ← normal symbol colour
    WIN_BTN_HOVER_SYMBOL_COLOR = "#ffffff"  # ← symbol colour when close btn hovered

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

        # symbol
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
        self._mac_mode  = True      # starts in macOS mode
        self._on_toggle = on_toggle
        self._thumb_x   = 4        # animated property

    # ── animated thumb position ───────────────────────────────────
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
        self._anim = anim   # keep reference

        if self._on_toggle:
            self._on_toggle(self._mac_mode)

    def paintEvent(self, e):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # pill background
        pill_color = QColor("#3f4865") if self._mac_mode else QColor("#d6cbb0")
        p.setPen(Qt.NoPen)
        p.setBrush(pill_color)
        p.drawRoundedRect(0, 0, w, h, h // 2, h // 2)

        # labels
        label_font = QFont("Inter", 8) if sys.platform == "darwin" else QFont("Inter", 8)
        label_font.setBold(True)
        p.setFont(label_font)

        # macOS label (left side)                                                                                                                                       
        mac_alpha = 230 if self._mac_mode else 100
        p.setPen(QColor(255, 255, 255, mac_alpha))
        p.drawText(QRect(0, 0, w // 2, h), Qt.AlignCenter, "MAC")

        # Windows label (right side)
        win_alpha = 230 if not self._mac_mode else 100
        win_color = QColor(63, 72, 101, win_alpha) if not self._mac_mode else QColor(255, 255, 255, win_alpha)
        p.setPen(win_color)
        p.drawText(QRect(w // 2, 0, w // 2, h), Qt.AlignCenter, "WIN")

        # thumb
        thumb_size = 24
        thumb_y    = (h - thumb_size) // 2
        thumb_color = QColor("#ffffff") if self._mac_mode else QColor("#3f4865")
        p.setPen(Qt.NoPen)
        p.setBrush(thumb_color)
        p.drawEllipse(self._thumb_x, thumb_y, thumb_size, thumb_size)

        # thumb icon
        icon_font = QFont("Apple Color Emoji" if sys.platform == "darwin" else "Inter", 10)
        p.setFont(icon_font)
        icon_color = QColor("#3f4865") if self._mac_mode else QColor("#ffffff")
        p.setPen(icon_color)
        icon = "" if self._mac_mode else "⊞"
        p.drawText(
            QRect(self._thumb_x, thumb_y, thumb_size, thumb_size),
            Qt.AlignCenter, icon
        )


# ─────────────────────────────────────────────────────────────────
#  Title bar  (holds both button groups + the toggle)
# ─────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    # ── title bar height ──────────────────────────────────────────────────
    HEIGHT = 40   # ← change total title bar height (px) here
                  #   also update _WinButton.WIN_BTN_H to match

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setFixedHeight(self.HEIGHT)
        self._drag_pos  = None
        self._win       = window
        self._mac_mode  = True

        # Main row layout
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # ── macOS buttons (left) ──────────────────────────────────
        self._mac_group = QWidget(self)
        self._mac_group.setStyleSheet("background: transparent;")
        mac_row = QHBoxLayout(self._mac_group)
        mac_row.setContentsMargins(14, 0, 0, 0)  # ← left padding before the traffic lights (px)
        mac_row.setSpacing(8)                      # ← gap between each traffic-light circle (px)
        mac_row.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self._m_close = _MacButton(
            "#FF5F56", "#e04a44",           # ← close btn: normal colour, hover colour
            window.close, self._mac_group)
        self._m_min   = _MacButton(
            "#FFBD2E", "#e0a228",           # ← minimise btn: normal colour, hover colour
            window.showMinimized, self._mac_group)
        self._m_max   = _MacButton(
            "#27C93F", "#1fb534",           # ← maximise btn: normal colour, hover colour
            lambda: window.showNormal() if window.isMaximized() else window.showMaximized(),
            self._mac_group)
        mac_row.addWidget(self._m_close)
        mac_row.addWidget(self._m_min)
        mac_row.addWidget(self._m_max)

        # ── Windows buttons (right) ───────────────────────────────
        self._win_group = QWidget(self)
        self._win_group.setStyleSheet("background: transparent;")
        self._win_group.hide()
        win_row = QHBoxLayout(self._win_group)
        win_row.setContentsMargins(0, 0, 0, 0)
        win_row.setSpacing(0)
        win_row.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        self._w_min   = _WinButton(
            "─", "#d6cbb0",                # ← minimise btn symbol, hover background colour
            window.showMinimized, parent=self._win_group)
        self._w_max   = _WinButton(
            "□", "#d6cbb0",                # ← maximise btn symbol, hover background colour
            lambda: window.showNormal() if window.isMaximized() else window.showMaximized(),
            parent=self._win_group)
        self._w_close = _WinButton(
            "✕", "#e81123",                # ← close btn symbol, hover background colour (classic Windows red)
            window.close, is_close=True, parent=self._win_group)
        win_row.addWidget(self._w_min)
        win_row.addWidget(self._w_max)
        win_row.addWidget(self._w_close)

        # ── toggle (centre) ───────────────────────────────────────
        self._toggle = OsToggle(on_toggle=self._on_os_switched, parent=self)

        # Assemble row
        row.addWidget(self._mac_group,  0)
        row.addStretch(1)
        row.addWidget(self._toggle,     0, Qt.AlignVCenter)
        row.addStretch(1)
        row.addWidget(self._win_group,  0)

    # ── toggle callback ───────────────────────────────────────────
    def _on_os_switched(self, mac_mode: bool):
        self._mac_mode = mac_mode
        self._mac_group.setVisible(mac_mode)
        self._win_group.setVisible(not mac_mode)
        self.update()

    # ── drag ─────────────────────────────────────────────────────
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

    # ── paint the bar background — same colour as window body, no visible seam ──
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG))   # ← uses the same BG constant as the window body
        # Only round the TOP two corners; bottom edge is flat against content
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


# ─────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(700, 450)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = TitleBar(self)
        root.addWidget(self.title_bar)

        self.content = QWidget(self)
        self.content.setStyleSheet("background: transparent;")
        root.addWidget(self.content, 1)

        # Content area
        cl = QVBoxLayout(self.content)
        cl.setContentsMargins(32, 24, 32, 32)
        cl.setAlignment(Qt.AlignCenter)

        lbl = QLabel("Your content goes here")
        lbl.setFont(QFont("Georgia", 15))
        lbl.setStyleSheet("color: #5a4a2a; background: transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        cl.addWidget(lbl)

    # ── paint the whole window with full rounded corners ──────────
    def paintEvent(self, e):
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())