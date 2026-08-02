"""Where this program lives, and where its output goes."""

import os
import shutil
import sys

from gi.repository import GLib

PROGRAM = "programmers-screenshot"
SHUTTER_SOUND = "shutter.wav"


def running_program():
    """The copy of this program that is executing right now.

    Helper processes must re-invoke *this* code — resolving through PATH could
    pick up a different, possibly older, installed version.
    """
    return os.path.abspath(sys.argv[0])


def installed_command():
    """A stable path for the desktop to invoke later, e.g. from a shortcut.

    Prefers whatever is on PATH, since a source checkout may move or vanish.
    """
    return shutil.which(PROGRAM) or running_program()


def sound_file():
    """The capture sound, wherever this copy of the program keeps it.

    Installed, it sits beside the package directory; in a checkout it is still
    in packaging/. Returns None if it cannot be found, which is not fatal.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(here, os.pardir, "sounds", SHUTTER_SOUND),
        os.path.join(here, os.pardir, os.pardir, "packaging", SHUTTER_SOUND),
        os.path.join("/usr/share", PROGRAM, "sounds", SHUTTER_SOUND),
    )
    for candidate in candidates:
        path = os.path.normpath(candidate)
        if os.path.isfile(path):
            return path
    return None


def default_directory():
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    return os.path.join(pictures or os.path.expanduser("~"), "Screenshots")
