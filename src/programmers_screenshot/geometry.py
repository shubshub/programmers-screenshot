"""Rectangles, in logical screen pixels."""

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

    def scaled(self, factor):
        return Rect(
            self.x * factor, self.y * factor, self.width * factor, self.height * factor
        )

    def rounded(self):
        """Snap to whole pixels, keeping the edges where they were."""
        left, top = round(self.x), round(self.y)
        return Rect(left, top, round(self.right) - left, round(self.bottom) - top)

    def clipped_to(self, other):
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        return Rect(
            x, y, max(0, min(self.right, other.right) - x),
            max(0, min(self.bottom, other.bottom) - y)
        )

    def __bool__(self):
        return self.width > 0 and self.height > 0


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
