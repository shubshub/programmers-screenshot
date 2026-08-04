"""Rubbing out what you drag over.

Drag it across the canvas and it takes out the parts of any mark it sweeps
through — half a pen stroke, a bite out of a rectangle, a hole in a pixelate
block. A plain click with no drag takes the whole mark instead, which is the
quick way to get rid of something outright.

Nothing is rasterised. The eraser records the discs it swept and hands them
to the marks it touched; each one punches those holes at draw time, so they
come out as sharp in the captured PNG as they look on screen. See
Item.draw().
"""

from .. import painting, theme
from ..actions import Compound, RemoveItem, ReplaceItem
from ..geometry import Rect, circle_touches, union
from ..settings import ChoiceSetting
from .base import MIN_DRAG, DragTool
from .step import RemoveStep, Step

SIZE = ChoiceSetting(
    "eraser-size", "Size", 18, ((10, "S"), (18, "M"), (32, "L"), (56, "XL"))
)

# How far apart swept discs may be before gaps show between them. The pointer
# can jump a long way between motion events, and an eraser that skips is worse
# than a slow one.
STEP = 4.0


class EraserTool(DragTool):
    """Drag to rub out what you touch. Click to remove a whole mark."""

    name = "eraser"
    label = "Eraser"
    settings = (SIZE,)

    def __init__(self):
        super().__init__()
        self._swept = []          # (x, y) centres of the discs dragged through

    # -- gesture ------------------------------------------------------------

    def begin(self, point, values):
        super().begin(point, values)
        self._swept = [point]

    def extend(self, point, shift=False):
        super().extend(point, shift)
        self._sweep_to(point)

    def _sweep_to(self, point):
        """Fill in the gap since the last motion event.

        Discs are laid along the way rather than only where events land, or a
        quick flick leaves the mark it crossed untouched between samples.
        """
        last = self._swept[-1]
        dx, dy = point[0] - last[0], point[1] - last[1]
        distance = (dx * dx + dy * dy) ** 0.5
        if not distance:
            return  # the pointer has not actually moved
        for step in range(1, int(distance / STEP) + 1):
            along = step * STEP / distance
            self._swept.append((last[0] + dx * along, last[1] + dy * along))
        self._swept.append(point)

    def cancel(self):
        super().cancel()
        self._swept = []

    def complete(self, start, end, values):
        radius = self._radius(values)
        if self._is_a_click(start, end):
            whole = self._topmost(end)
            if whole is None:
                return None
            return RemoveStep(whole) if isinstance(whole, Step) else RemoveItem(whole)

        circles = [(x, y, radius) for x, y in self._swept]
        changes = self._erasures(circles)
        return Compound(changes) if changes else None

    @staticmethod
    def _is_a_click(start, end):
        return (abs(end[0] - start[0]) < MIN_DRAG
                and abs(end[1] - start[1]) < MIN_DRAG)

    def _erasures(self, circles):
        """One ReplaceItem per mark the sweep actually reached."""
        if self.canvas is None:
            return []
        changes = []
        for item in self.canvas.scene.items:
            box = item.bounds()
            if box is None:
                continue
            touching = [c for c in circles if circle_touches(box, c)]
            if touching:
                changes.append(ReplaceItem(item, item.with_erasure(touching)))
        return changes

    def pending_erasure(self):
        """What the sweep has taken out so far.

        The overlay draws the marks through this, so the hole opens up under
        the pointer rather than appearing when the button comes up.
        """
        if not self.dragging or not self._swept:
            return ()
        radius = self._radius(self._values)
        return [(x, y, radius) for x, y in self._swept]

    def commit(self):
        """Land a sweep that is still in progress.

        Only reachable by pressing Enter to capture mid-drag, but without it
        the screen would show the holes and the saved PNG would not.
        """
        if not self.dragging or self._is_a_click(self._start, self._end):
            return None
        changes = self._erasures(self.pending_erasure())
        self.cancel()
        return Compound(changes) if changes else None

    def _topmost(self, point):
        """The last-drawn mark covering this point, which is the visible one."""
        if self.canvas is None:
            return None
        for item in reversed(self.canvas.scene.items):
            box = item.bounds()
            if box is not None and box.contains(*point):
                return item
        return None

    def _radius(self, values):
        return values.get("eraser-size", SIZE.default) / 2.0

    # -- drawing ------------------------------------------------------------

    def draw_drag(self, cr, canvas, start, end, values):
        """Just the head of the eraser. The rubbing out is already visible --
        the overlay draws the marks through pending_erasure() -- so drawing
        the trail as well would only put something back over the hole."""
        radius = self._radius(values)
        painting.use(cr, theme.SWATCH_RING)
        cr.set_line_width(1.0)
        cr.new_sub_path()
        cr.arc(end[0], end[1], radius, 0, 6.2831853)
        cr.stroke()

    def drag_extent(self, start, end, values):
        radius = self._radius(values)
        boxes = [
            Rect(x - radius, y - radius, radius * 2, radius * 2)
            for x, y in self._swept
        ]
        return union(boxes) if boxes else None

    def draw_icon(self, cr, box, colour):
        """A rubber held at an angle, with a band across the worn end."""
        painting.use(cr, colour)
        cr.set_line_width(1.6)
        left, right = box.x + 7, box.right - 7
        top, bottom = box.y + 11, box.bottom - 9
        cr.move_to(left, bottom)
        cr.line_to(left + 5, top)
        cr.line_to(right, top)
        cr.line_to(right - 5, bottom)
        cr.close_path()
        cr.stroke()
        cr.move_to(left + 2.5, bottom - 5.5)
        cr.line_to(right - 2.5, bottom - 5.5)
        cr.stroke()


