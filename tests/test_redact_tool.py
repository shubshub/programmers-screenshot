#!/usr/bin/env python3
"""Redaction: a solid bar that replaces what was underneath.

    python3 tests/test_redact_tool.py
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
from programmers_screenshot.tools.items import Redaction  # noqa: E402
from programmers_screenshot.tools.redact import BLACK, FILL, WHITE  # noqa: E402


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def redacting(fill=BLACK):
        h = Harness(pixbuf, bounds)
        h.use_tool("redact")
        h.overlay.values.set(FILL, fill)
        return h

    check.section("the tool is registered with its own fill setting")
    h = redacting()
    check("redact tool present", any(t.name == "redact" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("only a fill setting", keys == {"redact-fill"}, keys)
    check("it does not share the pen's colour", "colour" not in keys)
    fills = [b.value for b in h.bar.setting_buttons]
    check("black and white only", fills == [BLACK, WHITE], fills)
    check("black by default", h.overlay.values.get(FILL) == BLACK)

    check.section("a drag commits a redaction")
    h = redacting()
    x, y = h.canvas_point()
    h.drag(x, y, 300, 120)
    check("one item", len(h.items) == 1, len(h.items))
    check("of the right kind", isinstance(h.items[0], Redaction))
    check("carrying the fill", h.items[0].colour == BLACK)

    check.section("a click leaves nothing")
    h = redacting()
    h.click(*h.canvas_point())
    check("no item", not h.items, h.items)

    check.section("the pixels underneath are gone, not dimmed")
    # The whole point of redaction over pixelation: nothing of the original
    # survives into the exported image, so every pixel inside is exactly the
    # fill and none of them vary with what used to be there.
    region = None
    for fill, name in ((BLACK, "black"), (WHITE, "white")):
        h = redacting(fill)
        x, y = h.canvas_point()
        region = Rect(x - 20, y - 20, 340, 160)
        h.overlay.scene.do(SetRegion(region))
        before = h.overlay.render()          # the same region, un-redacted
        h.drag(x, y, 300, 120)
        after = h.overlay.render()

        wanted = tuple(round(channel * 255) for channel in fill)
        inside = [
            (px, py)
            for px in range(26, 314, 6)
            for py in range(26, 134, 6)
        ]
        wrong = [p for p in inside if pixel(after, *p) != wanted]
        check("%s: every pixel inside is exactly the fill" % name,
              not wrong, "%d of %d differ" % (len(wrong), len(inside)))
        survivors = [
            p for p in inside
            if pixel(before, *p) != wanted and pixel(after, *p) == pixel(before, *p)
        ]
        check("%s: which means nothing of the original is left" % name,
              not survivors,
              "%d of %d pixels still match what was underneath"
              % (len(survivors), len(inside)))

        outside = [(px, py) for px in range(2, 18, 4) for py in range(2, 18, 4)]
        check("%s: nothing painted outside the bar" % name,
              all(pixel(after, *p) == pixel(before, *p) for p in outside),
              "%d of %d changed"
              % (sum(1 for p in outside
                     if pixel(after, *p) != pixel(before, *p)), len(outside)))

    check.section("undo takes it back")
    h = redacting()
    h.drag(*h.canvas_point(), 200, 80)
    check("committed", len(h.items) == 1)
    h.key("z", control=True)
    check("undone", not h.items, h.items)
    h.key("z", control=True, shift=True)
    check("redone", len(h.items) == 1)

    check.section("bounds cover the bar")
    item = Redaction((10, 10), (110, 60), BLACK, 0)
    box = item.bounds()
    check("covers the rectangle",
          box.x <= 10 and box.y <= 10 and box.right >= 110 and box.bottom >= 60,
          box)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
