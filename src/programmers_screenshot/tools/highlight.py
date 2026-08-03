"""A marker pen: a translucent wash that tints without hiding."""

from .. import painting
from ..settings import ColourSetting, WidthSetting
from .items import Highlight
from .pen import PenTool

YELLOW = (1.00, 0.95, 0.25)
GREEN = (0.55, 0.95, 0.35)
CYAN = (0.45, 0.85, 1.00)
PINK = (1.00, 0.55, 0.80)

# Its own palette, not the shared one. Multiplying by white changes nothing
# and multiplying by black turns the page black, so two of the six swatches
# would be useless and one actively wrong.
INK = ColourSetting(
    "highlight-ink",
    "Ink",
    YELLOW,
    swatches=(YELLOW, GREEN, CYAN, PINK),
    names=("Yellow", "Green", "Cyan", "Pink"),
)

# Its own thickness too: a highlighter at 2 px is a pen.
THICKNESS = WidthSetting(
    "highlight-width", "Width", 20,
    ((12, "12 px"), (20, "20 px"), (32, "32 px")),
)


class HighlighterTool(PenTool):
    """Freehand, like the pen, but laid down as ink rather than paint."""

    name = "highlight"
    label = "Highlighter"
    settings = (INK, THICKNESS)

    def _stroke(self):
        return Highlight(
            self._points,
            self._values.get("highlight-ink", INK.default),
            self._values.get("highlight-width", THICKNESS.default),
        )

    def draw_icon(self, cr, box, colour):
        """A chisel tip on a diagonal, wider than the pen's nib."""
        painting.use(cr, colour)
        cr.set_line_width(5.0)
        cr.set_line_cap(0)  # butt, so it reads as a flat chisel
        cr.move_to(box.x + 9, box.bottom - 8)
        cr.line_to(box.right - 10, box.y + 9)
        cr.stroke()
        cr.set_line_width(1.6)
        cr.move_to(box.x + 6, box.bottom - 5)
        cr.line_to(box.right - 7, box.bottom - 5)
        cr.stroke()
