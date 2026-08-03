#!/usr/bin/env python3
"""The tool framework: scene, actions, settings, and adding a tool.

The last section is the one that matters. It defines a tool *inside this file*
and drives it end to end. If that ever needs a change to a core module to pass,
the framework has failed its purpose.

    python3 tests/test_framework.py
"""

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import Checker, Harness, pixel, render_overlay  # noqa: E402

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)

from programmers_screenshot import capture, theme, toolbar  # noqa: E402
from programmers_screenshot.actions import AddItem, SetRegion  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402
from programmers_screenshot.scene import Scene  # noqa: E402
from programmers_screenshot.settings import (  # noqa: E402
    COLOUR,
    WIDTH,
    ChoiceSetting,
    SettingValues,
)
from programmers_screenshot.tools import ShapeTool  # noqa: E402
from programmers_screenshot.tools.items import Item, Stroke  # noqa: E402


# --------------------------------------------------------------------------
# A tool written the way a newcomer would write one. Nothing outside this file
# knows it exists.
# --------------------------------------------------------------------------


class Blob(Item):
    """A filled square, so the test can find it in the rendered pixels."""

    def __init__(self, start, end, colour):
        self.rect = Rect.from_points(start, end)
        self.colour = colour

    def draw(self, cr):
        cr.set_source_rgb(*self.colour)
        cr.rectangle(self.rect.x, self.rect.y, self.rect.width, self.rect.height)
        cr.fill()

    def bounds(self):
        return self.rect


SIZE = ChoiceSetting("blob-size", "Size", "M", (("S", "S"), ("M", "M")))


class BlobTool(ShapeTool):
    name = "blob"
    label = "Blob"
    icon_text = "B"
    settings = (COLOUR, SIZE)

    def make_item(self, start, end, values):
        rect = Rect.from_points(start, end)
        if not rect:
            return None
        return Blob(start, end, values["colour"])


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    def overlay(tools=None):
        return Harness(pixbuf, bounds, tools)

    # ---------------------------------------------------------------- scene
    check.section("the scene applies and takes back changes")
    scene = Scene()
    item = Stroke([(0, 0), (5, 5)], (1, 0, 0), 4)
    check("starts empty", scene.region is None and not scene.items)
    scene.do(item)
    check("a bare item is added", scene.items == [item])
    check("undo is available", scene.can_undo and not scene.can_redo)
    scene.undo()
    check("undo removes it", scene.items == [])
    check("redo is available", scene.can_redo)
    scene.redo()
    check("redo puts it back", scene.items == [item])

    scene.do(SetRegion(Rect(1, 2, 3, 4)))
    check("region set", scene.region == Rect(1, 2, 3, 4))
    scene.undo()
    check("region undone to previous", scene.region is None)
    scene.redo()
    scene.do(AddItem(Stroke([(1, 1)], (0, 1, 0), 2)))
    check("a new action clears the redo stack", not scene.can_redo)
    check("doing nothing is not an action", scene.do(None) is False)

    # ------------------------------------------------------------- settings
    check.section("settings are shared by key, not by tool")
    values = SettingValues()
    check("falls back to the default", values.get(COLOUR) == COLOUR.default)
    values.set(COLOUR, theme.PALETTE[3])
    check("remembers what was set", values.get(COLOUR) == theme.PALETTE[3])
    snapshot = values.snapshot((COLOUR, WIDTH))
    check("snapshot carries both keys", set(snapshot) == {"colour", "width"}, snapshot)
    values.set(COLOUR, theme.PALETTE[2])
    check("snapshot is a copy, not a view", snapshot["colour"] == theme.PALETTE[3])

    # --------------------------------------------------------------- region
    check.section("the region is optional")
    h = overlay()
    check("capture is always available", h.overlay.capture_region() is not None)
    check(
        "with no region it is the whole screen",
        h.overlay.capture_region() == Rect(0, 0, bounds.width, bounds.height),
        h.overlay.capture_region(),
    )
    x, y = h.canvas_point()
    h.drag(x, y, 300, 200)
    check("dragging sets the region", h.overlay.scene.region is not None)
    check("capture follows the region",
          h.overlay.capture_region().width == 300, h.overlay.capture_region())
    h.click(x + 20, y + 20)
    check("a click clears it again", h.overlay.scene.region is None)

    # ------------------------------------------------------------------ pen
    check.section("the pen commits a stroke with the settings it started with")
    h = overlay()
    h.use_tool("pen")
    h.overlay.values.set(COLOUR, theme.PALETTE[0])
    h.overlay.values.set(WIDTH, 8)
    x, y = h.canvas_point()
    h.drag(x, y, 120, 90, steps=6)
    strokes = h.overlay.scene.items
    check("one stroke committed", len(strokes) == 1, len(strokes))
    check("colour captured", strokes[0].colour == theme.PALETTE[0])
    check("width captured", strokes[0].width == 8)
    check("follows the drag", len(strokes[0].points) >= 3, len(strokes[0].points))

    check("changing a setting mid-session does not rewrite the stroke",
          (lambda: (h.overlay.values.set(WIDTH, 2), strokes[0].width == 8)[1])())

    h.key("z", control=True)
    check("ctrl+z undoes the stroke", h.overlay.scene.items == [])
    h.key("z", control=True, shift=True)
    check("ctrl+shift+z redoes it", len(h.overlay.scene.items) == 1)

    check.section("a click with the pen leaves a dot")
    h = overlay()
    h.use_tool("pen")
    h.click(*h.canvas_point())
    check("dot committed", len(h.overlay.scene.items) == 1, h.overlay.scene.items)

    # ------------------------------------------------------------- settings bar
    check.section("the settings row appears only for tools that have settings")
    h = overlay()
    check("no row for the region tool", h.bar.settings_rect is None)
    h.use_tool("pen")
    check("row for the pen", h.bar.settings_rect is not None)
    check("row sits under the main bar",
          h.bar.settings_rect.y == h.bar.rect.bottom)
    check("row is part of the bar for hit testing",
          h.bar.covers(h.bar.settings_rect.x + 5,
                                   h.bar.settings_rect.y + 5))
    swatches = [b for b in h.bar.setting_buttons
                if b.setting.key == "colour"]
    widths = [b for b in h.bar.setting_buttons
              if b.setting.key == "width"]
    check("a swatch per palette colour", len(swatches) == len(theme.PALETTE))
    check("a button per width", len(widths) == 4, len(widths))
    check("options do not overlap",
          all(a.rect.right <= b.rect.x
              for a, b in zip(h.bar.setting_buttons,
                              h.bar.setting_buttons[1:])))

    target = swatches[3]
    h.click(target.rect.x + 2, target.rect.y + 2)
    check("clicking a swatch selects it",
          h.overlay.values.get(COLOUR) == target.value, h.overlay.values.get(COLOUR))
    check("selecting a setting does not capture", not h.finished)

    check.section("the settings row cannot be drawn on")
    h.press(h.bar.settings_rect.x + 300,
            h.bar.settings_rect.y + 5)
    h.move(h.bar.settings_rect.x + 400,
           h.bar.settings_rect.y + 200)
    h.release(h.bar.settings_rect.x + 400,
              h.bar.settings_rect.y + 200)
    check("no stroke from the settings row", not h.overlay.scene.items)

    # ------------------------------------------------- drawing order on screen
    check.section("annotations stay visible while a region is dragged over them")
    # Regression: the region tool undims its rectangle by repainting the frozen
    # screen. Drawn from preview(), that ran after the annotations and wiped
    # them until the drag was released.
    h = overlay()
    h.use_tool("pen")
    h.overlay.values.set(COLOUR, (0.0, 1.0, 0.0))
    h.overlay.values.set(WIDTH, 20)
    x, y = h.canvas_point()
    h.drag(x, y, 300, 0, steps=10)

    def is_green(read, at_x, at_y):
        red, green, blue = read(at_x, at_y)
        return green > 180 and red < 80 and blue < 80

    check("the stroke is on screen", is_green(render_overlay(h), x + 150, y),
          render_overlay(h)(x + 150, y))

    h.use_tool("rectangle")
    h.press(x - 100, y + 100)
    h.move(x + 400, y - 60)
    check("gesture really started", h.overlay._dragging)
    read = render_overlay(h)
    check("still visible mid-drag", is_green(read, x + 150, y), read(x + 150, y))
    check("the region under it is undimmed",
          sum(read(x + 380, y - 40)) > sum(read(x + 900, y)),
          "%s inside vs %s outside" % (read(x + 380, y - 40), read(x + 900, y)))

    h.release(x + 400, y - 60)
    read = render_overlay(h)
    check("and after releasing", is_green(read, x + 150, y), read(x + 150, y))

    check.section("only one region is undimmed at a time")
    # Each point is judged against how it looks with nothing marked out at all.
    # Comparing the two regions to each other instead depended on what the
    # screenshot behind them happened to be, and flipped when the pointer moved
    # to a monitor with darker content under the new region.
    h = overlay()
    x, y = h.canvas_point()
    in_new, in_old = (x + 1100, y + 70), (x + 100, y + 70)
    dimmed = render_overlay(h)
    dim_new, dim_old = dimmed(*in_new), dimmed(*in_old)

    h.drag(x, y, 200, 150)                    # commit a region round in_old
    h.press(x + 900, y)                       # start a second round in_new
    h.move(x + 1300, y + 150)
    read = render_overlay(h)
    check("the pending region is revealed",
          sum(read(*in_new)) > sum(dim_new) + 30,
          "%s vs %s dimmed" % (read(*in_new), dim_new))
    check("the committed one goes back to dimmed",
          all(abs(a - b) <= 2 for a, b in zip(read(*in_old), dim_old)),
          "%s vs %s dimmed" % (read(*in_old), dim_old))

    # ----------------------------------------------------------------- bake
    check.section("annotations are baked into the captured image")
    h = overlay()
    h.use_tool("pen")
    h.overlay.values.set(COLOUR, (1.0, 0.0, 0.0))
    h.overlay.values.set(WIDTH, 16)
    x, y = h.canvas_point()
    h.drag(x, y, 200, 0, steps=8)
    h.overlay.scene.do(SetRegion(Rect(x - 20, y - 20, 240, 40)))
    baked = h.overlay.render()
    check("cropped to the region", (baked.get_width(), baked.get_height()) == (240, 40),
          "%dx%d" % (baked.get_width(), baked.get_height()))
    middle = pixel(baked, 120, 20)
    check("the stroke is in the pixels", middle[0] > 200 and middle[1] < 60,
          "rgb%s" % (middle,))

    check.section("with no region the whole screen is captured")
    h = overlay()
    baked = h.overlay.render()
    check("full size", (baked.get_width(), baked.get_height())
          == (pixbuf.get_width(), pixbuf.get_height()),
          "%dx%d" % (baked.get_width(), baked.get_height()))

    check.section("Capture returns a pixbuf, cancel returns nothing")
    h = overlay()
    h.click_button(toolbar.CAPTURE)
    check("captured something", h.finished and h.result is not None)
    check("it is an image", h.result.get_width() > 0)
    h = overlay()
    h.click_button(toolbar.CANCEL)
    check("cancel gives None", h.finished and h.result is None)

    # -------------------------------------------------- adding a tool: the point
    check.section("a tool defined outside the core works with no core changes")
    custom = [t() for t in (BlobTool,)]
    h = overlay(tools=custom)
    check("it is the active tool", h.overlay.active_tool.name == "blob")
    check("it got a toolbar button",
          h.button(toolbar.TOOL, "blob") is not None)
    check("its settings built a row", h.bar.settings_rect is not None)
    keys = {b.setting.key for b in h.bar.setting_buttons}
    check("including its own custom setting", keys == {"colour", "blob-size"}, keys)

    h.overlay.values.set(COLOUR, (0.0, 1.0, 0.0))
    x, y = h.canvas_point()
    h.drag(x, y, 100, 60)
    check("its gesture committed an item", len(h.overlay.scene.items) == 1)
    check("of its own type", isinstance(h.overlay.scene.items[0], Blob))

    h.key("z", control=True)
    check("undo works on it for free", h.overlay.scene.items == [])
    h.key("z", control=True, shift=True)

    h.overlay.scene.do(SetRegion(Rect(x, y, 100, 60)))
    baked = h.overlay.render()
    corner = pixel(baked, 50, 30)
    check("and it lands in the captured image",
          corner[1] > 200 and corner[0] < 60, "rgb%s" % (corner,))

    size_button = next(b for b in h.bar.setting_buttons
                       if b.setting.key == "blob-size" and b.value == "S")
    h.click(size_button.rect.x + 2, size_button.rect.y + 2)
    check("its custom setting is selectable",
          h.overlay.values.get(SIZE) == "S", h.overlay.values.get(SIZE))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
