#!/usr/bin/env python3
"""Knowing about versions, and mostly keeping quiet about it.

No real network call happens here. The fetch is injected, so the suite tests
what the program does with an answer rather than whether GitHub is up.

    python3 tests/test_updates.py
"""

import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk  # noqa: E402

from programmers_screenshot import alerts, state, updates  # noqa: E402

CHANGELOG = """\
programmers-screenshot (0.21.0) noble; urgency=medium

  * Related tools now share a button. Pen and Highlighter sit together
    under Ink.
  * The redaction tool is now called Black Bar.

 -- Shubshub  Tue, 04 Aug 2026 16:05:00 +1200

programmers-screenshot (0.20.0) noble; urgency=medium

  * A floating palette you can drag around.

 -- Shubshub  Tue, 04 Aug 2026 14:20:00 +1200
"""


class Checker:
    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n%s" % title)

    def __call__(self, name, condition, detail=""):
        suffix = "  [%s]" % (detail,) if detail != "" and detail is not None else ""
        print("%s %s%s" % ("  ok  " if condition else " FAIL ", name, suffix))
        if not condition:
            self.failures.append(name)

    def report(self):
        print("\n%d failure(s)" % len(self.failures))
        return 1 if self.failures else 0


def main():
    check = Checker()
    home = tempfile.mkdtemp(prefix="programmers-screenshot-updates-")
    real_path, real_show = state.path, alerts.show
    state.path = lambda: os.path.join(home, "state.json")

    said = []
    alerts.show = lambda *a: said.append(a)

    try:
        # --------------------------------------------------------------
        check.section("versions compare as numbers, not as text")
        check("0.10.0 is newer than 0.9.0", updates.is_newer("0.10.0", "0.9.0"))
        check("and the string comparison that would not be",
              not ("0.10.0" > "0.9.0"))
        check("a v prefix does not confuse it",
              updates.is_newer("v0.22.0", "0.21.0"))
        check("equal is not newer", not updates.is_newer("1.2.3", "1.2.3"))
        check("older is not newer", not updates.is_newer("1.2.3", "1.3.0"))
        check("nonsense is not newer", not updates.is_newer("banana", "1.0.0"))
        check("nor is a missing one", not updates.is_newer(None, "1.0.0"))

        # --------------------------------------------------------------
        check.section("it asks at most once a day")
        state.save({})
        check("with nothing known, ask", updates.due())
        state.remember(checked=time.time())
        check("having just asked, do not", not updates.due())
        state.remember(checked=time.time() - updates.CHECK_EVERY - 1)
        check("a day later, ask again", updates.due())

        # --------------------------------------------------------------
        check.section("it speaks only when there is something newer")
        state.save({})
        del said[:]
        updates.run_check("0.21.0", lambda: ("v0.22.0", "https://example/rel"))
        check("a newer release is announced", len(said) == 1, said)
        check("naming both versions",
              "0.22.0" in said[0][1] and "0.21.0" in said[0][1], said[0][1])
        check("as an alert window, not a desktop notification",
              said[0][0] == "Update available", said[0][0])
        check("with a button to the page", said[0][3] == "https://example/rel")
        check("and the check is timestamped",
              isinstance(state.load().get("checked"), float))

        del said[:]
        updates.run_check("0.21.0", lambda: ("v0.22.0", "https://example/rel"))
        check("the same version is not announced twice", not said, said)

        state.save({})
        del said[:]
        updates.run_check("0.21.0", lambda: ("v0.21.0", "u"))
        check("being up to date is silent", not said, said)

        state.save({})
        updates.run_check("0.21.0", lambda: ("v0.20.0", "u"))
        check("an older release is silent", not said, said)

        # --------------------------------------------------------------
        check.section("every failure is silent, and still counts as a check")
        state.save({})
        del said[:]
        updates.run_check("0.21.0", lambda: None)     # offline, 403, bad JSON
        check("nothing is said", not said, said)
        check("but it does not retry in a loop",
              isinstance(state.load().get("checked"), float))

        # --------------------------------------------------------------
        check.section("reading the shipped changelog")
        lines = updates.entry_for("0.21.0", CHANGELOG)
        check("it finds that version's bullets", len(lines) == 2, lines)
        check("wrapped lines are joined up",
              lines[0].endswith("under Ink."), lines[0])
        check("it stops at the next version",
              all("palette" not in l for l in lines), lines)
        check("an absent version gives nothing",
              updates.entry_for("9.9.9", CHANGELOG) == [])

        real_read = updates.read_changelog
        updates.read_changelog = lambda path=None: CHANGELOG
        try:
            check.section("what an upgrade brought")
            state.save({})
            check("a first install says nothing",
                  updates.upgrade_notice("0.21.0") is None)
            check("and asking does not itself record anything",
                  state.load().get("ran") is None,
                  "recording is announce_upgrade's job, not this one's")

            state.save({"ran": "0.20.0"})
            notice = updates.upgrade_notice("0.21.0")
            check("an upgrade is reported", notice is not None)
            check("naming the new version", "0.21.0" in notice[0], notice[0])
            check("and listing what changed", "Black Bar" in notice[1], notice[1])
            check("all of it, since a window can scroll",
                  notice[1].count("•") == 2, notice[1])

            state.save({"ran": "0.21.0"})
            check("the same version again is silent",
                  updates.upgrade_notice("0.21.0") is None)

            state.save({"ran": "0.22.0"})
            check("a downgrade is silent",
                  updates.upgrade_notice("0.21.0") is None)

            check.section("announcing it happens once")
            state.save({"ran": "0.20.0"})
            del said[:]
            check("it announces", updates.announce_upgrade("0.21.0"))
            check("saying what is new", said and "Updated to" in said[0][0], said)
            del said[:]
            check("and not a second time",
                  not updates.announce_upgrade("0.21.0"))
            check("with nothing said", not said, said)
        finally:
            updates.read_changelog = real_read

        check.section("a missing or broken changelog is not an error")
        updates.read_changelog = lambda path=None: ""
        state.save({"ran": "0.20.0"})
        check("no notice, no exception", updates.upgrade_notice("0.21.0") is None)
        updates.read_changelog = real_read

        check.section("the alert is a window, and it builds")
        if Gtk.init_check()[0]:
            window = alerts.build({
                "heading": "Update available", "body": "0.23.0 is out.",
                "label": "Release notes", "uri": "https://example/rel",
            })
            labels = [c.get_label()
                      for c in window.get_action_area().get_children()]
            check("it can be dismissed", "Close" in labels, labels)
            check("and offers the link", "Release notes" in labels, labels)
            window.destroy()

            # An entry with no link should not grow an empty button.
            plain = alerts.build({"heading": "Updated", "body": "• a thing",
                                  "label": None, "uri": None})
            labels = [c.get_label()
                      for c in plain.get_action_area().get_children()]
            check("with no link, only Close", labels == ["Close"], labels)
            plain.destroy()

            check("a malformed payload is refused, not crashed on",
                  alerts.run("{not json") == 1)
        else:
            check("a display is available to build the window", False)

        check.section("state that cannot be read means nothing is known")
        with open(state.path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        check("it reads as empty", state.load() == {}, state.load())
        check("so a check is due", updates.due())
    finally:
        state.path, alerts.show = real_path, real_show
        shutil.rmtree(home, ignore_errors=True)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
