"""A text tool: click, type, click away.

The first tool whose state outlives a single gesture. It holds a caret and a
growing block of text until something ends it — clicking elsewhere, switching
tools, or capturing — at which point commit() hands the finished text over.
"""

import cairo

from .. import painting, theme
from ..geometry import Rect
from ..settings import COLOUR, ChoiceSetting
from .base import Tool
from .items import Item

PADDING = 6      # px between the text and the edge of its background
CARET_WIDTH = 2

# Its own key rather than `width`, which means stroke thickness elsewhere.
SIZE = ChoiceSetting(
    "text-size", "Size", 20, ((14, "S"), (20, "M"), (28, "L"), (40, "XL"))
)
# Always white when on, so there is nothing to choose but on or off.
BACKGROUND = ChoiceSetting(
    "text-background", "Backing", False, ((False, "Off"), (True, "White"))
)

BACKGROUND_COLOUR = (1, 1, 1)


def _measuring_context():
    """A throwaway context, for sizing text outside of a draw.

    bounds() has to know how wide the text is, and there is no drawing context
    to hand at that point.
    """
    return cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


def layout(lines, size):
    """Line advances and the block size, all from the font's own metrics.

    Measured per line rather than per glyph, and the height comes from the
    font rather than the ink, so a line without descenders does not sit at a
    different spacing from one with them.
    """
    cr = _measuring_context()
    painting.select_font(cr, theme.FONT_UI, size)
    ascent, _descent, line_height = cr.font_extents()[:3]
    widths = [cr.text_extents(line).x_advance for line in lines]
    return {
        "ascent": ascent,
        "line_height": line_height,
        "widths": widths,
        "width": max(widths) if widths else 0.0,
        "height": line_height * len(lines),
    }


class TextBlock(Item):
    """Lines of text, optionally on a white box covering the whole block."""

    def __init__(self, origin, lines, colour, size, background):
        self.origin = origin
        self.lines = tuple(lines)
        self.colour = colour
        self.size = size
        self.background = background

    def box(self):
        """The background rectangle: as wide as the longest line, as tall as
        the paragraph, whether or not it is actually painted."""
        metrics = layout(self.lines, self.size)
        x, y = self.origin
        return Rect(
            x,
            y,
            metrics["width"] + PADDING * 2,
            metrics["height"] + PADDING * 2,
        )

    def draw(self, cr):
        metrics = layout(self.lines, self.size)
        if self.background:
            painting.use(cr, BACKGROUND_COLOUR)
            box = self.box()
            cr.rectangle(box.x, box.y, box.width, box.height)
            cr.fill()

        painting.select_font(cr, theme.FONT_UI, self.size)
        x, y = self.origin
        for index, line in enumerate(self.lines):
            baseline = y + PADDING + metrics["ascent"] + index * metrics["line_height"]
            painting.use(cr, self.colour)
            cr.move_to(x + PADDING, baseline)
            cr.show_text(line)

    def bounds(self):
        box = self.box()
        return Rect(box.x - 2, box.y - 2, box.width + 4, box.height + 4)

    def is_empty(self):
        return not any(line.strip() for line in self.lines)


class TextTool(Tool):
    """Click to place a caret, type, click away to commit."""

    name = "text"
    label = "Text"
    settings = (SIZE, BACKGROUND, COLOUR)

    def __init__(self):
        self._origin = None
        self._lines = [""]
        self._values = {}

    # -- gesture -----------------------------------------------------------

    def begin(self, point, values):
        """A press on the canvas puts the caret here. The overlay has already
        committed whatever was being typed before."""
        self._origin = point
        self._lines = [""]
        self._values = values

    def finish(self, point, shift=False):
        return None  # typing continues after the button comes up

    def cancel(self):
        self._origin = None
        self._lines = [""]

    def commit(self):
        if self._origin is None:
            return None
        block = self._block()
        self.cancel()
        return None if block.is_empty() else block

    @property
    def editing(self):
        return self._origin is not None

    # -- keyboard ----------------------------------------------------------

    def key_press(self, key, text, control, shift):
        if not self.editing:
            return False
        if control:
            # Swallow shortcuts rather than let Ctrl+Z eat a committed item
            # from under someone who is mid-sentence.
            return True
        if key in ("Return", "KP_Enter"):
            self._lines.append("")
            return True
        if key == "BackSpace":
            self._backspace()
            return True
        if key == "Escape":
            self.cancel()
            return True
        if text and text.isprintable():
            self._lines[-1] += text
            return True
        return False

    def _backspace(self):
        if self._lines[-1]:
            self._lines[-1] = self._lines[-1][:-1]
        elif len(self._lines) > 1:
            self._lines.pop()

    # -- drawing -----------------------------------------------------------

    def preview(self, cr, canvas):
        if not self.editing:
            return
        self._block().draw(cr)
        self._draw_caret(cr)

    def _draw_caret(self, cr):
        metrics = layout(self._lines, self._size())
        x, y = self._origin
        top = y + PADDING + metrics["line_height"] * (len(self._lines) - 1)
        painting.use(cr, self._colour())
        cr.rectangle(
            x + PADDING + metrics["widths"][-1],
            top,
            CARET_WIDTH,
            metrics["line_height"],
        )
        cr.fill()

    def bounds(self):
        if not self.editing:
            return None
        box = self._block().bounds()
        # room for the caret sitting past the end of the last line
        return Rect(box.x, box.y, box.width + CARET_WIDTH + 2, box.height)

    def draw_icon(self, cr, box, colour):
        painting.select_font(cr, theme.FONT_UI, 17)
        painting.draw_text_centred(cr, "T", box, colour)

    # -- helpers -----------------------------------------------------------

    def _size(self):
        return self._values.get("text-size", SIZE.default)

    def _colour(self):
        return self._values.get("colour", COLOUR.default)

    def _block(self):
        return TextBlock(
            self._origin,
            self._lines,
            self._colour(),
            self._size(),
            self._values.get("text-background", BACKGROUND.default),
        )
