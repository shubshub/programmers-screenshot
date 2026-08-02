"""Registering the tool as a GNOME custom keyboard shortcut."""

import sys

from gi.repository import Gio

from .paths import installed_command

DEFAULT_ACCELERATOR = "<Shift><Super>s"

MEDIA_KEYS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_KEY_SCHEMA = MEDIA_KEYS_SCHEMA + ".custom-keybinding"
BINDING_PATH = (
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
    "programmers-screenshot/"
)

MANUAL_INSTRUCTIONS = (
    "GNOME shortcut settings were not found. Bind it by hand in\n"
    "Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts,\n"
    "using 'programmers-screenshot' as the command.\n"
)


def install(accelerator):
    if not _schemas_available():
        sys.stderr.write(MANUAL_INSTRUCTIONS)
        return 1

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
    Gio.Settings.sync()

    print("Removed the programmers-screenshot hotkey")
    return 0


def _schemas_available():
    source = Gio.SettingsSchemaSource.get_default()
    if source is None:
        return False
    return all(
        source.lookup(schema, True) is not None
        for schema in (MEDIA_KEYS_SCHEMA, CUSTOM_KEY_SCHEMA)
    )
