"""Command line entry point."""

import argparse
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import capture, hotkey, notifications, output, tools
from .overlay import Overlay

APP_ID = "com.github.shubshub.programmers-screenshot"
VERSION = "0.15.0"

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
    # Internal: the detached process that keeps a notification's buttons alive.
    parser.add_argument(
        "--notification-agent", metavar="FILE", help=argparse.SUPPRESS
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    return parser


def main(argv=None):
    options = build_parser().parse_args(argv if argv is not None else sys.argv[1:])

    if options.notification_agent:
        return notifications.run_agent(options.notification_agent)
    if options.uninstall_hotkey:
        return hotkey.uninstall()
    if options.install_hotkey:
        return hotkey.install(options.install_hotkey)
    if options.no_save and options.no_clipboard:
        sys.stderr.write("nothing to do: --no-save and --no-clipboard together\n")
        return EXIT_BAD_USAGE
    if not options.full and not cairo_is_usable():
        return EXIT_CANCELLED

    GLib.set_prgname(APP_ID)
    GLib.set_application_name("Programmers Screenshot")
    if not Gtk.init_check()[0]:
        sys.stderr.write("cannot open a display\n")
        return EXIT_CANCELLED

    display = Gdk.Display.get_default()
    try:
        pixbuf, bounds = capture.capture_screen(display)
    except capture.CaptureError as error:
        sys.stderr.write("%s\n" % error)
        return EXIT_CANCELLED

    if options.full:
        output.deliver(pixbuf, options)
        return EXIT_OK

    captured = run_overlay(pixbuf, bounds)
    if captured is None:
        return EXIT_CANCELLED

    output.deliver(captured, options)
    return EXIT_OK


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
