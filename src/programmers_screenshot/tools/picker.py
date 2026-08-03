"""An eyedropper: click a pixel, get its colour on the clipboard.

The odd one out. Every other tool leaves something on the scene; this one
reads a pixel and writes to the clipboard, and the scene is untouched. So
there is nothing to undo and nothing of it in the captured image — only the
readout it leaves on screen so you can see that it worked.
"""

import cairo

from .. import output, painting, theme
from ..geometry import Rect
from ..settings import ChoiceSetting
from .base import Tool

HEX = "hex"
RGB = "rgb"

FORMAT = ChoiceSetting(
    "colour-format", "Copy as", HEX, ((HEX, "#hex"), (RGB, "rgb()"))
)

SWATCH = 16
GAP = 8


def read_pixel(canvas, point):
    """The colour of one pixel of the frozen screen, as 0-255 ints.

    Painted through a one-pixel surface rather than read out of the frozen
    one directly: once the overlay is realised that surface lives on the X
    server and has no pixels to read on this side.
    """
    x = point[0] * canvas.scale
    y = point[1] * canvas.scale
    tiny = cairo.ImageSurface(cairo.FORMAT_RGB24, 1, 1)
    cr = cairo.Context(tiny)
    cr.set_source_surface(canvas.surface, -x, -y)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
    tiny.flush()
    data = tiny.get_data()
    return (data[2], data[1], data[0])  # the surface is BGRA in memory


def format_colour(rgb, style):
    if style == RGB:
        return "rgb(%d, %d, %d)" % rgb
    return "#%02X%02X%02X" % rgb


class PickerTool(Tool):
    """Click a pixel; its colour goes on the clipboard."""

    name = "picker"
    label = "Colour picker"
    settings = (FORMAT,)

    def __init__(self):
        self._picked = None  # (point, rgb, text), kept only to show you it worked
        self._style = FORMAT.default

    def begin(self, point, values):
        self._style = values.get("colour-format", FORMAT.default)

    def finish(self, point, shift=False):
        """Picks on release, like every other tool acts on release.

        Returns None: nothing joins the scene, so there is nothing to undo.
        """
        if self.canvas is None:
            return None
        rgb = read_pixel(self.canvas, point)
        text = format_colour(rgb, self._style)
        output.copy_text(text)
        self._picked = (point, rgb, text)
        return None

    def settings_changed(self, values):
        """Re-format what is already showing, so switching between #hex and
        rgb() answers the question you just asked rather than the next one."""
        self._style = values.get("colour-format", self._style)
        if self._picked:
            point, rgb, _text = self._picked
            text = format_colour(rgb, self._style)
            output.copy_text(text)
            self._picked = (point, rgb, text)

    def cancel(self):
        self._picked = None

    # -- drawing -----------------------------------------------------------

    def preview(self, cr, canvas):
        """The readout for the last pick. Copying with nothing to show for it
        feels broken, and this is not on the scene so it stays out of the
        capture."""
        if not self._picked:
            return
        point, rgb, text = self._picked
        box = self._readout(cr, text, point)
        painting.fill_rounded(cr, box, theme.LABEL_BG, 4)

        swatch = Rect(
            box.x + painting.LABEL_PAD_X,
            box.y + (box.height - SWATCH) / 2,
            SWATCH,
            SWATCH,
        )
        painting.use(cr, tuple(channel / 255 for channel in rgb))
        cr.rectangle(swatch.x, swatch.y, swatch.width, swatch.height)
        cr.fill()
        painting.use(cr, theme.SWATCH_EDGE)
        cr.set_line_width(1.0)
        cr.rectangle(swatch.x + 0.5, swatch.y + 0.5, swatch.width - 1, swatch.height - 1)
        cr.stroke()

        painting.select_font(cr, theme.FONT_MONO, theme.FONT_SIZE_LABEL)
        painting.draw_text(
            cr, text, swatch.right + GAP, box.y + painting.LABEL_PAD_Y,
            theme.LABEL_TEXT,
        )

    @staticmethod
    def _readout(cr, text, point):
        """Just below and right of the pick, so the pixel itself stays visible."""
        inner = painting.label_box(cr, text, 0, 0)
        return Rect(
            point[0] + GAP, point[1] + GAP, inner.width + SWATCH + GAP, inner.height
        )

    def bounds(self):
        """Generously, since working out the real width needs a cairo context
        and this only decides how much gets repainted."""
        if not self._picked:
            return None
        point = self._picked[0]
        return Rect(point[0] - 4, point[1] - 4, 280, 48)

    def draw_icon(self, cr, box, colour):
        """A dropper: a slanted body with a point at the bottom left."""
        painting.use(cr, colour)
        cr.set_line_width(2.6)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(box.x + 12, box.bottom - 12)
        cr.line_to(box.right - 9, box.y + 9)
        cr.stroke()
        cr.move_to(box.x + 8, box.bottom - 8)
        cr.line_to(box.x + 14, box.bottom - 10)
        cr.line_to(box.x + 10, box.bottom - 14)
        cr.close_path()
        cr.fill()
