#!/usr/bin/env python3
"""Tooltips: hovering a toolbar button says what it is.

    python3 tests/test_tooltips.py
"""

import os
import sys

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import Checker, Harness  # noqa: E402

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)

from programmers_screenshot import capture, theme, toolbar  # noqa: E402
from programmers_screenshot.tools import ALL_TOOLS  # noqa: E402


def measuring_context():
    return cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


def centre(rect):
    return rect.x + rect.width / 2, rect.y + rect.height / 2


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()
    cr = measuring_context()

    check.section("every tool has something to say")
    # A new tool shipping with a blank label would give a silent button.
    for factory in ALL_TOOLS:
        tool = factory()
        check("%s has a label" % tool.name, bool(tool.label), tool.label)

    check.section("hovering a tool button reports its label")
    h = Harness(pixbuf, bounds)
    for factory in ALL_TOOLS:
        name = factory.name
        button = h.button(toolbar.TOOL, name)
        h.move(*centre(button.rect))
        check("%s -> %r" % (name, factory.label),
              h.bar.tooltip_for(h.bar.hovered) == factory.label,
              h.bar.tooltip_for(h.bar.hovered))

    check.section("the other buttons")
    h.move(*centre(h.button(toolbar.CANCEL).rect))
    check("the cross explains itself",
          h.bar.tooltip_for(h.bar.hovered)
          == "Close without capturing",
          h.bar.tooltip_for(h.bar.hovered))
    h.move(*centre(h.button(toolbar.CAPTURE).rect))
    check("Capture needs none, it is already a word",
          h.bar.tooltip_for(h.bar.hovered) is None)

    check.section("moving away clears it")
    h.move(*h.canvas_point())
    check("nothing hovered", h.bar.hovered is None)
    check("no tooltip", h.bar.tooltip_for(h.bar.hovered) is None)

    check.section("settings that draw pictures get names")
    h = Harness(pixbuf, bounds)
    h.use_tool("line")
    wanted = {
        "shape": {"Line", "Circle", "Arrow"},
        "width": {"2 px", "4 px", "8 px", "16 px"},
        "colour": {"Red", "Amber", "Green", "Blue", "White", "Black"},
    }
    for key, expected in wanted.items():
        buttons = [b for b in h.bar.setting_buttons if b.setting.key == key]
        said = {h.bar.tooltip_for(b) for b in buttons}
        check("%s options are named" % key, said == expected, sorted(s or "-" for s in said))

    check.section("settings that already show their caption do not repeat it")
    h = Harness(pixbuf, bounds)
    h.use_tool("text")
    for key in ("text-size", "text-background"):
        buttons = [b for b in h.bar.setting_buttons if b.setting.key == key]
        check("%s stays quiet" % key,
              all(h.bar.tooltip_for(b) is None for b in buttons))

    check.section("the box stays on the monitor")
    h = Harness(pixbuf, bounds)
    monitor = h.overlay.monitor
    for kind, name in ((toolbar.TOOL, "rectangle"), (toolbar.CANCEL, None)):
        button = h.button(kind, name)
        text = h.bar.tooltip_for(button)
        box = h.bar.tooltip_box(cr, text, button)
        check("%s: left edge on screen" % (name or "cancel"),
              box.x >= monitor.x, box.x)
        check("%s: right edge on screen" % (name or "cancel"),
              box.right <= monitor.right, "%.0f vs %.0f" % (box.right, monitor.right))

    check.section("it sits below the whole bar, never on the settings row")
    h = Harness(pixbuf, bounds)
    h.use_tool("pen")  # pen has settings, so there are two rows
    button = h.button(toolbar.TOOL, "pen")
    box = h.bar.tooltip_box(cr, "Pen", button)
    bar = h.bar
    check("clears the settings row",
          box.y >= bar.settings_rect.bottom, "%.0f vs %.0f" % (box.y, bar.settings_rect.bottom))
    h.use_tool("rectangle")  # no settings row
    box = h.bar.tooltip_box(cr, "Region", button)
    check("sits just under the bar when there is no settings row",
          box.y >= bar.rect.bottom, "%.0f vs %.0f" % (box.y, bar.rect.bottom))

    check.section("nothing shows mid-drag")
    # Hover is not updated once the pointer is grabbed, so a stale tooltip
    # would otherwise hang there for the whole gesture.
    h = Harness(pixbuf, bounds)
    hovered_button = h.button(toolbar.TOOL, "pen")
    h.move(*centre(hovered_button.rect))
    check("hovered before the drag", h.bar.hovered is not None)

    x, y = h.canvas_point()
    h.press(x, y)
    h.move(x + 80, y + 40)
    check("still dragging", h.overlay._dragging)
    check("and still hovering that button, staleley",
          h.bar.hovered is hovered_button)

    box = h.bar.tooltip_box(cr, "Pen", hovered_button)
    drawn = render_area(h, bounds, box)
    h.bar.hovered = None
    blank = render_area(h, bounds, box)
    check("the tooltip area is untouched while dragging", drawn == blank,
          "%d bytes differ" % sum(1 for a, b in zip(drawn, blank) if a != b))

    h.release(x + 80, y + 40)

    return check.report()


def render_area(harness, bounds, box):
    """Paint the overlay and return the bytes of one rectangle of it."""
    surface = cairo.ImageSurface(
        cairo.FORMAT_ARGB32, int(bounds.width), int(bounds.height)
    )
    harness.overlay._on_draw(harness.overlay.window, cairo.Context(surface))
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    rows = []
    for py in range(int(box.y), int(box.bottom)):
        start = py * stride + int(box.x) * 4
        rows.append(bytes(data[start:start + int(box.width) * 4]))
    return b"".join(rows)


if __name__ == "__main__":
    sys.exit(main())
