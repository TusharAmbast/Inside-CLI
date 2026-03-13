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
  Content   : parent name (muted, small)
            + process name (bold, large)
            + thin divider line
            + AI explanation text (wrapped, streaming-friendly)

  Position  : fixed on the RIGHT side of the plot area, vertically centred
              between the top and bottom divider lines.
              The plot's usable X width shrinks by BOX_W + BOX_GAP so blobs
              LERP left to make room.

This module only exports constants + a draw function — no QWidget subclass.
ScatterPlotWidget calls draw_detail_box(painter, ...) inside its paintEvent.
"""

from PySide6.QtCore import QRectF, Qt
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
    bh = min(BOX_H, plot_h - 10)
    bw = min(BOX_W, plot_w // 3)
    x  = plot_x + plot_w - bw
    y  = plot_y + (plot_h - bh) // 2
    return x, y, bw, bh


def _wrap_text(text: str, font: QFont, max_w: int) -> list[str]:
    """
    Word-wrap `text` to fit within max_w pixels using the given font.
    Returns a list of lines ready for drawText().
    """
    fm    = QFontMetrics(font)
    words = text.split()
    lines = []
    line  = ""
    for word in words:
        test = (line + " " + word).strip()
        if fm.horizontalAdvance(test) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_detail_box(painter: QPainter,
                    plot_x: int, plot_y: int, plot_w: int, plot_h: int,
                    proc_name: str, parent_name: str,
                    ai_text: str = ""):
    """
    Draw the rounded detail card at its fixed position.
    Call this inside paintEvent AFTER drawing blobs/belts.

    ai_text: the LLM explanation string.
             Pass "⏳ Loading explanation..." while the thread is running,
             then update self._panel_ai_text and call self.update() when done.
    """
    bx, by, bw, bh = box_rect(plot_x, plot_y, plot_w, plot_h)
    rect = QRectF(bx + 0.5, by + 0.5, bw - 1, bh - 1)

    # ── Box background + border ───────────────────────────────────────
    painter.setBrush(BG_CLR)
    painter.setPen(QPen(BORDER_CLR, 1))
    painter.drawRoundedRect(rect, BOX_RADIUS, BOX_RADIUS)

    max_w = bw - PAD_H * 2   # usable text width inside the box

    # ── Parent name (small, muted) ────────────────────────────────────
    parent_font = QFont("Georgia", 9)
    painter.setFont(parent_font)
    painter.setPen(QColor(120, 125, 145))
    fm_p = QFontMetrics(parent_font)
    ty   = by + PAD_V + fm_p.ascent()
    painter.drawText(bx + PAD_H, ty, parent_name or "—")

    # ── Process name (larger, bold, dark) — word-wrapped ─────────────
    proc_font = QFont("Georgia", 13, QFont.Weight.Bold)
    painter.setFont(proc_font)
    painter.setPen(BORDER_CLR)
    fm_n = QFontMetrics(proc_font)
    ny   = ty + fm_p.descent() + 8 + fm_n.ascent()

    # Wrap the process name in case it's long
    for ln in _wrap_text(proc_name, proc_font, max_w):
        if ny > by + bh - PAD_V:
            break
        painter.drawText(bx + PAD_H, ny, ln)
        ny += fm_n.height()

    # ── Thin divider line between header and AI text ──────────────────
    divider_y = ny + 10
    painter.setPen(QPen(QColor(63, 72, 101, 60), 1))
    painter.drawLine(bx + PAD_H, divider_y,
                     bx + bw - PAD_H, divider_y)

    # ── AI explanation text (small, word-wrapped) ─────────────────────
    ai_font = QFont("Georgia", 8)
    painter.setFont(ai_font)
    fm_ai   = QFontMetrics(ai_font)
    line_h  = fm_ai.height() + 2   # a little extra leading

    # Clip drawing to stay inside the box bottom
    clip_bottom = by + bh - PAD_V

    # Show muted colour for loading state, normal colour for real text
    if ai_text.startswith("⏳"):
        painter.setPen(QColor(140, 140, 160, 180))
    else:
        painter.setPen(QColor(63, 72, 101, 210))

    ay = divider_y + 14 + fm_ai.ascent()  # first text line Y

    for ln in _wrap_text(ai_text, ai_font, max_w):
        if ay > clip_bottom:
            # Too long to fit — draw "…" on last visible line
            painter.drawText(bx + PAD_H, ay - line_h + fm_ai.ascent(), "…")
            break
        painter.drawText(bx + PAD_H, ay, ln)
        ay += line_h