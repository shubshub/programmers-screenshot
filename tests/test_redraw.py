#!/usr/bin/env python3
"""Partial redraws must leave the screen exactly as a full repaint would.

Gestures only repaint the area they report as damaged, which is what keeps
freehand drawing smooth. Get that area wrong and stale pixels are left behind
— and because releasing the button triggers a full repaint, the mess only
shows up *during* the drag, which is easy to miss.

So these tests keep one persistent surface, honour exactly the areas the
overlay asks to have redrawn, and then compare it against a full repaint.

    python3 tests/test_redraw.py
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

from programmers_screenshot import capture  # noqa: E402
from programmers_screenshot.settings import COLOUR, WIDTH  # noqa: E402

TOLERANCE = 8  # per channel, for antialiasing differences
SAMPLE_STEP = 2  # check every other pixel; artifacts are never one pixel wide


class Screen:
    """A persistent surface that only repaints what it is asked to."""

    def __init__(self, harness, bounds):
        self.harness = harness
        self.width = int(bounds.width)
        self.height = int(bounds.height)
        self.surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, self.width, self.height
        )
        self._queued = []
        harness.overlay.window.queue_draw_area = self._queue_area
        harness.overlay.window.queue_draw = self._queue_all

    def _queue_area(self, x, y, width, height):
        self._queued.append((x, y, width, height))

    def _queue_all(self):
        self._queued.append(None)

    def prime(self):
        """The first full paint, which a real window gets when it is mapped."""
        self._queue_all()
        self.flush()

    def flush(self):
        """Serve the queued redraws, clipped exactly as GTK would clip them."""
        for area in self._queued:
            cr = cairo.Context(self.surface)
            if area is not None:
                cr.rectangle(*area)
                cr.clip()
            self.harness.overlay._on_draw(self.harness.overlay.window, cr)
        self._queued.clear()

    def differences_from_full_repaint(self):
        truth = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        self.harness.overlay._on_draw(
            self.harness.overlay.window, cairo.Context(truth)
        )
        self.surface.flush()
        truth.flush()
        mine, theirs = self.surface.get_data(), truth.get_data()
        stride = self.surface.get_stride()

        wrong = []
        for y in range(0, self.height, SAMPLE_STEP):
            for x in range(0, self.width, SAMPLE_STEP):
                offset = y * stride + x * 4
                for channel in range(3):
                    if abs(mine[offset + channel] - theirs[offset + channel]) > TOLERANCE:
                        wrong.append((x, y))
                        break
        return wrong


def describe(wrong):
    if not wrong:
        return ""
    xs = [point[0] for point in wrong]
    ys = [point[1] for point in wrong]
    return "%d points, x %d..%d y %d..%d" % (
        len(wrong), min(xs), max(xs), min(ys), max(ys)
    )


def main():
    Gtk.init_check()
    pixbuf, bounds = capture.capture_screen(Gdk.Display.get_default())
    check = Checker()

    check.section("growing and shrinking a region leaves nothing behind")
    # Regression: the size label sits above the region, so a redraw clipped to
    # the region alone orphaned the label at every step of the drag. Releasing
    # triggers a full repaint, which is why it only showed up mid-drag.
    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    x, y = h.canvas_point()

    h.press(x - 100, y + 200)
    screen.flush()
    for step in range(1, 25):
        h.move(x - 100 + step * 30, y + 200 - step * 12)
        screen.flush()
    for step in range(24, 12, -1):
        h.move(x - 100 + step * 30, y + 200 - step * 12)
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("a narrow region, whose label is wider than it is")
    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    h.press(x, y)
    screen.flush()
    for step in range(1, 16):
        h.move(x + 12, y + step * 20)  # 12 px wide, label far wider
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("freehand drawing leaves nothing behind")
    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    h.use_tool("pen")
    h.overlay.values.set(COLOUR, (1.0, 0.0, 0.0))
    h.overlay.values.set(WIDTH, 16)
    h.press(x, y)
    screen.flush()
    for step in range(1, 40):
        h.move(x + step * 18, y + (step % 9) * 14)
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("the crosshair follows the pointer without smearing")
    # Idle motion used to queue no redraw at all unless the toolbar hover
    # changed, so the guides stayed wherever they were first painted.
    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    for step in range(1, 12):
        h.move(x + step * 90, y + step * 60)
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("starting a drag clears the hint and the guides")
    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    h.move(x + 300, y + 200)
    screen.flush()
    h.press(x, y)
    screen.flush()
    h.move(x + 250, y + 180)
    screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("shapes at the widest thickness leave nothing behind")
    # These pass whether ShapeTool.drag_extent asks the item for its bounds or
    # just returns the raw drag box: with the shapes as they are, the overlay's
    # 8px margin and the union with the previous frame absorb the overhang.
    # Keep them anyway — they are what will notice when a future shape, a wider
    # stroke, or a flared arrowhead stops fitting. The guard that bites today
    # is the bounds check in tests/test_line_tool.py.
    from programmers_screenshot.tools.line import SHAPE  # noqa: E402

    for shape in ("line", "box", "circle", "arrow"):
        h = Harness(pixbuf, bounds)
        screen = Screen(h, bounds)
        screen.prime()
        h.use_tool("line")
        h.overlay.values.set(SHAPE, shape)
        h.overlay.values.set(COLOUR, (1.0, 0.0, 0.0))
        h.overlay.values.set(WIDTH, 16)
        h.press(x, y)
        screen.flush()
        for step in range(1, 22):
            h.move(x + step * 34, y + step * 16)
            screen.flush()
        # Shrinking is what exposes it: growing unions each frame with the last,
        # which happens to cover the overhang, but pulling back leaves the old
        # stroke's cap and arrowhead outside the new damage.
        for step in range(21, 4, -1):
            h.move(x + step * 34, y + step * 16)
            screen.flush()
        wrong = screen.differences_from_full_repaint()
        check("%s matches a full repaint" % shape, not wrong, describe(wrong))

    check.section("dragging a step badge into place leaves nothing behind")
    from programmers_screenshot.tools.step import SIZE  # noqa: E402

    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    h.use_tool("step")
    h.overlay.values.set(COLOUR, (0.85, 0.1, 0.1))
    h.overlay.values.set(SIZE, 21)
    for placed in range(3):  # a few already on the scene, then drag another
        h.click(x + placed * 80, y)
    screen.flush()
    h.press(x, y + 200)
    screen.flush()
    for step in range(1, 20):
        h.move(x + step * 40, y + 200 + step * 12)
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("a growing block of text leaves nothing behind")
    # The box grows as you type and shrinks on backspace, and unlike a drag
    # there is no release to trigger a full repaint and tidy up.
    from programmers_screenshot.tools.text import BACKGROUND, SIZE  # noqa: E402

    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    h.use_tool("text")
    h.overlay.values.set(SIZE, 28)
    h.overlay.values.set(BACKGROUND, True)
    h.overlay.values.set(COLOUR, (0.9, 0.1, 0.1))
    h.click(x, y)
    screen.flush()
    for character in "a longer line of text":
        h.type_text(character)
        screen.flush()
    h.key("Return")
    screen.flush()
    for character in "and a second":
        h.type_text(character)
        screen.flush()
    for _ in range(8):  # backspacing shrinks it again
        h.key("BackSpace")
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    check.section("drawing inside an existing region")
    h = Harness(pixbuf, bounds)
    screen = Screen(h, bounds)
    screen.prime()
    h.drag(x - 60, y - 40, 700, 400)  # commit a region first
    h.use_tool("pen")
    h.overlay.values.set(COLOUR, (0.0, 1.0, 0.0))
    h.overlay.values.set(WIDTH, 10)
    screen.flush()
    h.press(x, y)
    screen.flush()
    for step in range(1, 30):
        h.move(x + step * 20, y + (step % 7) * 16)
        screen.flush()
    wrong = screen.differences_from_full_repaint()
    check("matches a full repaint", not wrong, describe(wrong))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
