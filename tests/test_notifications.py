#!/usr/bin/env python3
"""Notification wiring: the agent handoff, its text, and the paths involved.

Nothing here pops up a notification or opens a window; the two action handlers
talk to the desktop and are left to manual testing.

    python3 tests/test_notifications.py
"""

import os
import subprocess
import sys
import tempfile

import gi

gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "src"))

from programmers_screenshot import notifications, paths  # noqa: E402
from programmers_screenshot.cli import build_parser  # noqa: E402

LAUNCHER = os.path.join(ROOT, "bin", "programmers-screenshot")


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


def sample_png(directory):
    path = os.path.join(directory, "Screenshot_2026-01-02_03-04-05.png")
    GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 640, 480).savev(
        path, "png", [], []
    )
    return path


def main():
    check = Checker()
    workspace = tempfile.mkdtemp(prefix="programmers-screenshot-test-")
    image = sample_png(workspace)

    check.section("the notification body describes the file on disk")
    body = notifications.describe(image)
    first, second = body.split("\n")
    check("filename leads", first == os.path.basename(image), first)
    check("real dimensions", "640 × 480" in second, second)
    check("folder included", workspace in second, second)

    check.section("the body survives an unreadable file")
    missing = os.path.join(workspace, "gone.png")
    body = notifications.describe(missing)
    check("still names the file", body.startswith("gone.png"), body.replace("\n", " | "))

    check.section("--notification-agent is parsed but hidden")
    options = build_parser().parse_args(["--notification-agent", image])
    check("routes to the agent", options.notification_agent == image)
    help_text = build_parser().format_help()
    check("stays out of --help", "--notification-agent" not in help_text)

    check.section("helper processes re-invoke this code, not PATH")
    # Regression: resolving through PATH spawned a different installed build
    # that did not understand --notification-agent.
    check(
        "running_program is this program",
        os.path.abspath(sys.argv[0]) == paths.running_program(),
        paths.running_program(),
    )
    check(
        "installed_command may differ",
        isinstance(paths.installed_command(), str),
        paths.installed_command(),
    )

    check.section("the launcher accepts the agent flag")
    # The bug was only visible end to end: the flag has to survive the launcher.
    result = subprocess.run(
        [LAUNCHER, "--notification-agent"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    check(
        "flag is recognised",
        "unrecognized arguments" not in result.stderr,
        result.stderr.strip().splitlines()[-1] if result.stderr else "",
    )
    check(
        "missing value is an argument error",
        "expected one argument" in result.stderr,
        result.stderr.strip().splitlines()[-1] if result.stderr else "",
    )

    os.unlink(image)
    os.rmdir(workspace)

    print("\n%d failure(s)" % len(check.failures))
    return 1 if check.failures else 0


if __name__ == "__main__":
    sys.exit(main())
