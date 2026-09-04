"""Where this program lives, where its output goes, and what it remembers.

The three things this program stores between runs -- preferences, machine
state, and the hotkeys it displaced -- are three files of JSON in the same
place, read and written the same way. Each module still owns what its file
means; only the plumbing is here.
"""

import json
import os
import shutil
import subprocess
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


def spawn_detached(arguments):
    """Start a detached copy of ourselves. False if it could not be launched.

    Anything that has to outlive this process goes through here: a
    notification with buttons, an alert window, the update check. All of them
    re-invoke the running program, which is why this lives beside
    running_program() rather than with any one caller.
    """
    try:
        subprocess.Popen(
            [running_program()] + arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # survives us exiting
        )
        return True
    except OSError:
        return False


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


def config_file(name):
    """One of our files under the user's config directory."""
    return os.path.join(GLib.get_user_config_dir(), PROGRAM, name)


def read_json(path):
    """The object stored in `path`, or {} if there is not one to be had.

    Missing, unreadable, malformed and "not an object at all" all mean the
    same thing: nothing is known yet. Nothing this program remembers is worth
    failing a screenshot over, so none of it raises.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_json(path, values):
    """Write it, making the directory if it is not there.

    Raises OSError. Whether that matters is the caller's call: losing a
    preference somebody just chose is worth hearing about, losing a timestamp
    is not.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(values, handle, indent=2, sort_keys=True)
