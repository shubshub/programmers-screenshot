"""Pixelation: coarse blocks over a rectangle.

For faces, unrelated windows and incidental clutter. **Not** for secrets —
pixelation only averages the pixels, and the averages leak: pixelated text can
be recovered by rendering candidate strings, pixelating them the same way and
matching. Use the redaction tool for anything that must not get out.

The blocks are baked when the drag ends: the tool crops the frozen screen,
shrinks it, and hands the item its own small surface. The item then draws that
scaled back up, so it needs nothing from the overlay afterwards and works
unchanged when the capture is rendered.
"""

import cairo

from .. import painting, theme
from ..geometry import Rect
from ..settings import ChoiceSetting
from .base import ShapeTool
from .items import Item

class BlockSetting(ChoiceSetting):
    """Draws each option as a square of the size it makes."""

    draws_caption = False

    def draw_option(self, cr, box, value, active):
        if active:
            painting.fill_rounded(cr, box, theme.ACCENT_SOFT, 4)
        largest = max(self.options())
        side = max(4.0, value / largest * (theme.SETTINGS_OPTION - 10))
        painting.use(cr, theme.ACCENT if active else theme.SETTINGS_MARK)
        cr.rectangle(
            box.x + (box.width - side) / 2,
            box.y + (box.height - side) / 2,
            side,
            side,
        )
        cr.fill()


# Its own key: "width" means stroke thickness, and a 2px block is not a block.
BLOCK = BlockSetting(
    "pixel-block", "Blocks", 14, ((8, "Fine"), (14, "Medium"), (24, "Coarse"))
)


class Pixelation(Item):
    """A rectangle of the screen, shrunk and drawn back blocky."""

    def __init__(self, rect, blocks, block):
        self.rect = rect
        self.blocks = blocks  # a small ImageSurface, one pixel per block
        self.block = block

    def paint(self, cr):
        wide = self.blocks.get_width()
        tall = self.blocks.get_height()
        if not wide or not tall:
            return
        cr.save()
        cr.rectangle(self.rect.x, self.rect.y, self.rect.width, self.rect.height)
        cr.clip()
        cr.translate(self.rect.x, self.rect.y)
        cr.scale(self.rect.width / wide, self.rect.height / tall)
        cr.set_source_surface(self.blocks, 0, 0)
        # Nearest, or cairo would smooth the blocks straight back out again.
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()

    def bounds(self):
        return Rect(
            self.rect.x - 1, self.rect.y - 1, self.rect.width + 2, self.rect.height + 2
        )


def shrink(canvas, rect, block):
    """One pixel per block, averaged from the frozen screen.

    The screen is in physical pixels and the rectangle is in logical ones, so
    the source is scaled before it is sampled.
    """
    wide = max(1, int(round(rect.width / block)))
    tall = max(1, int(round(rect.height / block)))
    small = cairo.ImageSurface(cairo.FORMAT_RGB24, wide, tall)

    cr = cairo.Context(small)
    source_width = max(1.0, rect.width * canvas.scale)
    source_height = max(1.0, rect.height * canvas.scale)
    cr.scale(wide / source_width, tall / source_height)
    cr.translate(-rect.x * canvas.scale, -rect.y * canvas.scale)
    cr.set_source_surface(canvas.surface, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)  # average, do not point-sample
    cr.paint()
    small.flush()
    return small


class PixelateTool(ShapeTool):
    """Drag a rectangle and the screen underneath goes blocky."""

    name = "pixelate"
    label = "Pixelate"
    settings = (BLOCK,)

    def make_item(self, start, end, values):
        rect = Rect.from_points(start, end)
        if not rect or self.canvas is None:
            return None
        block = values.get("pixel-block", BLOCK.default)
        return Pixelation(rect, shrink(self.canvas, rect, block), block)

    def draw_drag(self, cr, canvas, start, end, values):
        """Preview from the canvas being drawn to, which saves relying on the
        one stashed at the start of the gesture."""
        rect = Rect.from_points(start, end)
        if not rect:
            return
        block = values.get("pixel-block", BLOCK.default)
        Pixelation(rect, shrink(canvas, rect, block), block).draw(cr)

    def drag_extent(self, start, end, values):
        """The plain rectangle. Asking make_item would shrink the region a
        second time on every motion event for no gain."""
        rect = Rect.from_points(start, end)
        return Rect(rect.x - 1, rect.y - 1, rect.width + 2, rect.height + 2)

    def draw_icon(self, cr, box, colour):
        """A little checkerboard."""
        painting.use(cr, colour)
        side = 5
        origin_x = box.x + (box.width - side * 3) / 2
        origin_y = box.y + (box.height - side * 3) / 2
        for row in range(3):
            for column in range(3):
                if (row + column) % 2:
                    continue
                cr.rectangle(
                    origin_x + column * side, origin_y + row * side, side, side
                )
        cr.fill()
