#!/usr/bin/env python3
"""The floating palette, and the sub-tool flyouts.

Bar mode is the default and has to stay exactly as it was, so the first
section checks that nothing moved for anyone who does not turn this on.

    python3 tests/test_palette.py
"""

import sys
import types

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from support import Checker, Harness  # noqa: E402

from programmers_screenshot import capture, preferences, theme  # noqa: E402
from programmers_screenshot import toolbar as tb  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402
from programmers_screenshot.settings import SettingValues  # noqa: E402
from programmers_screenshot.tools import build_tools  # noqa: E402

MONITOR = Rect(0, 0, 1920, 1080)


def bars(mode, origin=None, monitors=None):
    return tb.Toolbars(build_tools(), monitors or [MONITOR], SettingValues(),
                       mode, origin)


def centre(rect):
    return (rect.x + rect.width / 2, rect.y + rect.height / 2)


def main():
    check = Checker()
    if not Gtk.init_check()[0]:
        check("a display is available", False)
        return check.report()

    # ------------------------------------------------------------------
    check.section("bar mode is untouched")
    second = Rect(1920, 0, 1280, 1024)
    fixed = bars(tb.BAR, monitors=[MONITOR, second])
    check("still one bar per monitor", len(fixed.bars) == 2, len(fixed.bars))
    check("still full width and pinned to the top",
          fixed.bars[0].rect == Rect(0, 0, 1920, theme.BAR_HEIGHT),
          fixed.bars[0].rect)
    check("no palette to speak of", fixed.palette is None)
    check("and nothing to grab", not fixed.grab_at(*centre(fixed.bars[0].rect)))

    # ------------------------------------------------------------------
    check.section("palette mode gives one floating rectangle")
    floating = bars(tb.PALETTE, monitors=[MONITOR, second])
    check("one palette, not one per monitor", len(floating.bars) == 1,
          len(floating.bars))
    palette = floating.palette
    check("it is compact, not full width",
          palette.rect.width < MONITOR.width / 2, palette.rect.width)
    check("it sits over the screen, not above it",
          palette.rect.y > MONITOR.y, palette.rect.y)
    check("a button per tool or group, not per tool",
          len([b for b in palette.buttons if b.kind == tb.TOOL])
          == len(palette.entries), len(palette.entries))
    for kind in (tb.CAPTURE, tb.CANCEL, tb.SETTINGS):
        check("%s is reachable on it" % kind,
              any(b.kind == kind for b in palette.buttons))
    check("the tools are a grid, not a row",
          len({b.rect.y for b in palette.buttons if b.kind == tb.TOOL}) > 1)

    check.section("it has a handle, and only the handle picks it up")
    check("the strip is a grab", floating.grab_at(*centre(palette.grab_rect)))
    tool_button = next(b for b in palette.buttons if b.kind == tb.TOOL)
    check("a tool button is not", not floating.grab_at(*centre(tool_button.rect)))
    check("nor is bare canvas", not floating.grab_at(900, 900))

    # ------------------------------------------------------------------
    check.section("dragging it moves everything on it")
    before = (palette.rect.x, palette.rect.y)
    button_before = centre(tool_button.rect)
    palette.move_to(before[0] + 300, before[1] + 200)
    check("the rectangle moved",
          (palette.rect.x, palette.rect.y) == (before[0] + 300, before[1] + 200),
          (palette.rect.x, palette.rect.y))
    moved_button = next(b for b in palette.buttons if b.kind == tb.TOOL)
    check("and the buttons went with it",
          centre(moved_button.rect) == (button_before[0] + 300,
                                        button_before[1] + 200),
          centre(moved_button.rect))
    check("hit testing follows", palette.button_at(*centre(moved_button.rect))
          is moved_button)

    check.section("it cannot be dragged off every screen")
    # `floating` spans two monitors, so the far edges are the outer edges of
    # the pair -- reaching the second one is the point, not a failure.
    palette.move_to(-5000, -5000)
    check("the handle is still on the leftmost",
          palette.grab_rect.right > MONITOR.x, palette.rect.x)
    check("and has not gone above the top", palette.rect.y >= MONITOR.y,
          palette.rect.y)
    palette.move_to(9000, 9000)
    check("nor off the right of the rightmost",
          palette.rect.x < second.right, palette.rect.x)
    check("and it did get as far as that second monitor",
          palette.rect.x > MONITOR.right, palette.rect.x)
    check("nor below the bottom",
          palette.rect.y <= second.bottom - theme.PALETTE_GRAB, palette.rect.y)

    check.section("tooltips flip above when there is no room below")
    context = _measuring_context()
    palette.move_to(100, 100)
    high_at = palette.rect.bottom          # note it now; the palette moves below
    high = palette.tooltip_box(context, "Pen", tool_button)

    palette.move_to(100, MONITOR.bottom - 80)
    low = palette.tooltip_box(context, "Pen", tool_button)

    check("below when there is room", high.y >= high_at, (high.y, high_at))
    check("above when there is not", low.bottom <= palette.rect.y + 1,
          (low.bottom, palette.rect.y))
    check("and on the screen either way",
          low.y >= MONITOR.y and high.bottom <= MONITOR.bottom)

    # ------------------------------------------------------------------
    check.section("a tool with variants keeps them off the settings row")
    bar = tb.Toolbar(build_tools(), MONITOR, SettingValues())
    line = next(t for t in bar.tools if t.name == "line")
    bar.show_settings_for(line)
    keys = {b.setting.key for b in bar.setting_buttons}
    check("shape is not on the row", "shape" not in keys, keys)
    check("but colour and width still are", keys == {"colour", "width"}, keys)

    pen = next(t for t in bar.tools if t.name == "pen")
    bar.show_settings_for(pen)
    check("a tool without variants is unaffected",
          {b.setting.key for b in bar.setting_buttons} == {"colour", "width"})

    check.section("the flyout opens beside the button")
    bar.show_settings_for(line)
    button = next(b for b in bar.buttons if b.kind == tb.TOOL and b.tool is line)
    bar.open_flyout(button)
    _owner, rect, options = bar.flyout
    check("four shapes", [b.value for b in options]
          == ["line", "box", "circle", "arrow"], [b.value for b in options])
    check("beside the button, not over it",
          rect.x >= button.rect.right or rect.right <= button.rect.x,
          (rect.x, button.rect.x))
    check("it belongs to the toolbar for hit testing",
          bar.covers(*centre(rect)))
    check("and its options are findable",
          bar.button_at(*centre(options[2].rect)) is options[2])
    check("they are VARIANT buttons", options[0].kind == tb.VARIANT)
    check("each one names itself on hover",
          bar.tooltip_for(options[3]) == "Arrow", bar.tooltip_for(options[3]))

    check.section("a flyout near the right edge opens to the left instead")
    narrow = tb.Toolbar(build_tools(), Rect(0, 0, 1920, 1080), SettingValues())
    edge = next(b for b in narrow.buttons if b.kind == tb.TOOL and b.tool.name == "line")
    edge.rect = Rect(1900, 6, theme.TOOL_BUTTON, theme.TOOL_BUTTON)
    narrow.open_flyout(edge)
    _o, flyout_rect, _b = narrow.flyout
    check("it went left", flyout_rect.right <= edge.rect.x, flyout_rect)
    check("and stayed on the monitor", flyout_rect.x >= 0, flyout_rect.x)

    check.section("closing it")
    check("close_flyouts reports it did something", bars_with_flyout(narrow))
    check("and it is gone", narrow.flyout is None)

    # ------------------------------------------------------------------
    check.section("switching mode takes effect at once, not next launch")
    # The settings window is opened from the toolbar, so a toggle that did
    # nothing until restart would look broken.
    pixbuf, real_bounds = capture.capture_screen(Gdk.Display.get_default())
    h = Harness(pixbuf, real_bounds)
    check("it starts in bar mode", h.overlay.toolbars.mode == tb.BAR)
    h.overlay._apply_toolbar_mode({"toolbar": tb.PALETTE, "palette": None})
    check("switching gives a palette", h.overlay.toolbars.mode == tb.PALETTE)
    check("and just one of it", len(h.overlay.toolbars.bars) == 1)
    check("with the active tool's settings on it",
          h.overlay.toolbars.bars[0].tools is h.overlay.tools)
    h.overlay._apply_toolbar_mode({"toolbar": tb.BAR})
    check("switching back restores a bar per monitor",
          len(h.overlay.toolbars.bars) == len(h.overlay.monitors),
          len(h.overlay.toolbars.bars))

    # ------------------------------------------------------------------
    check.section("the palette can be dragged onto another monitor")
    # It could not: the clamp kept the grab strip on whichever monitor the
    # pointer happened to be on when the overlay opened, so on two screens
    # the palette was stuck on one of them. Every check here passes on a
    # single monitor, which is exactly how that got through.
    right = Rect(0, 0, 1920, 1080)
    left = Rect(-1600, 40, 1600, 900)
    pair = tb.Toolbars(build_tools(), [right, left], SettingValues(), tb.PALETTE)
    moving = pair.palette
    check("it starts on the monitor the pointer was on",
          moving.current_monitor() == right, moving.current_monitor())

    moving.move_to(left.x + 300, left.y + 200)
    check("and can be dragged onto the other one",
          moving.rect.x == left.x + 300, moving.rect.x)
    check("which it then knows it is on",
          moving.current_monitor() == left, moving.current_monitor())

    moving.move_to(right.x + 500, right.y + 100)
    check("and back again", moving.rect.x == right.x + 500, moving.rect.x)
    check("knowing that too", moving.current_monitor() == right)

    check.section("but still not somewhere it cannot be got back from")
    moving.move_to(-99999, -99999)
    check("the handle stays on the leftmost screen",
          moving.grab_rect.right > left.x, moving.rect.x)
    check("and not above it", moving.rect.y >= left.y, moving.rect.y)
    moving.move_to(99999, 99999)
    check("nor off the right of the rightmost",
          moving.rect.x < right.right, moving.rect.x)
    check("nor below it",
          moving.rect.y <= right.bottom - theme.PALETTE_GRAB, moving.rect.y)

    check.section("tooltips and flyouts follow it across")
    ruler = _measuring_context()
    moving.move_to(left.x + 100, left.y + 100)
    tip = moving.tooltip_box(ruler, "Pen", moving.buttons[0])
    check("a tooltip is kept on the screen it is now on",
          left.x <= tip.x and tip.right <= left.right, (tip.x, tip.right))

    # A tool button hard against the right edge of the left-hand monitor: its
    # flyout has to open leftwards, judged against that monitor and not the
    # one the palette started on.
    edge = next(b for b in moving.buttons if b.kind == tb.TOOL and b.members)
    edge.rect = Rect(left.right - 30, left.y + 100, theme.TOOL_BUTTON,
                     theme.TOOL_BUTTON)
    moving.open_flyout(edge)
    _o, flyout_rect, _b = moving.flyout
    check("and a flyout opens away from that screen's edge",
          flyout_rect.right <= edge.rect.x, (flyout_rect.x, edge.rect.x))
    check("staying on it", flyout_rect.x >= left.x, flyout_rect.x)
    moving.flyout = None

    check.section("a position remembered on the second monitor is restored there")
    reopened = tb.Toolbars(build_tools(), [right, left], SettingValues(),
                           tb.PALETTE, (left.x + 250, left.y + 150))
    check("it comes back where it was left",
          (reopened.palette.rect.x, reopened.palette.rect.y)
          == (left.x + 250, left.y + 150),
          (reopened.palette.rect.x, reopened.palette.rect.y))
    check("on the right screen", reopened.palette.current_monitor() == left)

    check.section("related tools share one button")
    bar2 = tb.Toolbar(build_tools(), MONITOR, SettingValues())
    names = [[m.name for m in e] for e in bar2.entries]
    check("pen and highlighter are one entry",
          ["pen", "highlight"] in names, names)
    check("black bar and pixelate are another",
          ["redact", "pixelate"] in names, names)
    check("eleven tools become nine buttons",
          len([b for b in bar2.buttons if b.kind == tb.TOOL]) == 9,
          len([b for b in bar2.buttons if b.kind == tb.TOOL]))
    check("ungrouped tools are untouched",
          ["rectangle"] in names and ["eraser"] in names, names)

    check.section("the group button shows, and remembers, its member")
    group = next(b for b in bar2.buttons if b.members
                 and b.members[0].group == "Redact")
    check("it starts on the first member",
          bar2.shown(group).label == "Black Bar", bar2.shown(group).label)
    check("and it has a flyout to open", tb.Toolbar.has_flyout(group))

    bar2.open_flyout(group)
    entries = bar2.flyout.buttons
    check("the flyout lists the members",
          [b.tool.label for b in entries] == ["Black Bar", "Pixelate"],
          [b.tool.label for b in entries])
    check("they carry a tool, not a setting value",
          entries[0].setting is None and entries[0].tool is not None)

    # Choosing the second member is what the overlay records.
    holder = types.SimpleNamespace(chosen=bar2.chosen)
    tb.Toolbars.choose_member(holder, entries[1])
    check("the group now shows Pixelate",
          bar2.shown(group).label == "Pixelate", bar2.shown(group).label)
    check("so one click gets it next time, no flyout needed",
          bar2.shown(group) is entries[1].tool)

    check.section("a tool without a group has no flyout")
    plain = next(b for b in bar2.buttons
                 if b.kind == tb.TOOL and b.tool.name == "eraser")
    check("no members", plain.members is None)
    check("and nothing behind it", not tb.Toolbar.has_flyout(plain))

    check.section("the preference decides which you get")
    check("bar is the default", preferences.DEFAULTS["toolbar"] == tb.BAR,
          preferences.DEFAULTS["toolbar"])
    check("and a palette position is remembered",
          "palette" in preferences.DEFAULTS)

    return check.report()


def bars_with_flyout(bar):
    holder = types.SimpleNamespace(bars=[bar])
    return tb.Toolbars.close_flyouts(holder)


def _measuring_context():
    import cairo
    return cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


if __name__ == "__main__":
    sys.exit(main())
