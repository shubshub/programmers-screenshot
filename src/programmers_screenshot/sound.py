"""The capture sound.

Played by handing the file to whichever command line player is around, rather
than by linking an audio library: the sound is a nicety, and a missing player
should cost nothing but silence.
"""

import shutil
import subprocess

from gi.repository import Gio

from .paths import sound_file

# In preference order. canberra-gtk-play comes first because it follows the
# desktop's sound theme volume; the rest just play the file.
PLAYERS = (
    ("canberra-gtk-play", ["-f"]),
    ("paplay", []),
    ("pw-play", []),
    ("aplay", ["-q"]),
)

SOUND_SCHEMA = "org.gnome.desktop.sound"
EVENT_SOUNDS_KEY = "event-sounds"


def play():
    """Fire the shutter sound and return at once. True if it was started."""
    if not desktop_wants_sound():
        return False
    path = sound_file()
    if path is None:
        return False
    command = player_command(path)
    if command is None:
        return False
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True


def player_command(path):
    """The first available player, as a full argument list."""
    for name, arguments in PLAYERS:
        executable = shutil.which(name)
        if executable:
            return [executable] + arguments + [path]
    return None


def desktop_wants_sound():
    """Follow the desktop's event-sounds switch, if the desktop has one."""
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(SOUND_SCHEMA, True) is None:
        return True
    return Gio.Settings.new(SOUND_SCHEMA).get_boolean(EVENT_SOUNDS_KEY)
