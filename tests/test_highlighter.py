#!/usr/bin/env python3
"""The highlighter: a wash of colour that tints without hiding.

    python3 tests/test_highlighter.py
"""

import sys

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from support import Checker, Harness, pixel  # noqa: E402

from programmers_screenshot import capture  # noqa: E402
from programmers_screenshot.actions import SetRegion  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402
from programmers_screenshot.tools.highlight import (  # noqa: E402
    INK,
    THICKNESS,
    YELLOW,
)
from programmers_screenshot.tools.items import Highlight  # noqa: E402


def on_colour(item, back=(1, 1, 1), span=140):
    """Draw one item on a flat background and hand back a pixel reader."""
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, span, span)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*back)
    cr.paint()
    item.draw(cr)
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()

    def read(x, y):
        offset = y * stride + x * 4
        return (data[offset + 2], data[offset + 1], data[offset])

    return read


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def marking(ink=YELLOW, width=20):
        h = Harness(pixbuf, bounds)
        h.use_tool("highlight")
        h.overlay.values.set(INK, ink)
        h.overlay.values.set(THICKNESS, width)
        return h

    check.section("the tool is registered with its own ink and width")
    h = marking()
    check("highlighter present", any(t.name == "highlight" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("its own keys", keys == {"highlight-ink", "highlight-width"}, keys)
    check("it does not share the pen's colour", "colour" not in keys)
    check("nor the pen's width", "width" not in keys)
    inks = [b.value for b in h.bar.setting_buttons if b.setting.key == "highlight-ink"]
    check("no black or white in the palette",
          (0.0, 0.0, 0.0) not in inks and (1.0, 1.0, 1.0) not in inks, inks)

    check.section("a drag commits one highlight")
    h = marking()
    x, y = h.canvas_point()
    h.drag(x, y, 240, 0, steps=8)
    check("one item", len(h.items) == 1, len(h.items))
    check("of the right kind", isinstance(h.items[0], Highlight))
    check("carrying its ink and width",
          h.items[0].colour == YELLOW and h.items[0].width == 20)

    check.section("it tints rather than covers")
    read = on_colour(Highlight([(20, 70), (120, 70)], YELLOW, 24))
    inked = read(70, 70)
    check("the ink is on the page", inked != (255, 255, 255), inked)
    check("but it is not opaque paint",
          inked[0] > 200 and inked[1] > 200, inked)
    check("and it takes the ink's own hue",
          inked[2] < inked[0] and inked[2] < inked[1], inked)
    check("off the stroke the page is untouched", read(70, 20) == (255, 255, 255),
          read(70, 20))

    check.section("it stays visible on a dark screenshot, not only a light one")
    # The guard against going back to multiply, which looks better on paper
    # but barely touches a dark UI -- and dark is most of what gets shot here.
    for name, back in (("white page", (1, 1, 1)), ("dark UI", (0.11, 0.12, 0.15)),
                       ("near black", (0.03, 0.03, 0.04))):
        read = on_colour(Highlight([(20, 70), (120, 70)], YELLOW, 24), back)
        plain = tuple(round(channel * 255) for channel in back)
        moved = sum(abs(a - b) for a, b in zip(read(70, 70), plain))
        check("%s: the ink is clearly visible" % name, moved > 80,
              "moved the pixel by %d" % moved)

    check.section("crossing its own path does not double up")
    # cairo unions a stroke into one shape before compositing, so a single
    # stroke() call is enough -- no need to build it through a group.
    crossing = Highlight(
        [(20, 20), (100, 100), (100, 20), (20, 100)], YELLOW, 24
    )
    read = on_colour(crossing)
    arm = read(35, 35)
    middle = read(60, 60)
    check("the crossing matches a plain arm", middle == arm,
          "%s at the crossing vs %s on an arm" % (middle, arm))

    check.section("two separate strokes do compound, as a second pass should")
    span = 140
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, span, span)
    cr = cairo.Context(surface)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    Highlight([(20, 70), (120, 70)], YELLOW, 24).draw(cr)
    once = None
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    once = (data[70 * stride + 70 * 4 + 2], data[70 * stride + 70 * 4 + 1],
            data[70 * stride + 70 * 4])
    Highlight([(20, 70), (120, 70)], YELLOW, 24).draw(cr)
    surface.flush()
    twice = (data[70 * stride + 70 * 4 + 2], data[70 * stride + 70 * 4 + 1],
             data[70 * stride + 70 * 4])
    check("a second pass is darker", sum(twice) < sum(once),
          "%s then %s" % (once, twice))

    check.section("it reaches the captured image")
    h = marking(width=32)
    x, y = h.canvas_point()
    h.overlay.scene.do(SetRegion(Rect(x - 20, y - 40, 300, 100)))
    before = h.overlay.render()
    h.drag(x, y, 240, 0, steps=8)
    after = h.overlay.render()
    on_line = [(px, 40) for px in range(40, 240, 8)]
    changed = [p for p in on_line if pixel(after, *p) != pixel(before, *p)]
    check("the stroke changed the image", len(changed) > 15, len(changed))
    check("and it did not black it out",
          all(sum(pixel(after, *p)) > 0 for p in on_line))

    check.section("a click leaves a dot, and undo takes it back")
    h = marking()
    h.click(*h.canvas_point())
    check("dot committed", len(h.items) == 1, h.items)
    h.key("z", control=True)
    check("undone", not h.items)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
