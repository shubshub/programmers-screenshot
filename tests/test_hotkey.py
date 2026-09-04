#!/usr/bin/env python3
"""Claiming Print Screen, and giving it back.

Runs against a private GSettings store and a temporary config directory, so
it never touches the shortcuts you are actually using.

    python3 tests/test_hotkey.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

from checker import Checker

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)

# The child does the real work, under GSETTINGS_BACKEND=memory so nothing it
# writes escapes. Importing Gio in this process first would fix the backend
# before the child could choose it.
CHILD = r'''
import json, os, sys
sys.path.insert(0, %(src)r)
from gi.repository import Gio
from programmers_screenshot import hotkey

SHELL = hotkey.SHELL_SCHEMA
result = {}

def held(key):
    return list(Gio.Settings.new(SHELL).get_strv(key))

# Seed the shell bindings the way a real desktop has them.
Gio.Settings.new(SHELL).set_strv("show-screenshot-ui", ["Print"])
Gio.Settings.new(SHELL).set_strv("screenshot", ["<Shift>Print"])
result["before"] = {"ui": held("show-screenshot-ui"), "shot": held("screenshot")}

hotkey.install("Print")
result["after_install"] = {"ui": held("show-screenshot-ui"), "shot": held("screenshot")}
result["binding"] = Gio.Settings.new_with_path(
    hotkey.CUSTOM_KEY_SCHEMA, hotkey.BINDING_PATH).get_string("binding")
result["remembered"] = json.load(open(hotkey.displaced_file()))

# A second install must not record the emptied value over the real original.
hotkey.install("Print")
result["remembered_twice"] = json.load(open(hotkey.displaced_file()))

hotkey.uninstall()
result["after_uninstall"] = {"ui": held("show-screenshot-ui"), "shot": held("screenshot")}
result["file_gone"] = not os.path.exists(hotkey.displaced_file())

# An accelerator nobody holds should disturb nothing.
Gio.Settings.new(SHELL).set_strv("show-screenshot-ui", ["Print"])
hotkey.install("<Ctrl><Alt><Shift>F9")
result["uncontested"] = held("show-screenshot-ui")
result["uncontested_file"] = os.path.exists(hotkey.displaced_file())
hotkey.uninstall()

print("@@" + json.dumps(result))
'''


def main():
    check = Checker()
    config = tempfile.mkdtemp(prefix="programmers-screenshot-hotkey-")
    environment = dict(os.environ)
    environment["GSETTINGS_BACKEND"] = "memory"
    environment["XDG_CONFIG_HOME"] = config

    try:
        finished = subprocess.run(
            [sys.executable, "-c", CHILD % {"src": os.path.join(ROOT, "src")}],
            capture_output=True,
            text=True,
            timeout=90,
            env=environment,
        )
        line = [text for text in finished.stdout.splitlines()
                if text.startswith("@@")]
        if not line:
            print(finished.stdout)
            print(finished.stderr)
            check("the child ran", False, "no result")
            return check.report()
        result = json.loads(line[0][2:])

        check.section("it starts from a desktop that owns Print")
        check("GNOME holds Print", result["before"]["ui"] == ["Print"],
              result["before"]["ui"])

        check.section("installing on Print frees it first")
        check("the shell no longer holds Print",
              result["after_install"]["ui"] == [], result["after_install"]["ui"])
        check("our shortcut has it", result["binding"] == "Print", result["binding"])
        check("an unrelated binding is untouched",
              result["after_install"]["shot"] == ["<Shift>Print"],
              result["after_install"]["shot"])
        check("and what was taken is written down",
              result["remembered"] == {
                  "org.gnome.shell.keybindings show-screenshot-ui": ["Print"]},
              result["remembered"])

        check.section("installing twice keeps the original, not the emptied value")
        check("still the real original",
              result["remembered_twice"] == result["remembered"],
              result["remembered_twice"])

        check.section("uninstalling gives it back")
        check("GNOME has Print again",
              result["after_uninstall"]["ui"] == ["Print"],
              result["after_uninstall"]["ui"])
        check("and the note is cleared", result["file_gone"])

        check.section("an accelerator nobody holds disturbs nothing")
        check("GNOME keeps Print", result["uncontested"] == ["Print"],
              result["uncontested"])
        check("nothing written down", not result["uncontested_file"])
    finally:
        shutil.rmtree(config, ignore_errors=True)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
