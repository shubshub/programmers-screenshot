"""Desktop notifications, including the buttons on them.

A notification with buttons needs a live process to receive the click, but the
tool itself has to exit straight away or shell pipelines like
``$(programmers-screenshot)`` would hang waiting on it. So a notification that
offers actions is handed to a detached copy of ourselves running in agent
mode, which lives only as long as the notification does.
"""

import os
import subprocess

import gi

gi.require_version("Notify", "0.7")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf, Gio, GLib, Notify  # noqa: E402

from .paths import running_program

APP_NAME = "Programmers Screenshot"
ICON = "programmers-screenshot"

OPEN_IMAGE = "open-image"
OPEN_FOLDER = "open-folder"

# The agent should never outlive its usefulness, even if the notification is
# left sitting in the message tray.
AGENT_LIFETIME_SECONDS = 300
# Enough for a launch to leave the building before we exit.
LAUNCH_GRACE_MS = 500

FILE_MANAGER = "org.freedesktop.FileManager1"
FILE_MANAGER_PATH = "/org/freedesktop/FileManager1"


def announce_file(path):
    """Report a saved screenshot, with buttons to open it or show its folder."""
    if not _spawn_agent(path):
        show_simple("Screenshot captured", describe(path))


def show_simple(summary, body):
    """A notification with no buttons, which needs nobody left alive."""
    try:
        Notify.init(APP_NAME)
        Notify.Notification.new(summary, body, ICON).show()
    except (GLib.Error, RuntimeError):
        pass


def describe(path):
    """Filename first, then size and folder.

    GNOME truncates the body when the notification is collapsed, so the most
    identifying part has to come first. Dimensions are read back from the file
    rather than passed in, so they describe what actually landed on disk.
    """
    detail = []
    info = GdkPixbuf.Pixbuf.get_file_info(path)
    if info and info[0] is not None:
        detail.append("%d × %d" % (info[1], info[2]))
    detail.append(os.path.dirname(path))
    return "%s\n%s" % (os.path.basename(path), " · ".join(detail))


def spawn_detached(arguments):
    """Start a detached copy of ourselves. False if it could not be launched."""
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


def _spawn_agent(path):
    """Start the detached agent for a captured file.

    Kept separate from show_notice(): this one has two actions, and showing a
    file in its folder goes over D-Bus to the file manager rather than being
    a URI anything can open.
    """
    return spawn_detached(["--notification-agent", path])


# --------------------------------------------------------------------------
# agent mode
# --------------------------------------------------------------------------


def run_agent(path):
    """Show the notification and wait for a button, or for it to go away."""
    Notify.init(APP_NAME)
    loop = GLib.MainLoop()
    acting = {"now": False}

    def activate(_notification, action, _user_data=None):
        acting["now"] = True
        if action == OPEN_FOLDER:
            show_in_file_manager(path)
        else:
            open_file(path)
        GLib.timeout_add(LAUNCH_GRACE_MS, loop.quit)

    notification = Notify.Notification.new("Screenshot captured", describe(path), ICON)
    notification.add_action(OPEN_IMAGE, "Open Image", activate, None)
    notification.add_action(OPEN_FOLDER, "Show in Folder", activate, None)
    notification.connect(
        "closed", lambda *_: None if acting["now"] else loop.quit()
    )

    try:
        notification.show()
    except GLib.Error:
        return 1

    GLib.timeout_add_seconds(AGENT_LIFETIME_SECONDS, loop.quit)
    loop.run()
    return 0


def open_file(path):
    """Open the image in whatever handles PNGs."""
    return _launch_uri(GLib.filename_to_uri(path, None))


def show_in_file_manager(path):
    """Open the containing folder with the file selected, if we can."""
    uri = GLib.filename_to_uri(path, None)
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            FILE_MANAGER,
            FILE_MANAGER_PATH,
            FILE_MANAGER,
            None,
        )
        proxy.call_sync(
            "ShowItems",
            GLib.Variant("(ass)", ([uri], "")),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        return True
    except GLib.Error:
        # No FileManager1 on the bus: settle for opening the folder itself.
        folder = os.path.dirname(path)
        return _launch_uri(GLib.filename_to_uri(folder, None))


def _launch_uri(uri):
    try:
        return Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error:
        return False
