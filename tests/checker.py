"""The tally every suite prints, and the one path insert they all need.

Import this before anything from `programmers_screenshot`: it puts `src/` on
`sys.path`, so a suite run straight from a checkout finds the package. The
tests directory itself is already `sys.path[0]` when a suite is run as
`python3 tests/test_x.py`, so `src/` is the only path anyone has to arrange,
and this is the single place that does it.

Nothing here imports GTK. The suites that never open a display -- hotkey,
skill, sound, updates and the rest -- import this instead of `support`, which
would drag in the overlay and a temporary config directory they do not want.
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
)


class Checker:
    """Prints a running tally and remembers what failed."""

    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n%s" % title)

    def __call__(self, name, condition, detail=""):
        # detail may be a tuple (a colour, a size); wrap it so % does not
        # treat it as an argument list.
        suffix = "  [%s]" % (detail,) if detail != "" and detail is not None else ""
        print("%s %s%s" % ("  ok  " if condition else " FAIL ", name, suffix))
        if not condition:
            self.failures.append(name)

    def report(self):
        print("\n%d failure(s)" % len(self.failures))
        return 1 if self.failures else 0
