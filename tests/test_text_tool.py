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
    keys = {b.setting.key for b in h.overlay.toolbar.setting_buttons}
    check("size, backing and colour", keys == {"text-size", "text-background", "colour"},
          keys)
    check("size does not share the width key", "width" not in keys)
    backing = [b.value for b in h.overlay.toolbar.setting_buttons
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
    white = sum(
        1 for px in range(20, 380, 4) for py in range(20, 100, 4)
        if is_white(pixel(h.result, px, py))
    )
    check("its white backing is in the image", white > 40, white)

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
    # Counted against a render of the same region with no text at all, since
    # the screenshot underneath has plenty of white of its own.
    region = Rect(x - 10, y - 10, 300, 90)

    def white_count(background):
        h = typing(size=28, background=background)
        h.overlay.scene.do(SetRegion(region))
        if background is not None:
            h.click(x, y)
            h.type_text("bare")
        # Through the Capture button, so the text is committed the way it
        # would be in use — render() alone would miss it.
        h.click_button("capture")
        return sum(
            1 for px in range(5, 295, 3) for py in range(5, 85, 3)
            if is_white(pixel(h.result, px, py))
        )

    baseline = white_count(None)
    without = white_count(False)
    with_backing = white_count(True)
    check("backing on paints a solid white block",
          with_backing > baseline + 100,
          "%d vs %d baseline" % (with_backing, baseline))
    check("backing off adds almost none",
          without < baseline * 1.3 + 30,
          "%d vs %d baseline" % (without, baseline))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
