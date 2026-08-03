#!/usr/bin/env python3
"""Pixelation: blocks derived from the frozen screen.

    python3 tests/test_pixelate_tool.py
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
from programmers_screenshot.tools.pixelate import BLOCK, Pixelation  # noqa: E402


def distinct_colours(image, width, height, step=3):
    return len({
        pixel(image, px, py)
        for px in range(4, width - 4, step)
        for py in range(4, height - 4, step)
    })


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def pixelating(block=14):
        h = Harness(pixbuf, bounds)
        h.use_tool("pixelate")
        h.overlay.values.set(BLOCK, block)
        return h

    check.section("the tool is registered with its own block setting")
    h = pixelating()
    check("pixelate tool present", any(t.name == "pixelate" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("only a block setting", keys == {"pixel-block"}, keys)
    check("it does not share the pen's width", "width" not in keys)
    check("three block sizes", len(h.bar.setting_buttons) == 3,
          len(h.bar.setting_buttons))

    check.section("a drag commits a pixelation, a click does not")
    h = pixelating()
    x, y = h.canvas_point()
    h.drag(x, y, 300, 160)
    check("one item", len(h.items) == 1, len(h.items))
    check("of the right kind", isinstance(h.items[0], Pixelation))
    h = pixelating()
    h.click(*h.canvas_point())
    check("a click leaves nothing", not h.items, h.items)

    check.section("the block setting really changes the blocks")
    # Checked on the grid the item holds and on how many colours survive.
    # Measuring run lengths in the image does not work: large flat areas of a
    # real screenshot give neighbouring blocks the same colour, and the runs
    # merge straight through the boundaries.
    grids, colours = {}, {}
    for block in (8, 24):
        h = pixelating(block)
        x, y = h.canvas_point()
        h.drag(x, y, 320, 160)
        item = h.items[0]
        grids[block] = (item.blocks.get_width(), item.blocks.get_height())
        h.overlay.scene.do(SetRegion(Rect(x, y, 320, 160)))
        colours[block] = distinct_colours(h.overlay.render(), 320, 160)

    check("block 8 gives a 40 by 20 grid", grids[8] == (40, 20), grids[8])
    check("block 24 gives a 13 by 7 grid", grids[24] == (13, 7), grids[24])
    check("coarser blocks leave far fewer colours",
          colours[24] * 2 < colours[8], "%d vs %d" % (colours[24], colours[8]))

    check.section("a block is one flat colour, not a gradient")
    h = pixelating(24)
    x, y = h.canvas_point()
    h.drag(x, y, 320, 160)
    h.overlay.scene.do(SetRegion(Rect(x, y, 320, 160)))
    baked = h.overlay.render()
    corner = pixel(baked, 60, 60)
    patch = [pixel(baked, 60 + dx, 60 + dy) for dx in range(0, 8) for dy in range(0, 8)]
    check("every sample in the patch matches", all(p == corner for p in patch),
          "%d of %d differ" % (sum(1 for p in patch if p != corner), len(patch)))

    check.section("the blocks come from the screenshot, not the overlay")
    # The overlay dims everything it draws over; a block taken from the dimmed
    # screen would be far darker than the capture it was supposed to sample.
    h = pixelating(24)
    x, y = h.canvas_point()
    h.drag(x, y, 240, 120)
    h.overlay.scene.do(SetRegion(Rect(x, y, 240, 120)))
    baked = h.overlay.render()

    def mean(values):
        return sum(values) / len(values)

    block_colour = pixel(baked, 60, 60)
    source = [
        pixel(pixbuf, int(x) + 48 + dx, int(y) + 48 + dy)
        for dx in range(0, 24, 2)
        for dy in range(0, 24, 2)
    ]
    for channel in range(3):
        wanted = mean([p[channel] for p in source])
        check("channel %d is the average of the capture" % channel,
              abs(block_colour[channel] - wanted) < 40,
              "%d vs %.0f" % (block_colour[channel], wanted))

    check.section("undo takes it back")
    h = pixelating()
    h.drag(*h.canvas_point(), 200, 100)
    check("committed", len(h.items) == 1)
    h.key("z", control=True)
    check("undone", not h.items, h.items)
    h.key("z", control=True, shift=True)
    check("redone", len(h.items) == 1)

    check.section("bounds cover the rectangle")
    h = pixelating()
    x, y = h.canvas_point()
    h.drag(x, y, 200, 100)
    box = h.items[0].bounds()
    check("covers it", box.x <= x and box.right >= x + 200, box)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
