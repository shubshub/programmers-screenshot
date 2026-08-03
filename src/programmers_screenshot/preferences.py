"""App-wide preferences, and the window that edits them.

Distinct from settings.py: those are the per-tool knobs on the second toolbar
row, chosen per gesture and forgotten when the overlay closes. These outlive
the session and live in a file.

The only preference so far is a stored default for --no-save and --directory,
which already worked from the command line. A flag always beats what is
stored here; see cli.apply_preferences.
"""

import json
import os

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gtk  # noqa: E402

from .paths import default_directory

DEFAULTS = {"save": True, "directory": None}


def path():
    """Where the preferences live. A file, for the same reason the displaced
    hotkeys are one: this program has no GSettings schema of its own."""
    return os.path.join(
        GLib.get_user_config_dir(), "programmers-screenshot", "preferences.json"
    )


def load():
    """Stored preferences, with anything missing or unreadable defaulted."""
    values = dict(DEFAULTS)
    try:
        with open(path(), "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return values
    if isinstance(stored, dict):
        values.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return values


def save(values):
    target = path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(values, handle, indent=2, sort_keys=True)


def build(values, parent=None):
    """Assemble the window. Returns (dialog, toggle, chooser).

    Split from edit() only so the greying-out can be checked without a person
    to click Close.
    """
    dialog = Gtk.Dialog(title="Settings", transient_for=parent, modal=True)
    dialog.set_keep_above(True)  # the overlay it opens over is keep-above too
    dialog.add_button("Close", Gtk.ResponseType.CLOSE)

    toggle = Gtk.CheckButton(label="Save screenshots to a folder")
    toggle.set_active(bool(values["save"]))

    caption = Gtk.Label(label="Folder", halign=Gtk.Align.START)
    chooser = Gtk.FileChooserButton.new(
        "Choose where screenshots are saved", Gtk.FileChooserAction.SELECT_FOLDER
    )
    chooser.set_filename(values["directory"] or default_directory())

    def follow_toggle(*_args):
        """The folder only means anything while saving is on."""
        enabled = toggle.get_active()
        caption.set_sensitive(enabled)
        chooser.set_sensitive(enabled)

    toggle.connect("toggled", follow_toggle)
    follow_toggle()

    grid = Gtk.Grid(row_spacing=12, column_spacing=12, margin=16)
    grid.attach(toggle, 0, 0, 2, 1)
    grid.attach(caption, 0, 1, 1, 1)
    grid.attach(chooser, 1, 1, 1, 1)
    dialog.get_content_area().add(grid)
    return dialog, toggle, chooser


def edit(parent=None):
    """Show the settings window, write what it says, and return it.

    Blocks until the window is closed. The caller is responsible for letting
    go of any pointer grab first — see Overlay._edit_preferences.
    """
    values = load()
    dialog, toggle, chooser = build(values, parent)

    dialog.show_all()
    dialog.run()

    chosen = {
        "save": toggle.get_active(),
        # None when the chooser never resolved a folder; keep what we had.
        "directory": chooser.get_filename() or values["directory"],
    }
    dialog.destroy()
    save(chosen)
    return chosen
