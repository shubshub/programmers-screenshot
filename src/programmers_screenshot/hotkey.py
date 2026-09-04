"""Registering the tool as a GNOME custom keyboard shortcut.

Print is the key people reach for, and GNOME holds it for its own screenshot
UI. Claiming it means switching that off, so installing records what it took
and uninstalling gives it back — otherwise removing our shortcut would leave
the user permanently without their Print Screen key and no clue why.
"""

import contextlib
import json
import os
import sys

from gi.repository import Gio, GLib

from .paths import installed_command

DEFAULT_ACCELERATOR = "Print"

MEDIA_KEYS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_KEY_SCHEMA = MEDIA_KEYS_SCHEMA + ".custom-keybinding"
SHELL_SCHEMA = "org.gnome.shell.keybindings"
BINDING_PATH = (
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
    "programmers-screenshot/"
)

# Where the Print family lives. Scanning every schema on the system for a
# conflict would be slow and mostly noise; this covers the realistic
# collisions and can grow if another one turns up.
CONTESTED = (
    (SHELL_SCHEMA, "screenshot"),
    (SHELL_SCHEMA, "screenshot-window"),
    (SHELL_SCHEMA, "show-screenshot-ui"),
    (SHELL_SCHEMA, "show-screen-recording-ui"),
)

MANUAL_INSTRUCTIONS = (
    "GNOME shortcut settings were not found. Bind it by hand in\n"
    "Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts,\n"
    "using 'programmers-screenshot' as the command.\n"
)


def displaced_file():
    """Where the bindings we switched off are remembered.

    A file rather than gsettings, since the tool has no schema of its own to
    put them in.
    """
    return os.path.join(
        GLib.get_user_config_dir(), "programmers-screenshot", "displaced.json"
    )


def install(accelerator):
    if not _schemas_available():
        sys.stderr.write(MANUAL_INSTRUCTIONS)
        return 1

    taken = _release(accelerator)

    media_keys = Gio.Settings.new(MEDIA_KEYS_SCHEMA)
    registered = list(media_keys.get_strv("custom-keybindings"))
    if BINDING_PATH not in registered:
        registered.append(BINDING_PATH)
        media_keys.set_strv("custom-keybindings", registered)

    binding = Gio.Settings.new_with_path(CUSTOM_KEY_SCHEMA, BINDING_PATH)
    binding.set_string("name", "Programmers Screenshot")
    binding.set_string("command", installed_command())
    binding.set_string("binding", accelerator)
    Gio.Settings.sync()

    print("Bound %s to programmers-screenshot" % accelerator)
    for schema, key in taken:
        print("  turned off %s %s, which had it" % (schema, key))
    if taken:
        print("  --uninstall-hotkey puts them back")
    return 0


def uninstall():
    if not _schemas_available():
        return 0

    media_keys = Gio.Settings.new(MEDIA_KEYS_SCHEMA)
    remaining = [
        path
        for path in media_keys.get_strv("custom-keybindings")
        if path != BINDING_PATH
    ]
    media_keys.set_strv("custom-keybindings", remaining)

    binding = Gio.Settings.new_with_path(CUSTOM_KEY_SCHEMA, BINDING_PATH)
    for key in ("name", "command", "binding"):
        binding.reset(key)

    restored = _restore()
    Gio.Settings.sync()

    print("Removed the programmers-screenshot hotkey")
    for schema, key in restored:
        print("  gave %s %s back its shortcut" % (schema, key))
    return 0


# --------------------------------------------------------------------------
# making room
# --------------------------------------------------------------------------


def _release(accelerator):
    """Clear any GNOME binding holding this accelerator, remembering it.

    Returns what was switched off, so the caller can say. Anything already
    remembered from an earlier install is kept: two installs in a row must not
    record the second run's empty value over the real original.
    """
    remembered = _load()
    taken = []

    for schema, key in CONTESTED:
        if not _schema_exists(schema):
            continue
        settings = Gio.Settings.new(schema)
        held = list(settings.get_strv(key))
        if accelerator not in held:
            continue
        remaining = [value for value in held if value != accelerator]
        settings.set_strv(key, remaining)
        remembered.setdefault("%s %s" % (schema, key), held)
        taken.append((schema, key))

    if taken:
        _save(remembered)
    return taken


def _restore():
    """Put back everything install() switched off, and forget it."""
    remembered = _load()
    restored = []
    for entry, value in remembered.items():
        schema, key = entry.rsplit(" ", 1)
        if not _schema_exists(schema):
            continue
        Gio.Settings.new(schema).set_strv(key, value)
        restored.append((schema, key))
    if remembered:
        with contextlib.suppress(OSError):
            os.unlink(displaced_file())
    return restored


def _load():
    try:
        with open(displaced_file(), "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _save(remembered):
    path = displaced_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(remembered, handle, indent=2, sort_keys=True)


def _schema_exists(schema):
    source = Gio.SettingsSchemaSource.get_default()
    return source is not None and source.lookup(schema, True) is not None


def _schemas_available():
    return all(
        _schema_exists(schema) for schema in (MEDIA_KEYS_SCHEMA, CUSTOM_KEY_SCHEMA)
    )
