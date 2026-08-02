"""Small cairo helpers shared by the toolbar and the tools."""

import math

from . import theme


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
