#!/usr/bin/env python3
"""The capture sound: the asset, its generator, and how it gets played.

Nothing here makes a noise.

    python3 tests/test_sound.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)

from checker import Checker  # noqa: E402
from programmers_screenshot import paths, sound  # noqa: E402

GENERATOR = os.path.join(ROOT, "tools", "make-shutter-sound.py")
COMMITTED = os.path.join(ROOT, "packaging", "shutter.wav")


def main():
    check = Checker()

    check.section("the sound file is found and is valid audio")
    found = paths.sound_file()
    check("located", found is not None, found)
    with wave.open(found, "rb") as handle:
        channels = handle.getnchannels()
        rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.getnframes()
    check("mono", channels == 1, channels)
    check("16-bit", width == 2, width)
    check("44.1 kHz", rate == 44100, rate)
    duration_ms = 1000.0 * frames / rate
    check("short enough to feel instant", duration_ms < 400, "%.0f ms" % duration_ms)

    check.section("the committed file matches its generator")
    # The generator is deterministic, so drift would mean the asset was edited
    # by hand and can no longer be reproduced. Re-run it over the real file and
    # confirm nothing changed, keeping a copy in case it does.
    workspace = tempfile.mkdtemp(prefix="shutter-test-")
    backup = os.path.join(workspace, "committed.wav")
    try:
        shutil.copy(COMMITTED, backup)
        result = subprocess.run(
            [sys.executable, GENERATOR], capture_output=True, text=True, timeout=60
        )
        check("generator runs", result.returncode == 0, result.stderr.strip()[:120])
        with open(COMMITTED, "rb") as fresh, open(backup, "rb") as original:
            identical = fresh.read() == original.read()
        check("regenerating is a no-op", identical)
        if not identical:
            shutil.copy(backup, COMMITTED)  # leave the tree as we found it
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    check.section("playback picks a real player")
    command = sound.player_command(found)
    check("a player was chosen", command is not None, command and command[0])
    if command:
        check("the player exists", os.path.exists(command[0]), command[0])
        check("the file is the last argument", command[-1] == found)

    check.section("the desktop's sound switch is respected")
    check("returns a boolean", isinstance(sound.desktop_wants_sound(), bool),
          sound.desktop_wants_sound())

    check.section("--no-sound is accepted")
    from programmers_screenshot.cli import build_parser

    check("off by default", build_parser().parse_args([]).no_sound is False)
    check("can be switched off", build_parser().parse_args(["--no-sound"]).no_sound)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
