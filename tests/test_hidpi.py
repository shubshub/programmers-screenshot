#!/usr/bin/env python3
"""The overlay on a display where physical and logical pixels differ.

The capture comes back in physical pixels; the overlay draws in logical ones.
Getting that wrong showed a magnified crop of the top-left corner instead of
the desktop, while the saved PNG stayed correct -- so the tests here check
what is on screen, not what is in the file, and check the file too so the
part that already worked keeps working.

    python3 tests/test_hidpi.py
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf, Gtk  # noqa: E402

from support import Checker, Harness, render_overlay  # noqa: E402

from programmers_screenshot.actions import SetRegion  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402

# Logical size of the pretend screen.
WIDE, TALL = 200, 100

BLUE = "blue"
GREEN = "green"


def two_tone(scale):
    """A capture `scale` times the logical size: left half blue, right green.

    Split down the middle, so which half a point lands in says whether the
    scale was honoured. At 2x, logical x=150 is physical x=300 -- green. Draw
    it unscaled and logical 150 reads physical 150, which is blue.
    """
    pixbuf = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, False, 8, int(WIDE * scale), int(TALL * scale)
    )
    pixbuf.fill(0x0000FFFF)
    half = int(WIDE * scale / 2)
    pixbuf.new_subpixbuf(half, 0, half, int(TALL * scale)).fill(0x00FF00FF)
    return pixbuf


def hue(rgb):
    """Which half a pixel came from. Survives the overlay's dimming, which
    darkens everything but cannot turn blue into green."""
    red, green, blue = rgb
    return GREEN if green > blue else BLUE


def png_pixel(pixbuf, x, y):
    data = pixbuf.get_pixels()
    offset = y * pixbuf.get_rowstride() + x * pixbuf.get_n_channels()
    return tuple(data[offset:offset + 3])


def main():
    check = Checker()
    if not Gtk.init_check()[0]:
        check("a display is available", False)
        return check.report()

    bounds = Rect(0, 0, WIDE, TALL)

    for scale in (1, 2, 3):
        check.section("a %dx display" % scale)
        harness = Harness(two_tone(scale), bounds)
        check("the overlay works out the scale",
              harness.overlay.scale == scale, harness.overlay.scale)

        read = render_overlay(harness)
        # Three logical points either side of the midline. Under the bug every
        # one of them reads from the left half of the capture.
        for x, expected in ((40, BLUE), (110, GREEN), (150, GREEN)):
            found = hue(read(x, 50))
            check("logical x=%d shows the %s half" % (x, expected),
                  found == expected, found)

    check.section("the undimmed region is not magnified either")
    # reveal() repaints the capture inside the selection. It had the same
    # defect, so fixing only the backdrop would leave this one wrong.
    harness = Harness(two_tone(2), bounds)
    harness.overlay.scene.do(SetRegion(Rect(100, 25, 80, 50)))
    read = render_overlay(harness)

    inside = read(150, 50)
    check("inside the region it is undimmed", max(inside) > 200, inside)
    check("and it is the green half", hue(inside) == GREEN, inside)

    outside = read(40, 50)
    check("outside it is still dimmed", max(outside) < 200, outside)
    check("and still the blue half", hue(outside) == BLUE, outside)

    check.section("the captured PNG was already right and stays right")
    harness = Harness(two_tone(2), bounds)
    captured = harness.overlay.render()
    check("it comes out at physical size",
          (captured.get_width(), captured.get_height()) == (WIDE * 2, TALL * 2),
          (captured.get_width(), captured.get_height()))
    check("its left half is blue",
          hue(png_pixel(captured, 100, 100)) == BLUE,
          png_pixel(captured, 100, 100))
    check("its right half is green",
          hue(png_pixel(captured, 300, 100)) == GREEN,
          png_pixel(captured, 300, 100))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
