"""Redaction: cover something with a solid bar.

For sharing a screenshot that has a token, an email address or a customer
name in it. The fill replaces the pixels, so there is nothing left in the
exported image to recover — unlike pixelation, whose block averages leak.
"""

from .. import painting
from ..geometry import Rect
from ..settings import ColourSetting
from .base import ShapeTool
from .items import Redaction

BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)

# Its own key rather than the shared colour: a redaction bar wants to be black
# or white, and inheriting whatever the pen was last set to would give a red
# one. Truly black, too, rather than the palette's near-black.
FILL = ColourSetting(
    "redact-fill", "Fill", BLACK, swatches=(BLACK, WHITE), names=("Black", "White")
)


class RedactTool(ShapeTool):
    """Drag a rectangle and it is filled solid."""

    name = "redact"
    label = "Redact"
    settings = (FILL,)

    def make_item(self, start, end, values):
        if not Rect.from_points(start, end):
            return None
        # Width is meaningless for a fill; Shape wants one, so it gets zero.
        return Redaction(start, end, values.get("redact-fill", FILL.default), 0)

    def draw_icon(self, cr, box, colour):
        """A censor bar."""
        painting.use(cr, colour)
        bar = Rect(box.x + 6, box.y + box.height / 2 - 4, box.width - 12, 8)
        painting.rounded_rect(cr, bar, 2)
        cr.fill()
