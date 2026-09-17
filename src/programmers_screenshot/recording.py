"""Recording a region of the screen, by driving ffmpeg.

Nothing here encodes anything. That is ffmpeg's job, the same way the shutter
sound and the clipboard are other programs' jobs: this owns where the file
goes, the command line that fills it, and the one piece of state that lets a
second invocation stop the first.

Three processes, because a recording outlives the command that starts it. The
run you launch marks out a region and exits, so a shell pipeline is not held
open for the length of the recording; a detached agent owns ffmpeg and the
notification with the Stop button on it; and the next --record finds the
agent's ffmpeg through state.json and interrupts it, which is what makes the
same hotkey a toggle. ffmpeg finalises the file on SIGINT, so stopping it that
way leaves a playable recording rather than a truncated one.
"""

import contextlib
import json
import os
import shutil
import signal
import subprocess
import tempfile

from gi.repository import Gio, GLib

from . import notifications, output, state
from .paths import spawn_detached

PROGRAM = "ffmpeg"
FILENAME_FORMAT = "Recording_%Y-%m-%d_%H-%M-%S"
FRAMERATE = 25
# Recordings hold whatever screenshots hold, so they land as privately.
FILE_MODE = output.FILE_MODE

MISSING = (
    "recording needs ffmpeg: sudo apt install ffmpeg"
)
NO_WAYLAND = (
    "recording needs an X11 session. Under Wayland the only route is the\n"
    "portal's screencast, which cannot start without somebody picking the\n"
    "screen in a dialog first -- so a hotkey cannot begin one."
)

# One pass, so the palette is made from the same frames it is applied to.
GIF_FILTER = "[0:v] split [a][b];[a] palettegen [p];[b][p] paletteuse"

POLL_MS = 1000

ICON = "media-record"  # the red dot, from the desktop's own icon theme


def unavailable(display):
    """Why this machine cannot record, or None if it can."""
    if not shutil.which(PROGRAM):
        return MISSING
    from .capture import is_x11  # here: capture pulls in Gdk, this module need not

    if not is_x11(display):
        return NO_WAYLAND
    return None


# --------------------------------------------------------------------------
# the recording in progress
# --------------------------------------------------------------------------


def running():
    """The pid of a recording already in progress, or None.

    Checked against /proc rather than taken on trust: an agent killed outright
    leaves its pid behind in state.json, and a pid on its own is a promise
    about a number the kernel is free to hand to somebody else. Reading back
    the command name means a stale entry can never aim a signal at whatever
    process inherited the number.
    """
    pid = state.load().get("recording")
    try:
        with open("/proc/%d/comm" % pid, "r", encoding="utf-8") as handle:
            return pid if handle.read().strip() == PROGRAM else None
    except (OSError, TypeError):
        return None


def stop_running():
    """Stop a recording in progress. True if there was one to stop."""
    pid = running()
    if pid is None:
        return False
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGINT)  # ffmpeg finalises the file and exits
    return True


# --------------------------------------------------------------------------
# starting one
# --------------------------------------------------------------------------


def destination(options):
    """The file the recording will end up in.

    Named up front, and printed before a single frame is in it, because the
    command that starts a recording exits straight away: waiting for the file
    to exist would mean waiting for the recording to finish.
    """
    suffix = ".gif" if options.gif else ".webm"
    return output.destination(
        options.directory, options.output, FILENAME_FORMAT + suffix
    )


def command(path, area):
    """The ffmpeg that fills `path` from `area` of the X display.

    `area` is in physical pixels, which is what x11grab addresses -- the
    caller has already multiplied by the display scale. Realtime VP9: the
    default deadline is tuned for encoding a film overnight and drops most of
    the frames of a large region when it has to keep up with one.
    """
    return [
        PROGRAM, "-nostdin", "-loglevel", "error", "-y",
        "-f", "x11grab",
        "-framerate", str(FRAMERATE),
        "-video_size", "%dx%d" % (area.width, area.height),
        "-i", "%s+%d,%d" % (os.environ.get("DISPLAY") or ":0", area.x, area.y),
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p",
        "-deadline", "realtime", "-cpu-used", "4",
        "-b:v", "0", "-crf", "31",
        path,
    ]


def start(area, options):
    """Hand `area` to a detached agent, and say where it is being written.

    Returns an exit code. `area` is in physical pixels.
    """
    path = destination(options)
    payload = json.dumps({"path": path, "area": [area.x, area.y, area.width,
                                                 area.height]})
    if not spawn_detached(["--record-agent", payload]):
        return 1
    print(path)
    return 0


# --------------------------------------------------------------------------
# agent mode: the process that owns ffmpeg for as long as it runs
# --------------------------------------------------------------------------


STATUS_ITEM = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
  </interface>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
  </interface>
</node>
"""

ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/StatusNotifierItem/Menu"
WATCHER = "org.kde.StatusNotifierWatcher"
STOP_ID = 1
STOP_LABEL = "Stop recording"


class Indicator:
    """A red dot in the status area, with Stop on it, spoken over D-Bus.

    StatusNotifierItem is an interface, not a library. The AppIndicator
    typelib is a convenience wrapper round it and one more package to have
    installed -- and a Recommends that somebody skips would mean the only
    control a running recording has quietly does not appear. Gio is already
    a hard dependency, so this talks to the desktop itself.

    The menu is here because of how a click is read: GNOME's AppIndicator
    extension opens the item's menu on a single click and only calls Activate
    on a double one, so an item with no menu looks broken to anybody who
    clicks it once. There is one item on it and it never changes, which is
    why the layout is a constant and the revision never moves. Activate and
    the middle click do the same thing, for a desktop that reads them.

    Nothing here is worth failing a recording over: if the bus is not there,
    or nothing is listening for these, the recording still runs and the
    notification's Stop button and the command itself still end it.
    """

    def __init__(self, on_stop):
        self.on_stop = on_stop
        self.bus = None
        self.registrations = ()
        nodes = Gio.DBusNodeInfo.new_for_xml(STATUS_ITEM)
        self.interfaces = {
            info.name: info for info in nodes.interfaces
        }
        self.properties = {
            "org.kde.StatusNotifierItem": {
                "Category": GLib.Variant("s", "ApplicationStatus"),
                "Id": GLib.Variant("s", "programmers-screenshot"),
                "Title": GLib.Variant("s", "Recording"),
                "Status": GLib.Variant("s", "Active"),
                "IconName": GLib.Variant("s", ICON),
                "ItemIsMenu": GLib.Variant("b", False),
                "Menu": GLib.Variant("o", MENU_PATH),
            },
            "com.canonical.dbusmenu": {
                "Version": GLib.Variant("u", 3),
                "Status": GLib.Variant("s", "normal"),
                "TextDirection": GLib.Variant("s", "ltr"),
                "IconThemePath": GLib.Variant("as", []),
            },
        }

    def show(self):
        """Offer it to the desktop. False if there is no bus to offer it to.

        The last step is deliberately asynchronous. A watcher reads the item's
        properties back before it answers the registration, and a blocking
        call could not serve them: the reply would be waiting on this thread,
        and so would every incoming question about the item. It deadlocks
        until the timeout, and nothing appears. Sent this way it is answered
        out of the main loop the recording is already running under.
        """
        name = "org.kde.StatusNotifierItem-%d-1" % os.getpid()
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self.bus.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus",
                "org.freedesktop.DBus", "RequestName",
                GLib.Variant("(su)", (name, 4)),  # 4: do not queue behind another
                None, Gio.DBusCallFlags.NONE, 2000, None,
            )
            self.registrations = (
                self.bus.register_object(
                    ITEM_PATH, self.interfaces["org.kde.StatusNotifierItem"],
                    self._called, self._property, None),
                self.bus.register_object(
                    MENU_PATH, self.interfaces["com.canonical.dbusmenu"],
                    self._called, self._property, None),
            )
        except GLib.Error:
            self.close()
            return False

        self.bus.call(
            WATCHER, "/StatusNotifierWatcher", WATCHER,
            "RegisterStatusNotifierItem", GLib.Variant("(s)", (name,)),
            None, Gio.DBusCallFlags.NONE, 5000, None, self._registered,
        )
        return True

    def _registered(self, bus, result):
        """Nothing took it -- no watcher, or it said no. Take the object back."""
        try:
            bus.call_finish(result)
        except GLib.Error:
            self.close()

    def close(self):
        for registration in self.registrations:
            with contextlib.suppress(GLib.Error):
                self.bus.unregister_object(registration)
        self.registrations = ()

    # -- what the desktop asks of it ---------------------------------------

    def _property(self, _bus, _sender, _path, interface, name):
        return self.properties.get(interface, {}).get(name)

    def _called(self, _bus, _sender, _path, _interface, method, parameters,
                invocation):
        if method in ("Activate", "SecondaryActivate"):
            self.on_stop()
            invocation.return_value(None)
        elif method == "GetLayout":
            invocation.return_value(GLib.Variant(
                "(u(ia{sv}av))",
                (1, (0, {"children-display": GLib.Variant("s", "submenu")},
                     [GLib.Variant.new_variant(self._item())])),
            ))
        elif method == "GetGroupProperties":
            invocation.return_value(GLib.Variant(
                "(a(ia{sv}))", ([(STOP_ID, self._item_properties())],)
            ))
        elif method == "GetProperty":
            _id, name = parameters.unpack()
            invocation.return_value(GLib.Variant(
                "(v)", (self._item_properties().get(name, GLib.Variant("b", False)),)
            ))
        elif method == "Event":
            identifier, event = parameters.unpack()[:2]
            if event == "clicked" and identifier == STOP_ID:
                self.on_stop()
            invocation.return_value(None)
        elif method == "AboutToShow":
            # One item that never changes: there is nothing to rebuild first.
            invocation.return_value(GLib.Variant("(b)", (False,)))
        else:
            invocation.return_value(None)

    def _item(self):
        return GLib.Variant("(ia{sv}av)", (STOP_ID, self._item_properties(), []))

    @staticmethod
    def _item_properties():
        return {
            "label": GLib.Variant("s", STOP_LABEL),
            "enabled": GLib.Variant("b", True),
            "visible": GLib.Variant("b", True),
        }


def indicator(on_stop):
    """The dot, once the desktop has taken it, or None if it would not."""
    dot = Indicator(on_stop)
    return dot if dot.show() else None


def run_agent(payload):
    """Record until somebody stops it, then finish the file and announce it."""
    spec = json.loads(payload)
    path = spec["path"]
    # With --gif the deliverable is a conversion of the recording, so ffmpeg
    # writes a WebM beside it and that one is removed once it is converted.
    recorded = os.path.splitext(path)[0] + ".webm"

    # Made here, at the mode it has to keep: ffmpeg opens the name and
    # truncates it, and a file it creates itself would be at the umask's mode
    # for the whole recording. What lands in it is somebody's screen.
    _create_privately(recorded)

    errors = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(
            command(recorded, _Area(*spec["area"])),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=errors,
        )
    except OSError:
        notifications.show_simple("Recording failed", MISSING)
        return 1

    state.remember(recording=process.pid)
    loop = GLib.MainLoop()
    # A poll rather than a child watch, which would reap the process out from
    # under Popen. A second's lag on a recording somebody just stopped is not
    # something anybody can see.
    GLib.timeout_add(POLL_MS, lambda: loop.quit() if process.poll() is not None else True)
    notification = notifications.recording_started(stop_running)
    dot = indicator(stop_running)
    loop.run()
    _close(notification)
    if dot is not None:
        dot.close()

    state.remember(recording=None)
    return _finish(recorded, path, errors)


def _finish(recorded, path, errors):
    """Whatever ffmpeg left behind, turned into the file that was promised."""
    if not _wrote_something(recorded):
        errors.seek(0)
        detail = errors.read().decode("utf-8", "replace").strip().splitlines()
        notifications.show_simple(
            "Recording failed", detail[-1] if detail else "ffmpeg wrote nothing"
        )
        with contextlib.suppress(OSError):
            os.unlink(recorded)
        return 1

    if path != recorded:
        if not _to_gif(recorded, path):
            notifications.show_simple(
                "Recording saved, but not converted", recorded
            )
            return 1
        with contextlib.suppress(OSError):
            os.unlink(recorded)

    with contextlib.suppress(OSError):
        os.chmod(path, FILE_MODE)
    notifications.announce_file(path)
    return 0


def _wrote_something(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def _to_gif(source, target):
    """Convert, through a palette made from the recording's own colours."""
    _create_privately(target)
    completed = subprocess.run(
        [PROGRAM, "-nostdin", "-loglevel", "error", "-y", "-i", source,
         "-filter_complex", GIF_FILTER, target],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0 and os.path.exists(target)


def _create_privately(path):
    """Put the file there at 0600, for ffmpeg to open and truncate."""
    with contextlib.suppress(OSError):
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, FILE_MODE))
        os.chmod(path, FILE_MODE)  # it may have been there already, at 0644


def _close(notification):
    with contextlib.suppress(Exception):  # noqa: BLE001 - it is only a banner
        notification.close()


class _Area:
    """A rectangle in whole physical pixels, which is all ffmpeg accepts.

    Both sides are rounded down to an even number: yuv420p stores one chroma
    sample per two pixels each way, so an odd width has nowhere to put the
    last column and ffmpeg refuses the encode outright.
    """

    def __init__(self, x, y, width, height):
        self.x, self.y = int(x), int(y)
        self.width = max(2, int(width) - int(width) % 2)
        self.height = max(2, int(height) - int(height) % 2)


def area_of(region, bounds, scale):
    """The region marked out on the overlay, as ffmpeg addresses it.

    The overlay works in logical pixels from the top left of the virtual
    screen; x11grab wants physical pixels from the root window's corner. On a
    HiDPI display those differ by the scale the capture was read at, the same
    factor the renderer uses to place a crop.
    """
    return _Area(
        (bounds.x + region.x) * scale,
        (bounds.y + region.y) * scale,
        region.width * scale,
        region.height * scale,
    )
