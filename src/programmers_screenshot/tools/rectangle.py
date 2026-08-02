"""The region tool: marks out what gets captured."""

from .. import painting
from ..actions import SetRegion
from ..geometry import Rect
from .base import MIN_DRAG, Tool


class RectangleTool(Tool):
    """Click and drag to set the capture region. A plain click clears it."""

    name = "rectangle"
    label = "Region"
    settings = ()

    def __init__(self):
        self._start = None
        self._end = None

    def begin(self, point, values):
        self._start = point
        self._end = point

    def extend(self, point):
        if self._start is not None:
            self._end = point

    def finish(self, point):
        if self._start is None:
            return None
        rect = Rect.from_points(self._start, point)
        self.cancel()
        if rect.width < MIN_DRAG or rect.height < MIN_DRAG:
            return SetRegion(None)  # a click means "the whole screen again"
        return SetRegion(rect)

    def cancel(self):
        self._start = None
        self._end = None

    def pending_region(self):
        """The overlay draws this for us, under the annotations."""
        if self._start is None:
            return None
        return Rect.from_points(self._start, self._end) or None

    def bounds(self):
        if self._start is None:
            return None
        return Rect.from_points(self._start, self._end)

    def draw_icon(self, cr, box, colour):
        painting.use(cr, colour)
        cr.set_line_width(1.6)
        cr.set_dash([3.0, 2.5])
        cr.rectangle(box.x + 4.5, box.y + 5.5, box.width - 9, box.height - 11)
        cr.stroke()
        cr.set_dash([])
