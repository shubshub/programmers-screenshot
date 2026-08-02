"""Straight lines, outlined circles and arrows.

One tool with a shape selector rather than three: all three are the same
gesture, and they share the same colour and thickness, so putting them behind
one button keeps the toolbar short.
"""

from .. import painting, theme
from ..geometry import snap_to_45, square_corner
from ..settings import COLOUR, WIDTH, ChoiceSetting
from .base import ShapeTool
from .items import Arrow, Ellipse, Line

LINE = "line"
CIRCLE = "circle"
ARROW = "arrow"

SHAPES = {LINE: Line, CIRCLE: Ellipse, ARROW: Arrow}


class ShapeSetting(ChoiceSetting):
    """Draws each option as the shape it makes, rather than as a caption."""

    PREVIEW_WIDTH = 1.8

    def draw_option(self, cr, box, value, active):
        if active:
            painting.fill_rounded(cr, box, theme.ACCENT_SOFT, 4)
        colour = theme.ACCENT if active else theme.SETTINGS_MARK
        inset = 7
        start = (box.x + inset, box.bottom - inset)
        end = (box.right - inset, box.y + inset)
        SHAPES[value](start, end, colour, self.PREVIEW_WIDTH).draw(cr)


SHAPE = ShapeSetting(
    "shape", "Shape", LINE, ((LINE, "Line"), (CIRCLE, "Circle"), (ARROW, "Arrow"))
)


class LineTool(ShapeTool):
    """Drag out a line, an outlined circle, or an arrow."""

    name = "line"
    label = "Line"
    settings = (SHAPE, COLOUR, WIDTH)

    def make_item(self, start, end, values):
        if start == end:
            return None
        shape = SHAPES[values.get("shape", SHAPE.default)]
        return shape(
            start,
            end,
            values.get("colour", COLOUR.default),
            values.get("width", WIDTH.default),
        )

    def constrain(self, start, end, values):
        """Shift squares a circle off, and snaps a line or arrow to 45s."""
        if values.get("shape") == CIRCLE:
            return square_corner(start, end)
        return snap_to_45(start, end)

    def draw_icon(self, cr, box, colour):
        """A segment with handles at both ends, so it does not read as the
        pen's diagonal nib."""
        left, bottom = box.x + 9, box.bottom - 9
        right, top = box.right - 9, box.y + 9
        painting.use(cr, colour)
        cr.set_line_width(1.6)
        cr.move_to(left, bottom)
        cr.line_to(right, top)
        cr.stroke()
        for x, y in ((left, bottom), (right, top)):
            painting.circle(cr, x, y, 2.8, colour)
