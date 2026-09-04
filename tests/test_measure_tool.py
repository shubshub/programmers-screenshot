#!/usr/bin/env python3
"""The ruler: distances in physical pixels.

    python3 tests/test_measure_tool.py
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from support import Checker, Harness  # noqa: E402

from programmers_screenshot import capture  # noqa: E402
from programmers_screenshot.tools.items import Measurement  # noqa: E402

RED = (0.9, 0.1, 0.1)


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def measuring():
        h = Harness(pixbuf, bounds)
        h.use_tool("measure")
        return h

    check.section("the tool is registered")
    h = measuring()
    check("measure tool present", any(t.name == "measure" for t in h.overlay.tools))
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("just a colour, no thickness", keys == {"colour"}, keys)

    check.section("a drag commits a measurement")
    h = measuring()
    x, y = h.canvas_point()
    h.drag(x, y, 240, 96)
    check("one item", len(h.items) == 1, len(h.items))
    check("of the right kind", isinstance(h.items[0], Measurement))

    clicked = measuring()
    clicked.click(*clicked.canvas_point())
    check("a click leaves nothing", not clicked.items, clicked.items)

    check.section("the numbers match the drag")
    item = h.items[0]
    across, down, diagonal = item.spans()
    check("width", round(across) == 240, across)
    check("height", round(down) == 96, down)
    check("diagonal", round(diagonal) == 258, diagonal)
    check("all three are shown when it is not on an axis",
          item.text() == "240 × 96 · 258 px", item.text())

    check.section("they are physical pixels, not logical ones")
    # On a HiDPI screen the two differ, and the physical number is the one
    # anyone measuring a screen wants.
    doubled = Measurement((0, 0), (240, 96), RED, 2.0)
    across, down, diagonal = doubled.spans()
    check("scaled by the canvas", (round(across), round(down)) == (480, 192),
          (across, down))
    check("and the text follows", doubled.text() == "480 × 192 · 517 px",
          doubled.text())
    check("the overlay hands its own scale to the item",
          abs(h.items[0].scale - h.overlay.scale) < 1e-9,
          "%s vs %s" % (h.items[0].scale, h.overlay.scale))

    check.section("a straight drag reads as one number")
    flat = Measurement((10, 10), (250, 10), RED, 1.0)
    check("horizontal", flat.text() == "240 px", flat.text())
    upright = Measurement((10, 10), (10, 100), RED, 1.0)
    check("vertical", upright.text() == "90 px", upright.text())

    check.section("shift snaps it to an axis")
    h = measuring()
    x, y = h.canvas_point()
    h.drag(x, y, 300, 40, steps=3, shift=True)
    item = h.items[0]
    check("snapped flat", abs(item.end[1] - y) < 0.5, "dy %.2f" % (item.end[1] - y))
    check("and reads as a single number", item.text().count("×") == 0, item.text())

    h = measuring()
    h.drag(x, y, 300, 40, steps=3)
    check("unconstrained by default", h.items[0].text().count("×") == 1,
          h.items[0].text())

    check.section("it goes into the captured image, like every other tool")
    h = measuring()
    x, y = h.canvas_point()
    h.drag(x, y, 200, 0)
    check("committed to the scene", len(h.items) == 1)
    h.click_button("capture")
    check("captured", h.finished and h.result is not None)

    check.section("undo takes it back")
    h = measuring()
    h.drag(*h.canvas_point(), 200, 80)
    h.key("z", control=True)
    check("undone", not h.items, h.items)

    check.section("bounds allow for the ticks and the readout")
    item = Measurement((100, 100), (300, 100), RED, 1.0)
    box = item.bounds()
    check("taller than the line itself", box.height > 20, box)
    check("wider than the two ends", box.x < 100 and box.right > 300, box)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
