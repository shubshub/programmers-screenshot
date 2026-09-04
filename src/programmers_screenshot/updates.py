"""Knowing about versions: what is newer out there, and what just changed here.

Two jobs that share their arithmetic and their silence.

**Is there a newer release?** Asks GitHub, at most once a day, only if turned
on, and never on the path that takes a screenshot. This is the only network
call the program makes.

**What did the upgrade bring?** Reads the changelog already shipped inside the
package. No network at all.

Both stay quiet unless there is genuinely something to say. Offline, rate
limited, malformed, missing file, first install, downgrade — all silence. A
screenshot tool that interrupts you to report that it could not check for
updates has made your day worse for nothing.
"""

import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request

from . import alerts, state
from .paths import PROGRAM

LATEST_URL = "https://api.github.com/repos/shubshub/programmers-screenshot/releases/latest"
RELEASES_URL = "https://github.com/shubshub/programmers-screenshot/releases"

CHECK_EVERY = 24 * 60 * 60   # seconds
TIMEOUT = 5                  # seconds; a screenshot tool does not wait about

# GitHub rejects requests without one.
USER_AGENT = "programmers-screenshot"

ENTRY = re.compile(r"^%s \(([^)]+)\)" % re.escape(PROGRAM))


# --------------------------------------------------------------------------
# comparing versions
# --------------------------------------------------------------------------


def parts(version):
    """A version as numbers, for comparing. Anything odd sorts as nothing.

    Numeric, not lexical: as strings "0.9.0" beats "0.10.0", which would have
    started lying the moment a 0.10 release existed.
    """
    cleaned = (version or "").strip().lstrip("v")
    pieces = cleaned.split(".")
    try:
        return tuple(int(piece) for piece in pieces)
    except ValueError:
        return ()


def is_newer(candidate, current):
    """True if `candidate` is a later version than `current`."""
    left, right = parts(candidate), parts(current)
    return bool(left) and bool(right) and left > right


# --------------------------------------------------------------------------
# is there a newer release
# --------------------------------------------------------------------------


def due(now=None, store=None):
    """Whether enough time has passed to ask again."""
    known = state.load() if store is None else store
    last = known.get("checked")
    if not isinstance(last, (int, float)):
        return True
    return (time.time() if now is None else now) - last >= CHECK_EVERY


def fetch(url=LATEST_URL):
    """The latest release, as (version, page url). None if we cannot tell.

    Every failure is None: no network, no DNS, a 403 for rate limiting, a
    body that is not the JSON we expected. There is nothing a user could do
    with any of them.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as reply:
            payload = json.loads(reply.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str):
        return None
    page = payload.get("html_url")
    return (tag, page if isinstance(page, str) else RELEASES_URL)


def run_check(current, fetcher=fetch):
    """The detached check. Returns True if it announced something.

    Runs in a process of its own, well after the capture is done, so nothing
    here can put a network timeout between a keypress and the overlay.
    """
    found = fetcher()
    state.remember(checked=time.time())
    if found is None:
        return False

    tag, page = found
    if not is_newer(tag, current):
        return False
    if state.load().get("announced") == tag:
        return False   # already said so; do not nag every day

    state.remember(announced=tag)
    alerts.show(
        "Update available",
        "%s %s is out.\nYou have %s.\n\nInstall it with apt, or download the "
        ".deb from the release page." % (PROGRAM, tag.lstrip("v"), current),
        "Release notes",
        page,
    )
    return True


# --------------------------------------------------------------------------
# what did this upgrade bring
# --------------------------------------------------------------------------


def changelog_path():
    """This copy's changelog, in a checkout or installed. None if absent.

    The checkout comes first. Looking in /usr/share first meant a checkout
    read the *installed* package's changelog -- a different version of a
    different build -- and found no entry for the version it was actually
    running. Same trap as resolving the program through PATH: code should
    describe itself, not whatever else is on the system.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(here, os.pardir, os.pardir, "packaging", "changelog"),
        os.path.join("/usr/share/doc", PROGRAM, "changelog.Debian.gz"),
    )
    for candidate in candidates:
        path = os.path.normpath(candidate)
        if os.path.isfile(path):
            return path
    return None


def read_changelog(path=None):
    """The changelog text, whether or not it arrived gzipped."""
    path = changelog_path() if path is None else path
    if path is None:
        return ""
    try:
        if path.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return handle.read()
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, ValueError, EOFError):
        return ""


def entry_for(version, text):
    """The bullet lines of one version's changelog entry."""
    wanted = parts(version)
    lines, collecting = [], False
    for line in text.splitlines():
        found = ENTRY.match(line)
        if found:
            if collecting:
                break
            collecting = parts(found.group(1)) == wanted
            continue
        if collecting and line.strip().startswith("*"):
            lines.append(line.strip().lstrip("* ").strip())
        elif collecting and line.startswith("    ") and lines:
            lines[-1] += " " + line.strip()   # a bullet wrapped onto more lines
    return lines


def upgrade_notice(current, bullets=None):
    """What to say about having been upgraded to `current`, or None.

    Silent on a first install -- a changelog for versions you never ran is
    noise, not a welcome -- and on a downgrade, where listing what you just
    lost helps nobody.
    """
    previous = state.load().get("ran")
    if previous is None or not is_newer(current, previous):
        return None
    lines = entry_for(current, read_changelog())
    if not lines:
        return None
    # All of them. A notification body had to be trimmed to fit; a window
    # scrolls, so there is no reason to hide half of what changed.
    shown = lines if bullets is None else lines[:bullets]
    return ("Updated to %s" % current, "\n\n".join("• " + line for line in shown))


def announce_upgrade(current):
    """Show the upgrade notice if there is one, and stop it happening twice."""
    notice = upgrade_notice(current)
    state.remember(ran=current)
    if notice is None:
        return False
    heading, body = notice
    alerts.show(heading, body, "Release notes", RELEASES_URL)
    return True
