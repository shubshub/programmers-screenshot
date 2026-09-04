#!/usr/bin/env python3
"""The colour picker: reads a pixel, writes to the clipboard, leaves the
scene alone.

The clipboard is stubbed rather than written to, so running the suite does
not take over yours.

    python3 tests/test_picker.py
"""

import sys

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from support import Checker, Harness, pixel  # noqa: E402

from programmers_screenshot import capture, output  # noqa: E402
from programmers_screenshot.tools import picker  # noqa: E402
from programmers_screenshot.tools.picker import (  # noqa: E402
    FORMAT,
    HEX,
    RGB,
    format_colour,
    read_pixel,
)


class Clipboard:
    """Stands in for the real one, and remembers what it was handed."""

    def __init__(self):
        self.written = []

    def __enter__(self):
        self._real = output.copy_text
        picker.output.copy_text = self.written.append
        return self

    def __exit__(self, *_):
        picker.output.copy_text = self._real

    @property
    def last(self):
        return self.written[-1] if self.written else None


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def picking(style=HEX):
        h = Harness(pixbuf, bounds)
        h.use_tool("picker")
        h.overlay.values.set(FORMAT, style)
        return h

    check.section("the tool is registered")
    h = picking()
    check("picker present", any(t.name == "picker" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("just a format setting", keys == {"colour-format"}, keys)
    styles = [b.value for b in h.bar.setting_buttons]
    check("hex and rgb", styles == [HEX, RGB], styles)

    check.section("formatting")
    check("hex", format_colour((58, 123, 213), HEX) == "#3A7BD5",
          format_colour((58, 123, 213), HEX))
    check("rgb", format_colour((58, 123, 213), RGB) == "rgb(58, 123, 213)",
          format_colour((58, 123, 213), RGB))
    check("hex pads to two digits", format_colour((0, 8, 255), HEX) == "#0008FF",
          format_colour((0, 8, 255), HEX))

    check.section("it reads the pixel that is actually there")
    h = picking()
    x, y = h.canvas_point()
    wanted = pixel(pixbuf, int(x), int(y))
    got = read_pixel(h.overlay.canvas(), (x, y))
    check("matches the capture", got == wanted, "%s vs %s" % (got, wanted))

    # and through a surface it cannot read directly, as the real overlay has
    server_side = cairo.ImageSurface(cairo.FORMAT_RGB24, 4, 4)
    scratch = cairo.Context(server_side)
    scratch.set_source_rgb(0.2, 0.4, 0.6)
    scratch.paint()
    server_side.flush()

    class FakeCanvas:
        surface = server_side
        scale = 1.0

    check("samples any surface, not just a readable one",
          read_pixel(FakeCanvas(), (2, 2)) == (51, 102, 153),
          read_pixel(FakeCanvas(), (2, 2)))

    check.section("a click copies the colour and changes nothing else")
    with Clipboard() as board:
        h = picking()
        x, y = h.canvas_point()
        h.click(x, y)
        expected = format_colour(pixel(pixbuf, int(x), int(y)), HEX)
        check("copied the hex", board.last == expected,
              "%s vs %s" % (board.last, expected))
        check("nothing joined the scene", not h.items, h.items)
        check("no region either", h.region is None)
        check("and it did not close the overlay", not h.finished)
        check("there is nothing to undo", not h.overlay.scene.can_undo)

    check.section("the readout shows what was picked")
    with Clipboard():
        h = picking()
        check("nothing to show before a pick", h.overlay.active_tool.bounds() is None)
        h.click(*h.canvas_point())
        check("something to show after", h.overlay.active_tool.bounds() is not None)
        h.overlay.active_tool.cancel()
        check("switching away clears it", h.overlay.active_tool.bounds() is None)

    check.section("changing the format re-answers the same question")
    with Clipboard() as board:
        h = picking(HEX)
        x, y = h.canvas_point()
        h.click(x, y)
        first = board.last
        check("hex first", first.startswith("#"), first)
        button = next(b for b in h.bar.setting_buttons if b.value == RGB)
        h.click(button.rect.x + 4, button.rect.y + 4)
        check("now rgb, for the same pixel",
              board.last.startswith("rgb(") and board.last != first, board.last)
        picked = h.overlay.active_tool._picked
        check("the readout followed", picked[2] == board.last, picked[2])

    check.section("the clipboard helper asks for text, not an image")
    helper = output._clipboard_helper(image=False)
    if helper is None:
        check("no helper installed, skipping", True)
    else:
        check("targets text/plain", "text/plain" in helper, helper)
        check("the image one still targets a PNG",
              "image/png" in output._clipboard_helper(image=True),
              output._clipboard_helper(image=True))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
