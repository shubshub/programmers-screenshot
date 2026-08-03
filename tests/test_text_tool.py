#!/usr/bin/env python3
"""The text tool: click, type, click away.

    python3 tests/test_text_tool.py
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
from programmers_screenshot.tools.text import (  # noqa: E402
    BACKGROUND,
    PADDING,
    SIZE,
    TextBlock,
    layout,
)

RED = (0.9, 0.1, 0.1)


def is_white(rgb, tolerance=6):
    return all(channel >= 255 - tolerance for channel in rgb)


def block_coverage(background):
    """Draw one text block alone; report how much of its box it fills.

    Returns (fraction of the box painted, pixels painted outside the box).
    """
    import cairo

    origin = (10, 10)
    block = TextBlock(origin, ("bare",), RED, 28, background)
    box = block.box()
    width, height = int(box.width) + 20, int(box.height) + 20
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    block.draw(cairo.Context(surface))
    surface.flush()

    data, stride = surface.get_data(), surface.get_stride()
    inside = painted = outside = 0
    for py in range(height):
        for px in range(width):
            alpha = data[py * stride + px * 4 + 3]
            within = (origin[0] <= px < origin[0] + box.width
                      and origin[1] <= py < origin[1] + box.height)
            if within:
                inside += 1
                painted += 1 if alpha > 200 else 0
            elif alpha > 40:
                outside += 1
    return painted / inside, outside


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def typing(size=20, background=False, colour=RED):
        h = Harness(pixbuf, bounds)
        h.use_tool("text")
        h.overlay.values.set(SIZE, size)
        h.overlay.values.set(BACKGROUND, background)
        h.overlay.values.set(COLOUR, colour)
        return h

    def texts(h):
        return [i.lines for i in h.items if isinstance(i, TextBlock)]

    check.section("the tool is registered with its own size and backing")
    h = typing()
    check("text tool present", any(t.name == "text" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("size, backing and colour", keys == {"text-size", "text-background", "colour"},
          keys)
    check("size does not share the width key", "width" not in keys)
    backing = [b.value for b in h.bar.setting_buttons
               if b.setting.key == "text-background"]
    check("backing is just off or on", backing == [False, True], backing)

    check.section("typing goes into a caret placed by clicking")
    h = typing()
    x, y = h.canvas_point()
    h.click(x, y)
    check("editing after the click", h.overlay.active_tool.editing)
    h.type_text("hello")
    check("nothing committed while typing", not h.items, h.items)
    check("the tool holds the text", h.overlay.active_tool._lines == ["hello"],
          h.overlay.active_tool._lines)

    check.section("Enter makes a new line and does not capture")
    h.key("Return")
    check("still editing, not captured", not h.finished)
    h.type_text("world")
    check("two lines", h.overlay.active_tool._lines == ["hello", "world"],
          h.overlay.active_tool._lines)

    check.section("clicking away commits")
    h.click(x + 600, y + 400)
    check("one text item", len(texts(h)) == 1, texts(h))
    check("with both lines", texts(h)[0] == ("hello", "world"), texts(h)[0])
    check("and a fresh caret at the new point", h.overlay.active_tool.editing)

    check.section("an empty box commits nothing")
    h = typing()
    h.click(x, y)
    h.click(x + 300, y)
    check("no items", not h.items, h.items)
    h.type_text("   ")
    h.click(x + 600, y)
    check("whitespace alone is still nothing", not h.items, h.items)

    check.section("backspace deletes, and joins back up lines")
    h = typing()
    h.click(x, y)
    h.type_text("ab")
    h.key("BackSpace")
    check("character removed", h.overlay.active_tool._lines == ["a"],
          h.overlay.active_tool._lines)
    h.key("Return")
    h.key("BackSpace")
    check("empty line removed", h.overlay.active_tool._lines == ["a"],
          h.overlay.active_tool._lines)

    check.section("Escape drops the text but keeps the overlay open")
    h = typing()
    h.click(x, y)
    h.type_text("scrap")
    h.key("Escape")
    check("not committed", not h.items, h.items)
    check("no longer editing", not h.overlay.active_tool.editing)
    check("overlay still open", not h.finished)
    h.key("Escape")
    check("a second Escape closes it", h.finished and h.result is None)

    check.section("Ctrl+Z while typing does not eat a committed item")
    h = typing()
    h.click(x, y)
    h.type_text("keep me")
    h.click(x + 400, y)
    check("first text committed", len(texts(h)) == 1)
    h.type_text("second")
    h.key("z", control=True)
    check("the committed one survives", len(texts(h)) == 1, texts(h))
    check("still typing", h.overlay.active_tool.editing)

    check.section("settings apply to the text already being typed")
    # Regression: begin() snapshots the settings, which is right for a drag but
    # left an active text box on stale values until you started a new one.
    h = typing(size=20, background=False, colour=RED)
    h.click(x, y)
    h.type_text("live")
    tool = h.overlay.active_tool

    def setting_button(key, value):
        return next(b for b in h.bar.setting_buttons
                    if b.setting.key == key and b.value == value)

    def press_setting(key, value):
        rect = setting_button(key, value).rect
        h.click(rect.x + 4, rect.y + 4)

    check("starts without backing", tool._block().background is False)
    press_setting("text-background", True)
    check("backing switches on straight away", tool._block().background is True,
          tool._block().background)
    check("still the same text", tool._lines == ["live"], tool._lines)
    check("still editing", tool.editing)

    press_setting("colour", (0.25, 0.62, 1.0))
    check("colour applies too", tool._block().colour == (0.25, 0.62, 1.0),
          tool._block().colour)
    press_setting("text-size", 40)
    check("size applies too", tool._block().size == 40, tool._block().size)

    h.click(x + 700, y + 300)
    committed = [i for i in h.items if isinstance(i, TextBlock)][0]
    check("and the committed item keeps them",
          committed.background and committed.size == 40, committed.size)

    check.section("a drag still keeps the settings it started with")
    # The counterpart: gesture tools must not pick up mid-flight changes.
    h = typing()
    h.use_tool("pen")
    h.overlay.values.set(COLOUR, RED)
    h.press(x, y)
    h.move(x + 60, y + 40)
    h.overlay.active_tool.settings_changed(h.overlay.values)
    h.overlay.values.set(COLOUR, (0.0, 0.0, 1.0))
    h.release(x + 120, y + 80)
    stroke = h.items[0]
    check("stroke kept the colour it began with", stroke.colour == RED, stroke.colour)

    check.section("switching tools commits rather than losing it")
    h = typing()
    h.click(x, y)
    h.type_text("kept")
    h.use_tool("pen")
    check("committed on the way out", texts(h) == [("kept",)], texts(h))

    check.section("text typed and then captured is in the PNG")
    # Regression: render() draws the scene and nothing else, so uncommitted
    # work used to be dropped silently.
    h = typing(size=28, background=True)
    h.click(x, y)
    h.type_text("shipped")
    h.overlay.scene.do(SetRegion(Rect(x - 10, y - 10, 400, 120)))
    h.click_button("capture")
    check("captured", h.finished and h.result is not None)
    check("the text became an item", len(texts(h)) == 1, texts(h))

    # Inside the backing box specifically. Counting pixels that merely differ
    # from an un-typed capture depended on how much the white box stood out
    # from whatever was behind it, and hovered either side of its threshold.
    block = [i for i in h.items if isinstance(i, TextBlock)][0]
    box = block.box()
    inside = [
        (10 + 3 + dx, 10 + 3 + dy)
        for dx in range(0, int(box.width) - 6, 5)
        for dy in range(0, int(box.height) - 6, 5)
    ]
    white = [p for p in inside if is_white(pixel(h.result, *p))]
    check("its white backing reached the image",
          len(white) > len(inside) * 0.5,
          "%d of %d sampled points are white" % (len(white), len(inside)))
    check("and the glyphs are on top of it",
          len(white) < len(inside),
          "%d of %d are not white" % (len(inside) - len(white), len(inside)))

    check.section("the backing covers the longest line and the whole paragraph")
    for lines in (("short", "a much longer line here"), ("a much longer line here", "short")):
        block = TextBlock((100, 100), lines, RED, 20, True)
        metrics = layout(lines, 20)
        box = block.box()
        check("width follows the longest line %s" % (lines[0][:6],),
              abs(box.width - (metrics["width"] + PADDING * 2)) < 0.5, box.width)
        check("height covers both lines %s" % (lines[0][:6],),
              abs(box.height - (metrics["height"] + PADDING * 2)) < 0.5, box.height)

    single = TextBlock((100, 100), ("a much longer line here",), RED, 20, True).box()
    doubled = TextBlock((100, 100), ("a much longer line here", "x"), RED, 20, True).box()
    check("a second line makes it taller, not wider",
          doubled.height > single.height and abs(doubled.width - single.width) < 0.5,
          "%.0fx%.0f vs %.0fx%.0f" % (single.width, single.height,
                                      doubled.width, doubled.height))

    check.section("the backing is painted only when it is switched on")
    # Drawn on its own rather than over the screenshot: counting white pixels
    # in a capture depends on whatever happens to be behind it.
    filled_on, outside_on = block_coverage(True)
    filled_off, outside_off = block_coverage(False)
    check("backing on fills the box with opaque white",
          filled_on > 0.9, "%.0f%% of the box" % (filled_on * 100))
    check("and paints nothing outside it",
          outside_on == 0, outside_on)
    check("backing off leaves the box empty apart from the glyphs",
          filled_off < 0.25, "%.0f%% of the box" % (filled_off * 100))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
