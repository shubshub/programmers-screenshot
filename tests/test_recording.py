#!/usr/bin/env python3
"""Recording a region: what ffmpeg is told, and how the second press stops it.

The recording itself cannot be checked here -- it needs a real X display and a
real ffmpeg, and it is a manual check -- but everything around it can: the
command line, where the file lands, and the one piece of state that makes the
same hotkey a toggle. That last one is exercised against a real process, so
the signal really is sent to a real pid.

    python3 tests/test_recording.py
"""

import os
import stat
import subprocess
import sys
import tempfile
import types

from checker import Checker  # noqa: E402

from gi.repository import GLib  # noqa: E402

from programmers_screenshot import cli, preferences, recording, state  # noqa: E402
from programmers_screenshot.geometry import Rect  # noqa: E402

CONFIG = tempfile.mkdtemp(prefix="programmers-screenshot-recording-")
state.path = lambda: os.path.join(CONFIG, "state.json")
preferences.path = lambda: os.path.join(CONFIG, "preferences.json")


def options(**overrides):
    """The handful of fields the recorder reads off the parsed command line."""
    values = {"directory": None, "output": None, "gif": False, "mic": False}
    values.update(overrides)
    return types.SimpleNamespace(**values)


def rect(x, y, width, height):
    return types.SimpleNamespace(x=x, y=y, width=width, height=height)


def flag(argv, name):
    """The value of one flag, as the real parser sees it."""
    return getattr(cli.build_parser().parse_args(argv), name)


class FakeInvocation:
    """Stands in for the D-Bus call the desktop is waiting on an answer to."""

    def __init__(self):
        self.answered = None

    def return_value(self, value):
        self.answered = value


def ask(dot, method, parameters=None):
    """Put a method call to the indicator the way the bus would, and read
    back what it answered."""
    invocation = FakeInvocation()
    dot._called(None, None, None, None, method, parameters, invocation)
    return invocation.answered


class FakeDisplay:
    """Stands in for a GdkDisplay; only its class name is ever read."""


class X11Display(FakeDisplay):
    pass


def main():
    check = Checker()
    workspace = tempfile.mkdtemp(prefix="programmers-screenshot-recording-")

    # ----------------------------------------------------------------------
    check.section("the area handed to ffmpeg")

    screen = rect(0, 0, 1920, 1080)
    area = recording.area_of(rect(10, 20, 300, 200), screen, 1.0)
    check("x and y are the region's", (area.x, area.y) == (10, 20), (area.x, area.y))
    check("so are the width and height",
          (area.width, area.height) == (300, 200), (area.width, area.height))

    # The overlay's origin is the corner of the virtual screen, which is not
    # the root window's corner when a monitor sits left of the primary one.
    offset = recording.area_of(rect(10, 20, 300, 200), rect(-1920, 0, 3840, 1080), 1.0)
    check("a screen starting left of zero is added in",
          (offset.x, offset.y) == (-1910, 20), (offset.x, offset.y))

    # HiDPI: the region is in logical pixels, x11grab addresses physical ones.
    scaled = recording.area_of(rect(10, 20, 300, 200), screen, 2.0)
    check("the display scale multiplies the offset",
          (scaled.x, scaled.y) == (20, 40), (scaled.x, scaled.y))
    check("and the size", (scaled.width, scaled.height) == (600, 400),
          (scaled.width, scaled.height))

    # yuv420p has one chroma sample per two pixels each way, so ffmpeg refuses
    # an odd width outright -- which would fail only when somebody dragged one.
    odd = recording.area_of(rect(0, 0, 101, 51), screen, 1.0)
    check("an odd width is rounded down to even", odd.width == 100, odd.width)
    check("and an odd height too", odd.height == 50, odd.height)
    tiny = recording.area_of(rect(0, 0, 1, 1), screen, 1.0)
    check("a one-pixel region still asks for something encodable",
          (tiny.width, tiny.height) == (2, 2), (tiny.width, tiny.height))

    # ----------------------------------------------------------------------
    check.section("the ffmpeg command line")

    os.environ["DISPLAY"] = ":9"
    line = recording.command("/tmp/out.webm", recording.area_of(
        rect(10, 20, 300, 200), screen, 1.0))
    pairs = dict(zip(line, line[1:]))
    check("it grabs from X11", pairs.get("-f") == "x11grab", pairs.get("-f"))
    check("the size is the region's", pairs.get("-video_size") == "300x200",
          pairs.get("-video_size"))
    check("the input names the display and the corner",
          pairs.get("-i") == ":9+10,20", pairs.get("-i"))
    check("the frame rate is set", pairs.get("-framerate") == "25",
          pairs.get("-framerate"))
    check("it encodes to VP9", pairs.get("-c:v") == "libvpx-vp9", pairs.get("-c:v"))
    check("in realtime, or it would drop most of the frames",
          pairs.get("-deadline") == "realtime", pairs.get("-deadline"))
    check("stdin is not read, so it cannot eat a terminal's keys",
          "-nostdin" in line)
    check("the file it writes is the last word", line[-1] == "/tmp/out.webm",
          line[-1])
    check("without --mic there is no sound", "pulse" not in line, line)

    heard = recording.command("/tmp/out.webm", recording.area_of(
        rect(10, 20, 300, 200), screen, 1.0), mic="alsa_input.usb-mic")
    inputs = [heard[i + 1] for i, word in enumerate(heard) if word == "-i"]
    check("a microphone is a second input, through pulse, by its name",
          inputs == [":9+10,20", "alsa_input.usb-mic"] and "pulse" in heard,
          inputs)
    check("the sound is Opus, which WebM carries",
          dict(zip(heard, heard[1:])).get("-c:a") == "libopus")
    check("and the file is still the last word", heard[-1] == "/tmp/out.webm")

    # ----------------------------------------------------------------------
    check.section("under Wayland: which shared monitor, and the GStreamer line")

    # The monitors on the machine this was written on: the 1920x1200 sits to
    # the right of the 3440x1440, 240 pixels down, as the portal reported it.
    streams = [
        (83, {"position": (3440, 240), "size": (1920, 1200)}),
        (84, {"position": (0, 0), "size": (3440, 1440)}),
    ]
    on_right = recording.area_of(rect(3540, 290, 400, 300), screen, 1.0)
    chosen = recording.stream_for(on_right, 1.0, streams)
    check("the stream holding the area is the one recorded",
          chosen and chosen[0] == 83, chosen)
    on_left = recording.area_of(rect(100, 100, 400, 300), screen, 1.0)
    check("and the other monitor's area picks the other stream",
          recording.stream_for(on_left, 1.0, streams)[0] == 84)
    check("an area on no shared monitor gets nothing, so it can ask again",
          recording.stream_for(on_left, 1.0, streams[:1]) is None)
    doubled = recording.area_of(rect(3540, 290, 400, 300), screen, 2.0)
    check("at scale 2 the stream is met in physical pixels",
          recording.stream_for(doubled, 2.0, streams)[1] == Rect(6880, 480, 3840, 2400),
          recording.stream_for(doubled, 2.0, streams))

    node, where = chosen
    gst = recording.screencast_command("/tmp/a b.webm", on_right, 7, node, where)
    words = dict(word.split("=", 1) for word in gst if "=" in word and "," not in word)
    check("it is gst-launch, stopping cleanly on SIGINT", gst[:3] == ["gst-launch-1.0", "-q", "-e"],
          gst[:3])
    check("from the portal's PipeWire connection",
          (words.get("fd"), words.get("path")) == ("7", "83"), words)
    check("cropped to the area, relative to its monitor",
          [words.get(k) for k in ("left", "top", "right", "bottom")]
          == ["100", "50", "1420", "850"], words)
    check("a path with a space stays one word",
          "location=/tmp/a b.webm" in gst, gst)
    check("without --mic there is no sound", "pulsesrc" not in gst)
    named = recording.screencast_command("/tmp/o.webm", on_right, 7, node, where,
                                         mic="alsa_input.usb-mic")
    check("a microphone is a pulse source, by its name, as Opus",
          "device=alsa_input.usb-mic" in named and "opusenc" in named, named)
    either = recording.screencast_command("/tmp/o.webm", on_right, 7, node, where,
                                          mic="default")
    check("and --mic with none picked leaves the choice to the desktop",
          "pulsesrc" in either and not any(w.startswith("device=") for w in either))

    # ----------------------------------------------------------------------
    check.section("the microphones offered on the toolbar")

    # The two on the machine this was written on: one sound card, so the
    # descriptions differ only in the middle.
    captions = recording._captions([
        "Family 17h/19h HD Audio Controller Headphones Stereo Microphone",
        "Family 17h/19h HD Audio Controller Digital Microphone",
    ])
    check("what they share is dropped, front and back",
          captions == ["Headphones Stereo", "Digital"], captions)
    check("one on its own keeps its whole name",
          recording._captions(["USB Microphone"]) == ["USB Microphone"])
    check("identical names are left whole rather than emptied",
          recording._captions(["Mic", "Mic"]) == ["Mic", "Mic"])
    long = recording._captions(["A microphone with a very long name indeed"])[0]
    check("a long one is cut to fit the toolbar",
          len(long) <= recording.CAPTION_LENGTH and long.endswith("\u2026"), long)

    listed = """[
      {"name": "alsa_output.speakers.monitor", "description": "Monitor of Speakers",
       "properties": {"device.class": "monitor"}},
      {"name": "alsa_input.usb-mic", "description": "Blue Yeti",
       "properties": {"device.class": "sound"}}
    ]"""
    real_run = subprocess.run
    try:
        subprocess.run = lambda *_a, **_k: types.SimpleNamespace(stdout=listed)
        check("the speakers' monitor is not offered as a microphone",
              recording.microphones() == (("alsa_input.usb-mic", "Blue Yeti"),),
              recording.microphones())
        subprocess.run = lambda *_a, **_k: types.SimpleNamespace(stdout="")
        check("nothing said means nothing offered", recording.microphones() == ())

        def missing(*_args, **_kwargs):
            raise FileNotFoundError("pactl")

        subprocess.run = missing
        check("and so does no pactl", recording.microphones() == ())
    finally:
        subprocess.run = real_run

    def heard(argv, stored):
        preferences.save(dict(preferences.DEFAULTS, mic=stored))
        return cli.with_preferences(cli.build_parser().parse_args(argv)).mic

    check("the one picked on the toolbar is the one heard",
          heard(["--record"], "alsa_input.usb-mic") == "alsa_input.usb-mic")
    check("None picked is silence", heard(["--record"], None) is None)
    check("--mic with none picked is the desktop's default",
          heard(["--record", "--mic"], None) == "default")
    check("but --mic does not override which one was picked",
          heard(["--record", "--mic"], "alsa_input.usb-mic") == "alsa_input.usb-mic")

    # ----------------------------------------------------------------------
    check.section("the Stop bar stays out of the recorded area")
    # x11grab records every pixel in the area, the bar's too if it were there.

    single = [Rect(0, 0, 1920, 1080)]
    bar = (200, 40)
    gap = recording.BAR_GAP
    where = recording.bar_position(Rect(100, 100, 400, 300), single, bar)
    check("below the area, centred on it",
          where == (200, 400 + gap), where)

    where = recording.bar_position(Rect(0, 900, 300, 170), single, bar)
    check("above it when there is no room below",
          where == (50, 900 - gap - 40), where)
    check("slid along the edge rather than off the screen", where[0] >= 0, where)

    where = recording.bar_position(Rect(0, 0, 1000, 1080), single, bar)
    check("beside it when it is the full height",
          where == (1000 + gap, 520), where)

    where = recording.bar_position(Rect(0, 0, 1920, 1080), single, bar)
    check("nowhere when it fills the only monitor", where is None, where)

    pair = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)]
    where = recording.bar_position(Rect(0, 0, 1920, 1080), pair, bar)
    check("on the other monitor when it fills one",
          where is not None and where[0] >= 1920, where)

    # The machine this was found on: a second monitor listed first, and the
    # bar clamped onto it, three thousand pixels from the area it belonged to.
    pair = [Rect(3440, 240, 1920, 1200), Rect(0, 0, 3440, 1440)]
    where = recording.bar_position(Rect(100, 100, 400, 300), pair, bar)
    check("next to the area when its own monitor has room, whatever the order",
          where == (200, 400 + gap), where)

    stopped = []
    shown = recording.StopBar(Rect(100, 100, 400, 300), lambda: stopped.append(1))
    buttons = [child for child in shown.window.get_child().get_children()
               if child.get_label() == "Stop"]
    check("the bar has a Stop button", len(buttons) == 1, buttons)
    buttons[0].clicked()
    check("and pressing it stops the recording", stopped == [1], stopped)
    shown.tick(75)
    check("the clock reads minutes and seconds",
          shown.clock.get_text() == "1:15", shown.clock.get_text())
    shown.close()

    # ----------------------------------------------------------------------
    check.section("where the recording lands")

    path = recording.destination(options(directory=workspace))
    check("in the chosen folder", os.path.dirname(path) == workspace, path)
    check("named for when it was taken",
          os.path.basename(path).startswith("Recording_"), path)
    check("a WebM by default", path.endswith(".webm"), path)
    check("the folder is made ready for it", os.path.isdir(workspace))

    check("--gif asks for a GIF instead",
          recording.destination(options(directory=workspace, gif=True))
          .endswith(".gif"))

    named = os.path.join(workspace, "chosen.webm")
    check("-o wins over the timestamp",
          recording.destination(options(directory=workspace, output=named)) == named)

    # ----------------------------------------------------------------------
    check.section("the file is private from the first frame")
    # ffmpeg opens the name and truncates it, so a file it creates itself
    # would sit at the umask's mode for the whole recording -- and what is
    # going into it is a video of somebody's screen.

    previous_umask = os.umask(0o022)
    try:
        fresh = os.path.join(workspace, "fresh.webm")
        recording._create_privately(fresh)
        mode = stat.S_IMODE(os.stat(fresh).st_mode)
        check("a new file is 0600", mode == 0o600, oct(mode))

        loose = os.path.join(workspace, "loose.webm")
        os.close(os.open(loose, os.O_CREAT | os.O_WRONLY, 0o666))
        recording._create_privately(loose)
        mode = stat.S_IMODE(os.stat(loose).st_mode)
        check("and one already there is tightened", mode == 0o600, oct(mode))
    finally:
        os.umask(previous_umask)

    # ----------------------------------------------------------------------
    check.section("what cannot record says so")

    real_program = recording.PROGRAM
    try:
        recording.PROGRAM = "no-such-program-anywhere"
        refusal = recording.unavailable(X11Display())
        check("without ffmpeg it names the package",
              refusal and "apt install ffmpeg" in refusal, refusal)

        recording.PROGRAM = "sleep"  # something that is certainly installed
        check("with it, an X11 session can record",
              recording.unavailable(X11Display()) is None)
        real_gst = recording.GST
        try:
            recording.GST = "no-such-program-anywhere"
            refusal = recording.unavailable(FakeDisplay())
            check("under Wayland without GStreamer it names the packages",
                  refusal and "gstreamer1.0-pipewire" in refusal, refusal)
        finally:
            recording.GST = real_gst

        # ------------------------------------------------------------------
        check.section("the second press stops the first recording")

        check("nothing running, nothing to stop", recording.stop_running() is False)

        # A real process, so the pid, the signal and /proc are all real. It
        # stands in for ffmpeg by name, which is what running() checks.
        process = subprocess.Popen(["sleep", "30"])
        state.remember(recording=process.pid)
        check("a live recording is found", recording.running() == process.pid,
              recording.running())

        check("stopping reports that there was one", recording.stop_running() is True)
        process.wait(timeout=5)
        check("and the process is gone", process.poll() is not None, process.poll())
        check("nothing is left running", recording.running() is None)

        # The regression this guards: a pid on its own is a number the kernel
        # is free to hand to somebody else, so a stale entry left by a killed
        # agent could aim a signal at whatever inherited it.
        other = subprocess.Popen(["sleep", "30"])
        state.remember(recording=other.pid)
        recording.PROGRAM = "ffmpeg"
        check("a pid that is not our recorder is ignored",
              recording.running() is None, recording.running())
        check("so nothing is signalled", recording.stop_running() is False)
        check("and that process is untouched", other.poll() is None)
        other.kill()
        other.wait(timeout=5)

        # ------------------------------------------------------------------
        check.section("--record is the same key, going the other way")

        recording.PROGRAM = "sleep"
        process = subprocess.Popen(["sleep", "30"])
        state.remember(recording=process.pid)
        code = cli.main(["--record"])
        check("it exits cleanly", code == 0, code)
        process.wait(timeout=5)
        check("having stopped the recording", process.poll() is not None)
    finally:
        recording.PROGRAM = real_program

    # ----------------------------------------------------------------------
    check.section("the dot in the status area, and what it answers")
    # The one control a running recording has. It is answered straight off
    # the bus rather than through a library: the desktop asks these exact
    # questions, so they are what is checked, no session bus required.

    stopped = []
    dot = recording.Indicator(lambda: stopped.append("stop"))

    check("it names an icon the theme has",
          dot._property(None, None, None, "org.kde.StatusNotifierItem",
                        "IconName").unpack() == "media-record")
    check("it says what it is, for a desktop that shows the title",
          dot._property(None, None, None, "org.kde.StatusNotifierItem",
                        "Title").unpack() == "Recording")
    check("it points at its own menu",
          dot._property(None, None, None, "org.kde.StatusNotifierItem",
                        "Menu").unpack() == recording.MENU_PATH)
    check("an interface it does not serve has nothing to say",
          dot._property(None, None, None, "org.example.Nonsense", "Id") is None)

    revision, layout = ask(dot, "GetLayout").unpack()
    entries = [(child[1].get("label"), child[1].get("enabled"))
               for child in layout[2]]
    check("the menu offers exactly one thing: stopping",
          entries == [("Stop recording", True)], entries)
    check("and it has a revision, which never moves", revision == 1, revision)

    check("nothing has been stopped yet", stopped == [], stopped)
    ask(dot, "Event", GLib.Variant("(isvu)", (recording.STOP_ID, "hovered",
                                              GLib.Variant("i", 0), 0)))
    check("hovering over it does nothing", stopped == [], stopped)

    ask(dot, "Event", GLib.Variant("(isvu)", (recording.STOP_ID, "clicked",
                                              GLib.Variant("i", 0), 0)))
    check("clicking it stops the recording", stopped == ["stop"], stopped)

    # A desktop that reads a click as Activate rather than opening the menu --
    # a middle click on GNOME, a single click elsewhere -- gets the same thing.
    ask(dot, "Activate", GLib.Variant("(ii)", (0, 0)))
    check("so does activating it directly", stopped == ["stop", "stop"], stopped)

    check("there is nothing to rebuild before it opens",
          ask(dot, "AboutToShow", GLib.Variant("(i)", (0,))).unpack() == (False,))

    # ----------------------------------------------------------------------
    check.section("the flags are on the parser")

    check("--record", flag(["--record"], "record") is True)
    check("--gif", flag(["--record", "--gif"], "gif") is True)
    check("--mic", flag(["--record", "--mic"], "mic") is True)
    check("none is on by default",
          flag([], "record") is False and flag([], "mic") is False)
    check("the agent is internal but reachable",
          flag(["--record-agent", "{}"], "record_agent") == "{}")

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
