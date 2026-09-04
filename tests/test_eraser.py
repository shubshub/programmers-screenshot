#!/usr/bin/env python3
"""Rubbing out marks, in part and in whole.

The interesting checks read pixels rather than object state: "the item still
exists but with holes in it" is only worth anything if the holes are actually
there, on screen and in the saved PNG both.

    python3 tests/test_eraser.py
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

from support import Checker, Harness, render_overlay  # noqa: E402

from programmers_screenshot import capture, theme  # noqa: E402
from programmers_screenshot.actions import SetRegion  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402
from programmers_screenshot.tools.eraser import SIZE, EraserTool  # noqa: E402
from programmers_screenshot.tools.items import Redaction  # noqa: E402
from programmers_screenshot.tools.step import Step  # noqa: E402

WHITE_CANVAS = 0xFFFFFFFF

# The redaction tool fills black by default, so a white backdrop is what makes
# "bar" and "hole" tell apart. Black marks on a black canvas would have every
# assertion below passing for the wrong reason.


class CountingContext:
    """A stand-in for a cairo context that counts the holes punched into it.

    Everything is a no-op except clip_extents, which reports the region being
    repainted, and arc, which is tallied. Enough for Item.draw(), and it
    answers the only question a timing test could: how much work did that
    frame actually do? Skipping far-away holes changes nothing you can see --
    they are clipped away regardless -- so counting is the only way to catch
    the filter being lost.
    """

    def __init__(self, extents):
        self.extents = extents
        self.arcs = 0

    def clip_extents(self):
        return self.extents

    def arc(self, *_args):
        self.arcs += 1

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def flat_harness(width=500, height=300):
    """A plain white screen with the whole of it marked as the capture region.

    The region keeps the overlay from dimming everything, so an on-screen
    reading is the annotation's own colour rather than a muddied version of it.
    """
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, width, height)
    pixbuf.fill(WHITE_CANVAS)
    harness = Harness(pixbuf, Rect(0, 0, width, height))
    harness.overlay.scene.do(SetRegion(Rect(0, 0, width, height)))
    return harness


def is_bar(rgb):
    """A black redaction bar."""
    return max(rgb) < 60


def is_hole(rgb):
    """White canvas showing through where the bar was rubbed out."""
    return min(rgb) > 200


def below_the_bar(dy=0):
    return theme.BAR_HEIGHT + theme.SETTINGS_HEIGHT + 30 + dy


def undo_depth(harness):
    return len(harness.overlay.scene._done)


def numbers(harness):
    return [i.number for i in harness.items if isinstance(i, Step)]


def png_pixel(pixbuf, x, y):
    data = pixbuf.get_pixels()
    o = y * pixbuf.get_rowstride() + x * pixbuf.get_n_channels()
    return tuple(data[o:o + 3])


def main():
    check = Checker()
    if not Gtk.init_check()[0]:
        check("a display is available", False)
        return check.report()

    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())

    check.section("the eraser is on the toolbar")
    h = Harness(pixbuf, bounds)
    eraser = next(t for t in h.overlay.tools if t.name == "eraser")
    check("it is offered", eraser is not None)
    check("with a size to pick", eraser.settings == (SIZE,), eraser.settings)

    # ------------------------------------------------------------------
    check.section("dragging through a redaction takes a bite out of it")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 200, 60)
    bar = h.items[-1]

    read = render_overlay(h)
    check("the bar is solid before erasing", is_bar(read(200, y + 30)),
          read(200, y + 30))
    check("and the canvas beside it is not", is_hole(read(400, y + 30)),
          read(400, y + 30))

    h.use_tool("eraser")
    h.drag(150, y + 30, 100, 0, steps=12)
    check("the bar is still on the scene", h.items[-1] is not bar)
    check("as one item, not fragments", len(h.items) == 1, len(h.items))
    check("and it carries the holes", len(h.items[-1].erased) > 0,
          len(h.items[-1].erased))

    read = render_overlay(h)
    check("what the eraser passed over is gone",
          is_hole(read(200, y + 30)), read(200, y + 30))
    check("what it did not pass over remains",
          is_bar(read(115, y + 10)), read(115, y + 10))

    check.section("it rubs out as you go, not when you let go")
    # The marks are drawn through the sweep in progress, so the hole opens up
    # under the pointer. Showing an outline until release and only then
    # applying it reads as a preview rather than an eraser.
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 200, 60)
    h.use_tool("eraser")

    h.press(150, y + 30)
    h.move(200, y + 30)
    # still mid-drag: nothing committed
    check("nothing has been committed yet",
          not h.items[-1].erased, h.items[-1].erased)
    read = render_overlay(h)
    check("but the hole is already on screen",
          is_hole(read(175, y + 30)), read(175, y + 30))
    check("and the untouched part is still solid",
          is_bar(read(115, y + 10)), read(115, y + 10))

    h.release(200, y + 30)
    check("releasing commits it", len(h.items[-1].erased) > 0)
    read = render_overlay(h)
    check("and it looks the same afterwards",
          is_hole(read(175, y + 30)), read(175, y + 30))

    check.section("abandoning a sweep with Escape leaves the mark alone")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 200, 60)
    h.use_tool("eraser")
    h.press(150, y + 30)
    h.move(220, y + 30)
    h.key("Escape")
    read = render_overlay(h)
    check("the bar is whole again", is_bar(read(180, y + 30)), read(180, y + 30))
    check("and nothing was committed", not h.items[-1].erased, h.items[-1].erased)

    check.section("undo puts the bar back whole")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 200, 60)
    h.use_tool("eraser")
    h.drag(150, y + 30, 100, 0, steps=12)
    read = render_overlay(h)
    check("erased first", is_hole(read(200, y + 30)), read(200, y + 30))
    h.overlay.scene.undo()
    read = render_overlay(h)
    check("solid again", is_bar(read(200, y + 30)), read(200, y + 30))

    # ------------------------------------------------------------------
    check.section("the holes are in the captured PNG too, not just on screen")
    # The whole point of keeping erasure as geometry rather than a bitmap.
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 200, 60)
    h.use_tool("eraser")
    h.drag(150, y + 30, 100, 0, steps=12)

    captured = h.overlay.render()
    check("the capture has the hole",
          is_hole(png_pixel(captured, 200, y + 30)),
          png_pixel(captured, 200, y + 30))
    check("and still has the rest of the bar",
          is_bar(png_pixel(captured, 115, y + 10)),
          png_pixel(captured, 115, y + 10))

    # ------------------------------------------------------------------
    check.section("it works the same on a pixelate block")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("pixelate")
    h.drag(100, y, 200, 60)
    block = h.items[-1]
    h.use_tool("eraser")
    h.drag(150, y + 30, 100, 0, steps=12)
    check("the block survives with holes", h.items[-1] is not block)
    check("and is still one block", len(h.items) == 1, len(h.items))
    check("carrying erasures", len(h.items[-1].erased) > 0)

    check.section("and on ink")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("pen")
    h.drag(100, y, 200, 0, steps=20)
    h.use_tool("eraser")
    h.drag(200, y, 0, 0)          # a click, not a drag
    check("a click takes the whole stroke", not h.items, h.items)
    h.overlay.scene.undo()
    h.use_tool("eraser")
    h.drag(180, y - 20, 0, 40, steps=10)   # a drag across it
    check("a drag leaves the stroke behind, holed",
          len(h.items) == 1 and len(h.items[0].erased) > 0,
          [len(i.erased) for i in h.items])

    # ------------------------------------------------------------------
    check.section("a fast flick does not skip what it crossed")
    # Motion events can land far apart; discs are laid along the way.
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 200, 60)
    h.use_tool("eraser")
    h.drag(90, y + 30, 220, 0, steps=1)    # one giant jump
    read = render_overlay(h)
    holed = [x for x in range(110, 290, 10) if is_hole(read(x, y + 30))]
    check("the whole crossing is erased, not just the ends",
          len(holed) > 15, "%d of 18 sample points" % len(holed))

    # ------------------------------------------------------------------
    check.section("a drag over nothing changes nothing")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(100, y, 100, 40)
    before = undo_depth(h)
    h.use_tool("eraser")
    h.drag(300, y + 150, 100, 0, steps=8)
    check("no undo entry was added", undo_depth(h) == before,
          (before, undo_depth(h)))

    # ------------------------------------------------------------------
    check.section("one drag over several marks undoes as one step")
    h = flat_harness()
    y = below_the_bar()
    h.use_tool("redact")
    h.drag(60, y, 80, 40)
    h.drag(200, y, 80, 40)
    h.drag(340, y, 80, 40)
    before = undo_depth(h)
    h.use_tool("eraser")
    h.drag(60, y + 20, 380, 0, steps=40)
    check("one entry for the whole sweep", undo_depth(h) == before + 1,
          (before, undo_depth(h)))
    check("all three were touched",
          all(len(i.erased) > 0 for i in h.items),
          [len(i.erased) for i in h.items])
    h.overlay.scene.undo()
    check("and one undo restores all three",
          all(len(i.erased) == 0 for i in h.items),
          [len(i.erased) for i in h.items])

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    check.section("a long sweep does not get slower the longer it goes")
    # It used to: the whole swept path was repainted every frame and every
    # disc laid so far was punched into it, so cost grew with the stroke and
    # the eraser seized up after a few seconds. These check the two causes
    # rather than the clock, which would only be a flake waiting to happen.
    tool = EraserTool()
    tool.begin((80, 400), {"eraser-size": 18})
    areas, counts = [], []
    x = 80.0
    for _ in range(8):
        for _ in range(30):
            x += 9
            tool.extend((x, 400))
        extent = tool.drag_extent((80, 400), (x, 400), {"eraser-size": 18})
        areas.append(extent.width * extent.height)
        counts.append(len(tool._swept))

    check("the swept path keeps growing, as it must",
          counts[-1] > counts[0] * 4, counts)
    check("but the area repainted each frame does not",
          max(areas) < min(areas) * 2, areas)
    check("and it stays about one disc across",
          max(areas) < (18 * 4) ** 2, max(areas))

    check.section("holes outside the repainted area are skipped")
    spread = [(100 + i * 2, 400, 9) for i in range(400)]
    mark = Redaction((50, 350), (950, 450), (0, 0, 0), 0).with_erasure(spread)
    near = mark._erased_within((500, 380, 560, 420))
    check("only the ones that could change a pixel",
          len(near) < 40, "%d of %d" % (len(near), len(spread)))
    check("and none of the far ones",
          all(480 <= c[0] <= 580 for c in near), near[:3])
    check("with everything on show, they all count",
          len(mark._erased_within((0, 0, 2000, 2000))) == len(spread))

    check.section("and draw() really does skip them")
    # Removing the filter changes nothing you can see -- the holes are clipped
    # away regardless -- so only counting the work catches it. This context
    # records how many arcs were actually punched.
    counting = CountingContext((500, 380, 560, 420))
    mark.draw(counting)
    check("only the holes near the repainted area are punched",
          counting.arcs < 40, "%d of %d" % (counting.arcs, len(spread)))

    everything = CountingContext((0, 0, 2000, 2000))
    mark.draw(everything)
    check("with the whole mark on show, all of them are",
          everything.arcs == len(spread), everything.arcs)

    check.section("standing still does not pile them up")
    idle = EraserTool()
    idle.begin((500, 400), {"eraser-size": 18})
    for i in range(300):
        idle.extend((500 + (i % 3), 400 + (i % 2)))
    check("300 events in one spot leave almost nothing",
          len(idle._swept) <= 3, len(idle._swept))

    slow = EraserTool()
    slow.begin((500, 400), {"eraser-size": 18})
    for i in range(300):
        slow.extend((500 + i * 2, 400))
    check("a slow 600px drag is spaced, not one per event",
          len(slow._swept) < 100, len(slow._swept))
    check("but still covers the ground",
          slow._swept[-1][0] >= 1080, slow._swept[-1])

    check.section("clicking a step badge still renumbers the rest")
    h = Harness(pixbuf, bounds)
    x, y = h.canvas_point()
    h.use_tool("step")
    for i in range(4):
        h.click(x + i * 90, y)
    check("four badges in order", numbers(h) == [1, 2, 3, 4], numbers(h))
    h.use_tool("eraser")
    h.click(x + 90, y)
    check("the gap is closed", numbers(h) == [1, 2, 3], numbers(h))
    h.use_tool("step")
    h.click(x + 400, y + 150)
    check("the next badge carries on rather than repeating",
          numbers(h) == [1, 2, 3, 4], numbers(h))
    h.overlay.scene.undo()
    h.overlay.scene.undo()
    check("undo restores the original numbering",
          numbers(h) == [1, 2, 3, 4], numbers(h))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
