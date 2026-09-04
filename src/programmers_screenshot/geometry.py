"""Rectangles and points, in logical screen pixels."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_points(cls, a, b):
        """The rectangle spanned by two corners, in any order."""
        (ax, ay), (bx, by) = a, b
        return cls(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay))

    @classmethod
    def from_geometry(cls, geometry):
        """Adapt a Gdk.Rectangle."""
        return cls(geometry.x, geometry.y, geometry.width, geometry.height)

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    @property
    def corners(self):
        return (
            (self.x, self.y),
            (self.right, self.y),
            (self.x, self.bottom),
            (self.right, self.bottom),
        )

    def contains(self, px, py):
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def translated(self, dx, dy):
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def grown(self, pad):
        """This rectangle, `pad` larger on every side.

        What a bounds() wants: the mark, plus however far its stroke, its
        head or its label overhangs it.
        """
        return Rect(
            self.x - pad, self.y - pad, self.width + pad * 2, self.height + pad * 2
        )

    def scaled(self, factor):
        return Rect(
            self.x * factor, self.y * factor, self.width * factor, self.height * factor
        )

    def rounded(self):
        """Snap to whole pixels, keeping the edges where they were."""
        left, top = round(self.x), round(self.y)
        return Rect(left, top, round(self.right) - left, round(self.bottom) - top)

    def __bool__(self):
        return self.width > 0 and self.height > 0


def square_corner(start, end):
    """Where `end` would be for a square drag, keeping the direction it went."""
    (x0, y0), (x1, y1) = start, end
    size = max(abs(x1 - x0), abs(y1 - y0))
    return (x0 + math.copysign(size, x1 - x0), y0 + math.copysign(size, y1 - y0))


def snap_to_45(start, end):
    """Where `end` would be on the nearest 45 degree ray, same distance out."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    distance = math.hypot(dx, dy)
    if not distance:
        return end
    step = math.pi / 4
    angle = round(math.atan2(dy, dx) / step) * step
    return (x0 + distance * math.cos(angle), y0 + distance * math.sin(angle))


def circle_touches(rect, circle):
    """Whether a disc reaches a rectangle at all.

    Used to skip marks an eraser sweep never came near, rather than making
    every mark punch every disc.
    """
    x, y, radius = circle
    nearest_x = min(max(x, rect.x), rect.right)
    nearest_y = min(max(y, rect.y), rect.bottom)
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius * radius


def union(rects):
    """Smallest rectangle covering all of them."""
    rects = list(rects)
    if not rects:
        return Rect(0, 0, 0, 0)
    x = min(r.x for r in rects)
    y = min(r.y for r in rects)
    return Rect(
        x, y, max(r.right for r in rects) - x, max(r.bottom for r in rects) - y
    )
