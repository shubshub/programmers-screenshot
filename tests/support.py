"""Shared scaffolding for the headless tests.

Drives the overlay's real event handlers with stand-in events, against a real
GTK display but without ever mapping a window.
"""

import os
import sys
import types

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk  # noqa: E402

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)

from programmers_screenshot import theme  # noqa: E402
from programmers_screenshot.overlay import Overlay  # noqa: E402
from programmers_screenshot.tools import build_tools  # noqa: E402


class Checker:
    """Prints a running tally and remembers what failed."""

    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n%s" % title)

    def __call__(self, name, condition, detail=""):
        # detail may be a tuple (a colour, a size); wrap it so % does not
        # treat it as an argument list.
        suffix = "  [%s]" % (detail,) if detail != "" and detail is not None else ""
        print("%s %s%s" % ("  ok  " if condition else " FAIL ", name, suffix))
        if not condition:
            self.failures.append(name)

    def report(self):
        print("\n%d failure(s)" % len(self.failures))
        return 1 if self.failures else 0


def event(x, y, button=1):
    return types.SimpleNamespace(x=x, y=y, button=button)


def pixel(pixbuf, x, y):
    """The (r, g, b) of one pixel."""
    data = pixbuf.get_pixels()
    offset = y * pixbuf.get_rowstride() + x * pixbuf.get_n_channels()
    return tuple(data[offset:offset + 3])


def render_overlay(harness):
    """Paint the overlay exactly as the draw handler would, and return a
    reader for its pixels. Used to check what is actually on screen mid-drag,
    which no amount of state inspection can tell you."""
    import cairo

    bounds = harness.overlay.bounds
    surface = cairo.ImageSurface(
        cairo.FORMAT_ARGB32, int(bounds.width), int(bounds.height)
    )
    harness.overlay._on_draw(harness.overlay.window, cairo.Context(surface))
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()

    def read(x, y):
        offset = int(y) * stride + int(x) * 4
        blue, green, red = data[offset], data[offset + 1], data[offset + 2]
        return (red, green, blue)

    return read


class Harness:
    """An Overlay with its window and exit path stubbed out."""

    def __init__(self, pixbuf, bounds, tools=None):
        self.overlay = Overlay(pixbuf, bounds, tools or build_tools())
        self.overlay.window = types.SimpleNamespace(
            queue_draw=lambda: None, queue_draw_area=lambda *a: None
        )
        self.overlay._finish = self._finish
        self.overlay._set_cursor = self._set_cursor
        self.finished = False
        self.result = None
        self.cursor = None

    def _finish(self, result):
        self.finished = True
        self.result = result

    def _set_cursor(self, name):
        self.cursor = name

    # -- input -------------------------------------------------------------

    def press(self, x, y, button=1):
        self.overlay._on_press(self.overlay.window, event(x, y, button))

    def move(self, x, y):
        self.overlay._on_motion(self.overlay.window, event(x, y))

    def release(self, x, y, button=1):
        self.overlay._on_release(self.overlay.window, event(x, y, button))

    def click(self, x, y):
        self.press(x, y)
        self.release(x, y)

    def drag(self, x, y, dx, dy, steps=1):
        self.press(x, y)
        for step in range(1, steps + 1):
            self.move(x + dx * step / steps, y + dy * step / steps)
        self.release(x + dx, y + dy)

    def key(self, name, control=False, shift=False):
        state = 0
        if control:
            state |= Gdk.ModifierType.CONTROL_MASK
        if shift:
            state |= Gdk.ModifierType.SHIFT_MASK
        self.overlay._on_key(
            self.overlay.window,
            types.SimpleNamespace(keyval=Gdk.keyval_from_name(name), state=state),
        )

    # -- positions ---------------------------------------------------------

    def button(self, kind, tool_name=None):
        for candidate in self.overlay.toolbar.buttons:
            if candidate.kind == kind and (
                tool_name is None or getattr(candidate.tool, "name", None) == tool_name
            ):
                return candidate
        raise AssertionError("no %s button on the toolbar" % kind)

    def click_button(self, kind, tool_name=None):
        rect = self.button(kind, tool_name).rect
        self.click(rect.x + rect.width / 2, rect.y + rect.height / 2)

    def use_tool(self, name):
        self.overlay._choose_tool(
            next(tool for tool in self.overlay.tools if tool.name == name)
        )

    def canvas_point(self, dx=0, dy=0):
        """A point safely below every toolbar row."""
        monitor = self.overlay.monitor
        return (
            monitor.x + 200 + dx,
            monitor.y + theme.BAR_HEIGHT + theme.SETTINGS_HEIGHT + 60 + dy,
        )

    @property
    def region(self):
        return self.overlay.scene.region

    @property
    def items(self):
        return self.overlay.scene.items
