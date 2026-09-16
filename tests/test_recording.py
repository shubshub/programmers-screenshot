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

from programmers_screenshot import cli, recording, state  # noqa: E402

CONFIG = tempfile.mkdtemp(prefix="programmers-screenshot-recording-")
state.path = lambda: os.path.join(CONFIG, "state.json")


def options(**overrides):
    """The handful of fields the recorder reads off the parsed command line."""
    values = {"directory": None, "output": None, "gif": False}
    values.update(overrides)
    return types.SimpleNamespace(**values)


def rect(x, y, width, height):
    return types.SimpleNamespace(x=x, y=y, width=width, height=height)


def flag(argv, name):
    """The value of one flag, as the real parser sees it."""
    return getattr(cli.build_parser().parse_args(argv), name)


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
        refusal = recording.unavailable(FakeDisplay())
        check("under Wayland it refuses rather than half-working",
              refusal and "X11" in refusal, refusal)

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
    check.section("the flags are on the parser")

    check("--record", flag(["--record"], "record") is True)
    check("--gif", flag(["--record", "--gif"], "gif") is True)
    check("neither is on by default", flag([], "record") is False)
    check("the agent is internal but reachable",
          flag(["--record-agent", "{}"], "record_agent") == "{}")

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
