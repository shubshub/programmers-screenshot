"""What happens to a captured image: file, clipboard, notification."""

import os
import shutil
import subprocess
import tempfile
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
    """Write a PNG, readable only by its owner, and return its path.

    Written under a private name and moved into place, rather than saved and
    then tightened. Tightening afterwards leaves a window: the whole image is
    on disk at the umask's mode — measured at 0644 — before the chmod lands,
    and that is long enough for another user to open it and keep reading
    through the descriptor. The rename also means no half-written PNG is ever
    visible under the final name.

    One consequence worth knowing: if the destination is a symlink, this
    replaces the link rather than writing through it.
    """
    if output:
        path = os.path.abspath(os.path.expanduser(output))
    else:
        folder = os.path.abspath(os.path.expanduser(directory or default_directory()))
        path = os.path.join(folder, datetime.now().strftime(FILENAME_FORMAT))

    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)

    # Alongside the destination, so the rename cannot cross a filesystem.
    handle, temporary = tempfile.mkstemp(dir=folder, prefix=".", suffix=".png")
    os.close(handle)
    try:
        pixbuf.savev(temporary, "png", [], [])
        os.chmod(temporary, FILE_MODE)  # mkstemp gives 0600; savev may not keep it
        os.replace(temporary, path)
    except BaseException:
        _discard(temporary)
        raise
    return path


def _discard(path):
    try:
        os.unlink(path)
    except OSError:
        pass


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


def deliver(pixbuf, options, quiet=False):
    """Save and/or copy, then say so. Returns the saved path, if any.

    `quiet` is for --input: nothing was photographed, so there is no shutter
    to sound and no shot to announce. The path is still printed.
    """
    if not quiet and not options.no_sound:
        sound.play()  # first, so the shutter lands with the capture

    path = None
    if not options.no_save:
        path = save(pixbuf, options.directory, options.output)
    if not options.no_clipboard:
        copy_to_clipboard(pixbuf)

    if path:
        print(path)
    if quiet:
        return path
    if path:
        notifications.announce_file(path)
    else:
        size = "%d × %d" % (pixbuf.get_width(), pixbuf.get_height())
        notifications.show_simple("Screenshot copied", size)
    return path
