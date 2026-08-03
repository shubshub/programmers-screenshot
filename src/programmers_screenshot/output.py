"""What happens to a captured image: file, clipboard, notification."""

import os
import shutil
import subprocess
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import notifications, sound
from .capture import is_x11
from .paths import default_directory

FILENAME_FORMAT = "Screenshot_%Y-%m-%d_%H-%M-%S.png"

# Screenshots taken by this tool routinely hold tokens, cookies and .env
# contents. The default umask would make them 0644 — fine under a 0750 home,
# not fine once -o or -d points somewhere shared like /tmp. The mode should
# not depend on where the file happens to land.
FILE_MODE = 0o600


def save(pixbuf, directory=None, output=None):
    """Write a PNG, readable only by its owner, and return its path."""
    if output:
        path = os.path.abspath(os.path.expanduser(output))
    else:
        folder = os.path.abspath(os.path.expanduser(directory or default_directory()))
        path = os.path.join(folder, datetime.now().strftime(FILENAME_FORMAT))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pixbuf.savev(path, "png", [], [])
    os.chmod(path, FILE_MODE)
    return path


def copy_to_clipboard(pixbuf):
    """Put the image on the clipboard so it outlives this process.

    xclip and wl-copy read stdin, then fork and keep serving the selection
    after we exit — something a plain GTK clipboard owner cannot do. The GTK
    path is only a fallback for when neither helper is installed.
    """
    helper = _clipboard_helper()
    if helper:
        succeeded, data = pixbuf.save_to_bufferv("png", [], [])
        if succeeded:
            process = subprocess.Popen(
                helper,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.stdin.write(data)
            process.stdin.close()  # closing the pipe is what releases the helper
            return True
    return _copy_via_gtk(pixbuf)


def copy_text(text):
    """Put a short string on the clipboard, the same way an image goes there.

    Note this is the same clipboard the capture uses, so taking a screenshot
    afterwards replaces whatever was copied.
    """
    helper = _clipboard_helper(image=False)
    if helper:
        try:
            process = subprocess.Popen(
                helper,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.stdin.write(text.encode("utf-8"))
            process.stdin.close()
            return True
        except OSError:
            pass

    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(text, -1)
    clipboard.store()
    return True


def _clipboard_helper(image=True):
    kind = "image/png" if image else "text/plain"
    if not is_x11(Gdk.Display.get_default()) and shutil.which("wl-copy"):
        return ["wl-copy", "--type", kind]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard", "-target", kind]
    return None


def _copy_via_gtk(pixbuf):
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_image(pixbuf)
    clipboard.store()
    deadline = GLib.get_monotonic_time() + 2 * GLib.USEC_PER_SEC
    while Gtk.events_pending() and GLib.get_monotonic_time() < deadline:
        Gtk.main_iteration_do(False)
    return True


def deliver(pixbuf, options):
    """Save and/or copy, then say so. Returns the saved path, if any."""
    if not options.no_sound:
        sound.play()  # first, so the shutter lands with the capture

    path = None
    if not options.no_save:
        path = save(pixbuf, options.directory, options.output)
    if not options.no_clipboard:
        copy_to_clipboard(pixbuf)

    if path:
        print(path)
        notifications.announce_file(path)
    else:
        size = "%d × %d" % (pixbuf.get_width(), pixbuf.get_height())
        notifications.show_simple("Screenshot copied", size)
    return path
