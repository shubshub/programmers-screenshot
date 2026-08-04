"""Small cairo helpers shared by the toolbar, the settings and the tools."""

import math

from . import theme
from .geometry import Rect


def use(cr, colour):
    """Set a source colour given as (r, g, b) or (r, g, b, a)."""
    if len(colour) == 4:
        cr.set_source_rgba(*colour)
    else:
        cr.set_source_rgb(*colour)


def rounded_rect(cr, rect, radius=theme.CORNER_RADIUS):
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    radius = min(radius, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + w - radius, y + h - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + h - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()


def fill_rounded(cr, rect, colour, radius=theme.CORNER_RADIUS):
    use(cr, colour)
    rounded_rect(cr, rect, radius)
    cr.fill()


def circle(cr, x, y, radius, colour):
    use(cr, colour)
    cr.arc(x, y, radius, 0, 2 * math.pi)
    cr.fill()


def circle_outline(cr, x, y, radius, colour, line_width):
    use(cr, colour)
    cr.set_line_width(line_width)
    cr.arc(x, y, radius, 0, 2 * math.pi)
    cr.stroke()


def select_font(cr, family, size):
    cr.select_font_face(family)
    cr.set_font_size(size)


def text_size(cr, text):
    extents = cr.text_extents(text)
    return extents.width, extents.height


def draw_text(cr, text, x, y, colour):
    """Draw text with (x, y) as the top-left of its ink, not the baseline."""
    extents = cr.text_extents(text)
    use(cr, colour)
    cr.move_to(x - extents.x_bearing, y - extents.y_bearing)
    cr.show_text(text)


def draw_text_centred(cr, text, rect, colour):
    width, height = text_size(cr, text)
    draw_text(
        cr,
        text,
        rect.x + (rect.width - width) / 2,
        rect.y + (rect.height - height) / 2,
        colour,
    )


# --------------------------------------------------------------------------
# the capture region
#
# Drawn both for the committed region and for the one being dragged out, so it
# lives here rather than in either caller.
# --------------------------------------------------------------------------


# The size label sits above the region, and on a narrow one it is wider than
# the region itself. A redraw clipped to the region alone leaves the previous
# label behind, so partial redraws need to know about this overhang.
LABEL_BAND = 34        # label height plus the gap above the region
LABEL_MAX_WIDTH = 130  # "99999 × 99999" plus padding, at FONT_SIZE_LABEL


def draw_region(cr, canvas, rect):
    reveal(cr, canvas, rect)
    region_outline(cr, rect)
    size_label(cr, canvas, rect)


def region_damage(rect):
    """Everything draw_region() can touch, for a partial redraw."""
    return Rect(
        rect.x - 2,
        rect.y - LABEL_BAND,
        max(rect.width, LABEL_MAX_WIDTH) + 4,
        rect.height + LABEL_BAND + 4,
    )


def draw_frozen_screen(cr, canvas):
    """Paint the captured screen across the overlay, at the right size.

    The capture is in physical pixels and the overlay draws in logical ones,
    so on a HiDPI display the two differ by canvas.scale. Painting it
    untransformed showed a magnified crop of the top-left corner instead of
    the desktop.

    Only for drawing to the screen. Overlay.render() has its own arithmetic,
    because there the annotations are what have to be scaled up, not the
    screen scaled down.
    """
    cr.save()
    if canvas.scale != 1:
        cr.scale(1.0 / canvas.scale, 1.0 / canvas.scale)
    cr.set_source_surface(canvas.surface, 0, 0)
    cr.paint()
    cr.restore()


def reveal(cr, canvas, rect):
    """Undim the region by repainting the frozen screen inside it."""
    cr.save()
    # Clip first, in logical coordinates, then let the paint do its own
    # scaling -- the rectangle is where the pointer went, not where the
    # captured pixels are.
    cr.rectangle(rect.x, rect.y, rect.width, rect.height)
    cr.clip()
    draw_frozen_screen(cr, canvas)
    cr.restore()


def region_outline(cr, rect):
    use(cr, theme.ACCENT)
    cr.set_line_width(1.0)
    cr.rectangle(rect.x + 0.5, rect.y + 0.5, rect.width - 1, rect.height - 1)
    cr.stroke()

    half = theme.HANDLE_SIZE / 2
    for cx, cy in rect.corners:
        cr.rectangle(cx - half, cy - half, theme.HANDLE_SIZE, theme.HANDLE_SIZE)
    cr.fill()


LABEL_PAD_X = 8
LABEL_PAD_Y = 5


def label_box(cr, text, x, y, centred=False):
    """Where a readout of `text` would sit, anchored at (x, y)."""
    select_font(cr, theme.FONT_MONO, theme.FONT_SIZE_LABEL)
    width, height = text_size(cr, text)
    box = Rect(x, y, width + LABEL_PAD_X * 2, height + LABEL_PAD_Y * 2)
    if centred:
        return Rect(x - box.width / 2, y - box.height / 2, box.width, box.height)
    return box


def draw_label(cr, text, box):
    """A small dark readout. Used for the region's size and the ruler's."""
    fill_rounded(cr, box, theme.LABEL_BG, 4)
    select_font(cr, theme.FONT_MONO, theme.FONT_SIZE_LABEL)
    draw_text(cr, text, box.x + LABEL_PAD_X, box.y + LABEL_PAD_Y, theme.LABEL_TEXT)


def size_label(cr, canvas, rect):
    """Pixel dimensions, above the region, or tucked inside if there is no
    room above."""
    pixels = rect.scaled(canvas.scale).rounded()
    text = "%d × %d" % (pixels.width, pixels.height)
    box = label_box(cr, text, rect.x, 0)
    box = Rect(box.x, rect.y - box.height - 6, box.width, box.height)
    if box.y < canvas.bounds.y:
        box = Rect(box.x, rect.y + 6, box.width, box.height)
    box = Rect(
        min(max(box.x, 0), max(0, canvas.bounds.width - box.width)),
        min(max(box.y, 0), max(0, canvas.bounds.height - box.height)),
        box.width,
        box.height,
    )
    draw_label(cr, text, box)
