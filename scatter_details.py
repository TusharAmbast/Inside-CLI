"""
scatter_details.py
─────────────────────────────────────────────────────────────────────────────
Detail panel drawn INSIDE paintEvent of ScatterPlotWidget.

  Box spec
  ────────
  Size      : 180 × 320 px
  Radius    : 10 px rounded corners
  Border    : 1 px  rgb(63, 72, 101)
  Background: rgb(245, 242, 233)
  Content   : parent name (muted, small) + process name (bold, large)

  Position  : fixed on the RIGHT side of the plot area, vertically centred
              between the top and bottom divider lines.
              The plot's usable X width shrinks by BOX_W + BOX_GAP so blobs
              LERP left to make room.

This module only exports constants + a draw function — no QWidget subclass.
ScatterPlotWidget calls draw_detail_box(painter, ...) inside its paintEvent.
"""

from PySide6.QtCore import QRectF
from PySide6.QtGui  import QPainter, QColor, QPen, QFont, QFontMetrics


# ─── Box constants ───────────────────────────────────────────────────────────

BOX_W      = 180
BOX_H      = 320
BOX_RADIUS = 10
BOX_GAP    = 12          # gap between right divider line and box left edge
BORDER_CLR = QColor(63,  72,  101)
BG_CLR     = QColor(245, 242, 233)

PAD_H = 16   # horizontal text padding inside box
PAD_V = 20   # top padding before first text line


def box_rect(plot_x: int, plot_y: int, plot_w: int, plot_h: int) -> tuple:
    """
    Return (x, y, w, h) of the detail box in widget coordinates.
    Box is right-aligned inside the plot area, vertically centred.
    Height is clamped so it never exceeds the plot area.
    """
    # Clamp height: at most plot_h - 10 (5px gap top + bottom)
    bh = min(BOX_H, plot_h - 10)
    bw = min(BOX_W, plot_w // 3)          # also clamp width on tiny windows
    x  = plot_x + plot_w - bw             # flush to right divider
    y  = plot_y + (plot_h - bh) // 2      # vertically centred
    return x, y, bw, bh


def draw_detail_box(painter: QPainter,
                    plot_x: int, plot_y: int, plot_w: int, plot_h: int,
                    proc_name: str, parent_name: str):
    """
    Draw the rounded detail card at its fixed position.
    Call this inside paintEvent AFTER drawing blobs/belts.
    """
    bx, by, bw, bh = box_rect(plot_x, plot_y, plot_w, plot_h)
    rect = QRectF(bx + 0.5, by + 0.5, bw - 1, bh - 1)

    painter.setBrush(BG_CLR)
    painter.setPen(QPen(BORDER_CLR, 1))
    painter.drawRoundedRect(rect, BOX_RADIUS, BOX_RADIUS)

    # ── parent name (small, muted) ────────────────────────────────────
    parent_font = QFont("Georgia", 9)
    painter.setFont(parent_font)
    painter.setPen(QColor(120, 125, 145))
    fm_p = QFontMetrics(parent_font)
    ty   = by + PAD_V + fm_p.ascent()
    painter.drawText(bx + PAD_H, ty, parent_name or "—")

    # ── process name (larger, bold, dark) ─────────────────────────────
    proc_font = QFont("Georgia", 13, QFont.Weight.Bold)
    painter.setFont(proc_font)
    painter.setPen(BORDER_CLR)
    fm_n = QFontMetrics(proc_font)
    ny   = ty + fm_p.descent() + 8 + fm_n.ascent()

    max_w = bw - PAD_H * 2
    chars = list(proc_name)
    line  = ""
    lines = []
    for ch in chars:
        test = line + ch
        if fm_n.horizontalAdvance(test) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = ch
    if line:
        lines.append(line)
    if not lines:
        lines = [proc_name]

    for ln in lines:
        if ny > by + bh - PAD_V:
            break
        painter.drawText(bx + PAD_H, ny, ln)
        ny += fm_n.height()