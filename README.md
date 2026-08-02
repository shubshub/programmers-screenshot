# programmers-screenshot

A minimal region screenshot tool for Ubuntu, built to sit on a single keypress.

Press the hotkey and the screen freezes and dims, with a toolbar across the top.
Pick a tool, mark out what you want, then hit **Capture** in the top right. The
region lands on your clipboard and in `~/Pictures/Screenshots` as a timestamped
PNG. No editor, no dialogs, no upload prompts.

Nothing is captured until you press Capture, so you can redraw the selection as
many times as you like first.

A shutter sound fires as the shot is taken. The notification that follows has
two buttons: **Open Image** opens the PNG, and **Show in Folder** opens the
containing folder with the file selected.

## Build and install

```bash
./build.sh --install
```

That produces `dist/programmers-screenshot_0.4.0_all.deb` and installs it with
apt (which pulls in the dependencies). To build without installing, drop the
flag and install by hand:

```bash
./build.sh
sudo apt install ./dist/programmers-screenshot_0.4.0_all.deb
```

## Bind it to a key

```bash
programmers-screenshot --install-hotkey
```

This registers a GNOME custom shortcut on <kbd>Shift</kbd>+<kbd>Super</kbd>+<kbd>S</kbd>
("Super" being the Windows key). Pass a different
[GTK accelerator](https://docs.gtk.org/gtk3/func.accelerator_parse.html) to
choose your own, and `--uninstall-hotkey` to remove it:

```bash
programmers-screenshot --install-hotkey '<Ctrl><Shift>Print'
programmers-screenshot --uninstall-hotkey
```

Prefer to do it yourself? Settings → Keyboard → View and Customize Shortcuts →
Custom Shortcuts, with `programmers-screenshot` as the command.

Note that GNOME already owns `Print` (screenshot UI), `<Shift>Print` (full
screen) and `<Alt>Print` (window), so pick something else or rebind those first.

## Using it

| Input | Result |
| --- | --- |
| Drag on the screen | Mark out a region with the active tool |
| **Capture**, or <kbd>Enter</kbd> | Take the shot |
| **✕**, <kbd>Esc</kbd>, or right-click | Close without capturing |
| Single click | Clear the selection |

Capture stays disabled until something is selected. The selection shows a live
pixel-size readout. Cancelling exits with status 1, so it composes in scripts.

The toolbar is not a drawing surface, so you can't *start* a selection under it
— but dragging upwards into it works, which is how you grab the top edge of the
screen.

### Tools

| Tool | Does |
| --- | --- |
| Rectangle | Click and drag to select a rectangular region |

## Options

```
-f, --full              capture the whole screen immediately, no overlay
-o, --output FILE       write the PNG to FILE
-d, --directory DIR     save into DIR instead of ~/Pictures/Screenshots
    --no-clipboard      don't touch the clipboard
    --no-save           clipboard only, no file
    --no-sound          don't play the shutter sound
    --install-hotkey [ACCEL]
    --uninstall-hotkey
```

The saved path is printed to stdout, so it pipes:

```bash
scp "$(programmers-screenshot)" server:/tmp/
```

See `man programmers-screenshot` for the full details.

## How it works

The screen is captured *before* the overlay appears and painted back as the
background, so tooltips, menus and animations hold still while you select.
Under X11 the capture reads the root window directly; under Wayland it goes
through the `org.gnome.Shell.Screenshot` D-Bus interface, so a GNOME session is
required there.

The overlay spans the full virtual screen rather than a single monitor, so
selections can cross monitor boundaries. The toolbar goes on whichever monitor
the pointer was on when the hotkey fired. Clipboard ownership is handed to
`xclip` (or `wl-copy` on Wayland) so the image survives after the process exits.

The notification's buttons need a process alive to receive the click, but the
command has to exit immediately or `$(programmers-screenshot)` would hang. So
the notification is handed to a detached copy of the program running in agent
mode, which exits when the notification is dismissed, a button is pressed, or
five minutes pass. GNOME hides buttons behind the notification's expander
arrow, so you may need to expand it to see them.

### The shutter sound

`packaging/shutter.wav` is generated, not recorded — `tools/make-shutter-sound.py`
synthesises two mechanical clicks (mirror, then blades) as noise bursts through
a lowpass filter with exponential decay, each over a damped sine that gives the
click a body. It is deterministic, so re-running it reproduces the same file
byte for byte, and a test asserts that the committed file still matches.

MIDI would have been the wrong format: it carries note messages rather than
audio, so it needs a synthesiser and a soundfont at playback time — neither of
which is installed by default — and a broadband click is not something a note
can express. The result is a 14 KB WAV that always plays.

Playback goes through whichever of `canberra-gtk-play`, `paplay`, `pw-play` or
`aplay` is present, preferring the first because it follows the desktop's sound
theme volume. If none is installed you get silence and nothing else. The
desktop's own *event sounds* setting is respected, and `--no-sound` overrides
per-invocation.

## Code layout

```
bin/programmers-screenshot        launcher; works from the checkout or /usr/bin
src/programmers_screenshot/
    cli.py                        argument parsing and the top-level flow
    capture.py                    reading pixels (X11 root, or GNOME D-Bus)
    overlay.py                    the modal window: events, drawing, grabs
    toolbar.py                    bar layout, hit testing, button drawing
    tools.py                      Tool base class + RectangleTool
    output.py                     saving and clipboard
    notifications.py              the notification and its buttons
    hotkey.py                     GNOME shortcut registration
    sound.py                      playing the shutter sound
    paths.py                      where this program and its assets live
    geometry.py                   Rect
    painting.py                   shared cairo helpers
    theme.py                      every colour and measurement
packaging/                        control, desktop entry, icon, man page, sound
tools/make-shutter-sound.py       regenerates packaging/shutter.wav
tests/                            headless behaviour tests
build.sh                          assembles the tree and runs dpkg-deb
```

### Adding a tool

Write a `Tool` subclass in `tools.py` and add it to `ALL_TOOLS`. The toolbar
button, its icon slot, and the event routing all come for free — a tool only
has to handle `press`/`drag`/`release`, draw itself, and report a `selection()`.

### Tests

```bash
python3 tests/test_interaction.py     # overlay: select, confirm, cancel
python3 tests/test_notifications.py   # notification wiring and agent handoff
python3 tests/test_sound.py           # the sound asset, generator and playback
```

They run against a real display but never show a window, and never make a
noise. The two notification actions talk to the desktop, so they are left to
manual testing.
