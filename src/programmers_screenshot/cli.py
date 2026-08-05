"""Command line entry point."""

import argparse
import copy
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import (  # noqa: I101
    capture, hotkey, notifications, output, preferences, tools, updates,
)
from .overlay import Overlay

APP_ID = "com.github.shubshub.programmers-screenshot"
VERSION = "0.23.0"

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
    # Internal: a notification carrying one link button, as JSON.
    parser.add_argument("--notice", metavar="JSON", help=argparse.SUPPRESS)
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

    if options.notification_agent:
        return notifications.run_agent(options.notification_agent)
    if options.notice:
        return notifications.run_notice(options.notice)
    if options.check_updates:
        updates.run_check(VERSION)
        return EXIT_OK
    if options.uninstall_hotkey:
        return hotkey.uninstall()
    if options.install_hotkey:
        return hotkey.install(options.install_hotkey)

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

    display = Gdk.Display.get_default()
    try:
        pixbuf, bounds = capture.capture_screen(display)
    except capture.CaptureError as error:
        sys.stderr.write("%s\n" % error)
        return EXIT_CANCELLED

    if options.full:
        output.deliver(pixbuf, with_preferences(options))
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
