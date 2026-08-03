#!/usr/bin/env python3
"""A toolbar on every monitor, all views of the same state.

Needs more than one monitor to say anything useful; on a single-screen
machine most of it is skipped.

    python3 tests/test_multi_monitor.py
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


def centre(rect):
    return rect.x + rect.width / 2, rect.y + rect.height / 2


def canvas_point_on(monitor):
    """Somewhere on this monitor that no toolbar covers."""
    return (
        monitor.x + 120,
        monitor.y + theme.BAR_HEIGHT + theme.SETTINGS_HEIGHT + 80,
    )


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    h = Harness(pixbuf, bounds)
    bars = h.overlay.toolbars.bars
    monitors = h.overlay.monitors

    check.section("one bar per monitor")
    check("a bar for every monitor", len(bars) == len(monitors),
          "%d bars, %d monitors" % (len(bars), len(monitors)))
    check("the pointer's monitor comes first",
          h.overlay.monitor == monitors[0], monitors[0])
    check("primary is that bar", h.overlay.toolbars.primary is bars[0])

    check.section("each bar is laid out inside its own monitor")
    for bar, monitor in zip(bars, monitors):
        within = (bar.rect.x == monitor.x and bar.rect.width == monitor.width
                  and bar.rect.y == monitor.y)
        check("bar spans %dx%d at (%d,%d)"
              % (monitor.width, theme.BAR_HEIGHT, monitor.x, monitor.y),
              within, bar.rect)
        buttons_inside = all(
            monitor.x <= b.rect.x and b.rect.right <= monitor.right
            for b in bar.buttons
        )
        check("  its buttons stay on that monitor", buttons_inside)

    if len(bars) < 2:
        print("\nonly one monitor: skipping the rest")
        return check.report()

    second = bars[1]
    second_monitor = monitors[1]

    check.section("the bars cover their own strips and nothing else")
    check("primary covers its own bar", h.overlay.toolbars.covers(*centre(bars[0].buttons[0].rect)))
    check("and the second bar's too",
          h.overlay.toolbars.covers(*centre(second.buttons[0].rect)))
    check("canvas on the second monitor is free",
          not h.overlay.toolbars.covers(*canvas_point_on(second_monitor)))

    check.section("a tool chosen anywhere is active everywhere")
    pen_on_second = next(b for b in second.buttons
                         if b.kind == toolbar.TOOL and b.tool.name == "pen")
    h.click(*centre(pen_on_second.rect))
    check("pen is active", h.overlay.active_tool.name == "pen")
    check("both bars show the settings row",
          all(bar.settings_rect is not None for bar in bars))
    h.use_tool("rectangle")
    check("and both hide it again",
          all(bar.settings_rect is None for bar in bars))

    check.section("Capture works from the second monitor")
    h = Harness(pixbuf, bounds)
    second = h.overlay.toolbars.bars[1]
    capture_button = next(b for b in second.buttons if b.kind == toolbar.CAPTURE)
    h.click(*centre(capture_button.rect))
    check("it captured", h.finished and h.result is not None)
    check("the whole screen, no region marked",
          (h.result.get_width(), h.result.get_height())
          == (pixbuf.get_width(), pixbuf.get_height()),
          "%dx%d" % (h.result.get_width(), h.result.get_height()))

    check.section("hovering one bar leaves the others alone")
    h = Harness(pixbuf, bounds)
    bars = h.overlay.toolbars.bars
    h.move(*centre(bars[1].buttons[0].rect))
    check("second bar is hovered", bars[1].hovered is not None)
    check("first bar is not", bars[0].hovered is None, bars[0].hovered)
    h.move(*centre(bars[0].buttons[0].rect))
    check("and it swaps over",
          bars[0].hovered is not None and bars[1].hovered is None)
    h.move(*canvas_point_on(h.overlay.monitors[0]))
    check("leaving the bars clears both",
          all(bar.hovered is None for bar in bars))

    check.section("only one tooltip is drawn")
    h = Harness(pixbuf, bounds)
    bars = h.overlay.toolbars.bars
    h.move(*centre(bars[1].buttons[0].rect))
    said = [bar.tooltip_for(bar.hovered) for bar in bars]
    check("exactly one bar has something to say",
          sum(1 for text in said if text) == 1, said)

    check.section("no drag can start under any bar")
    h = Harness(pixbuf, bounds)
    second_monitor = h.overlay.monitors[1]
    h.press(second_monitor.x + 300, second_monitor.y + 10)
    h.move(second_monitor.x + 500, second_monitor.y + 300)
    h.release(second_monitor.x + 500, second_monitor.y + 300)
    check("nothing marked out from the second bar", h.region is None, h.region)

    check.section("dragging upward into the second bar still works")
    h = Harness(pixbuf, bounds)
    second_monitor = h.overlay.monitors[1]
    start = canvas_point_on(second_monitor)
    h.press(*start)
    h.move(start[0] + 400, second_monitor.y + 2)
    h.release(start[0] + 400, second_monitor.y + 2)
    check("reaches the top of that monitor",
          h.region is not None and h.region.y <= second_monitor.y + 2, h.region)

    check.section("the hint is repeated on every monitor")
    h = Harness(pixbuf, bounds)
    surface = cairo.ImageSurface(
        cairo.FORMAT_ARGB32, int(bounds.width), int(bounds.height)
    )
    h.overlay._on_draw(h.overlay.window, cairo.Context(surface))
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()

    def hint_row_ink(monitor):
        row = int(monitor.y + monitor.height * 0.86) + 12
        centre_x = int(monitor.x + monitor.width / 2)
        return sum(
            1
            for px in range(centre_x - 200, centre_x + 200)
            if data[row * stride + px * 4 + 3] > 0
        )

    for index, monitor in enumerate(h.overlay.monitors):
        check("monitor %d has a hint" % index, hint_row_ink(monitor) > 100,
              hint_row_ink(monitor))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
