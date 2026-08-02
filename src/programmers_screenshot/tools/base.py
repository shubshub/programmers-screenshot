"""What a tool is.

A tool turns pointer gestures into a change to the scene. It receives the
gesture, draws its own in-progress preview, and on release hands back either
an Action or — the usual case — a bare Item meaning "add this".

Most tools are "drag from A to B and leave a shape behind"; those want
ShapeTool, which reduces the job to one method.
"""

from .. import painting, theme
from ..geometry import Rect

MIN_DRAG = 4  # px; below this a drag is really a click


class Tool:
    """Base class. Override only what you actually use."""

    name = ""       # stable identifier
    label = ""      # human name, shown as the button tooltip
    icon_text = None  # optional glyph, drawn if draw_icon is not overridden
    settings = ()   # Setting instances this tool exposes

    # -- gesture -----------------------------------------------------------

    def begin(self, point, values):
        """Pointer went down. `values` is a snapshot of this tool's settings."""

    def extend(self, point):
        """Pointer moved with the button held."""

    def finish(self, point):
        """Pointer came up. Return an Action, an Item, or None for nothing."""
        return None

    def cancel(self):
        """Abandon the gesture in progress."""

    # -- drawing -----------------------------------------------------------

    def preview(self, cr, canvas):
        """Draw the gesture in progress, over the dimmed screen.

        This runs after the committed annotations, so anything drawn here sits
        on top of them. A tool that needs to change the backdrop instead —
        undimming part of the screen, say — should use pending_region().
        """

    def pending_region(self):
        """The capture region this tool is dragging out right now, if any.

        The overlay draws it exactly where it draws the committed one: beneath
        the annotations. Without this a tool that undims the screen would paint
        over everything already drawn there.
        """
        return None

    def bounds(self):
        """Where the gesture in progress is, for partial redraws."""
        return None

    def draw_icon(self, cr, box, colour):
        """Paint the toolbar icon. The default renders `icon_text`, so a new
        tool does not have to know any cairo to get a usable button."""
        if not self.icon_text:
            return
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_UI + 2)
        painting.draw_text_centred(cr, self.icon_text, box, colour)


class ShapeTool(Tool):
    """Drag from A to B. Implement make_item() and you are done."""

    def __init__(self):
        self._start = None
        self._end = None
        self._values = {}

    def make_item(self, start, end, values):
        """Return the Item for a drag from `start` to `end`, or None."""
        raise NotImplementedError

    def begin(self, point, values):
        self._start = point
        self._end = point
        self._values = values

    def extend(self, point):
        if self._start is not None:
            self._end = point

    def finish(self, point):
        if self._start is None:
            return None
        item = self.make_item(self._start, point, self._values)
        self.cancel()
        return item

    def cancel(self):
        self._start = None
        self._end = None

    def preview(self, cr, canvas):
        if self._start is None:
            return
        item = self.make_item(self._start, self._end, self._values)
        if item is not None:
            item.draw(cr)

    def bounds(self):
        if self._start is None:
            return None
        return Rect.from_points(self._start, self._end)
