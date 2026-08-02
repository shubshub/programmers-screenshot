"""A step counter: numbered badges for annotating a process.

Everything this tool needs is here — the badge, the action that numbers it,
and the tool itself — so it stands as the worked example of adding a tool
being one new file.
"""

from .. import painting, theme
from ..actions import Action
from ..geometry import Rect
from ..settings import COLOUR, ChoiceSetting
from .base import DragTool
from .items import Item

# Above this the fill is light enough that the numeral has to go dark.
LIGHT_FILL = 0.55


def contrasting(colour):
    """Black or white, whichever will be readable on `colour`."""
    red, green, blue = colour[:3]
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return (0, 0, 0) if luminance > LIGHT_FILL else (1, 1, 1)


class SizeSetting(ChoiceSetting):
    """Draws each option as a disc of the size it makes."""

    def draw_option(self, cr, box, value, active):
        if active:
            painting.fill_rounded(cr, box, theme.ACCENT_SOFT, 4)
        largest = max(self.options())
        radius = value / largest * (theme.SETTINGS_OPTION / 2 - 3)
        painting.circle(
            cr,
            box.x + box.width / 2,
            box.y + box.height / 2,
            max(3.0, radius),
            theme.ACCENT if active else theme.SETTINGS_MARK,
        )


# Its own key rather than `width`: setting values are shared by key, and a 2px
# pen width would leave a badge you could not read.
SIZE = SizeSetting("step-size", "Size", 15, ((11, "S"), (15, "M"), (21, "L")))


class Step(Item):
    """A filled disc with a number in it."""

    RING = 1.6      # a ring in the numeral's colour, so the badge has an edge
    TEXT_RATIO = 1.3  # numeral size relative to the radius

    def __init__(self, centre, colour, radius):
        self.centre = centre
        self.colour = colour
        self.radius = radius
        self.number = 0  # assigned when it joins the scene, see AddStep

    def draw(self, cr):
        x, y = self.centre
        ink = contrasting(self.colour)
        painting.circle(cr, x, y, self.radius, self.colour)
        painting.circle_outline(cr, x, y, self.radius - self.RING / 2, ink, self.RING)
        self._draw_number(cr, ink)

    def _draw_number(self, cr, ink):
        """Shrink the numeral rather than let two or three digits spill out."""
        text = str(self.number)
        size = self.radius * self.TEXT_RATIO
        painting.select_font(cr, theme.FONT_UI, size)
        width, _height = painting.text_size(cr, text)

        room = (self.radius - self.RING) * 1.6
        if width > room:
            painting.select_font(cr, theme.FONT_UI, size * room / width)

        x, y = self.centre
        box = Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
        painting.draw_text_centred(cr, text, box, ink)

    def bounds(self):
        x, y = self.centre
        reach = self.radius + 2
        return Rect(x - reach, y - reach, reach * 2, reach * 2)


def next_number(scene):
    return sum(1 for item in scene.items if isinstance(item, Step)) + 1


class AddStep(Action):
    """Numbers the badge as it joins the scene.

    Holding a counter on the tool would drift the moment anything was undone.
    Deriving it here means undo hands the number back, and redo recomputes it
    rather than remembering a stale one.
    """

    def __init__(self, item):
        self.item = item

    def apply(self, scene):
        self.item.number = next_number(scene)
        scene.items.append(self.item)

    def revert(self, scene):
        scene.items.remove(self.item)


class StepTool(DragTool):
    """Click to drop the next numbered badge. Drag to place it exactly."""

    name = "step"
    label = "Step"
    settings = (SIZE, COLOUR)

    def complete(self, start, end, values):
        return AddStep(self._badge(end, values))

    def draw_drag(self, cr, canvas, start, end, values):
        badge = self._badge(end, values)
        badge.number = next_number(canvas.scene)
        badge.draw(cr)

    def drag_extent(self, start, end, values):
        return self._badge(end, values).bounds()

    @staticmethod
    def _badge(centre, values):
        return Step(
            centre,
            values.get("colour", COLOUR.default),
            values.get("step-size", SIZE.default),
        )

    def draw_icon(self, cr, box, colour):
        centre_x = box.x + box.width / 2
        centre_y = box.y + box.height / 2
        radius = 9
        painting.circle(cr, centre_x, centre_y, radius, colour)
        painting.select_font(cr, theme.FONT_UI, 12)
        painting.draw_text_centred(
            cr,
            "1",
            Rect(centre_x - radius, centre_y - radius, radius * 2, radius * 2),
            theme.BAR_BG,
        )
