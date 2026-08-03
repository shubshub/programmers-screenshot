#!/usr/bin/env python3
"""What the tool leaves on disk, and who can read it.

A screenshot of a programmer's screen is one of the more sensitive files a
desktop tool produces. Two things have to hold: nothing captured is left lying
around, and what is written is readable only by the person who took it.

    python3 tests/test_disk_hygiene.py
"""

import os
import shutil
import stat
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "src"))

import gi  # noqa: E402

gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf, GLib  # noqa: E402

from programmers_screenshot import capture, output  # noqa: E402


class Checker:
    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n%s" % title)

    def __call__(self, name, condition, detail=""):
        print("%s %s%s" % ("  ok  " if condition else " FAIL ", name,
                           ("  [%s]" % detail) if detail else ""))
        if not condition:
            self.failures.append(name)

    def report(self):
        print("\n%d failure(s)" % len(self.failures))
        return 1 if self.failures else 0


def a_pixbuf():
    return GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 4, 4)


def write_png(path):
    a_pixbuf().savev(path, "png", [], [])


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)


# --------------------------------------------------------------------------
# a stand-in for org.gnome.Shell.Screenshot
#
# The real one is only reachable on a Wayland session, so the path that cleans
# up after it has no other way of being exercised.
# --------------------------------------------------------------------------


class FakeReply:
    def __init__(self, value):
        self._value = value

    def unpack(self):
        return self._value


class FakeShell:
    """Answers the Screenshot call, optionally writing somewhere else.

    `redirect` is the whole point: GNOME Shell reports back the path it
    actually used, which is not always the one it was handed.
    """

    def __init__(self, redirect=None, succeeded=True, explode=False):
        self.redirect = redirect
        self.succeeded = succeeded
        self.explode = explode
        self.requested = None
        self.written_to = None

    def call_sync(self, _method, parameters, *_rest):
        if self.explode:
            raise GLib.Error("the shell is not answering")
        _cursor, _flash, requested = parameters.unpack()
        self.requested = requested
        self.written_to = self.redirect or requested
        write_png(self.written_to)
        return FakeReply((self.succeeded, self.written_to))


class StubGio:
    """Just the handful of Gio names the capture path touches."""

    shell = None

    class BusType:
        SESSION = 0

    class DBusProxyFlags:
        NONE = 0

    class DBusCallFlags:
        NONE = 0

    class DBusProxy:
        @staticmethod
        def new_for_bus_sync(*_args, **_kwargs):
            return StubGio.shell


def grab_with(shell):
    """Run the Wayland capture against a fake shell."""
    real = capture.Gio
    StubGio.shell = shell
    capture.Gio = StubGio
    try:
        return capture._grab_from_gnome_shell()
    finally:
        capture.Gio = real
        StubGio.shell = None


def main():
    check = Checker()
    workspace = tempfile.mkdtemp(prefix="programmers-screenshot-hygiene-")
    previous_umask = os.umask(0o022)  # the Ubuntu default, not this box's

    try:
        # ------------------------------------------------------------------
        check.section("a saved screenshot is readable only by its owner")

        for label, kwargs in (
            ("default naming", {"directory": os.path.join(workspace, "shots")}),
            ("an explicit -o", {"output": os.path.join(workspace, "named.png")}),
        ):
            path = output.save(a_pixbuf(), **kwargs)
            mode = mode_of(path)
            check("%s: mode is 0600" % label, mode == 0o600, oct(mode))
            check("%s: no group or world bits" % label,
                  not mode & (stat.S_IRWXG | stat.S_IRWXO), oct(mode))

        # Prove the umask really is permissive, so 0600 above can only have
        # come from an explicit chmod and not from inheriting a tight one.
        witness = os.path.join(workspace, "witness")
        os.close(os.open(witness, os.O_CREAT | os.O_WRONLY, 0o666))
        check("an ordinary file here would be 0644",
              mode_of(witness) == 0o644, oct(mode_of(witness)))

        # ------------------------------------------------------------------
        check.section("the Wayland capture cleans up after the shell")

        shell = FakeShell()
        pixbuf = grab_with(shell)
        check("it returns an image", pixbuf is not None)
        check("the requested file is gone", not os.path.exists(shell.requested),
              shell.requested)

        # The regression: the shell wrote somewhere else, and that copy is the
        # raw screen — it would outlive any redaction drawn on what we keep.
        elsewhere = os.path.join(workspace, "shell-chose-this.png")
        shell = FakeShell(redirect=elsewhere)
        pixbuf = grab_with(shell)
        check("redirected: it still returns an image", pixbuf is not None)
        check("redirected: the requested file is gone",
              not os.path.exists(shell.requested), shell.requested)
        check("redirected: and so is the one actually written",
              not os.path.exists(elsewhere), elsewhere)

        # A failed screenshot can still have left a file behind.
        elsewhere = os.path.join(workspace, "failed-but-written.png")
        shell = FakeShell(redirect=elsewhere, succeeded=False)
        pixbuf = grab_with(shell)
        check("failed: no image comes back", pixbuf is None)
        check("failed: nothing is left behind", not os.path.exists(elsewhere),
              elsewhere)

        # ------------------------------------------------------------------
        check.section("a shell that does not answer is survivable")

        shell = FakeShell(explode=True)
        try:
            pixbuf = grab_with(shell)
            raised = None
        except Exception as error:  # noqa: BLE001 - reporting whatever escapes
            pixbuf, raised = None, error
        check("no exception escapes", raised is None, raised)
        check("no image comes back", pixbuf is None)

        # ------------------------------------------------------------------
        check.section("no stray captures in the temp directory")

        leftovers = [
            name for name in os.listdir(tempfile.gettempdir())
            if name.startswith("programmers-screenshot-")
            and name.endswith(".png")
        ]
        check("none of ours remain", not leftovers, leftovers)
    finally:
        os.umask(previous_umask)
        shutil.rmtree(workspace, ignore_errors=True)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
