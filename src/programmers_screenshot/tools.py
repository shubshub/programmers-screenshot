"""Tools the toolbar can activate.

A tool owns one interaction on the frozen screen: it receives pointer events,
draws itself, and says which rectangle the capture button should grab. Adding
a tool means writing one class here and listing it in ``ALL_TOOLS`` — the
toolbar and overlay pick it up with no further changes.
"""

from dataclasses import dataclass

from . import painting, theme
from .geometry import Rect

MIN_DRAG = 4  # px; below this a drag is really just a click


@dataclass
class Canvas:
    """What a tool needs in order to paint itself onto the overlay."""

    surface: object  # the frozen screen, as a cairo surface
    bounds: Rect  # the virtual screen, in logical pixels
    scale: float  # physical pixels per logical pixel


class Tool:
    """Base class. Subclasses override whatever they actually use."""

    name = ""
    label = ""

    def reset(self):
        """Forget any in-progress or finished work."""

    def press(self, x, y):
        """Pointer went down on the canvas."""

    def drag(self, x, y):
        """Pointer moved with the button held."""

    def release(self, x, y):
        """Pointer came back up."""

    def selection(self):
        """The region to capture, or None if the tool has nothing yet."""
        return None

    def draw(self, cr, canvas):
        """Paint onto the dimmed overlay."""

    def draw_icon(self, cr, box, colour):
        """Paint this tool's toolbar icon inside ``box``."""


class RectangleTool(Tool):
    """Click and drag to mark out a rectangular region."""

    name = "rectangle"
    label = "Rectangle"

    def __init__(self):
        self._anchor = None
        self._cursor = None
        self._settled = False

    def reset(self):
        self._anchor = None
        self._cursor = None
        self._settled = False

    def press(self, x, y):
        self._anchor = (x, y)
        self._cursor = (x, y)
        self._settled = False

    def drag(self, x, y):
        if self._anchor is not None:
            self._cursor = (x, y)

    def release(self, x, y):
        if self._anchor is None:
            return
        self._cursor = (x, y)
        rect = Rect.from_points(self._anchor, self._cursor)
        # A stray click clears the selection rather than leaving a sliver.
        if rect.width < MIN_DRAG or rect.height < MIN_DRAG:
            self.reset()
        else:
            self._settled = True

    def selection(self):
        if self._anchor is None or self._cursor is None:
            return None
        rect = Rect.from_points(self._anchor, self._cursor)
        return rect if rect else None

    def draw(self, cr, canvas):
        rect = self.selection()
        if rect is None:
            return
        self._reveal(cr, canvas, rect)
        self._outline(cr, rect)
        self._size_label(cr, canvas, rect)

    def draw_icon(self, cr, box, colour):
        painting.use(cr, colour)
        cr.set_line_width(1.6)
        cr.set_dash([3.0, 2.5])
        inset = Rect(box.x + 4.5, box.y + 5.5, box.width - 9, box.height - 11)
        cr.rectangle(inset.x, inset.y, inset.width, inset.height)
        cr.stroke()
        cr.set_dash([])

    @staticmethod
    def _reveal(cr, canvas, rect):
        """Undim the selection by repainting the frozen screen inside it."""
        cr.save()
        cr.rectangle(rect.x, rect.y, rect.width, rect.height)
        cr.clip()
        cr.set_source_surface(canvas.surface, 0, 0)
        cr.paint()
        cr.restore()

    @staticmethod
    def _outline(cr, rect):
        painting.use(cr, theme.ACCENT)
        cr.set_line_width(1.0)
        cr.rectangle(rect.x + 0.5, rect.y + 0.5, rect.width - 1, rect.height - 1)
        cr.stroke()

        half = theme.HANDLE_SIZE / 2
        for cx, cy in rect.corners:
            cr.rectangle(cx - half, cy - half, theme.HANDLE_SIZE, theme.HANDLE_SIZE)
        cr.fill()

    @staticmethod
    def _size_label(cr, canvas, rect):
        """Pixel dimensions, above the selection or tucked inside if there is
        no room above."""
        pixels = rect.scaled(canvas.scale).rounded()
        text = "%d × %d" % (pixels.width, pixels.height)
        painting.select_font(cr, theme.FONT_MONO, theme.FONT_SIZE_LABEL)
        width, height = painting.text_size(cr, text)

        pad_x, pad_y = 8, 5
        box = Rect(rect.x, rect.y - height - pad_y * 2 - 6,
                   width + pad_x * 2, height + pad_y * 2)
        if box.y < canvas.bounds.y:
            box = Rect(box.x, rect.y + 6, box.width, box.height)
        box = Rect(
            min(max(box.x, 0), max(0, canvas.bounds.width - box.width)),
            min(max(box.y, 0), max(0, canvas.bounds.height - box.height)),
            box.width,
            box.height,
        )

        painting.fill_rounded(cr, box, theme.LABEL_BG, 4)
        painting.draw_text(cr, text, box.x + pad_x, box.y + pad_y, theme.LABEL_TEXT)


ALL_TOOLS = (RectangleTool,)


def build_tools():
    return [factory() for factory in ALL_TOOLS]
