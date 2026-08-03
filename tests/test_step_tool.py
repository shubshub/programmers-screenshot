#!/usr/bin/env python3
"""The step counter: numbered badges that survive undo.

    python3 tests/test_step_tool.py
"""

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import Checker, Harness, pixel  # noqa: E402

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)

from programmers_screenshot import capture  # noqa: E402
from programmers_screenshot.actions import SetRegion  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402
from programmers_screenshot.settings import COLOUR  # noqa: E402
from programmers_screenshot.tools.items import Stroke  # noqa: E402
from programmers_screenshot.tools.step import (  # noqa: E402
    SIZE,
    Step,
    StepTool,
    contrasting,
)

RED = (0.85, 0.1, 0.1)
WHITE = (1.0, 1.0, 1.0)


def near(rgb, colour, tolerance=12):
    """Is this pixel the given 0..1 colour, allowing for antialiasing?"""
    return all(
        abs(channel - round(wanted * 255)) <= tolerance
        for channel, wanted in zip(rgb, colour)
    )


def ink_outside_disc(number, colour, radius):
    """Render one badge on its own; report any numeral ink beyond its circle."""
    import cairo
    import math

    span = radius * 2 + 20
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, span, span)
    cr = cairo.Context(surface)
    badge = Step((span / 2, span / 2), colour, radius)
    badge.number = number
    badge.draw(cr)
    surface.flush()

    data = surface.get_data()
    stride = surface.get_stride()
    escaped = []
    for py in range(span):
        for px in range(span):
            offset = py * stride + px * 4
            if data[offset + 3] < 40:  # transparent: nothing drawn here
                continue
            distance = math.hypot(px - span / 2 + 0.5, py - span / 2 + 0.5)
            if distance > radius + 1.5:
                escaped.append((px, py))
    return escaped, radius


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def counting(colour=RED, size=15):
        h = Harness(pixbuf, bounds)
        h.use_tool("step")
        h.overlay.values.set(COLOUR, colour)
        h.overlay.values.set(SIZE, size)
        return h

    def numbers(h):
        return [i.number for i in h.items if isinstance(i, Step)]

    check.section("the tool is registered with its own size setting")
    h = counting()
    check("step tool present", any(t.name == "step" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("settings are size and colour", keys == {"step-size", "colour"}, keys)
    check("size does not share the width key", "width" not in keys)

    check.section("clicks number themselves in order")
    h = counting()
    x, y = h.canvas_point()
    for i in range(5):
        h.click(x + i * 90, y)
    check("five badges", len(h.items) == 5, len(h.items))
    check("numbered 1..5", numbers(h) == [1, 2, 3, 4, 5], numbers(h))

    check.section("undo hands the number back")
    h.key("z", control=True)
    check("badge removed", numbers(h) == [1, 2, 3, 4], numbers(h))
    h.key("z", control=True)
    check("and again", numbers(h) == [1, 2, 3], numbers(h))
    h.click(x + 400, y + 120)
    check("the next click takes 4, not 6", numbers(h) == [1, 2, 3, 4], numbers(h))

    check.section("redo recomputes rather than remembering")
    h.key("z", control=True)
    h.key("z", control=True, shift=True)
    check("back to four", numbers(h) == [1, 2, 3, 4], numbers(h))

    check.section("other tools do not consume numbers")
    h = counting()
    h.click(x, y)
    h.overlay.scene.do(Stroke([(x, y + 200), (x + 60, y + 200)], (0, 1, 0), 6))
    h.click(x + 120, y)
    h.use_tool("line")
    h.drag(x, y + 300, 200, 0)
    h.use_tool("step")
    h.click(x + 240, y)
    check("badges still 1, 2, 3", numbers(h) == [1, 2, 3], numbers(h))
    check("the other items are still there", len(h.items) == 5, len(h.items))

    check.section("the badge lands where the pointer is released")
    h = counting()
    h.press(x, y)
    h.move(x + 150, y + 90)
    h.release(x + 150, y + 90)
    placed = h.items[0].centre
    check("placed at the release point", placed == (x + 150, y + 90), placed)

    check.section("the numeral contrasts with the fill")
    check("white on a dark badge", contrasting(RED) == (1, 1, 1), contrasting(RED))
    check("black on a light badge", contrasting(WHITE) == (0, 0, 0), contrasting(WHITE))

    check.section("the badge is solid, with a readable numeral")
    # Compared against the same capture without the badge, so the test does not
    # depend on whatever happens to be on screen underneath.
    h = counting(colour=RED, size=21)
    h.overlay.scene.do(SetRegion(Rect(x - 30, y - 30, 60, 60)))
    before = h.overlay.render()
    h.click(x, y)
    after = h.overlay.render()

    check("fill is opaque and the chosen colour",
          near(pixel(after, 30 - 17, 30), RED), pixel(after, 30 - 17, 30))
    check("nothing painted outside the disc",
          pixel(after, 2, 2) == pixel(before, 2, 2),
          "%s vs %s" % (pixel(after, 2, 2), pixel(before, 2, 2)))
    check("the disc covered what was under it",
          pixel(after, 30, 30 - 17) != pixel(before, 30, 30 - 17))
    numeral = [(px, py) for px in range(22, 39) for py in range(22, 39)
               if not near(pixel(after, px, py), RED)]
    check("a numeral is drawn over the fill", len(numeral) > 8, len(numeral))

    check.section("two and three digits stay inside the badge")
    # Render the badge alone and check no ink escapes the circle.
    for number, label in ((7, "one digit"), (12, "two digits"), (105, "three digits")):
        escaped, radius = ink_outside_disc(number, RED, 15)
        check("%s: numeral stays within the disc" % label, not escaped,
              "%d px beyond r=%d" % (len(escaped), radius))

    check.section("bounds cover the disc")
    badge = Step((100, 100), RED, 15)
    box = badge.bounds()
    check("covers the radius", box.x <= 85 and box.right >= 115, box)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
