"""Freehand drawing."""

from .. import painting
from ..settings import COLOUR, WIDTH
from .base import Tool
from .items import Stroke


class PenTool(Tool):
    """Draw a freehand line in the chosen colour and thickness."""

    name = "pen"
    label = "Pen"
    settings = (COLOUR, WIDTH)

    def __init__(self):
        self._points = []
        self._values = {}

    def begin(self, point, values):
        self._points = [point]
        self._values = values

    def extend(self, point, shift=False):
        # Skip repeats: motion events outnumber actual movement.
        if self._points and point == self._points[-1]:
            return
        self._points.append(point)

    def finish(self, point, shift=False):
        if not self._points:
            return None
        self.extend(point)
        stroke = self._stroke()
        self.cancel()
        return stroke

    def cancel(self):
        self._points = []

    def preview(self, cr, canvas):
        if self._points:
            self._stroke().draw(cr)

    def bounds(self):
        return self._stroke().bounds() if self._points else None

    def _stroke(self):
        return Stroke(self._points, self._values.get("colour", COLOUR.default),
                      self._values.get("width", WIDTH.default))

    def draw_icon(self, cr, box, colour):
        """A nib on a diagonal shaft."""
        painting.use(cr, colour)
        cr.set_line_width(1.8)
        cr.set_line_cap(1)
        left, top = box.x + 9, box.y + 9
        right, bottom = box.x + box.width - 9, box.y + box.height - 9
        cr.move_to(left, bottom)
        cr.line_to(right, top)
        cr.stroke()
        # the tip
        cr.move_to(left - 1.5, bottom + 1.5)
        cr.line_to(left + 3.5, bottom - 0.5)
        cr.line_to(left + 0.5, bottom - 3.5)
        cr.close_path()
        cr.fill()
