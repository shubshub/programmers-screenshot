#!/usr/bin/env python3
"""Run every suite and say, in one line each, how it went.

    python3 tests/run.py

Each suite gets its own process. They replace module-level functions to stand
things in -- preferences.path, alerts.show, output.deliver -- and none of them
puts back what it took, so sharing an interpreter would let one suite decide
what the next one sees. A suite counts its own failures and prints them; this
only reads the last line of what it printed, repeats the output of anything
that went wrong, and exits non-zero if anything did.
"""

import glob
import os
import subprocess
import sys
import time

# Generous: the whole set takes about 12 seconds. This is here to stop a suite
# that has hung -- waiting on a dialog nobody will close -- from hanging the
# release with it.
TIMEOUT = 900


def run(path):
    """(passed, what to say about it, the output to show if it failed)."""
    try:
        finished = subprocess.run(
            [sys.executable, path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, "timed out after %d seconds" % TIMEOUT, ""
    lines = finished.stdout.strip().splitlines()
    tally = lines[-1] if lines else "said nothing"
    if finished.returncode != 0:
        return False, "%s (exit %d)" % (tally, finished.returncode), finished.stdout
    if tally != "0 failure(s)":
        return False, tally, finished.stdout
    return True, tally, ""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    suites = sorted(glob.glob(os.path.join(here, "test_*.py")))
    failures = []
    for path in suites:
        name = os.path.basename(path)
        started = time.time()
        passed, tally, output = run(path)
        print("%s %-28s %5.1fs  %s"
              % ("  ok  " if passed else " FAIL ", name, time.time() - started, tally))
        if not passed:
            failures.append(name)
            print("".join("        %s\n" % line for line in output.splitlines()))
    print("\n%d suites, %d failure(s)" % (len(suites), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
