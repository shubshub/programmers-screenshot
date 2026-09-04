#!/usr/bin/env python3
"""Stored preferences, and who wins when they disagree with a flag.

Clicking Close needs a person, so that part is not exercised. Everything
either side of it is: what gets written, what comes back, how it combines
with the command line, and that the folder chooser follows the toggle.

    python3 tests/test_preferences.py
"""

import json
import os
import shutil
import sys
import tempfile
import types

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402

from support import Checker, Harness  # noqa: E402

from programmers_screenshot import capture, cli, preferences  # noqa: E402


def options(**overrides):
    """The subset of the parsed command line that preferences touch."""
    parsed = cli.build_parser().parse_args([])
    for key, value in overrides.items():
        setattr(parsed, key, value)
    return parsed


def main():
    check = Checker()
    home = tempfile.mkdtemp(prefix="programmers-screenshot-prefs-")
    config = os.path.join(home, "preferences.json")
    real_path = preferences.path
    preferences.path = lambda: config

    try:
        check.section("with nothing stored, the defaults stand")
        check("no file yet", not os.path.exists(config))
        check("saving is on", preferences.load()["save"] is True)
        check("no folder chosen", preferences.load()["directory"] is None)

        check.section("what is written comes back")
        preferences.save({"save": False, "directory": "/tmp/shots"})
        loaded = preferences.load()
        check("the toggle round-trips", loaded["save"] is False, loaded)
        check("the folder round-trips", loaded["directory"] == "/tmp/shots", loaded)
        check("and it is on disk as json",
              json.load(open(config))["directory"] == "/tmp/shots")

        check.section("a damaged file does not take the program down")
        with open(config, "w", encoding="utf-8") as handle:
            handle.write("{not json at all")
        check("it falls back to the defaults",
              preferences.load() == preferences.DEFAULTS, preferences.load())
        with open(config, "w", encoding="utf-8") as handle:
            json.dump(["a", "list"], handle)
        check("as it does for the wrong shape",
              preferences.load() == preferences.DEFAULTS, preferences.load())

        check.section("unknown keys are dropped, known ones survive")
        preferences.save({"save": True, "directory": "/tmp/a", "wat": 1})
        loaded = preferences.load()
        check("the stray key is gone", "wat" not in loaded, loaded)
        check("the real ones are not", loaded["directory"] == "/tmp/a", loaded)

        # ------------------------------------------------------------------
        check.section("a stored folder fills in for a missing --directory")
        preferences.save({"save": True, "directory": "/tmp/stored"})
        parsed = cli.with_preferences(options())
        check("it is used", parsed.directory == "/tmp/stored", parsed.directory)

        check.section("but --directory beats it")
        parsed = cli.with_preferences(options(directory="/tmp/asked-for"))
        check("the flag wins", parsed.directory == "/tmp/asked-for", parsed.directory)

        check.section("saving switched off in the window")
        preferences.save({"save": False, "directory": "/tmp/stored"})
        parsed = cli.with_preferences(options())
        check("no_save is set", parsed.no_save is True)

        check.section("-o still writes a file, whatever is stored")
        # Naming an output file is a clearer instruction than a stored default.
        parsed = cli.with_preferences(options(output="/tmp/one-off.png"))
        check("no_save stays off", parsed.no_save is False, parsed.no_save)

        check.section("the preference never re-enables saving over --no-save")
        preferences.save({"save": True, "directory": None})
        parsed = cli.with_preferences(options(no_save=True))
        check("no_save survives", parsed.no_save is True)

        check.section("the folder chooser follows the toggle")
        if Gtk.init_check()[0]:
            dialog, toggle, chooser, floating, updates, scripted = (
                preferences.build(
                    {"save": True, "directory": home,
                     "toolbar": preferences.BAR, "updates": False}))
            check("enabled while saving is on", chooser.get_sensitive())
            toggle.set_active(False)
            check("greyed out when switched off", not chooser.get_sensitive())
            toggle.set_active(True)
            check("and back again", chooser.get_sensitive())
            check("it starts on the stored folder",
                  chooser.get_filename() == home, chooser.get_filename())
            check("and the floating toolbar is off by default",
                  not floating.get_active())
            check("as is the update check, which is the only network call",
                  not updates.get_active())
            check("and recipes, which let something else point this at a screen",
                  not scripted.get_active())
            dialog.destroy()
        else:
            check("no display, so the window was not built", False,
                  "cannot verify the dialog here")

        check.section("the overlay gets out of the way before the window opens")
        # The overlay is override-redirect on X11: it bypasses the window
        # manager and sits above everything, so a dialog opened over it maps
        # for a frame and is then buried, with the program stuck in the
        # dialog's event loop and no reachable way to close it. It also holds
        # a pointer and keyboard grab. Both have to be released first, and the
        # order matters -- releasing them after the dialog opens is too late.
        harness = Harness(*capture.capture_screen(Gdk.Display.get_default()))
        order = []

        harness.overlay.window = types.SimpleNamespace(
            queue_draw=lambda: None,
            queue_draw_area=lambda *a: None,
            hide=lambda: order.append("hide overlay"),
            show=lambda: order.append("show overlay"),
            get_display=lambda: types.SimpleNamespace(
                get_default_seat=lambda: types.SimpleNamespace(
                    ungrab=lambda: order.append("ungrab"))),
        )

        real_edit = preferences.edit
        preferences.edit = lambda: order.append("open window") or {}
        try:
            harness.overlay._edit_preferences()
        finally:
            preferences.edit = real_edit

        def before(first, second):
            """True only if both happened, in this order. A missing step is a
            failure to report, not an exception to crash on."""
            return (first in order and second in order
                    and order.index(first) < order.index(second))

        check("the grab is dropped", "ungrab" in order, order)
        check("the overlay hides at all", "hide overlay" in order, order)
        check("the overlay hides before the window opens",
              before("hide overlay", "open window"), order)
        check("the grab is dropped before the window opens",
              before("ungrab", "open window"), order)
        check("and the overlay comes back after",
              before("open window", "show overlay"), order)

        # Showing the window again fires map-event, which retakes the grab --
        # so nothing here should be trying to grab it a second time by hand.
        check("it does not re-grab by hand", order.count("ungrab") == 1, order)

        check.section("a change made in the window affects the capture in hand")
        # The bug: preferences were read once at startup, so switching saving
        # off in the settings window did nothing until the *next* screenshot --
        # the one you were holding still got written to disk.
        preferences.save({"save": True, "directory": None})
        before = cli.with_preferences(options())
        preferences.save({"save": False, "directory": None})
        after = cli.with_preferences(options())
        check("reading again picks the change up",
              before.no_save is False and after.no_save is True,
              (before.no_save, after.no_save))

        # ...and that it is read late is a property of main(), not just of the
        # helper. Stand in for the settings window by writing the file from
        # inside run_overlay, which is exactly when the real one writes it.
        delivered = {}
        real_run, real_deliver = cli.run_overlay, cli.output.deliver

        def overlay_that_changes_the_setting(pixbuf, bounds):
            preferences.save({"save": False, "directory": None})
            return pixbuf

        cli.run_overlay = overlay_that_changes_the_setting
        cli.output.deliver = lambda pixbuf, opts: delivered.update(
            no_save=opts.no_save, directory=opts.directory)
        preferences.save({"save": True, "directory": None})
        try:
            code = cli.main([])
        finally:
            cli.run_overlay, cli.output.deliver = real_run, real_deliver

        check("the capture completes", code == cli.EXIT_OK, code)
        check("and it honours the setting just made",
              delivered.get("no_save") is True, delivered)

        check.section("switched off plus --no-clipboard is caught as usage")
        # Both outputs disabled means the capture would go nowhere. The guard
        # in main() has to see the stored value, not just the flag.
        preferences.save({"save": False, "directory": None})
        code = cli.main(["--no-clipboard"])
        check("it exits with the usage code", code == cli.EXIT_BAD_USAGE, code)
    finally:
        preferences.path = real_path
        shutil.rmtree(home, ignore_errors=True)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
