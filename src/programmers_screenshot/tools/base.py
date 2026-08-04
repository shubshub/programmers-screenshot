"""What a tool is.

A tool turns pointer gestures into a change to the scene. It receives the
gesture, draws its own in-progress preview, and on release hands back either
an Action or — the usual case — a bare Item meaning "add this".

Nearly every tool is the same gesture: press, drag, and on release something
is set. That machinery lives in DragTool, which the region tool and every
shape tool build on. Reach for Tool directly only for something that is not a
drag at all.
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

    #: True if a gesture from this tool sets the capture region. Starting one
    #: drops whatever region is already there.
    sets_region = False

    #: The overlay hands the active tool a Canvas when a gesture starts, so a
    #: tool can read the frozen screen — pixelating has to sample it. Drawing
    #: gets one passed in and should use that; this is for the rest.
    canvas = None

    # -- gesture -----------------------------------------------------------

    def begin(self, point, values):
        """Pointer went down. `values` is a snapshot of this tool's settings."""

    def extend(self, point, shift=False):
        """Pointer moved with the button held."""

    def finish(self, point, shift=False):
        """Pointer came up. Return an Action, an Item, or None for nothing."""
        return None

    def cancel(self):
        """Abandon whatever is in progress, keeping none of it."""

    def settings_changed(self, values):
        """A setting was changed while this tool is active.

        `values` is a fresh snapshot, the same shape begin() is handed.

        Gesture tools ignore this: they take a snapshot at begin() so a stroke
        keeps the colour it started with, and nothing can be clicked mid-drag
        anyway. A tool with state that outlives one gesture re-reads them here,
        so the change shows on what is already on screen.
        """

    def commit(self):
        """Finish anything in progress. Return an Action, an Item, or None.

        Most tools finish on release and have nothing left over, so the default
        is None. A tool whose state outlives a single gesture — text being
        typed, say — returns it here. The overlay calls this before capturing,
        before switching tools and before a fresh gesture starts, so nothing
        half-finished is silently lost.
        """
        return None

    # -- keyboard ----------------------------------------------------------

    def key_press(self, key, text, control, shift):
        """Handle a key. Return True to stop the overlay acting on it too.

        The active tool gets first refusal, because the overlay's own bindings
        collide with typing: Enter captures, Escape closes. `key` is a GDK key
        name such as "Return"; `text` is what the key would type, if anything.
        """
        return False

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

    def pending_erasure(self):
        """Discs this tool is rubbing out right now, before it commits them.

        The overlay draws every mark through these, so an eraser takes effect
        under the pointer instead of only when the button comes up. Same idea
        as pending_region(): the gesture has to change what is already on the
        canvas, which a preview drawn on top cannot do.
        """
        return ()

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


class DragTool(Tool):
    """Anything defined by dragging from A to B.

    Owns the gesture — where it started, where it is now, and the settings it
    began with — so a subclass only says three things: what a finished drag
    means, what it looks like on the way, and how much of the screen it
    touches.
    """

    def __init__(self):
        self._start = None
        self._end = None
        self._values = {}

    # -- what subclasses fill in -------------------------------------------

    def complete(self, start, end, values):
        """The drag ended. Return an Action, an Item, or None."""
        raise NotImplementedError

    def draw_drag(self, cr, canvas, start, end, values):
        """Optional: paint the drag while it is happening."""

    def drag_extent(self, start, end, values):
        """Optional: everything draw_drag() touches, for partial redraws.

        The default is the rectangle between the two points, which is too
        small for anything with a stroke width — a line overhangs its ends by
        half its width, an arrowhead by several times more. Override it, or
        the drag will smear.
        """
        return Rect.from_points(start, end)

    def constrain(self, start, end, values):
        """Where the drag ends while Shift is held. Unconstrained by default."""
        return end

    # -- the machinery, written once ---------------------------------------

    @property
    def dragging(self):
        return self._start is not None

    def begin(self, point, values):
        self._start = point
        self._end = point
        self._values = values

    def extend(self, point, shift=False):
        if self.dragging:
            self._end = self._resolve(point, shift)

    def finish(self, point, shift=False):
        if not self.dragging:
            return None
        end = self._resolve(point, shift)
        result = self.complete(self._start, end, self._values)
        self.cancel()
        return result

    def cancel(self):
        self._start = None
        self._end = None

    def preview(self, cr, canvas):
        if self.dragging:
            self.draw_drag(cr, canvas, self._start, self._end, self._values)

    def bounds(self):
        if not self.dragging:
            return None
        return self.drag_extent(self._start, self._end, self._values)

    def _resolve(self, point, shift):
        if shift:
            return self.constrain(self._start, point, self._values)
        return point


class ShapeTool(DragTool):
    """A drag that leaves a shape behind. Implement make_item() and you are done."""

    def make_item(self, start, end, values):
        """Return the Item for a drag from `start` to `end`, or None."""
        raise NotImplementedError

    def complete(self, start, end, values):
        return self.make_item(start, end, values)

    def draw_drag(self, cr, canvas, start, end, values):
        item = self.make_item(start, end, values)
        if item is not None:
            item.draw(cr)

    def drag_extent(self, start, end, values):
        """Ask the shape how big it really is, stroke width and all."""
        item = self.make_item(start, end, values)
        return item.bounds() if item is not None else None
