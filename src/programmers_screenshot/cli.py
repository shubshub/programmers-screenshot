"""Command line entry point."""

import argparse
import copy
import os
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

from . import (  # noqa: I101
    alerts, capture, hotkey, notifications, output, preferences, recipe, skill,
    tools, updates,
)
from .geometry import Rect
from .overlay import Overlay

APP_ID = "com.github.shubshub.programmers-screenshot"
VERSION = "0.27.0"

EXIT_OK = 0
EXIT_CANCELLED = 1
EXIT_BAD_USAGE = 2


def build_parser():
    parser = argparse.ArgumentParser(
        prog="programmers-screenshot",
        description="Mark out a screen region, draw on it, then hit Capture. "
        "The result goes to the clipboard and to ~/Pictures/Screenshots.",
    )
    parser.add_argument(
        "-f", "--full", action="store_true",
        help="capture the whole screen immediately, without the overlay",
    )
    parser.add_argument(
        "-o", "--output", metavar="FILE", help="write the PNG to FILE"
    )
    parser.add_argument(
        "-d", "--directory", metavar="DIR",
        help="save into DIR instead of the default directory",
    )
    parser.add_argument(
        "--window", metavar="TITLE",
        help="capture the window whose title contains TITLE, even if buried",
    )
    parser.add_argument(
        "--list-windows", action="store_true",
        help="print the windows --window can name, and exit",
    )
    parser.add_argument(
        "--region", metavar="X,Y,W,H",
        help="capture this area of the screen, without the overlay",
    )
    parser.add_argument(
        "--origin", metavar="X,Y",
        help="measure every coordinate from this point instead of the corner",
    )
    parser.add_argument(
        "--input", metavar="FILE",
        help="annotate this image instead of capturing anything",
    )
    parser.add_argument(
        "--scale", metavar="FACTOR", type=float,
        help="the picture is this many of its pixels per one of yours",
    )
    parser.add_argument(
        "--viewport", metavar="WIDTH", type=float,
        help="the picture shows a page this many pixels wide (window.innerWidth); "
        "the scale follows from that",
    )
    parser.add_argument(
        "--dpr", metavar="FACTOR", type=float,
        help="the page's window.devicePixelRatio (default 1); with --viewport, "
        "corrects for a browser save cropped at a page zoom",
    )
    parser.add_argument(
        "--delay", metavar="SECONDS", type=float, default=0,
        help="wait this long before the screen is captured",
    )
    parser.add_argument(
        "--recipe", metavar="FILE",
        help='take the shot described by a JSON recipe ("-" reads stdin)',
    )
    parser.add_argument(
        "--recipe-help", action="store_true",
        help="print what a recipe can describe, and exit",
    )
    parser.add_argument(
        "--no-clipboard", action="store_true", help="do not touch the clipboard"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="copy only; do not write a file"
    )
    parser.add_argument(
        "--no-sound", action="store_true", help="do not play the shutter sound"
    )
    parser.add_argument(
        "--install-hotkey", nargs="?", const=hotkey.DEFAULT_ACCELERATOR,
        metavar="ACCEL",
        help="register a GNOME shortcut (default: %s)" % hotkey.DEFAULT_ACCELERATOR,
    )
    parser.add_argument(
        "--uninstall-hotkey", action="store_true", help="remove the GNOME shortcut"
    )
    parser.add_argument(
        "--install-skill", action="store_true",
        help="write a Claude Code skill, so any session knows this is here",
    )
    parser.add_argument(
        "--uninstall-skill", action="store_true", help="remove that skill"
    )
    # Internal: the detached process that keeps a notification's buttons alive.
    parser.add_argument(
        "--notification-agent", metavar="FILE", help=argparse.SUPPRESS
    )
    # Internal: an alert window carrying one link button, as JSON.
    parser.add_argument("--alert", metavar="JSON", help=argparse.SUPPRESS)
    # Internal: the detached update check, run well after any capture.
    parser.add_argument(
        "--check-updates", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument("--version", action="version", version=version_banner())
    return parser


def version_banner():
    """The version, and where this copy was loaded from.

    The number alone cannot tell you which code is running: a fix between
    releases does not bump it, so one version can cover several builds. That
    has already cost two rounds of debugging a bug that was fixed in the
    checkout and stale in /usr/share, both calling themselves 0.18.0. The
    path says which is which.
    """
    # One line: argparse re-wraps the version string, so a newline here comes
    # back out mangled.
    return "programmers-screenshot %s (from %s)" % (
        VERSION, os.path.dirname(os.path.abspath(__file__))
    )


def main(argv=None):
    options = build_parser().parse_args(argv if argv is not None else sys.argv[1:])

    # First, and before any mention of a display: whoever is about to drive
    # this needs to be able to ask what it can do from wherever they are.
    if options.recipe_help:
        print(recipe.describe())
        return EXIT_OK
    if options.notification_agent:
        return notifications.run_agent(options.notification_agent)
    if options.alert:
        return alerts.run(options.alert)
    if options.check_updates:
        updates.run_check(VERSION)
        return EXIT_OK
    if options.uninstall_skill:
        return skill.uninstall()
    if options.install_skill:
        return skill.install()
    if options.uninstall_hotkey:
        return hotkey.uninstall()
    if options.install_hotkey:
        return hotkey.install(options.install_hotkey)

    if scripted(options):
        try:
            # Read before anything is checked or captured: a recipe that
            # cannot be understood costs nothing and leaves nothing half
            # drawn, and what it says decides whether the switch applies.
            spec = recipe.load(options.recipe) if options.recipe else {}
        except recipe.RecipeError as error:
            sys.stderr.write("%s\n" % error)
            return EXIT_BAD_USAGE
        # A flag beats the recipe, the same way it beats a preference.
        options.output = options.output or spec.get("output")
        options.region = options.region or spec.get("region")
        options.window = options.window or spec.get("window")
        options.origin = options.origin or spec.get("origin")
        options.input = options.input or spec.get("input")
        options.scale = options.scale or spec.get("scale")
        if options.viewport is None:  # 0 is a mistake to name, not "none given"
            options.viewport = spec.get("viewport")
        if options.dpr is None:
            options.dpr = spec.get("dpr")
        options.delay = options.delay or spec.get("delay") or 0

        if reads_the_screen(options) and not preferences.load().get("scripted"):
            sys.stderr.write(
                "recipes are switched off. Tick \"Let a recipe drive captures\" in\n"
                "the settings window, on the overlay toolbar. See --recipe-help.\n"
            )
            return EXIT_BAD_USAGE
        if options.list_windows:
            try:
                print(capture.describe_windows())
            except capture.CaptureError as error:
                sys.stderr.write("%s\n" % error)
                return EXIT_CANCELLED
            return EXIT_OK
    else:
        spec = {}

    # An early warning only; the values that count are read again after the
    # overlay, since the settings window can change them while it is open.
    if with_preferences(options).no_save and options.no_clipboard:
        sys.stderr.write("nothing to do: --no-save and --no-clipboard together\n")
        return EXIT_BAD_USAGE
    if not options.full and not cairo_is_usable():
        return EXIT_CANCELLED

    GLib.set_prgname(APP_ID)
    GLib.set_application_name("Programmers Screenshot")
    if not Gtk.init_check()[0]:
        sys.stderr.write("cannot open a display\n")
        return EXIT_CANCELLED

    if options.delay:
        # After the display check, so a mistyped command fails at once rather
        # than in ten seconds' time.
        time.sleep(options.delay)

    display = Gdk.Display.get_default()
    try:
        if options.input:
            pixbuf, bounds = load_input(options.input)
        elif options.window:
            # Coordinates come back relative to the window, which is what a
            # caller working from inside it already has.
            pixbuf, bounds = capture.capture_window(display, options.window)
        else:
            pixbuf, bounds = capture.capture_screen(display)
    except capture.CaptureError as error:
        sys.stderr.write("%s\n" % error)
        return EXIT_CANCELLED

    # --input photographed nothing, so there is no shot to announce.
    quiet = bool(options.input)

    if options.full:
        output.deliver(pixbuf, with_preferences(options), quiet)
        after_capture(options)
        return EXIT_OK

    if scripted(options):
        try:
            captured = render_recipe(pixbuf, bounds, options, spec)
        except recipe.RecipeError as error:
            sys.stderr.write("%s\n" % error)
            return EXIT_BAD_USAGE
        output.deliver(captured, with_preferences(options), quiet)
        after_capture(options)
        return EXIT_OK

    captured = run_overlay(pixbuf, bounds)
    if captured is None:
        return EXIT_CANCELLED

    # After the overlay, not before: the settings window writes the file while
    # the overlay is up, and the capture in hand has to honour what it says.
    # Reading at startup meant a change only took effect from the next run.
    output.deliver(captured, with_preferences(options))
    after_capture(options)
    return EXIT_OK


def scripted(options):
    """Whether this run is being driven by a description rather than a person."""
    return options.list_windows or any(
        value is not None
        for value in (
            options.recipe, options.region, options.window, options.input
        )
    )


def reads_the_screen(options):
    """Whether this run looks at the screen, which is what wants permission.

    The switch exists so that nothing photographs somebody's screen without
    their say-so. --input does not: it draws on a picture the caller already
    had, and refusing it would be friction with nothing behind it. Listing
    windows still counts -- the titles alone say a good deal about what
    somebody is doing.
    """
    if options.list_windows:
        return True
    return options.input is None and scripted(options)


def load_input(path):
    """A PNG to draw on, as (pixbuf, bounds), instead of a capture.

    What this is for: a tab. Nothing outside a browser can address one -- a
    tab is not a window, and only the front tab of a window is being drawn at
    all -- so the browser takes its own picture of the tab it means, and this
    annotates that. Every other way round is a guess about which tab was in
    front.

    ponytail: still goes through the overlay to draw, so it wants a display
    even though it captures nothing. Split the renderer out of Overlay if
    annotating in CI is ever wanted.
    """
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.Error as error:
        raise capture.CaptureError("cannot read %s: %s" % (path, error.message))
    return pixbuf, Rect(0, 0, pixbuf.get_width(), pixbuf.get_height())


def render_recipe(pixbuf, bounds, options, spec):
    """The shot the recipe describes, with no window ever shown.

    An Overlay with nothing mapped: it is the thing that knows how to bake a
    scene into a region of the frozen screen, and that knowledge should not
    exist twice.
    """
    overlay = Overlay(pixbuf, bounds, tools.build_tools())
    frame = frame_for(bounds, options)
    if options.region is not None:
        overlay.scene.do(recipe.region(options.region, frame))
    recipe.annotate(spec, overlay, frame)
    return overlay.render()


def frame_for(bounds, options):
    """The caller's ruler: --scale as given, or worked out from --viewport.

    A browser knows window.innerWidth and the picture knows its own width, so
    nothing in between has to open the file to measure it. --scale beats
    --viewport when both are given, the way a flag beats a recipe.

    --dpr is window.devicePixelRatio. A Claude in Chrome save made at a page
    zoom other than 100% is cropped to 1/dpr of the viewport -- measured
    against dots the page drew, at 125% -- so the width alone lands every
    mark short by that much. The picture's width times dpr is the width the
    whole viewport was rendered at, and that over innerWidth is the scale.
    """
    scale = options.scale
    if not scale and options.viewport is not None:
        dpr = 1.0 if options.dpr is None else options.dpr
        for name, value in (("viewport", options.viewport), ("dpr", dpr)):
            if value <= 0:
                raise recipe.RecipeError("%s: expected a number more than zero" % name)
        scale = bounds.width * dpr / float(options.viewport)
    return recipe.Frame(bounds, options.origin, scale)


def after_capture(options):
    """Version housekeeping, once the screenshot is safely delivered.

    Deliberately last. Everything here can wait, and none of it may come
    between pressing the key and seeing the overlay -- a network timeout in
    that gap would be the worst bug this program could have.
    """
    updates.announce_upgrade(VERSION)
    if not preferences.load().get("updates"):
        return
    if updates.due():
        # A process of its own, so the request outlives us without us waiting
        # on it. Reading one timestamp first keeps this to once a day rather
        # than a spawn per screenshot.
        notifications.spawn_detached(["--check-updates"])


def with_preferences(options):
    """A copy of `options` with stored preferences filling what it omitted.

    A copy, not a mutation, so this can be called more than once and still
    read the command line rather than its own previous answer. Mutating meant
    an early call that switched saving off could never be switched back on by
    a later one.

    A flag always wins. Only ever tightens: a stored preference can switch
    saving off, never back on over --no-save.
    """
    stored = preferences.load()
    effective = copy.copy(options)
    # -o names a file to write, which is a clearer instruction than a stored
    # default, so it is not overridden by one.
    if not effective.no_save and not effective.output and not stored.get("save", True):
        effective.no_save = True
    if effective.directory is None and stored.get("directory"):
        effective.directory = stored["directory"]
    return effective


def run_overlay(pixbuf, bounds):
    """Run the overlay and return the captured pixbuf, or None if cancelled.

    The overlay renders it rather than returning a rectangle to crop, because
    only it knows about the annotations that have to be baked in.
    """
    return Overlay(pixbuf, bounds, tools.build_tools()).run()


def cairo_is_usable():
    """The overlay is drawn through the "draw" signal, which needs PyGObject's
    cairo bridge. Without it GTK hands us nothing to draw on and the overlay
    comes up blank, so fail loudly instead."""
    try:
        import cairo  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "missing pycairo — install it with: sudo apt install python3-cairo\n"
        )
        return False
    try:
        import gi._gi_cairo  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "PyGObject cannot marshal cairo contexts, so the overlay would come\n"
            "up blank. Install it with: sudo apt install python3-gi-cairo\n"
        )
        return False
    return True
