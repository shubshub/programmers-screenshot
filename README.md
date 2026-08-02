# programmers-screenshot

A minimal region screenshot tool for Ubuntu, built to sit on a single keypress.

Press the hotkey and the screen freezes and dims, with a toolbar across the top.
Mark out a region, scribble on it, then hit **Capture** in the top right. The
result lands on your clipboard and in `~/Pictures/Screenshots` as a timestamped
PNG. No editor, no dialogs, no upload prompts.

Nothing is captured until you press Capture, so you can redraw as many times as
you like first — and <kbd>Ctrl</kbd>+<kbd>Z</kbd> takes back whatever you last
did.

A shutter sound fires as the shot is taken. The notification that follows has
two buttons: **Open Image** opens the PNG, and **Show in Folder** opens the
containing folder with the file selected.

## Build and install

```bash
./build.sh --install
```

That produces `dist/programmers-screenshot_0.7.0_all.deb` and installs it with
apt (which pulls in the dependencies). To build without installing, drop the
flag and install by hand:

```bash
./build.sh
sudo apt install ./dist/programmers-screenshot_0.7.0_all.deb
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
| Drag on the screen | Use the active tool |
| **Capture**, or <kbd>Enter</kbd> | Take the shot |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> | Undo / redo |
| **✕**, <kbd>Esc</kbd>, or right-click | Close without capturing |
| <kbd>Esc</kbd> mid-drag | Abandon just that stroke |

**The region is optional.** With one marked out, Capture takes that; with none,
it takes the whole screen — the same thing `--full` does. So you can go straight
to drawing without marking anything out first. A plain click with the region
tool clears the region again.

The region shows a live pixel-size readout. Cancelling exits with status 1, so
it composes in scripts.

The toolbar is not a drawing surface, so you can't *start* a drag under it — but
dragging upwards into it works, which is how you grab the top edge of the
screen.

### Tools

| Tool | Does | Settings |
| --- | --- | --- |
| Region | Drag to set what gets captured; click to clear it | — |
| Pen | Draw freehand on the frozen screen | Colour, thickness |
| Line | Straight lines, outlined circles and arrows | Shape, colour, thickness |
| Step | Click to drop numbered badges: 1, 2, 3… | Size, colour |

Tools that have settings get a second toolbar row underneath the first, holding
just their own options. Setting values are shared by key, so the colour and
thickness you pick for the pen are the ones the line tool uses too.

Hold <kbd>Shift</kbd> while dragging to constrain: the region and the circle go
square, lines and arrows snap to 45° angles.

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
    toolbar.py                    both bar rows: layout, hit testing, drawing
    scene.py                      region + annotations, and undo/redo
    actions.py                    the undoable changes a tool can make
    settings.py                   Setting types and their shared values
    tools/
        base.py                   Tool, DragTool and ShapeTool
        items.py                  Item, and the shapes that get drawn
        rectangle.py              the region tool
        pen.py                    freehand drawing
        line.py                   lines, circles and arrows
        step.py                   numbered step badges
        __init__.py               ALL_TOOLS — the registry
    output.py                     saving and clipboard
    notifications.py              the notification and its buttons
    hotkey.py                     GNOME shortcut registration
    sound.py                      playing the shutter sound
    paths.py                      where this program and its assets live
    geometry.py                   Rect, and drag constraint helpers
    painting.py                   shared cairo helpers
    theme.py                      every colour and measurement
packaging/                        control, desktop entry, icon, man page, sound
tools/make-shutter-sound.py       regenerates packaging/shutter.wav
tests/                            headless behaviour tests
build.sh                          assembles the tree and runs dpkg-deb
```

### Adding a tool

Nearly every tool is the same gesture — press, drag, and on release something
is set. `DragTool` owns that: where the drag started, where it is now, and the
settings it began with. A subclass says only what a finished drag *means*
(`complete`), what it looks like on the way (`draw_drag`), and how much of the
screen it touches (`drag_extent`).

Most tools leave a shape behind, and those want `ShapeTool` — a thin layer over
`DragTool` where the only method you write is `make_item()`.

**1.** Write the file. Here is an arrow tool, in full:

```python
# src/programmers_screenshot/tools/arrow.py
from .base import ShapeTool
from .items import Item
from ..settings import COLOUR, WIDTH


class Arrow(Item):
    def __init__(self, start, end, colour, width):
        self.start, self.end = start, end
        self.colour, self.width = colour, width

    def draw(self, cr):
        cr.set_source_rgb(*self.colour)
        cr.set_line_width(self.width)
        cr.move_to(*self.start)
        cr.line_to(*self.end)
        cr.stroke()
        # ...and the head


class ArrowTool(ShapeTool):
    name = "arrow"
    label = "Arrow"
    icon_text = "↗"
    settings = (COLOUR, WIDTH)

    def make_item(self, start, end, values):
        return Arrow(start, end, values["colour"], values["width"])
```

**2.** Add it to the registry in `tools/__init__.py`:

```python
ALL_TOOLS = (RectangleTool, PenTool, ArrowTool)
```

That is the whole job. The toolbar button, the settings row, the live preview,
the undo entry and inclusion in the captured image all follow with no other
edits. `icon_text` is a plain glyph so you don't have to write cairo for a
button; override `draw_icon()` if you want to.

A drag that sets something other than an annotation subclasses `DragTool`
directly and returns an `Action` from `complete()` — `rectangle.py` does that,
returning a `SetRegion`. Only for gestures that are not drags at all — multi
click, click-to-place — reach for `Tool` and handle `begin`/`extend`/`finish`
yourself; `pen.py` is the worked example, since freehand needs every point
rather than just two.

Two things to get right in a new shape: `Item.bounds()` must cover everything
`draw()` paints, stroke overhang and all, because partial redraws trust it; and
`constrain()` decides what <kbd>Shift</kbd> does, with `square_corner()` and
`snap_to_45()` in `geometry.py` covering the usual cases.

This is enforced, not just documented: `tests/test_framework.py` defines a tool
inside the test file and drives it end to end. If that test ever needs a change
to a core module to pass, the framework has stopped doing its job.

### Tests

```bash
python3 tests/test_framework.py       # scene, settings, tools, adding a tool
python3 tests/test_interaction.py     # overlay: mark out, confirm, cancel
python3 tests/test_line_tool.py       # lines, circles, arrows and Shift
python3 tests/test_step_tool.py       # numbered badges and undo renumbering
python3 tests/test_redraw.py          # partial redraws leave no stale pixels
python3 tests/test_notifications.py   # notification wiring and agent handoff
python3 tests/test_sound.py           # the sound asset, generator and playback
```

They run against a real display but never show a window, and never make a
noise. `tests/support.py` holds the shared harness. The two notification
actions talk to the desktop, so they are left to manual testing.
