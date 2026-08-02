# Plan: drawing tools and a common tool framework

Status: proposed
Depends on: #1

## Why

The overlay has one tool, and `Tool` was written for that one tool. Its
`selection()` method returns a rectangle, which is meaningless for a pen. Every
new tool would need core changes in `overlay.py` and `toolbar.py`, which is
exactly the wrong shape.

This plan adds a **Pen** tool with colour and thickness, a **settings bar** for
per-tool options, and a **framework** that makes the next tool a new file plus
one line in a registry. Adapting the existing Rectangle tool to that framework
is part of the work, not a follow-up.

The measure of success is concrete: **adding an Arrow tool should be about a
dozen lines in one new file, with no edits to the overlay, the toolbar, the
undo stack or the capture pipeline.** A test asserts this.

## Decisions

Three questions were settled before writing this.

**1. Drawing does not require a region.** Tools are peers; the region is
optional state rather than a gate. Capture is always enabled: with a rectangle
it takes that region, without one it takes the whole virtual screen — the same
thing `--full` means. This is a behaviour change; today Capture is disabled
until something is selected.

**2. The settings bar is a second row** directly beneath the main toolbar,
shown only while the active tool declares settings. Predictable position, never
covers the selection, no off-screen edge cases.

```
+------------------------------------------------------+
| [rect] [pen]                        [x] [ Capture ]   |
+------------------------------------------------------+
| Colour  (*)(*)(*)(*)(*)     Width  o  o  O  O         |   <- only when the
+------------------------------------------------------+      tool has settings
|                                                       |
|                  frozen screen                        |
```

**3. Undo/redo**, `Ctrl+Z` and `Ctrl+Shift+Z`, over a stack of committed
actions. Not object selection or moving — that needs per-tool hit testing and
is out of scope.

## Non-goals

- Editing, moving or deleting individual annotations after they are committed.
- Text annotation, blur/pixelate, numbered steps. The framework should make
  these easy later; none are in this change.
- Persisting the last-used colour and width between runs. Worth doing, but
  listed under [Later](#later) so it does not widen this change.

## Architecture

Four concerns, currently tangled in `tools.py` and `overlay.py`, get separated.

| Piece | Responsibility |
| --- | --- |
| `Scene` | The mutable session state: optional region, ordered annotations, undo/redo |
| `Tool` | Turns pointer gestures into an `Action`; declares its settings |
| `Setting` | A knob the settings bar renders generically |
| `Item` | One committed annotation that knows how to draw itself |

The overlay stops knowing what a tool *is*. It routes events, draws the scene,
and asks the toolbar what was clicked.

### Scene and actions

Undo works over actions rather than items, so that setting the region is
undoable on exactly the same footing as drawing a stroke.

```python
class Action:
    """Something undoable that happened to the scene."""
    def apply(self, scene): ...
    def revert(self, scene): ...

class AddItem(Action):     # the common case
class SetRegion(Action):   # what the rectangle tool produces


class Scene:
    region: Rect | None
    items: list[Item]

    def do(self, action): ...   # apply, push to undo, clear redo
    def undo(self): ...
    def redo(self): ...
```

### Tool

```python
class Tool:
    name = ""             # stable id
    label = ""            # human name, used as the button tooltip
    icon_text = None      # optional glyph, e.g. "✏" — see Icons below
    settings = ()         # Setting instances, or empty for none

    def begin(self, point, values): ...   # pointer down
    def extend(self, point): ...          # pointer moved, button held
    def finish(self, point): ...          # pointer up -> Action, Item, or None
    def cancel(self): ...                 # Esc mid-gesture
    def preview(self, cr): ...            # draw the in-progress gesture
    def draw_icon(self, cr, box, colour): ...   # optional if icon_text is set
```

`finish()` returning a bare `Item` is wrapped in `AddItem` automatically, so the
usual tool never mentions actions at all.

`values` is a mapping of the tool's current setting values, passed in at
`begin()` so a stroke keeps the colour it was started with even if the setting
changes mid-drag.

### ShapeTool: the easy path

Most tools are "drag from A to B and leave a shape behind". They get a base
class that reduces the job to one method.

```python
class ShapeTool(Tool):
    """Drag from A to B. Implement make_item() and you are done."""
    def make_item(self, start, end, values):
        raise NotImplementedError
```

An Arrow tool, in full:

```python
# tools/arrow.py
from .base import ShapeTool
from .items import Arrow
from ..settings import COLOUR, WIDTH


class ArrowTool(ShapeTool):
    name = "arrow"
    label = "Arrow"
    icon_text = "↗"
    settings = (COLOUR, WIDTH)

    def make_item(self, start, end, values):
        return Arrow(start, end, values["colour"], values["width"])
```

Then one line in `tools/__init__.py`:

```python
ALL_TOOLS = (RectangleTool, PenTool, ArrowTool)
```

The toolbar button, icon, settings bar, preview, undo entry and inclusion in
the captured image all follow with no further work.

### Settings

Settings are declarative so the bar can render them without knowing which tool
it is serving.

```python
class Setting:
    key, label, default

class ColourSetting(Setting):   # rendered as swatches
    swatches = (...)

class ChoiceSetting(Setting):   # rendered as segmented buttons
    options = ((value, label), ...)
```

Thickness is a `ChoiceSetting` of preset widths (2, 4, 8, 16 px) drawn as dots
of increasing size, not a slider — easier to hit, and the sizes that matter are
few.

Two shared instances live in `settings.py` so every tool that wants them gets
consistent behaviour:

```python
COLOUR = ColourSetting("colour", "Colour", default=RED, swatches=PALETTE)
WIDTH  = ChoiceSetting("width", "Width", default=4, options=((2,"S"),(4,"M"),(8,"L"),(16,"XL")))
```

**Values are shared by key, not per tool.** Choosing red for the pen means the
arrow is also red. That is nearly always what people expect, and it halves the
state.

### Icons

Requiring cairo for an icon is a barrier for someone adding a tool. So
`icon_text` renders a centred glyph, and `draw_icon()` stays available for
anything that wants to draw properly. The existing Rectangle icon keeps its
drawn dashed outline; Pen can start as a glyph.

## Capture pipeline

Annotations have to be baked into the output. `Overlay.run()` currently returns
a `Rect` and `cli.select_region()` crops. That boundary moves: **the overlay
returns a finished pixbuf**, because only it knows about the scene.

```
frozen surface  ->  ImageSurface at physical resolution
                    cr.scale(scale, scale)          # so items draw in logical coords
                    paint frozen screen
                    draw every item in order
                    crop to scene.region, or the whole screen if None
                 -> Gdk.pixbuf_get_from_surface()
```

The `scale` factor already exists on the overlay for HiDPI; items are authored
in logical pixels and scaled once at bake time.

### Draw order on screen

1. frozen screen
2. dim wash
3. if a region exists, repaint it undimmed
4. every committed item, at full brightness
5. region outline, handles, size readout
6. main toolbar, then the settings bar
7. the active tool's `preview()`

Annotations are drawn everywhere, not clipped to the region, so you can see
what you have drawn; the region outline is what tells you what will be kept.

## Files

| File | Change |
| --- | --- |
| `scene.py` | new — region, items, undo/redo |
| `actions.py` | new — `Action`, `AddItem`, `SetRegion` |
| `settings.py` | new — `Setting` types, shared `COLOUR`/`WIDTH`, value store |
| `tools/__init__.py` | new — `ALL_TOOLS` registry |
| `tools/base.py` | new — `Tool`, `ShapeTool` |
| `tools/items.py` | new — `Item` and the drawable shapes |
| `tools/rectangle.py` | ported from `tools.py`; now produces `SetRegion` |
| `tools/pen.py` | new — freehand stroke |
| `tools.py` | removed, replaced by the package |
| `toolbar.py` | add the settings row and its generic renderers |
| `overlay.py` | route through the scene; undo keys; return a pixbuf |
| `cli.py` | `select_region()` takes the overlay's pixbuf directly |
| `theme.py` | palette, settings-bar metrics |

## Risks

**Redraw cost is the real one.** Every motion event currently calls
`queue_draw()`, repainting the whole 5360×1440 overlay. Rectangle drags survive
that; freehand generates far more motion events and will not. Two mitigations,
in order:

1. `queue_draw_area()` over the changed bounds instead of the whole window.
2. Cache committed items on their own surface, so a drag only repaints the
   in-progress stroke.

Start with (1); (2) if it is still not smooth. This should be measured on the
5360×1440 layout, not a single monitor.

**Capture semantics change.** "Capture is inert with nothing selected" is an
existing passing test and becomes wrong — it must be replaced with "Capture
with nothing selected takes the whole screen", not deleted quietly.

**The settings bar grows the dead zone.** The toolbar is already not a drawing
surface; a second row makes that strip about 86 px. Dragging upward from below
into it still works, as now.

## Testing

Existing suites stay green, with the one deliberate change noted above.

New coverage:

- **Scene**: apply, undo, redo, redo cleared by a new action.
- **Settings**: defaults, shared-by-key values, bar hit testing.
- **Pen**: a drag produces one stroke carrying the colour and width that were
  active when it started.
- **Bake**: an annotated capture contains the annotation, and cropping to a
  region keeps the right pixels.
- **Extensibility** — the one that matters. A toy tool defined *inside the
  test* must appear on the toolbar, receive events, commit an item, undo, and
  land in the captured image, with no core file touched. If that test needs a
  core change to pass, the framework has failed its purpose.

## Delivery

Sequenced so each step is reviewable and leaves the tool working.

1. `Scene`, `Action`, and the `Tool`/`ShapeTool` base; port Rectangle. Only
   visible change: Capture is always enabled.
2. Settings model and the settings bar, with Rectangle declaring none.
3. Pen tool with colour and width.
4. Undo/redo and its keys.
5. Docs: README "adding a tool" section, man page, `--help`.

## Later

Deliberately out of this change, listed so they are not forgotten:

- Remember colour and width between runs.
- Arrow, ellipse, line, text, blur, numbered steps — each a file plus a
  registry line, if this plan works.
- Object selection and editing.
- A settings-bar overflow behaviour for tools with many options.
