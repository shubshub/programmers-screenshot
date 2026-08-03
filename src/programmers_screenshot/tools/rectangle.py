"""The region tool: marks out what gets captured."""

from .. import painting
from ..actions import SetRegion
from ..geometry import Rect, square_corner
from .base import MIN_DRAG, DragTool


class RectangleTool(DragTool):
    """Click and drag to set the capture region. A plain click clears it."""

    name = "rectangle"
    label = "Region"
    settings = ()
    sets_region = True

    def complete(self, start, end, values):
        rect = Rect.from_points(start, end)
        if rect.width < MIN_DRAG or rect.height < MIN_DRAG:
            return SetRegion(None)  # a click means "the whole screen again"
        return SetRegion(rect)

    def constrain(self, start, end, values):
        return square_corner(start, end)

    def pending_region(self):
        """The overlay draws this for us, under the annotations — and damages
        the chrome round it, so drag_extent stays the plain rectangle."""
        if not self.dragging:
            return None
        return Rect.from_points(self._start, self._end) or None

    def draw_icon(self, cr, box, colour):
        painting.use(cr, colour)
        cr.set_line_width(1.6)
        cr.set_dash([3.0, 2.5])
        cr.rectangle(box.x + 4.5, box.y + 5.5, box.width - 9, box.height - 11)
        cr.stroke()
        cr.set_dash([])
