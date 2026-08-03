#!/usr/bin/env python3
"""The line tool: straight lines, outlined circles and arrows.

    python3 tests/test_line_tool.py
"""

import math
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
from programmers_screenshot.settings import COLOUR, WIDTH  # noqa: E402
from programmers_screenshot.tools.items import (  # noqa: E402
    Arrow,
    Box,
    Ellipse,
    Line,
)
from programmers_screenshot.tools.line import SHAPE  # noqa: E402

RED = (1.0, 0.0, 0.0)


def is_red(rgb):
    return rgb[0] > 180 and rgb[1] < 70 and rgb[2] < 70


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def drawing(shape, width=12):
        """A harness with the line tool active and one shape ready to draw."""
        h = Harness(pixbuf, bounds)
        h.use_tool("line")
        h.overlay.values.set(SHAPE, shape)
        h.overlay.values.set(COLOUR, RED)
        h.overlay.values.set(WIDTH, width)
        return h

    check.section("the tool is registered and offers three shapes")
    h = Harness(pixbuf, bounds)
    check("line tool present", any(t.name == "line" for t in h.overlay.tools))
    h.use_tool("line")
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("settings row has shape, colour and width",
          keys == {"shape", "colour", "width"}, keys)
    shapes = [b.value for b in h.bar.setting_buttons
              if b.setting.key == "shape"]
    check("four shapes offered",
          shapes == ["line", "box", "circle", "arrow"], shapes)

    check.section("each shape commits its own kind of item")
    for shape, kind in (("line", Line), ("box", Box), ("circle", Ellipse),
                        ("arrow", Arrow)):
        h = drawing(shape)
        x, y = h.canvas_point()
        h.drag(x, y, 300, 200)
        items = h.items
        check("%s: one item" % shape, len(items) == 1, len(items))
        check("%s: right kind" % shape, isinstance(items[0], kind),
              type(items[0]).__name__)
        check("%s: carries colour and width" % shape,
              items[0].colour == RED and items[0].width == 12)

    check.section("a click leaves nothing")
    for shape in ("line", "box", "circle", "arrow"):
        h = drawing(shape)
        h.click(*h.canvas_point())
        check("%s: no item from a click" % shape, not h.items, h.items)

    check.section("shape chosen at the start is the shape you get")
    h = drawing("line")
    x, y = h.canvas_point()
    h.press(x, y)
    h.move(x + 200, y + 120)
    h.overlay.values.set(SHAPE, "arrow")  # switch mid-drag
    h.release(x + 200, y + 120)
    check("still a line", isinstance(h.items[0], Line), type(h.items[0]).__name__)

    check.section("switching shape does not disturb committed items")
    h = drawing("line")
    x, y = h.canvas_point()
    h.drag(x, y, 200, 100)
    h.overlay.values.set(SHAPE, "circle")
    h.drag(x, y + 250, 200, 100)
    check("two items", len(h.items) == 2, len(h.items))
    check("first is still a line", isinstance(h.items[0], Line))
    check("second is a circle", isinstance(h.items[1], Ellipse))

    check.section("shift constrains the drag")
    h = drawing("line")
    x, y = h.canvas_point()
    h.drag(x, y, 300, 40, steps=3, shift=True)  # nearly horizontal -> snaps flat
    end = h.items[0].end
    check("line snapped to 45s", abs(end[1] - y) < 0.5, "dy %.2f" % (end[1] - y))

    h = drawing("circle")
    h.drag(x, y, 300, 180, steps=3, shift=True)
    box = Rect.from_points(h.items[0].start, h.items[0].end)
    check("circle squared off", abs(box.width - box.height) < 0.5,
          "%.1f x %.1f" % (box.width, box.height))

    h = drawing("line")
    h.drag(x, y, 300, 40, steps=3)  # same drag, no shift
    check("unconstrained by default", abs(h.items[0].end[1] - y - 40) < 0.5,
          h.items[0].end)

    check.section("each shape reaches the captured image")
    # A horizontal line across the middle of the region.
    h = drawing("line", width=14)
    x, y = h.canvas_point()
    h.drag(x, y, 240, 0, steps=6)
    h.overlay.scene.do(SetRegion(Rect(x - 20, y - 20, 280, 40)))
    baked = h.overlay.render()
    check("line: on the line", is_red(pixel(baked, 140, 20)), pixel(baked, 140, 20))

    h = drawing("arrow", width=14)
    h.drag(x, y, 240, 0, steps=6)
    h.overlay.scene.do(SetRegion(Rect(x - 40, y - 40, 320, 80)))
    baked = h.overlay.render()
    check("arrow: on the shaft", is_red(pixel(baked, 140, 40)), pixel(baked, 140, 40))
    # the head flares above and below the shaft, near the tip
    tip_column = [pixel(baked, 268, row) for row in range(10, 70)]
    check("arrow: has a head at the tip", sum(1 for p in tip_column if is_red(p)) >= 2,
          sum(1 for p in tip_column if is_red(p)))

    check.section("the rectangle is an outline, not a filled block")
    h = drawing("box", width=10)
    h.drag(x, y, 300, 200, steps=6)
    h.overlay.scene.do(SetRegion(Rect(x, y, 300, 200)))
    baked = h.overlay.render()
    top_edge = [pixel(baked, column, 4) for column in range(40, 260, 10)]
    check("box: painted along the top edge",
          sum(1 for p in top_edge if is_red(p)) > 15,
          sum(1 for p in top_edge if is_red(p)))
    left_edge = [pixel(baked, 4, row) for row in range(40, 160, 10)]
    check("box: painted down the left edge",
          sum(1 for p in left_edge if is_red(p)) > 8,
          sum(1 for p in left_edge if is_red(p)))
    check("box: hollow in the middle", not is_red(pixel(baked, 150, 100)),
          pixel(baked, 150, 100))

    check.section("shift squares the rectangle off too")
    h = drawing("box")
    h.drag(x, y, 300, 180, steps=3, shift=True)
    box = Rect.from_points(h.items[0].start, h.items[0].end)
    check("box squared off", abs(box.width - box.height) < 0.5,
          "%.1f x %.1f" % (box.width, box.height))

    check.section("the circle is an outline, not a disc")
    h = drawing("circle", width=10)
    h.drag(x, y, 300, 200, steps=6)
    h.overlay.scene.do(SetRegion(Rect(x, y, 300, 200)))
    baked = h.overlay.render()
    left_edge = [pixel(baked, column, 100) for column in range(0, 20)]
    check("circle: painted at the left edge",
          any(is_red(p) for p in left_edge),
          sum(1 for p in left_edge if is_red(p)))
    check("circle: hollow in the middle", not is_red(pixel(baked, 150, 100)),
          pixel(baked, 150, 100))
    check("circle: nothing in the corner", not is_red(pixel(baked, 4, 4)),
          pixel(baked, 4, 4))

    check.section("bounds cover the stroke, not just the drag box")
    # Regression: the drag rectangle alone ignores the stroke overhang and the
    # arrowhead, which made partial redraws smear.
    line = Line((0, 0), (100, 0), RED, 20)
    check("line padded by half its width", line.bounds().y <= -10, line.bounds())
    arrow = Arrow((0, 0), (100, 0), RED, 20)
    check("arrow padded by its head",
          arrow.bounds().y <= -arrow.head_length(), arrow.bounds())
    check("arrow head scales with width",
          Arrow((0, 0), (9, 0), RED, 20).head_length()
          > Arrow((0, 0), (9, 0), RED, 2).head_length())

    check.section("the shape setting draws without a caption font")
    # The options render miniature shapes; make sure that path executes.
    import cairo
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 40)
    context = cairo.Context(surface)
    for value in ("line", "circle", "arrow"):
        SHAPE.draw_option(context, Rect(2, 2, 30, 30), value, value == "circle")
    check("all three option icons drew", True)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
