"""Annotations, once committed to the scene.

An item is a finished mark. It knows how to draw itself in logical screen
coordinates and roughly where it sits, and nothing else — the same drawing
call is used for the on-screen preview and for baking the captured image.
"""

from .. import painting
from ..geometry import Rect


class Item:
    """One committed annotation."""

    def draw(self, cr):
        raise NotImplementedError

    def bounds(self):
        """Roughly where this sits, for redrawing only the part that changed.

        None means "no idea", which costs a full repaint but is never wrong.
        """
        return None


class Stroke(Item):
    """A freehand line. A stroke of one point is a dot."""

    def __init__(self, points, colour, width):
        self.points = tuple(points)
        self.colour = colour
        self.width = width

    def draw(self, cr):
        if not self.points:
            return
        cr.save()
        painting.use(cr, self.colour)
        cr.set_line_width(self.width)
        cr.set_line_cap(1)   # cairo.LINE_CAP_ROUND
        cr.set_line_join(1)  # cairo.LINE_JOIN_ROUND

        if len(self.points) == 1:
            x, y = self.points[0]
            cr.move_to(x, y)
            cr.line_to(x, y)  # a round cap on a zero-length line is a dot
        else:
            cr.move_to(*self.points[0])
            for point in self.points[1:]:
                cr.line_to(*point)
        cr.stroke()
        cr.restore()

    def bounds(self):
        if not self.points:
            return None
        xs = [x for x, _ in self.points]
        ys = [y for _, y in self.points]
        pad = self.width / 2 + 1
        return Rect(
            min(xs) - pad,
            min(ys) - pad,
            max(xs) - min(xs) + pad * 2,
            max(ys) - min(ys) + pad * 2,
        )
