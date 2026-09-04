#!/usr/bin/env python3
"""Recipes: a shot described as JSON, with nobody at the keyboard.

The parsing half needs no screen at all -- a synthetic canvas stands in for
the frozen desktop. Only the last section, which renders a real capture,
wants a display, and it says so and skips itself when there is none.

    python3 tests/test_recipe.py
"""

import contextlib
import os
import shutil
import sys
import tempfile

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

from support import Checker, pixel  # noqa: E402

from programmers_screenshot import (  # noqa: E402
    capture, cli, output, preferences, recipe, theme,
)
from programmers_screenshot.geometry import Rect  # noqa: E402
from programmers_screenshot.overlay import Overlay  # noqa: E402
from programmers_screenshot.render import Canvas  # noqa: E402
from programmers_screenshot.scene import Scene  # noqa: E402
from programmers_screenshot.tools import build_tools, items  # noqa: E402
from programmers_screenshot.tools.pixelate import Pixelation  # noqa: E402
from programmers_screenshot.tools.step import Step  # noqa: E402
from programmers_screenshot.tools.text import TextBlock  # noqa: E402

SCREEN = Rect(0, 0, 200, 120)

#: A coordinate list of the right shape for each kind of mark.
SAMPLE = {
    recipe.RECT: [10, 10, 40, 30],
    recipe.ENDS: [[10, 10], [40, 30]],
    recipe.POINT: [10, 10],
}
#: What each name should end up putting on the scene.
EXPECTED = {
    "box": items.Box,
    "ellipse": items.Ellipse,
    "line": items.Line,
    "arrow": items.Arrow,
    "step": Step,
    "label": TextBlock,
    "redact": items.Redaction,
    "pixelate": Pixelation,
}


def white_surface(bounds):
    """A stand-in for the frozen screen: flat white, so a mark shows up."""
    surface = cairo.ImageSurface(
        cairo.FORMAT_RGB24, int(bounds.width), int(bounds.height)
    )
    cr = cairo.Context(surface)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    surface.flush()
    return surface


def white_pixbuf(bounds):
    pixbuf = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, False, 8, int(bounds.width), int(bounds.height)
    )
    pixbuf.fill(0xFFFFFFFF)
    return pixbuf


class Stand:
    """Just enough of an Overlay for recipe.annotate: a scene and a canvas."""

    def __init__(self, bounds=SCREEN):
        self.bounds = bounds
        self.scene = Scene()
        self._canvas = Canvas(white_surface(bounds), bounds, 1.0, self.scene)

    def canvas(self):
        return self._canvas


def refused(check, name, text, mentioning=None):
    """Check that a recipe is rejected, and that the message says which bit."""
    try:
        recipe.parse(text)
    except recipe.RecipeError as error:
        said = str(error)
        check(name, mentioning is None or mentioning in said, said)
        return
    check(name, False, "accepted")


def entry_for(name):
    entry = {name: SAMPLE[recipe.ENTRIES[name].shape]}
    if name == "label":
        entry["text"] = "hello"
    return entry


def main():
    check = Checker()

    check.section("a recipe is read, or refused with the offending bit named")
    spec = recipe.parse('{"region": [1, 2, 3, 4], "annotate": [{"box": [0,0,9,9]}]}')
    check("a good one comes back as a dict", spec["region"] == [1, 2, 3, 4], spec)
    refused(check, "not JSON at all", "nonsense", "not valid JSON")
    refused(check, "a list, not an object", "[]", "JSON object")
    refused(check, "a misspelled top-level key", '{"anotate": []}', "anotate")
    refused(check, "a negative delay", '{"delay": -1}', "delay")
    refused(check, "an output that is not a path", '{"output": 7}', "output")
    refused(check, "a window that is not a title", '{"window": []}', "window")
    refused(check, "an input that is not a path", '{"input": 3}', "input")
    refused(check, "an origin that is not a point", '{"origin": [1]}', "origin")
    refused(check, "a scale of zero", '{"scale": 0}', "scale")
    refused(check, "a viewport of zero", '{"viewport": 0}', "viewport")
    refused(check, "a dpr of zero", '{"dpr": 0}', "dpr")
    refused(check, "annotate that is not a list", '{"annotate": {}}', "annotate")

    check.section("a bad mark names its own position in the list")
    for text, wanted in (
        ('{"annotate": [{"box": [0,0,9,9]}, {"box": [0,0,9]}]}', "annotate[1]"),
        ('{"annotate": [{"blob": [0,0]}]}', "annotate[0]"),
        ('{"annotate": [{"box": [0,0,9,9], "color": "red"}]}', "color"),
        ('{"annotate": [{"box": [0,0,0,9]}]}', "more than zero"),
        ('{"annotate": [{"box": [0,0,9,"nine"]}]}', "not a number"),
        ('{"annotate": [{"box": [0,0,9,9], "colour": "puce"}]}', "puce"),
        ('{"annotate": [{"arrow": [0, 0, 9, 9]}]}', "two points"),
        ('{"annotate": [{"label": [0, 0]}]}', 'needs a "text" string'),
    ):
        stand = Stand()
        try:
            recipe.annotate(recipe.parse(text), stand, recipe.Frame(stand.bounds))
            check("refuses %s" % text[13:45], False, "accepted")
        except recipe.RecipeError as error:
            check("refuses %s" % text[13:45], wanted in str(error), error)

    check.section("nothing is drawn when any part of it is wrong")
    stand = Stand()
    with contextlib.suppress(recipe.RecipeError):
        recipe.annotate(
            recipe.parse(
                '{"annotate": [{"box": [0,0,9,9]}, {"step": [1,1]}, {"arrow": []}]}'
            ),
            stand,
            recipe.Frame(stand.bounds),
        )
    check("the scene is left empty", stand.scene.items == [], stand.scene.items)

    check.section("every mark the table offers can be drawn")
    for name in recipe.ENTRIES:
        stand = Stand()
        recipe.annotate({"annotate": [entry_for(name)]}, stand,
                        recipe.Frame(stand.bounds))
        drawn = stand.scene.items
        check(
            "%s makes a %s" % (name, EXPECTED[name].__name__),
            len(drawn) == 1 and isinstance(drawn[0], EXPECTED[name]),
            drawn,
        )

    check.section("the parameters an entry carries")
    stand = Stand()
    recipe.annotate({"annotate": [
        {"box": [10, 10, 40, 30], "colour": "green", "width": 9},
        {"redact": [10, 10, 40, 30]},
        {"step": [20, 20]},
        {"step": [40, 20]},
        {"label": [5, 5], "text": "two\nlines", "size": 30},
    ]}, stand, recipe.Frame(stand.bounds))
    box, redaction, first, second, text = stand.scene.items
    check("colour is looked up by name", box.colour == theme.PALETTE[2], box.colour)
    check("width is taken as given", box.width == 9, box.width)
    check("a redaction defaults to black", redaction.colour == theme.PALETTE[5])
    check("badges number themselves 1, 2",
          (first.number, second.number) == (1, 2))
    check("a newline starts a new line", text.lines == ("two", "lines"), text.lines)
    check("size reaches the text", text.size == 30)

    check.section("coordinates are absolute, whatever the screen bounds are")
    # A second monitor to the left puts the origin at a negative x; a caller
    # reporting a window position has no idea about that, so the recipe stays
    # in screen coordinates and the shift happens here.
    stand = Stand(Rect(-200, -20, 400, 140))
    recipe.annotate({"annotate": [{"box": [-190, -10, 40, 30]}]}, stand,
                    recipe.Frame(stand.bounds))
    check("the mark is shifted onto the capture",
          stand.scene.items[0].start == (10.0, 10.0), stand.scene.items[0].start)
    area = recipe.region([-190, -10, 40, 30], recipe.Frame(stand.bounds))
    area.apply(stand.scene)
    check("and so is the region", stand.scene.region == Rect(10, 10, 40, 30),
          stand.scene.region)
    check("--region takes the same numbers as a string",
          recipe.region("-190,-10,40,30", recipe.Frame(stand.bounds)).region
          == Rect(10, 10, 40, 30))
    for bad in ("1,2,3", "a,b,c,d"):
        try:
            recipe.region(bad, recipe.Frame(stand.bounds))
            check("--region %s is refused" % bad, False, "accepted")
        except recipe.RecipeError as error:
            check("--region %s is refused" % bad, True, error)

    check.section("--recipe-help says what can be asked for")
    described = recipe.describe()
    check("every mark is listed",
          all(name in described for name in recipe.ENTRIES))
    check("every colour is listed",
          all(name in described for name in recipe.COLOURS))
    check("it says a display is needed", "no display" in described)
    check("and that it is off until switched on", "Off until switched on" in described)
    check("it names the Chrome handoff", "save_to_disk" in described)
    check("and the pixel ratio", "devicePixelRatio" in described)

    check.section("the flags that reach it")
    parsed = cli.build_parser().parse_args(
        ["--region", "1,2,3,4", "--delay", "2", "--recipe", "-"]
    )
    check("--region is carried", parsed.region == "1,2,3,4")
    check("--window counts as scripted too",
          cli.scripted(cli.build_parser().parse_args(["--window", "Chrome"])))
    check("--input does too, and is what a browser tab goes through",
          cli.scripted(cli.build_parser().parse_args(["--input", "tab.png"])))

    check.section("only the runs that look at a screen need permission")
    # The switch is there so nothing photographs somebody's screen unasked.
    # Annotating a picture the caller already had is not that.
    def parse(*flags):
        return cli.build_parser().parse_args(list(flags))
    for flags, wanted in (
        (("--region", "0,0,9,9"), True),
        (("--window", "Chrome"), True),
        (("--list-windows",), True),
        (("--input", "tab.png"), False),
        (("--input", "tab.png", "--region", "0,0,9,9"), False),
        ((), False),
    ):
        check("%s -> %s" % (" ".join(flags) or "(nothing)", wanted),
              cli.reads_the_screen(parse(*flags)) == wanted)
    check("--delay is a number", parsed.delay == 2.0)
    check("--viewport is carried", parse("--viewport", "1720").viewport == 1720.0)
    check("--dpr is carried", parse("--dpr", "1.25").dpr == 1.25)
    check("--recipe is carried", parsed.recipe == "-")
    check("a recipe counts as scripted", cli.scripted(parsed))
    check("an ordinary run does not",
          not cli.scripted(cli.build_parser().parse_args([])))

    check.section("a scale converts the caller's ruler to the picture's")
    # A browser screenshot 1242 px wide of a 1720 px viewport: the page's own
    # coordinates, halved-ish, with no conversion asked of the caller.
    stand = Stand()
    recipe.annotate({"annotate": [{"box": [100, 200, 400, 50]}]}, stand,
                    recipe.Frame(stand.bounds, None, 0.5))
    box = stand.scene.items[0]
    check("the mark is placed at the picture's size",
          (box.start, box.end) == ((50.0, 100.0), (250.0, 125.0)),
          (box.start, box.end))
    check("but its stroke is not scaled with it", box.width == 4, box.width)
    check("no scale leaves everything alone",
          recipe.Frame(stand.bounds).at(10, 20) == (10.0, 20.0))

    check.section("a viewport width stands in for the scale")
    # The browser knows window.innerWidth and the picture knows its own width,
    # so nobody has to open the file with a third tool to measure it.
    picture = Rect(0, 0, 1242, 952)
    frame = cli.frame_for(picture, parse("--input", "x.jpg", "--viewport", "1720"))
    check("scale is the picture's width over the viewport's",
          abs(frame.scale - 1242 / 1720.0) < 1e-9, frame.scale)
    check("--scale still wins when both are given",
          cli.frame_for(picture, parse("--scale", "0.5", "--viewport", "1720")).scale
          == 0.5)
    check("neither leaves the ruler alone",
          cli.frame_for(picture, parse("--input", "x.jpg")).scale == 1.0)
    try:
        cli.frame_for(picture, parse("--viewport", "0"))
        check("a viewport of zero is refused", False, "accepted")
    except recipe.RecipeError as error:
        check("a viewport of zero is refused", "viewport" in str(error), error)

    check.section("a page zoom crops the save, and --dpr accounts for it")
    # The post-mortem's capture: a 994 px wide save of a 1376 px viewport at
    # a page zoom of 125%. Two dots the page drew at known points measured
    # 0.9024 x 0.9027 picture px per logical px with no offset, so the save is
    # the top-left 1/dpr of the viewport, and width / viewport alone is a
    # quarter short. The expected rectangle below is where the dots put it.
    saved = Rect(0, 0, 994, 762)
    zoomed = cli.frame_for(
        saved, parse("--input", "x.jpg", "--viewport", "1376", "--dpr", "1.25")
    )
    check("the scale is width x dpr over viewport",
          abs(zoomed.scale - 994 * 1.25 / 1376.0) < 1e-9, zoomed.scale)
    stand = Stand(saved)
    recipe.annotate({"annotate": [{"box": [4, 84, 790, 202]}]}, stand, zoomed)
    box = stand.scene.items[0]
    landed = tuple(round(v) for v in (
        box.start[0], box.start[1], box.end[0] - box.start[0], box.end[1] - box.start[1]
    ))
    check("the row lands where the calibration dots say, within a pixel",
          all(abs(a - b) <= 1 for a, b in zip(landed, (4, 76, 713, 182))), landed)
    check("without --dpr the arithmetic is what it was",
          cli.frame_for(saved, parse("--viewport", "1376")).scale == 994 / 1376.0)
    check("--scale still wins over both",
          cli.frame_for(saved, parse("--scale", "0.5", "--viewport", "1376",
                                     "--dpr", "1.25")).scale == 0.5)
    try:
        cli.frame_for(saved, parse("--viewport", "1376", "--dpr", "0"))
        check("a dpr of zero is refused", False, "accepted")
    except recipe.RecipeError as error:
        check("a dpr of zero is refused", "dpr" in str(error), error)

    check.section("--input is quiet: nothing was photographed")
    heard = []
    real = output.sound.play, output.notifications.announce_file
    output.sound.play = lambda: heard.append("shutter")
    output.notifications.announce_file = lambda path: heard.append("notice")
    folder = tempfile.mkdtemp(prefix="programmers-screenshot-quiet-")
    try:
        quiet = parse("--input", "x.jpg", "-o", os.path.join(folder, "a.png"),
                      "--no-clipboard")
        written = output.deliver(white_pixbuf(SCREEN), quiet, quiet=True)
        check("the file is still written and its path returned",
              bool(written) and os.path.exists(written), written)
        check("but no shutter and no notification", heard == [], heard)
        output.deliver(white_pixbuf(SCREEN),
                       parse("-o", os.path.join(folder, "b.png"), "--no-clipboard"))
        check("a real shot still sounds and announces",
              heard == ["shutter", "notice"], heard)
    finally:
        output.sound.play, output.notifications.announce_file = real
        shutil.rmtree(folder, ignore_errors=True)

    check.section("an origin moves where coordinates start")
    # An origin of (90, 40) says "call that corner (0, 0)", so a mark at
    # (10, 10) in the caller's numbers lands at (100, 50) in the capture.
    stand = Stand()
    recipe.annotate({"annotate": [{"box": [10, 10, 40, 30]}]}, stand,
                    recipe.Frame(stand.bounds, [90, 40]))
    check("the mark is measured from the origin",
          stand.scene.items[0].start == (100.0, 50.0), stand.scene.items[0].start)
    check("and so is a region",
          recipe.region([10, 10, 40, 30],
                        recipe.Frame(stand.bounds, [90, 40])).region
          == Rect(100, 50, 40, 30))

    check.section("naming a window")
    # No window is captured here: that wants a live X11 desktop with something
    # open on it. What is checked is that asking for one that is not there
    # says so, and lists what is, rather than failing silently or picking one.
    try:
        capture.capture_window(Gdk.Display.get_default(), "no such window at all")
        check("an absent window is refused", False, "accepted")
    except capture.CaptureError as error:
        check("an absent window is refused", "no such window at all" in str(error))
    except Exception as error:  # no display, or no libwnck
        check("an absent window is refused", True, "skipped: %s" % error)

    check.section("it is off until switched on")
    check("the stored default is off", preferences.DEFAULTS["scripted"] is False)

    if not Gtk.init_check()[0]:
        print("\nno display: skipping the render")
        return check.report()

    check.section("a described shot renders, with no window ever shown")
    overlay = Overlay(white_pixbuf(SCREEN), SCREEN, build_tools())
    overlay.scene.do(recipe.region("20,10,60,40", recipe.Frame(SCREEN)))
    recipe.annotate({"annotate": [
        {"box": [30, 20, 40, 20], "colour": "red", "width": 4},
        {"arrow": [[70, 45], [50, 30]]},
        {"step": [35, 25]},
    ]}, overlay, recipe.Frame(SCREEN))
    shot = overlay.render()
    check("cropped to the region",
          (shot.get_width(), shot.get_height()) == (60, 40),
          (shot.get_width(), shot.get_height()))
    # The box's top edge runs along y=20, which is row 10 of the crop.
    red = pixel(shot, 30, 10)
    check("the box is drawn, in red", red[0] > 180 and red[1] < 90, red)
    check("and the screen underneath is still there", pixel(shot, 2, 38) == (255, 255, 255),
          pixel(shot, 2, 38))
    check("three marks were baked in", len(overlay.scene.items) == 3)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
