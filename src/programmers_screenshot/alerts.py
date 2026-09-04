"""Alert windows: the ones that say something and wait to be dismissed.

Distinct from notifications.py, which posts to the desktop's notification
service and disappears on its own. These are windows. They take focus and
they stay until closed, which is the point — a notification about a new
version is easy to miss, and a changelog does not fit in one.

Shown from a detached process for the same reason a notification with buttons
needs one: the program that took the screenshot has already exited, and
something has to be alive to hold the window. Nothing here ever runs before a
capture is delivered.
"""

import contextlib
import json

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .paths import spawn_detached

TITLE = "Programmers Screenshot"
WIDTH = 460
MAX_HEIGHT = 320   # past this the body scrolls rather than growing the window


def show(heading, body, label=None, uri=None):
    """Put up an alert window, in a process of its own. False if it could not.

    Returns rather than raising, and the caller ignores it: an update notice
    that cannot be shown is not worth interrupting anything over.
    """
    payload = json.dumps(
        {"heading": heading, "body": body, "label": label, "uri": uri}
    )
    return spawn_detached(["--alert", payload])


def build(notice):
    """The window itself. Split out so it can be checked without a person."""
    dialog = Gtk.Dialog(title=TITLE)
    dialog.set_default_size(WIDTH, -1)

    heading = Gtk.Label(halign=Gtk.Align.START)
    heading.set_markup(
        "<big><b>%s</b></big>" % GLib.markup_escape_text(notice.get("heading", ""))
    )

    body = Gtk.Label(label=notice.get("body", ""), halign=Gtk.Align.START,
                     xalign=0.0)
    body.set_line_wrap(True)
    body.set_max_width_chars(52)
    body.set_selectable(True)   # so a version number can be copied out

    # Scrolls rather than growing without limit: a changelog entry can run to
    # a dozen bullets and a window taller than the screen helps nobody.
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroller.set_max_content_height(MAX_HEIGHT)
    scroller.set_propagate_natural_height(True)
    scroller.add(body)

    layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                     margin=16)
    layout.pack_start(heading, False, False, 0)
    layout.pack_start(scroller, True, True, 0)
    dialog.get_content_area().add(layout)

    dialog.add_button("Close", Gtk.ResponseType.CLOSE)
    if notice.get("label") and notice.get("uri"):
        dialog.add_button(notice["label"], Gtk.ResponseType.ACCEPT)
    return dialog


def run(payload):
    """Agent mode: show the window and wait for it to be dismissed."""
    try:
        notice = json.loads(payload)
    except ValueError:
        return 1
    if not Gtk.init_check()[0]:
        return 1

    dialog = build(notice)
    dialog.show_all()
    answer = dialog.run()
    dialog.destroy()

    if answer == Gtk.ResponseType.ACCEPT:
        with contextlib.suppress(GLib.Error):
            Gio.AppInfo.launch_default_for_uri(notice["uri"], None)
    return 0
