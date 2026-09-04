"""App-wide preferences, and the window that edits them.

Distinct from settings.py: those are the per-tool knobs on the second toolbar
row, chosen per gesture and forgotten when the overlay closes. These outlive
the session and live in a file.

Six of them: whether a capture is saved and to which folder, how the toolbar
is presented and where the palette was last dropped, whether GitHub is asked
about new releases, and whether a recipe may take a shot with nobody
watching. A flag always beats what is stored here; see cli.with_preferences.
"""

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk  # noqa: E402

from .paths import config_file, default_directory, read_json, write_json

BAR = "bar"
PALETTE = "palette"

DEFAULTS = {
    "save": True,
    "directory": None,
    # How the controls are presented: a bar across the top of every monitor,
    # or one floating rectangle you drag where you want it.
    "toolbar": BAR,
    # Where the palette was left, as [x, y]. None means "work it out".
    "palette": None,
    # Ask GitHub about newer releases. Off until asked: this is the only
    # network call the program makes, and it should not start making it
    # because someone pressed Print Screen.
    "updates": False,
    # Let --region and --recipe take a shot with nobody watching. Off until
    # asked, for the same reason as updates and more so: a person pressing
    # Print Screen knows what is on their screen, and something running a
    # recipe does not.
    "scripted": False,
}


def path():
    """Where the preferences live. A file, for the same reason the displaced
    hotkeys are one: this program has no GSettings schema of its own."""
    return config_file("preferences.json")


def load():
    """Stored preferences, with anything missing or unreadable defaulted.

    Keys nobody recognises are dropped rather than carried along, so an old
    file cannot smuggle a setting past the window that edits them.
    """
    values = dict(DEFAULTS)
    stored = read_json(path())
    values.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return values


def save(values):
    """Raises OSError: somebody just chose these and is owed the news."""
    write_json(path(), values)


def build(values):
    """Assemble the window. Returns the dialog and the widgets read on close.

    Split from edit() only so the greying-out can be checked without a person
    to click Close.
    """
    # No transient parent: the only caller hides its own window first, because
    # that window is override-redirect and would otherwise bury this one.
    dialog = Gtk.Dialog(title="Settings", modal=True)
    dialog.add_button("Close", Gtk.ResponseType.CLOSE)

    toggle = Gtk.CheckButton(label="Save screenshots to a folder")
    toggle.set_active(bool(values["save"]))

    floating = Gtk.CheckButton(label="Floating toolbar you can drag around")
    floating.set_active(values.get("toolbar") == PALETTE)

    scripted = Gtk.CheckButton(label="Let a recipe drive captures")
    scripted.set_tooltip_text(
        "Allows --region and --recipe, so a script or an agent can take an "
        "annotated shot with nobody at the keyboard. See --recipe-help."
    )
    scripted.set_active(bool(values.get("scripted")))

    updates = Gtk.CheckButton(label="Check GitHub for new versions")
    updates.set_tooltip_text(
        "Asks github.com once a day, after a capture. Nothing else is sent."
    )
    updates.set_active(bool(values.get("updates")))

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
    grid.attach(Gtk.Separator(), 0, 2, 2, 1)
    grid.attach(floating, 0, 3, 2, 1)
    grid.attach(updates, 0, 4, 2, 1)
    grid.attach(scripted, 0, 5, 2, 1)
    dialog.get_content_area().add(grid)
    return dialog, toggle, chooser, floating, updates, scripted


def edit():
    """Show the settings window, write what it says, and return it.

    Blocks until the window is closed. The caller is responsible for dropping
    any pointer grab and hiding its own window first — see
    Overlay._edit_preferences for why both matter.
    """
    values = load()
    dialog, toggle, chooser, floating, updates, scripted = build(values)

    dialog.show_all()
    dialog.run()

    chosen = dict(values)
    chosen.update({
        "save": toggle.get_active(),
        # None when the chooser never resolved a folder; keep what we had.
        "directory": chooser.get_filename() or values["directory"],
        "toolbar": PALETTE if floating.get_active() else BAR,
        "updates": updates.get_active(),
        "scripted": scripted.get_active(),
    })
    dialog.destroy()
    save(chosen)
    return chosen
