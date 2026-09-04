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

That produces `dist/programmers-screenshot_0.27.0_all.deb` and installs it with
apt (which pulls in the dependencies). To build without installing, drop the
flag and install by hand:

```bash
./build.sh
sudo apt install ./dist/programmers-screenshot_0.27.0_all.deb
```

## Bind it to a key

```bash
programmers-screenshot --install-hotkey
```

This registers a GNOME custom shortcut on <kbd>Print</kbd>.

GNOME holds that key for its own screenshot UI, and a custom shortcut does not
reliably win while it does — so installing **switches the built-in off** and
says so. It writes down what it took, and `--uninstall-hotkey` gives it back:

```bash
programmers-screenshot --install-hotkey                    # Print
programmers-screenshot --install-hotkey '<Shift><Super>s'  # or your own
programmers-screenshot --uninstall-hotkey                  # and put GNOME's back
```

Any [GTK accelerator](https://docs.gtk.org/gtk3/func.accelerator_parse.html)
works. An accelerator nobody holds disturbs nothing.

Prefer to do it yourself? Settings → Keyboard → View and Customize Shortcuts →
Custom Shortcuts, with `programmers-screenshot` as the command — but you will
have to clear GNOME's `Print` binding yourself first.

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
| Region | Drag to set what gets captured; a new drag replaces it, a click clears it | — |
| Pen | Draw freehand on the frozen screen | Colour, thickness |
| Highlighter | A translucent wash that tints without hiding | Ink, thickness |
| Line | Straight lines, rectangles, outlined circles and arrows | Shape, colour, thickness |
| Measure | Drag to read a distance in pixels | Colour |
| Colour picker | Click a pixel; its colour goes on the clipboard | Format (#hex or rgb()) |
| Redact | Drag a bar that covers something completely | Fill (black or white) |
| Pixelate | Drag to break an area into coarse blocks | Block size |
| Step | Click to drop numbered badges: 1, 2, 3… | Size, colour |
| Text | Click, type, click away. Enter makes a new line | Size, backing, colour |

**Redact secrets, pixelate clutter.** The redaction bar is opaque, so nothing
of what was underneath survives into the saved PNG. Pixelation only *averages*
the pixels, and those averages leak — pixelated text can be recovered by
rendering candidate strings, pixelating them the same way and matching. Use the
bar for tokens, keys and addresses; use the blocks for faces and clutter.

Hovering any toolbar button names it, including the colour swatches and the
line tool's shape icons, which carry no text of their own.

Tools that have settings get a second toolbar row underneath the first, holding
just their own options. Setting values are shared by key, so the colour and
thickness you pick for the pen are the ones the line tool uses too.

The colour picker is the one tool that leaves nothing behind: it copies and
shows you what it copied, but adds nothing to the scene and nothing to the
capture. Note that capturing puts the *image* on the clipboard, replacing the
colour — so pick, then press <kbd>Esc</kbd>, if the colour is what you came for.

Hold <kbd>Shift</kbd> while dragging to constrain: the region and the circle go
square, the rectangle too, and lines and arrows snap to 45° angles.

## Options

```
-f, --full              capture the whole screen immediately, no overlay
-o, --output FILE       write the PNG to FILE
-d, --directory DIR     save into DIR instead of ~/Pictures/Screenshots
    --window TITLE      capture that window, even if buried
    --input FILE        annotate this image instead of capturing
    --origin X,Y        measure coordinates from there, not from the corner
    --scale FACTOR      picture pixels per one of yours
    --viewport WIDTH    or the page width the picture shows; the scale follows
    --dpr FACTOR        and its devicePixelRatio, when the page is zoomed
    --list-windows      list the windows --window can name
    --region X,Y,W,H    capture that area, no overlay
    --delay SECONDS     wait before the screen is read
    --recipe FILE       take the shot a JSON recipe describes ("-" is stdin)
    --recipe-help       print what a recipe can describe, and exit
    --no-clipboard      don't touch the clipboard
    --no-save           clipboard only, no file
    --no-sound          don't play the shutter sound
    --install-hotkey [ACCEL]
    --uninstall-hotkey
    --install-skill     teach Claude Code sessions that this exists
    --uninstall-skill
```

The saved path is printed to stdout, so it pipes:

```bash
scp "$(programmers-screenshot)" server:/tmp/
```

See `man programmers-screenshot` for the full details.

## Recipes

A shot can be *described* instead of taken by hand, so something other than a
person can produce one — the documentation screenshots in this README, for
instance, without anybody dragging a rectangle:

```bash
programmers-screenshot --recipe - -o docs/img/save.png --no-clipboard <<'EOF'
{
  "region": [100, 100, 900, 500],
  "annotate": [
    {"box":   [150, 150, 350, 150], "colour": "red", "width": 4},
    {"arrow": [[650, 420], [520, 310]]},
    {"step":  [200, 200]},
    {"label": [200, 480], "text": "Press Save", "background": true},
    {"redact":[160, 330, 300, 40]}
  ]
}
EOF
```

Box, ellipse, line, arrow, step, label, redact and pixelate are all
expressible, in the colours and sizes the toolbar offers. Coordinates are
logical pixels from the top left of whatever is being captured, never relative
to the region.

`--window "Google Chrome"` captures one window *whatever is stacked on top of
it* — nothing is raised or focused, because under a compositor every window is
drawn to an offscreen pixmap of its own.

For a browser **tab**, use `--input` instead. Nothing outside a browser can
address a tab — a tab is not a window, and only the front tab of a window is
being drawn at all, so a background tab has no pixels on the screen to
photograph. Naming a window is only ever a guess about which tab is in front.
A browser can capture the tab it means, so let it, and annotate what it gives
you:

```bash
programmers-screenshot --input tab.jpg --viewport 1376 --dpr 1.25 -o shot.png --recipe -
```

`--viewport` is `window.innerWidth` and `--dpr` is `window.devicePixelRatio`;
the scale is worked out from those and the picture's own width, and with it
every coordinate in the recipe is the page's own, straight out of
`getBoundingClientRect()`, with nothing to convert. Pass both: a save made at a
page zoom other than 100% is cropped to 1/dpr of the viewport, so the width
alone lands every mark short — a quarter short at 125%, measured against dots
the page drew. `--scale` does the same by hand, if you know it. `--input` is
quiet — no shutter, no notification — because no screen was read.

With Claude in Chrome that is two tool calls, from the session that has the
Chrome tools connected (`claude --chrome`): one `browser_batch` holding a
`javascript_tool` call for `innerWidth`, `devicePixelRatio` and the
rectangles, then `computer` with `action: "screenshot"` and `save_to_disk:
true`, which names the JPEG it wrote under `/tmp/claude-chrome-screenshots-*/`.
Then one Bash call running the recipe. Do not scroll in that batch — a capture
straight after a scroll can be a stale frame — and give a heavy page a fresh
tab and a two-second wait. A nested `claude --chrome -p` is the fallback when
the session has no Chrome tools of its own: script it completely, because a
sub-agent left to scroll and look is what takes an hour. `--recipe-help` has
the details; so does `docs/postmortem-2026-09-03-claude-in-chrome-tab-capture.md`,
which is where they were learnt.

`--window` is X11 only and wants `gir1.2-wnck-3.0`; `--input` needs neither.

`--recipe-help` prints the whole reference, generated from the parser's own
table so it cannot go stale, including how to map coordinates out of a browser
onto the screen. That is the thing to read, or to hand to a program, before
writing a recipe.

Nothing is drawn until the whole recipe has been understood, so a mistake in
the last arrow does not leave the first three baked into a half-finished
image. The message names the entry and the exit status is 2.

**Off until you switch it on**, in the settings window, for the same reason
the update check is. A person pressing <kbd>Print</kbd> knows what is on their
screen; something running a recipe does not, and may catch a password manager,
a private message or a token in a terminal and then write it to a file. Prefer
a named `--region` to the whole screen, and redact anything sensitive in the
same recipe — a redaction replaces the pixels, so nothing of the original
reaches the PNG. The shutter still sounds, which is how the person at the desk
knows it happened.

It reads the real screen, so it wants a live desktop session on the same
machine. Over plain ssh, in a container or in CI there is no display and it
exits 1.

### Telling Claude Code about it

A recipe is no use to something that has never heard of it, and a session
working in another project has no reason to guess this program exists:

```bash
programmers-screenshot --install-skill
```

That writes `~/.claude/skills/programmers-screenshot/SKILL.md`, after which any
session offers it when a screenshot is wanted. The skill is deliberately thin —
the three ways in, how a browser tab is done, and *run `--recipe-help`* — so
that everything which could drift lives in the generated reference rather than
in a copy of it ageing on disk. `--uninstall-skill` takes it back.

Installing the skill does not switch recipes on. That stays a decision made in
the settings window.

## How it works

The screen is captured *before* the overlay appears and painted back as the
background, so tooltips, menus and animations hold still while you select.
Under X11 the capture reads the root window directly; under Wayland it goes
through the `org.gnome.Shell.Screenshot` D-Bus interface, so a GNOME session is
required there.

The overlay spans the full virtual screen rather than a single monitor, so
selections can cross monitor boundaries. Every monitor gets its own copy of the
toolbar, each laid out to that screen's width, and they are all views of the
same state — pick a tool on one and it lights up on the rest. The cost is that
the toolbar strip is not a drawing surface on *any* screen, so a drag cannot be
started under it anywhere; dragging upward into it still works.

Clipboard ownership is handed to
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
    toolbar.py                    one bar per monitor; rows, hit testing, drawing
    scene.py                      region + annotations, and undo/redo
    recipe.py                     a shot described as JSON, for scripts
    actions.py                    the undoable changes a tool can make
    settings.py                   Setting types and their shared values
    tools/
        base.py                   Tool, DragTool and ShapeTool
        items.py                  Item, and the shapes that get drawn
        rectangle.py              the region tool
        pen.py                    freehand drawing
        highlight.py              a translucent marker wash
        line.py                   lines, rectangles, circles and arrows
        measure.py                a ruler, in physical pixels
        picker.py                 the eyedropper
        redact.py                 solid bars that cover things up
        pixelate.py               coarse blocks over an area
        step.py                   numbered step badges
        text.py                   typing, with an optional white backing
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

`label` is what a hover tooltip says, so give a new tool a readable one.

A tool whose state outlives one gesture — text being typed — implements two
more. `key_press()` gets first refusal on the keyboard, which is how Enter
means a newline rather than Capture. `commit()` hands the finished work over,
and the overlay calls it before capturing, before switching tools and before
the next gesture begins, so nothing half-finished is lost. `text.py` is the
worked example.

This is enforced, not just documented: `tests/test_framework.py` defines a tool
inside the test file and drives it end to end. If that test ever needs a change
to a core module to pass, the framework has stopped doing its job.

### Tests

```bash
python3 tests/run.py                  # every suite, one process each

python3 tests/test_framework.py       # scene, settings, tools, adding a tool
python3 tests/test_interaction.py     # overlay: mark out, confirm, cancel
python3 tests/test_highlighter.py     # the wash, on light and dark
python3 tests/test_line_tool.py       # lines, circles, arrows and Shift
python3 tests/test_measure_tool.py    # distances, in physical pixels
python3 tests/test_picker.py          # reading a pixel, copying the value
python3 tests/test_pixelate_tool.py   # blocks, and where they come from
python3 tests/test_redact_tool.py     # the bar is opaque, nothing survives
python3 tests/test_step_tool.py       # numbered badges and undo renumbering
python3 tests/test_text_tool.py       # typing, committing, and the backing
python3 tests/test_tooltips.py        # hover labels for tools and settings
python3 tests/test_multi_monitor.py   # a toolbar per screen, sharing one state
python3 tests/test_redraw.py          # partial redraws leave no stale pixels
python3 tests/test_notifications.py   # notification wiring and agent handoff
python3 tests/test_sound.py           # the sound asset, generator and playback
```

They run against a real display but never show a window, and never make a
noise. `tests/support.py` holds the shared harness, `tests/checker.py` the
tally every suite prints, and `tests/run.py` runs the lot. The two
notification actions talk to the desktop, so they are left to manual testing.

## Licence

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Shubshub.

Use it, change it, ship it. The one condition is credit: keep the copyright
notice and the licence text with any copy or substantial portion of it.
