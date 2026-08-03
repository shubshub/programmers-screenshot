#!/usr/bin/env python3
"""Overlay behaviour: marking things out, then confirming with the toolbar.

Runs headless against the real GTK objects, driving the event handlers
directly. No display interaction is needed beyond opening one.

    python3 tests/test_interaction.py
"""

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import Checker, Harness  # noqa: E402

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)

from programmers_screenshot import capture, toolbar  # noqa: E402


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def overlay():
        return Harness(pixbuf, bounds)

    check.section("a drag marks out a region but does not capture")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 400, 400)
    check("region set", h.region is not None, h.region)
    check("nothing captured yet", not h.finished)

    check.section("the Capture button takes the region")
    h.click_button(toolbar.CAPTURE)
    check("finished", h.finished)
    check(
        "the image is the size of the region",
        h.result is not None
        and (h.result.get_width(), h.result.get_height()) == (400, 400),
        h.result and "%dx%d" % (h.result.get_width(), h.result.get_height()),
    )

    check.section("Capture with nothing marked out takes the whole screen")
    # Replaces the old "Capture is inert with nothing selected": under the
    # current model the region is optional and Capture is always live.
    h = overlay()
    h.click_button(toolbar.CAPTURE)
    check("finished", h.finished)
    check(
        "the image is the whole virtual screen",
        h.result is not None
        and (h.result.get_width(), h.result.get_height())
        == (pixbuf.get_width(), pixbuf.get_height()),
        h.result and "%dx%d" % (h.result.get_width(), h.result.get_height()),
    )

    check.section("the cancel button aborts")
    h = overlay()
    h.click_button(toolbar.CANCEL)
    check("finished with no image", h.finished and h.result is None)

    check.section("a button press that slides off does not fire")
    h = overlay()
    rect = h.button(toolbar.CANCEL).rect
    h.press(rect.x + rect.width / 2, rect.y + rect.height / 2)
    h.release(rect.x + rect.width / 2 + 400, rect.y + rect.height / 2)
    check("cancel did not fire", not h.finished)

    check.section("the toolbar is not a drawing surface")
    h = overlay()
    monitor = h.overlay.monitor
    h.press(monitor.x + 700, monitor.y + 10)
    h.move(monitor.x + 900, monitor.y + 300)
    h.release(monitor.x + 900, monitor.y + 300)
    check("no region started on the bar", h.region is None, h.region)

    check.section("dragging up into the bar still marks out that strip")
    h = overlay()
    top = h.overlay.monitor.y  # not necessarily 0: the active monitor may be offset
    x, y = h.canvas_point(dy=300)
    h.press(x, y)
    h.move(x + 500, top + 2)
    h.release(x + 500, top + 2)
    check("reaches the top of the monitor", h.region.y <= top + 2, h.region)

    check.section("starting a new region deletes the old one")
    # It used to stay on the scene and keep being drawn, so the new drag
    # looked like it was rubbing the old rectangle out as it swept across.
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 300, 200)
    first = h.region
    check("one region marked out", first is not None)
    h.press(x + 600, y + 300)
    check("pressing removes it immediately", h.region is None, h.region)
    h.move(x + 900, y + 500)
    h.release(x + 900, y + 500)
    check("the new one replaces it",
          h.region is not None and h.region != first, h.region)

    check.section("undo walks back through both")
    h.key("z", control=True)
    check("first undo drops the new region", h.region is None, h.region)
    h.key("z", control=True)
    check("second undo brings the old one back", h.region == first, h.region)

    check.section("abandoning the new drag leaves the old one deleted")
    h = overlay()
    h.drag(x, y, 300, 200)
    h.press(x + 600, y + 300)
    h.key("Escape")
    check("still open", not h.finished)
    check("the old region stays gone", h.region is None, h.region)
    h.key("z", control=True)
    check("undo brings it back", h.region is not None, h.region)

    check.section("a plain click clears the region")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 400, 400)
    h.click(x + 50, y + 50)
    check("cleared", h.region is None, h.region)

    check.section("keyboard shortcuts")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 300, 300)
    h.key("Return")
    check("Enter captures", h.finished and h.result is not None)

    h = overlay()
    h.key("Escape")
    check("Escape cancels", h.finished and h.result is None)

    h = overlay()
    x, y = h.canvas_point()
    h.press(x, y)
    h.move(x + 100, y + 100)
    h.key("Escape")
    check("Escape mid-drag abandons the gesture, not the session",
          not h.finished and h.region is None)

    h = overlay()
    h.press(*h.canvas_point(), button=3)
    check("right-click cancels", h.finished and h.result is None)

    check.section("the cursor tracks what is under it")
    h = overlay()
    h.move(monitor.x + 700, monitor.y + 10)
    check("arrow over the toolbar", h.cursor == "default", h.cursor)
    h.move(*h.canvas_point())
    check("crosshair over the canvas", h.cursor == "crosshair", h.cursor)

    check.section("tool buttons switch tools")
    h = overlay()
    check("region tool is active first", h.overlay.active_tool.name == "rectangle")
    h.click_button(toolbar.TOOL, "pen")
    check("pen selected", h.overlay.active_tool.name == "pen")
    check("clicking a tool does not capture", not h.finished)
    h.click_button(toolbar.TOOL, "rectangle")
    check("and back again", h.overlay.active_tool.name == "rectangle")

    check.section("switching tools abandons a gesture in progress")
    h = overlay()
    h.use_tool("pen")
    x, y = h.canvas_point()
    h.press(x, y)
    h.move(x + 50, y + 50)
    h.use_tool("rectangle")
    check("nothing was committed", not h.items, h.items)

    check.section("the captured pixels match the region")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 321, 234)
    h.click_button(toolbar.CAPTURE)
    check(
        "crop is the right size",
        (h.result.get_width(), h.result.get_height()) == (321, 234),
        "%dx%d" % (h.result.get_width(), h.result.get_height()),
    )

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
