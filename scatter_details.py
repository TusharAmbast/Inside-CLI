"""
scatter_details.py
─────────────────────────────────────────────────────────────────────────────
Detail panel drawn INSIDE paintEvent of ScatterPlotWidget / ScatterPlotElement.

  Box spec (at base 700×450 window, plot area ~600×290)
  ──────────────────────────────────────────────────────
  Size      : 180 × 320 px  (scales with plot area)
  Radius    : 10 px rounded corners  (scales)
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

All size/font constants are BASE values defined at the reference plot size
(BASE_PLOT_W × BASE_PLOT_H). draw_detail_box() derives a scale factor from
the actual plot dimensions and applies it uniformly, so the panel shrinks and
grows with the window.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui  import QPainter, QColor, QPen, QFont, QFontMetrics


# ─── Reference (base) plot dimensions ────────────────────────────────────────
# These match PAD_* in scatter_plot.py at the default 700×450 window.

BASE_PLOT_W = 600   # 700 - PAD_LEFT(50) - PAD_RIGHT(50)
BASE_PLOT_H = 290   # 450 - PAD_TOP(100) - PAD_BOTTOM(60)

# ─── Base box constants (at reference size) ───────────────────────────────────

_BOX_W      = 180
_BOX_H      = 320
_BOX_RADIUS = 10
_BOX_GAP    = 12     # gap between right divider line and box left edge
_PAD_H      = 16     # horizontal text padding inside box
_PAD_V      = 20     # top padding before first text line
_FONT_PARENT =  9    # pt — parent label (muted, small)
_FONT_PROC   = 13    # pt — process name (bold, large)

BORDER_CLR = QColor(63,  72,  101)
BG_CLR     = QColor(245, 242, 233)


# ─── Public constants used by scatter_plot.py ─────────────────────────────────
# These are the BASE values; the actual pixel sizes are computed at draw time.

BOX_W   = _BOX_W
BOX_GAP = _BOX_GAP


# ─── Scale helper ─────────────────────────────────────────────────────────────

def _scale(plot_w: int, plot_h: int) -> float:
    """
    Derive a single scale factor from the actual plot rect.
    We use the minimum of the two axes so the box never overflows.
    Clamped to [0.5, 2.0] for extreme window sizes.
    """
    sw = plot_w / BASE_PLOT_W
    sh = plot_h / BASE_PLOT_H
    return max(0.5, min(2.0, min(sw, sh)))


# ─── Public API ───────────────────────────────────────────────────────────────

def box_rect(plot_x: int, plot_y: int, plot_w: int, plot_h: int) -> tuple:
    """
    Return (x, y, w, h) of the detail box in widget coordinates.
    Box is right-aligned inside the plot area, vertically centred.
    All dimensions scale with the plot area.
    """
    s  = _scale(plot_w, plot_h)
    bw = min(int(_BOX_W * s), plot_w // 3)
    bh = min(int(_BOX_H * s), plot_h - 10)
    x  = plot_x + plot_w - bw          # flush to right divider
    y  = plot_y + (plot_h - bh) // 2   # vertically centred
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
    s  = _scale(plot_w, plot_h)

    pad_h      = max(4,  int(_PAD_H      * s))
    pad_v      = max(6,  int(_PAD_V      * s))
    radius     = max(4,  int(_BOX_RADIUS * s))
    font_par   = max(6,  int(_FONT_PARENT * s))
    font_proc  = max(8,  int(_FONT_PROC   * s))
    gap_lines  = max(2,  int(8 * s))       # gap between parent and proc lines

    bx, by, bw, bh = box_rect(plot_x, plot_y, plot_w, plot_h)
    rect = QRectF(bx + 0.5, by + 0.5, bw - 1, bh - 1)

    # Box background + border
    painter.setBrush(BG_CLR)
    painter.setPen(QPen(BORDER_CLR, 1))
    painter.drawRoundedRect(rect, radius, radius)

    # ── parent name (small, muted) ────────────────────────────────────
    parent_font = QFont("Georgia", font_par)
    painter.setFont(parent_font)
    painter.setPen(QColor(120, 125, 145))
    fm_p = QFontMetrics(parent_font)
    ty   = by + pad_v + fm_p.ascent()
    painter.drawText(bx + pad_h, ty, parent_name or "—")

    # ── process name (larger, bold, dark) ─────────────────────────────
    proc_font = QFont("Georgia", font_proc, QFont.Weight.Bold)
    painter.setFont(proc_font)
    painter.setPen(BORDER_CLR)
    fm_n = QFontMetrics(proc_font)
    ny   = ty + fm_p.descent() + gap_lines + fm_n.ascent()

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
    max_w = bw - pad_h * 2
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
        if ny > by + bh - pad_v:
            break
        painter.drawText(bx + pad_h, ny, ln)
        ny += fm_n.height()
