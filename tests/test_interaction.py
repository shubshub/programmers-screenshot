#!/usr/bin/env python3
"""Overlay behaviour: select with a tool, then confirm with the toolbar.

Runs headless against the real GTK objects, driving the event handlers
directly. No display interaction is needed beyond opening one.

    python3 tests/test_interaction.py
"""

import os
import sys
import types

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)

from programmers_screenshot import capture, theme, toolbar, tools  # noqa: E402
from programmers_screenshot.overlay import Overlay  # noqa: E402


class Checker:
    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n%s" % title)

    def __call__(self, name, condition, detail=""):
        mark = "  ok  " if condition else " FAIL "
        print("%s %s%s" % (mark, name, ("  [%s]" % detail) if detail else ""))
        if not condition:
            self.failures.append(name)


class Harness:
    """An Overlay with its window and exit path stubbed out."""

    def __init__(self, pixbuf, bounds):
        self.overlay = Overlay(pixbuf, bounds, tools.build_tools())
        self.overlay.window = types.SimpleNamespace(queue_draw=lambda: None)
        self.overlay._finish = self._finish
        self.overlay._set_cursor = self._set_cursor
        self.finished = False
        self.rect = None
        self.cursor = None

    def _finish(self, rect):
        self.finished = True
        self.rect = rect

    def _set_cursor(self, name):
        self.cursor = name

    # -- input shorthands --------------------------------------------------

    def click(self, x, y, button=1):
        self.press(x, y, button)
        self.release(x, y, button)

    def press(self, x, y, button=1):
        self.overlay._on_press(self.overlay.window, _event(x, y, button))

    def move(self, x, y):
        self.overlay._on_motion(self.overlay.window, _event(x, y))

    def release(self, x, y, button=1):
        self.overlay._on_release(self.overlay.window, _event(x, y, button))

    def key(self, name):
        self.overlay._on_key(
            self.overlay.window,
            types.SimpleNamespace(keyval=Gdk.keyval_from_name(name)),
        )

    def drag(self, x, y, width, height):
        self.press(x, y)
        self.move(x + width, y + height)
        self.release(x + width, y + height)

    # -- positions ---------------------------------------------------------

    def button(self, kind):
        return next(b for b in self.overlay.toolbar.buttons if b.kind == kind)

    def on_button(self, kind):
        rect = self.button(kind).rect
        return rect.x + rect.width / 2, rect.y + rect.height / 2

    def canvas_point(self, dx=0, dy=0):
        """A point safely below the toolbar."""
        monitor = self.overlay.monitor
        return monitor.x + 200 + dx, monitor.y + theme.BAR_HEIGHT + 100 + dy

    @property
    def selection(self):
        return self.overlay._selection()


def _event(x, y, button=1):
    return types.SimpleNamespace(x=x, y=y, button=button)


def main():
    Gtk.init_check()
    display = Gdk.Display.get_default()
    pixbuf, bounds = capture.capture_screen(display)

    check = Checker()

    def overlay():
        return Harness(pixbuf, bounds)

    check.section("a drag selects a region but does not capture")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 400, 400)
    check("selection made", h.selection is not None, h.selection)
    check("capture button enabled", h.overlay._can_capture())
    check("nothing captured yet", not h.finished)

    check.section("the Capture button returns the selection")
    h.click(*h.on_button(toolbar.CAPTURE))
    check("finished", h.finished)
    check(
        "rect matches the drag",
        h.rect is not None and (h.rect.width, h.rect.height) == (400, 400),
        h.rect,
    )

    check.section("Capture is inert with nothing selected")
    h = overlay()
    check("starts disabled", not h.overlay._can_capture())
    h.click(*h.on_button(toolbar.CAPTURE))
    check("did not finish", not h.finished)

    check.section("the cancel button aborts")
    h = overlay()
    h.click(*h.on_button(toolbar.CANCEL))
    check("finished with no rect", h.finished and h.rect is None)

    check.section("a button press that slides off does not fire")
    h = overlay()
    cx, cy = h.on_button(toolbar.CANCEL)
    h.press(cx, cy)
    h.release(cx + 400, cy)
    check("cancel did not fire", not h.finished)

    check.section("the toolbar is not a drawing surface")
    h = overlay()
    monitor = h.overlay.monitor
    h.press(monitor.x + 700, monitor.y + 10)
    h.move(monitor.x + 900, monitor.y + 300)
    h.release(monitor.x + 900, monitor.y + 300)
    check("no selection started on the bar", h.selection is None, h.selection)

    check.section("dragging up into the bar still selects that strip")
    h = overlay()
    x, y = h.canvas_point(dy=300)
    h.press(x, y)
    h.move(x + 500, monitor.y + 2)
    h.release(x + 500, monitor.y + 2)
    check("reaches the top of the screen", h.selection.y <= 2, h.selection)

    check.section("a plain click clears the selection")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 400, 400)
    h.click(x + 50, y + 50)
    check("cleared", h.selection is None, h.selection)
    check("capture disabled again", not h.overlay._can_capture())

    check.section("keyboard shortcuts")
    h = overlay()
    h.key("Return")
    check("Enter does nothing without a selection", not h.finished)
    x, y = h.canvas_point()
    h.drag(x, y, 300, 300)
    h.key("Return")
    check("Enter captures", h.finished and h.rect is not None, h.rect)

    h = overlay()
    h.key("Escape")
    check("Escape cancels", h.finished and h.rect is None)

    h = overlay()
    h.press(*h.canvas_point(), button=3)
    check("right-click cancels", h.finished and h.rect is None)

    check.section("the cursor tracks what is under it")
    h = overlay()
    h.move(monitor.x + 700, monitor.y + 10)
    check("arrow over the toolbar", h.cursor == "default", h.cursor)
    h.move(*h.canvas_point())
    check("crosshair over the canvas", h.cursor == "crosshair", h.cursor)

    check.section("tool buttons switch tools")
    h = overlay()
    h.click(*h.on_button(toolbar.TOOL))
    check("rectangle tool active", h.overlay.active_tool.name == "rectangle")
    check("clicking a tool does not capture", not h.finished)

    check.section("the captured pixels match the selection")
    h = overlay()
    x, y = h.canvas_point()
    h.drag(x, y, 321, 234)
    region = capture.crop(pixbuf, h.selection, h.overlay.scale)
    check(
        "crop is the right size",
        (region.get_width(), region.get_height()) == (321, 234),
        "%dx%d" % (region.get_width(), region.get_height()),
    )

    print("\n%d failure(s)" % len(check.failures))
    return 1 if check.failures else 0


if __name__ == "__main__":
    sys.exit(main())
