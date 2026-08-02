"""Annotations, once committed to the scene.

An item is a finished mark. It knows how to draw itself in logical screen
coordinates and roughly where it sits, and nothing else — the same drawing
call is used for the on-screen preview and for baking the captured image.

bounds() must cover everything draw() paints, including the stroke overhanging
its endpoints. Report it too small and the item smears during a drag, because
partial redraws trust it.
"""

import math

from .. import painting
from ..geometry import Rect

ROUND = 1  # cairo.LINE_CAP_ROUND / LINE_JOIN_ROUND


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
        cr.set_line_cap(ROUND)
        cr.set_line_join(ROUND)

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


class Shape(Item):
    """A stroked shape spanning two corners of a drag."""

    def __init__(self, start, end, colour, width):
        self.start = start
        self.end = end
        self.colour = colour
        self.width = width

    def _stroke_style(self, cr):
        painting.use(cr, self.colour)
        cr.set_line_width(self.width)
        cr.set_line_cap(ROUND)
        cr.set_line_join(ROUND)

    def _padded(self, pad):
        (x0, y0), (x1, y1) = self.start, self.end
        return Rect(
            min(x0, x1) - pad,
            min(y0, y1) - pad,
            abs(x1 - x0) + pad * 2,
            abs(y1 - y0) + pad * 2,
        )

    def bounds(self):
        return self._padded(self.width / 2 + 1)


class Line(Shape):
    """A straight line between the two ends of the drag."""

    def draw(self, cr):
        cr.save()
        self._stroke_style(cr)
        cr.move_to(*self.start)
        cr.line_to(*self.end)
        cr.stroke()
        cr.restore()


class Ellipse(Shape):
    """An outline inscribed in the drag box. Stroke only: never hides what is
    behind it, which is the point of ringing something."""

    def draw(self, cr):
        box = Rect.from_points(self.start, self.end)
        if box.width < 1 or box.height < 1:
            return
        # Build the path under a scaled transform, then restore before
        # stroking, so the line width stays even instead of being squashed
        # along with the circle.
        cr.save()
        cr.new_path()
        cr.translate(box.x + box.width / 2, box.y + box.height / 2)
        cr.scale(box.width / 2, box.height / 2)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()

        cr.save()
        self._stroke_style(cr)
        cr.stroke()
        cr.restore()


class Arrow(Shape):
    """A line with a head at the end you dragged to."""

    HEAD_RATIO = 3.2      # of the line width
    HEAD_MINIMUM = 11.0   # px, so thin arrows still read as arrows
    HEAD_SPREAD = 0.42    # radians either side of the shaft

    def head_length(self):
        return max(self.width * self.HEAD_RATIO, self.HEAD_MINIMUM)

    def draw(self, cr):
        (x0, y0), (x1, y1) = self.start, self.end
        if (x0, y0) == (x1, y1):
            return

        cr.save()
        self._stroke_style(cr)
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.stroke()

        angle = math.atan2(y1 - y0, x1 - x0)
        length = self.head_length()
        for side in (1, -1):
            back = angle + math.pi + side * self.HEAD_SPREAD
            cr.move_to(x1, y1)
            cr.line_to(x1 + length * math.cos(back), y1 + length * math.sin(back))
        cr.stroke()
        cr.restore()

    def bounds(self):
        # The head sweeps back from the tip, so it stays within head_length of
        # it; padding the whole box by that is generous but always right.
        return self._padded(self.head_length() + self.width / 2 + 1)
