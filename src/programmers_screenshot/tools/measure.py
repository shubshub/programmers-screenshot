"""A ruler: drag between two points and read the distance."""

from .. import painting
from ..geometry import Rect, snap_to_45
from ..settings import COLOUR
from .base import ShapeTool
from .items import Measurement


class MeasureTool(ShapeTool):
    """Drag to measure. Shift snaps to 45s, which is how you get an exactly
    horizontal or vertical reading."""

    name = "measure"
    label = "Measure"
    settings = (COLOUR,)

    def make_item(self, start, end, values):
        if start == end or self.canvas is None:
            return None
        return Measurement(
            start, end, values.get("colour", COLOUR.default), self.canvas.scale
        )

    def draw_drag(self, cr, canvas, start, end, values):
        """Uses the canvas being drawn to, so the reading is right even before
        the gesture has ended."""
        if start == end:
            return
        Measurement(
            start, end, values.get("colour", COLOUR.default), canvas.scale
        ).draw(cr)

    def constrain(self, start, end, values):
        return snap_to_45(start, end)

    def draw_icon(self, cr, box, colour):
        """A rule with ticks along it."""
        painting.use(cr, colour)
        cr.set_line_width(1.6)
        left, right = box.x + 6, box.right - 6
        middle = box.y + box.height / 2 + 3
        cr.rectangle(left, middle - 7, right - left, 7)
        cr.stroke()
        for step in range(1, 4):
            x = left + (right - left) * step / 4
            cr.move_to(x, middle - 7)
            cr.line_to(x, middle - 3)
        cr.stroke()

    def drag_extent(self, start, end, values):
        """The item's own bounds, which allow for the ticks and the readout."""
        if start == end:
            return Rect.from_points(start, end)
        return Measurement(start, end, (0, 0, 0), 1.0).bounds()
