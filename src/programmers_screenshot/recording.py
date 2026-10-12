"""Recording a region of the screen, by driving ffmpeg or GStreamer.

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

Under Wayland no program may read the screen, so the agent asks the desktop
portal to share the monitor the region is on and records that PipeWire stream
with gst-launch-1.0 instead, which finalises on SIGINT too when run with -e.
The portal asks somebody to pick a screen the first time; it hands back a
token that skips the question after that, which is what lets a hotkey start
one.
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
from .geometry import Rect
from .paths import spawn_detached

PROGRAM = "ffmpeg"
GST = "gst-launch-1.0"
FILENAME_FORMAT = "Recording_%Y-%m-%d_%H-%M-%S"
FRAMERATE = 25
# Recordings hold whatever screenshots hold, so they land as privately.
FILE_MODE = output.FILE_MODE

MISSING = (
    "recording needs ffmpeg: sudo apt install ffmpeg"
)
NO_GSTREAMER = (
    "recording under Wayland needs GStreamer and its PipeWire source:\n"
    "sudo apt install gstreamer1.0-tools gstreamer1.0-pipewire "
    "gstreamer1.0-plugins-good"
)
NO_PORTAL = (
    "the desktop portal would not share the screen (needs xdg-desktop-portal "
    "and the backend for this desktop)"
)
NOT_SHARED = "no screen was picked to share"
WRONG_SCREEN = (
    "the screen shared is not the one the area is on; record again and pick "
    "that one"
)

# One pass, so the palette is made from the same frames it is applied to.
GIF_FILTER = "[0:v] split [a][b];[a] palettegen [p];[b][p] paletteuse"

POLL_MS = 1000

ICON = "media-record"  # the red dot, from the desktop's own icon theme


def unavailable(display):
    """Why this machine cannot record, or None if it can."""
    from .capture import is_x11  # here: capture pulls in Gdk, this module need not

    if is_x11(display):
        return None if shutil.which(PROGRAM) else MISSING
    try:
        found = subprocess.run(
            ["gst-inspect-1.0", "--exists", "pipewiresrc"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5, check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        found = False
    return None if found and shutil.which(GST) else NO_GSTREAMER


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
            return pid if handle.read().strip() in (PROGRAM, GST) else None
    except (OSError, TypeError):
        return None


def stop_running():
    """Stop a recording in progress. True if there was one to stop."""
    pid = running()
    if pid is None:
        return False
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGINT)  # either one finalises the file and exits
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


CAPTION_LENGTH = 26  # what still fits a palette's width, one to a line


def microphones():
    """The sound inputs to offer, as ((source name, caption), ...).

    Asked of pactl, which PipeWire answers as well as PulseAudio does. Empty
    when it is not there or says nothing, and then nobody is offered a
    choice. The monitors are left out: they are what the speakers are
    playing, not a microphone.
    """
    try:
        listed = subprocess.run(
            ["pactl", "-f", "json", "list", "sources"], capture_output=True,
            text=True, timeout=3, check=False,
        ).stdout
        sources = json.loads(listed or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ()
    inputs = [
        (source["name"], source.get("description") or source["name"])
        for source in sources
        if source.get("properties", {}).get("device.class") != "monitor"
    ]
    return tuple(zip([name for name, _ in inputs], _captions(
        [description for _, description in inputs])))


def _captions(descriptions):
    """Short enough for the toolbar, and still telling them apart.

    Two microphones on one sound card share most of their description --
    "Family 17h/19h HD Audio Controller Digital Microphone" and the same
    with "Headphones Stereo" -- so the words they all begin and end with go,
    and "Digital" and "Headphones Stereo" are left.
    """
    words = [description.split() for description in descriptions]
    if len(words) > 1:
        for end in (0, -1):  # the front, then the back
            while all(len(each) > 1 for each in words) and \
                    len({each[end] for each in words}) == 1:
                for each in words:
                    del each[end]
    captions = []
    for each in words:
        caption = " ".join(each)
        if len(caption) > CAPTION_LENGTH:
            caption = caption[:CAPTION_LENGTH - 1].rstrip() + "\u2026"
        captions.append(caption)
    return captions


def command(path, area, mic=None):
    """The ffmpeg that fills `path` from `area` of the X display.

    `area` is in physical pixels, which is what x11grab addresses -- the
    caller has already multiplied by the display scale. Realtime VP9: the
    default deadline is tuned for encoding a film overnight and drops most of
    the frames of a large region when it has to keep up with one.

    With `mic`, the name of a pulse source -- or "default", whichever the
    sound settings have picked -- that input joins it as Opus. Through
    pulse, which PipeWire speaks too.
    """
    line = [
        PROGRAM, "-nostdin", "-loglevel", "error", "-y",
        "-f", "x11grab",
        "-framerate", str(FRAMERATE),
        "-video_size", "%dx%d" % (area.width, area.height),
        "-i", "%s+%d,%d" % (os.environ.get("DISPLAY") or ":0", area.x, area.y),
    ]
    if mic:
        # The queue is for the encoder falling behind: VP9 at a large size
        # can, and a full queue drops sound rather than waits.
        line += ["-f", "pulse", "-thread_queue_size", "1024", "-i", mic,
                 "-c:a", "libopus"]
    return line + [
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p",
        "-deadline", "realtime", "-cpu-used", "4",
        "-b:v", "0", "-crf", "31",
        path,
    ]


def screencast_command(path, area, fd, node, stream, mic=None):
    """The gst-launch-1.0 that fills `path` from `area` of a portal stream.

    `stream` is where the shared monitor sits, in the same physical pixels as
    `area`; `fd` and `node` are the PipeWire connection the portal opened.
    The frames are scaled to the monitor's size in those pixels before the
    crop, so the crop lands where the overlay said. That is a no-op at a
    whole-number scale, which is what the portal sends.

    VP8 rather than ffmpeg's VP9: it keeps up in real time on a whole
    monitor, and it is what GNOME's own recorder used. Same WebM either way.
    """
    # ponytail: fractional scaling resamples the frames, slightly soft; read
    # the stream's own size from its caps if that ever shows.
    width, height = int(round(stream.width)), int(round(stream.height))
    left = max(0, int(area.x - stream.x))
    top = max(0, int(area.y - stream.y))
    right = max(0, width - left - area.width)
    bottom = max(0, height - top - area.height)
    line = [GST, "-q", "-e", "webmmux", "name=mux", "!",
            "filesink", "location=" + path]
    # keepalive-time repeats the last frame while nothing on screen changes:
    # PipeWire sends none then, and a still screen would stop the clock.
    line += (
        "pipewiresrc fd=%d path=%d do-timestamp=true keepalive-time=1000"
        " ! videoscale ! video/x-raw,width=%d,height=%d"
        " ! videocrop left=%d top=%d right=%d bottom=%d"
        " ! videorate ! video/x-raw,framerate=%d/1 ! videoconvert ! queue"
        " ! vp8enc deadline=1 cpu-used=8 end-usage=cq cq-level=10"
        " target-bitrate=20000000 threads=%d ! queue ! mux."
        % (fd, node, width, height, left, top, right, bottom, FRAMERATE,
           min(os.cpu_count() or 1, 8))
    ).split()
    if mic:
        line.append("pulsesrc")
        if mic != "default":  # the one the sound settings picked
            line.append("device=" + mic)
        line += "! audioconvert ! audioresample ! opusenc ! queue ! mux.".split()
    return line


SCREENCAST = "org.freedesktop.portal.ScreenCast"
MONITOR = 1
EMBEDDED_CURSOR = 2
PERSIST_UNTIL_REVOKED = 2
CHOOSING_SECONDS = 300  # somebody is reading a dialog


# The portal ends a session when the connection that opened it closes, and Gio
# closes the shared connection once nothing refers to it: held here, it lasts
# as long as the agent, which is as long as the recording.
_connections = []


class Refused(Exception):
    """The portal would not share the screen, or not the part asked for."""


def screencast(area, scale):
    """Have the portal share the monitor `area` is on: (fd, node, stream).

    The token from last time goes in with the request, so the dialog only
    comes up the first time, or when the token stops working. The new token
    is kept whatever happens next. Raises Refused, with the reason to show.
    The session lives as long as this process's bus connection.
    """
    from .capture import PORTAL, PORTAL_PATH, portal_request

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error:
        raise Refused(NO_PORTAL) from None
    _connections.append(bus)
    created = portal_request(
        bus, SCREENCAST, "CreateSession", "(a{sv})", (),
        {"session_handle_token": GLib.Variant("s", "programmers_screenshot")},
    )
    if not created:
        raise Refused(NO_PORTAL)
    session = created["session_handle"]

    options = {
        "types": GLib.Variant("u", MONITOR),
        "multiple": GLib.Variant("b", True),
        "persist_mode": GLib.Variant("u", PERSIST_UNTIL_REVOKED),
    }
    if _cursor_modes(bus, PORTAL, PORTAL_PATH) & EMBEDDED_CURSOR:  # in the video, as x11grab has it
        options["cursor_mode"] = GLib.Variant("u", EMBEDDED_CURSOR)
    token = state.load().get("screencast")
    if token:
        options["restore_token"] = GLib.Variant("s", token)
    if portal_request(bus, SCREENCAST, "SelectSources", "(oa{sv})",
                      (session,), options) is None:
        raise Refused(NO_PORTAL)

    started = portal_request(bus, SCREENCAST, "Start", "(osa{sv})",
                             (session, ""), {}, seconds=CHOOSING_SECONDS)
    if not started:
        raise Refused(NOT_SHARED)
    state.remember(screencast=started.get("restore_token"))
    chosen = stream_for(area, scale, started.get("streams", []))
    if chosen is None:
        state.remember(screencast=None)  # so the next one asks again
        raise Refused(WRONG_SCREEN)

    try:
        reply, fds = bus.call_with_unix_fd_list_sync(
            PORTAL, PORTAL_PATH, SCREENCAST, "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (session, {})), GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE, 10000, None, None,
        )
        fd = fds.get(reply.unpack()[0])
    except GLib.Error:
        raise Refused(NO_PORTAL) from None
    return (fd,) + chosen


def _cursor_modes(bus, portal, portal_path):
    try:
        return bus.call_sync(
            portal, portal_path, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (SCREENCAST, "AvailableCursorModes")),
            GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 5000, None,
        ).unpack()[0]
    except GLib.Error:
        return 0


def stream_for(area, scale, streams):
    """The shared monitor holding the middle of `area`: (node, Rect), or None.

    The portal places each stream in logical pixels on the same layout the
    overlay was drawn over; `area` is in physical ones, so the stream is
    scaled to meet it.
    """
    middle = (area.x + area.width / 2, area.y + area.height / 2)
    for node, properties in streams:
        x, y = properties.get("position", (0, 0))
        width, height = properties.get("size", (0, 0))
        where = Rect(x, y, width, height).scaled(scale)
        if where.contains(*middle):
            return node, where
    return None


def start(area, options, scale=1.0, wayland=False):
    """Hand `area` to a detached agent, and say where it is being written.

    Returns an exit code. `area` is in physical pixels, `scale` the factor
    from logical ones, which the agent needs to place its bar beside it.
    `options.mic` is the source to hear, or None. A GIF has nowhere to put
    sound, so no source is asked of one.

    Under Wayland the agent runs its window through XWayland: a Wayland
    window cannot choose where it goes, and the bar has to go beside the
    area, not in it. Without XWayland there is no bar.
    """
    path = destination(options)
    payload = json.dumps({
        "path": path,
        "area": [area.x, area.y, area.width, area.height],
        "scale": scale,
        "mic": None if options.gif else options.mic,
        "wayland": wayland,
    })
    environment = dict(os.environ, GDK_BACKEND="x11") if wayland else None
    if not spawn_detached(["--record-agent", payload], environment):
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


BAR_GAP = 8  # logical pixels between the recorded area and the bar


def bar_position(region, monitors, size, gap=BAR_GAP):
    """Where a bar of `size` can sit on screen without being in `region`.

    x11grab records whatever is on screen there, and X11 has no way to leave
    a window out of a grab, so the only way to keep the bar out of the video
    is to keep it out of the area. Below first, where a toolbar is expected,
    then above, right and left, each slid along its edge to stay on the
    monitor. The area's own monitor is tried first, so the bar is not sent
    to the far side of another one while there is room next to the area.
    None when the area leaves no room on any of them.
    """
    width, height = size
    centre_x = region.x + (region.width - width) / 2
    centre_y = region.y + (region.height - height) / 2
    sides = (
        (centre_x, region.bottom + gap, True),
        (centre_x, region.y - gap - height, True),
        (region.right + gap, centre_y, False),
        (region.x - gap - width, centre_y, False),
    )
    middle = (region.x + region.width / 2, region.y + region.height / 2)
    nearest = sorted(monitors, key=lambda monitor: not monitor.contains(*middle))
    for monitor in nearest:
        for side_x, side_y, along_x in sides:
            x, y = side_x, side_y
            if along_x:
                x = min(max(x, monitor.x), monitor.right - width)
            else:
                y = min(max(y, monitor.y), monitor.bottom - height)
            if (monitor.x <= x and x + width <= monitor.right
                    and monitor.y <= y and y + height <= monitor.bottom):
                return int(x), int(y)
    return None


class StopBar:
    """A dot, how long it has been going, and Stop, just outside the area.

    A popup window, so no window manager decorates it, moves it or puts it
    in the task list, and it never takes focus from what is being recorded.
    Gtk is imported here rather than at the top: this module is also what a
    second --record loads to stop the first, and that needs no display.
    """

    def __init__(self, region, on_stop):
        from gi.repository import Gdk, Gtk

        from .capture import monitor_rects

        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.clock = Gtk.Label(label="0:00")
        stop = Gtk.Button(label="Stop")
        stop.connect("clicked", lambda *_: on_stop())
        dot = Gtk.Label()
        dot.set_markup('<span foreground="#e83d3d">\u25cf</span>')
        row = Gtk.Box(spacing=8, margin=6)
        for widget in (dot, self.clock, stop):
            row.pack_start(widget, False, False, 0)
        self.window.add(row)
        row.show_all()

        natural = self.window.get_preferred_size()[1]
        self.position = bar_position(
            region, monitor_rects(Gdk.Display.get_default()),
            (natural.width, natural.height),
        )
        if self.position is not None:
            self.window.move(*self.position)
            self.window.show()

    def tick(self, seconds):
        self.clock.set_text("%d:%02d" % divmod(int(seconds), 60))

    def close(self):
        self.window.destroy()


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

    area = _Area(*spec["area"])
    scale = spec.get("scale") or 1.0
    line, kept, missing = command(recorded, area, spec.get("mic")), (), MISSING
    if spec.get("wayland"):
        try:
            fd, node, stream = screencast(area, scale)
        except Refused as refusal:
            notifications.show_simple("Recording failed", str(refusal))
            with contextlib.suppress(OSError):
                os.unlink(recorded)
            return 1
        line = screencast_command(recorded, area, fd, node, stream,
                                  spec.get("mic"))
        kept, missing = (fd,), NO_GSTREAMER
    errors = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(
            line,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=errors,
            pass_fds=kept,
        )
    except OSError:
        notifications.show_simple("Recording failed", missing)
        return 1

    state.remember(recording=process.pid)
    loop = GLib.MainLoop()
    notification = notifications.recording_started(stop_running)
    dot = indicator(stop_running)
    try:
        bar = StopBar(
            Rect(area.x, area.y, area.width, area.height).scaled(1 / scale),
            stop_running)
    except RuntimeError:  # no X display for it: Wayland without XWayland
        bar = None
    started = GLib.get_monotonic_time()

    def poll():
        """A poll rather than a child watch, which would reap the process out
        from under Popen. A second's lag on a recording somebody just stopped
        is not something anybody can see."""
        if process.poll() is not None:
            loop.quit()
            return False
        if bar is not None:
            bar.tick((GLib.get_monotonic_time() - started) / 1e6)
        return True

    GLib.timeout_add(POLL_MS, poll)
    loop.run()
    if bar is not None:
        bar.close()
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
