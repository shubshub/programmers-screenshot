"""A screenshot described as JSON, so something other than a person can take one.

The overlay is a person marking out a region with a mouse. Everything under it
-- the scene, the items, the renderer -- works just as well with nobody there,
so a recipe is a way of saying what a person would have drawn:

    {"region": [100, 100, 900, 500],
     "annotate": [{"box": [150, 150, 350, 150]},
                  {"arrow": [[650, 420], [520, 310]]}]}

Coordinates are logical pixels, measured from the top left corner of whatever
is being captured: the named window with --window, or the whole virtual screen
without it. The scene works relative to the captured pixbuf, so coordinates
are shifted by its bounds on the way in -- nothing on a single monitor, and
1920 of it on a desk with a screen to the left.

Nothing is drawn until the whole recipe has been understood: a bad entry
raises RecipeError with the entry named, rather than leaving half a shot.
"""

import collections
import json
import sys

from . import theme
from .actions import SetRegion
from .geometry import Rect
from .settings import COLOUR, WIDTH
from .tools import items
from .tools.pixelate import BLOCK, Pixelation, shrink
from .tools.step import SIZE as STEP_SIZE, AddStep, Step
from .tools.text import SIZE as TEXT_SIZE, TextBlock


class RecipeError(ValueError):
    """The recipe could not be understood. Nothing has been drawn."""


#: What a recipe may say at the top level.
KEYS = ("input", "window", "origin", "scale", "viewport", "region", "delay",
        "output", "annotate")

#: What an entry may carry besides the shape itself. One set for all of them:
#: the mistake worth catching is a misspelling, not a width on a step badge.
PARAMS = ("colour", "width", "size", "block", "text", "background")

COLOURS = collections.OrderedDict(
    zip((name.lower() for name in theme.PALETTE_NAMES), theme.PALETTE)
)


# -- reading the numbers ----------------------------------------------------

def _numbers(value, count, where):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise RecipeError(
            "%s: expected %d numbers, got %s" % (where, count, json.dumps(value))
        )
    for number in value:
        # bool is an int, and [true, 0, 4, 4] is a mistake worth naming.
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise RecipeError("%s: %s is not a number" % (where, json.dumps(number)))
    return [float(number) for number in value]


def _rect(value, where, frame):
    x, y, width, height = _numbers(value, 4, where)
    if width <= 0 or height <= 0:
        raise RecipeError("%s: width and height must be more than zero" % where)
    left, top = frame.at(x, y)
    return Rect(left, top, *frame.span(width, height))


def _point(value, where, frame):
    x, y = _numbers(value, 2, where)
    return frame.at(x, y)


def _ends(value, where, frame):
    ends = value if isinstance(value, (list, tuple)) else []
    if len(ends) != 2 or not all(isinstance(end, (list, tuple)) for end in ends):
        raise RecipeError(
            "%s: expected two points, [[x, y], [x, y]], got %s"
            % (where, json.dumps(value))
        )
    return [_point(end, where, frame) for end in ends]


def _colour(entry, where, default=None):
    name = entry.get("colour")
    if name is None:
        return COLOURS[default] if default else COLOUR.default
    if isinstance(name, str) and name.lower() in COLOURS:
        return COLOURS[name.lower()]
    raise RecipeError(
        "%s: no colour called %s -- try one of %s"
        % (where, json.dumps(name), ", ".join(COLOURS))
    )


def _size(entry, key, default, where):
    value = entry.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise RecipeError(
            "%s: %s should be a number more than zero, not %s"
            % (where, key, json.dumps(value))
        )
    return float(value)


# -- turning an entry into an item ------------------------------------------

def _corners(kind, colour=None):
    """Box, ellipse and redaction: a rectangle given as [x, y, width, height]."""
    def build(value, entry, where, canvas, frame):
        rect = _rect(value, where, frame)
        return kind(
            (rect.x, rect.y), (rect.right, rect.bottom),
            _colour(entry, where, colour),
            _size(entry, "width", WIDTH.default, where),
        )
    return build


def _between(kind):
    """Line and arrow: two points, the mark running from the first to the
    second. An arrow's head lands on the second, which is the end that
    points at the thing."""
    def build(value, entry, where, canvas, frame):
        start, end = _ends(value, where, frame)
        return kind(
            start, end,
            _colour(entry, where),
            _size(entry, "width", WIDTH.default, where),
        )
    return build


def _step(value, entry, where, canvas, frame):
    return AddStep(Step(
        _point(value, where, frame),
        _colour(entry, where),
        _size(entry, "size", STEP_SIZE.default, where),
    ))


def _label(value, entry, where, canvas, frame):
    """A label is placed by "label" and worded by "text": one key cannot be
    both the point and the string."""
    words = entry.get("text")
    if not isinstance(words, str) or not words:
        raise RecipeError('%s: a label needs a "text" string to draw' % where)
    return TextBlock(
        _point(value, where, frame),
        words.split("\n"),
        _colour(entry, where),
        _size(entry, "size", TEXT_SIZE.default, where),
        bool(entry.get("background", False)),
    )


def _pixelate(value, entry, where, canvas, frame):
    rect = _rect(value, where, frame)
    block = _size(entry, "block", BLOCK.default, where)
    return Pixelation(rect, shrink(canvas, rect, block), block)


Entry = collections.namedtuple("Entry", "shape build doc")

RECT = "[x, y, width, height]"
ENDS = "[[x, y], [x, y]]"
POINT = "[x, y]"

#: Every mark a recipe can ask for. The table is what --recipe-help prints,
#: so the reference cannot drift from what the parser accepts.
ENTRIES = collections.OrderedDict((
    ("box", Entry(RECT, _corners(items.Box), "a rectangle outline")),
    ("ellipse", Entry(RECT, _corners(items.Ellipse),
                      "an outline inscribed in the rectangle")),
    ("line", Entry(ENDS, _between(items.Line), "a straight line")),
    ("arrow", Entry(ENDS, _between(items.Arrow),
                    "a line with its head on the second point")),
    ("step", Entry(POINT, _step,
                   "the next numbered badge, 1, 2, 3 as they are placed")),
    ("label", Entry(POINT, _label,
                    'words, top left at the point; needs "text" as well')),
    ("redact", Entry(RECT, _corners(items.Redaction, "black"),
                     "a solid block; the pixels underneath do not survive")),
    ("pixelate", Entry(RECT, _pixelate,
                       "the screen underneath, coarsened into blocks")),
))


def build(entry, where, canvas, frame):
    """One entry as a scene change. Raises RecipeError, having drawn nothing."""
    if not isinstance(entry, dict):
        raise RecipeError(
            "%s: expected an object naming a mark, got %s" % (where, json.dumps(entry))
        )
    named = [key for key in entry if key in ENTRIES]
    if len(named) != 1:
        raise RecipeError(
            "%s: name exactly one mark out of %s" % (where, ", ".join(ENTRIES))
        )
    name = named[0]
    unknown = [key for key in entry if key != name and key not in PARAMS]
    if unknown:
        raise RecipeError(
            "%s: %s does not take %s; it takes %s"
            % (where, name, ", ".join(sorted(unknown)), ", ".join(PARAMS))
        )
    return ENTRIES[name].build(entry[name], entry, where, canvas, frame)


# -- the recipe as a whole --------------------------------------------------

def load(source):
    """Read and check a recipe. `source` is a path, or "-" for standard input.

    Deliberately callable before the screen is touched: a recipe that cannot
    be understood should fail without a shutter going off.
    """
    try:
        if source == "-":
            text = sys.stdin.read()
        else:
            with open(source, "r", encoding="utf-8") as handle:
                text = handle.read()
    except OSError as error:
        raise RecipeError("cannot read the recipe: %s" % error)
    return parse(text)


def parse(text):
    try:
        spec = json.loads(text)
    except ValueError as error:
        raise RecipeError("the recipe is not valid JSON: %s" % error)
    if not isinstance(spec, dict):
        raise RecipeError("the recipe should be a JSON object, with %s in it"
                          % ", ".join(KEYS))
    unknown = [key for key in spec if key not in KEYS]
    if unknown:
        raise RecipeError(
            "the recipe does not take %s; it takes %s"
            % (", ".join(sorted(unknown)), ", ".join(KEYS))
        )
    delay = spec.get("delay")
    if delay is not None and (
        isinstance(delay, bool) or not isinstance(delay, (int, float)) or delay < 0
    ):
        raise RecipeError("delay: expected seconds, got %s" % json.dumps(delay))
    if spec.get("origin") is not None:
        numbers(spec["origin"], 2, "origin")
    for key in ("scale", "viewport"):
        value = spec.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0
        ):
            raise RecipeError("%s: expected a number more than zero, got %s"
                              % (key, json.dumps(value)))
    for key in ("output", "window", "input"):
        if spec.get(key) is not None and not isinstance(spec[key], str):
            raise RecipeError("%s: expected a string, got %s"
                              % (key, json.dumps(spec[key])))
    annotate = spec.get("annotate")
    if annotate is not None and not isinstance(annotate, list):
        raise RecipeError("annotate: expected a list of marks, got %s"
                          % json.dumps(annotate))
    return spec


def numbers(value, count, where):
    """A list of numbers from JSON, or from a comma-separated flag."""
    if isinstance(value, str):
        parts = value.split(",")
        if len(parts) != count:
            raise RecipeError(
                "%s: expected %d numbers separated by commas, got %r"
                % (where, count, value)
            )
        try:
            value = [float(part) for part in parts]
        except ValueError:
            raise RecipeError("%s: those are not all numbers: %r" % (where, value))
    return _numbers(value, count, where)


class Frame:
    """How a caller's numbers become coordinates on the capture.

    A caller works in whatever frame suits it -- a page's own coordinates, in
    a picture that may not be at the page's own size -- and this is the single
    place that turns those into coordinates on what was actually captured.
    Every number on the way in goes through it, so nothing else has to know
    that the caller was not using the same ruler.
    """

    def __init__(self, bounds, origin=None, scale=None):
        self.bounds = bounds
        self.origin = numbers(origin, 2, "origin") if origin else (0.0, 0.0)
        self.scale = float(scale) if scale else 1.0

    def at(self, x, y):
        return (
            x * self.scale + self.origin[0] - self.bounds.x,
            y * self.scale + self.origin[1] - self.bounds.y,
        )

    def span(self, width, height):
        return (width * self.scale, height * self.scale)


def region(value, frame):
    """A SetRegion for [x, y, w, h] or the "X,Y,W,H" of --region."""
    return SetRegion(_rect(numbers(value, 4, "region"), "region", frame))


def annotate(spec, overlay, frame):
    """Draw a loaded recipe's marks onto an overlay's scene.

    The region is not applied here: a recipe's region and --region are merged
    in the caller, along with its output and its delay, so that "a flag wins"
    is decided in one place.

    Every mark is built before any of them is applied, so a mistake in the
    last arrow does not leave the first three drawn.
    """
    canvas = overlay.canvas()
    changes = []
    for index, entry in enumerate(spec.get("annotate") or []):
        changes.append(build(entry, "annotate[%d]" % index, canvas, frame))
    for change in changes:
        overlay.scene.do(change)


# -- telling a caller what it can ask for -----------------------------------

def describe():
    """The whole capability, as text, for whoever is driving this.

    Printed by --recipe-help. Generated from the same table the parser uses,
    because a reference that is written out by hand goes stale.
    """
    marks = "\n".join(
        "  %-9s %-18s %s" % (name, entry.shape, entry.doc)
        for name, entry in ENTRIES.items()
    )
    return TEMPLATE % {
        "marks": marks,
        "colours": ", ".join(COLOURS),
        "params": ", ".join(PARAMS),
    }


TEMPLATE = """\
programmers-screenshot can take an annotated screenshot from a description,
with nobody at the keyboard. Three ways in, smallest first:

  programmers-screenshot --region X,Y,W,H -o shot.png --no-clipboard
  programmers-screenshot --window "Google Chrome" -o shot.png --no-clipboard
  programmers-screenshot --input tab.png -o shot.png --no-clipboard
  programmers-screenshot --recipe - -o shot.png --no-clipboard  < recipe.json

--list-windows prints the window titles --window can pick from. --delay N
waits before the screen is read, so a menu or a hover can be set up first.
--input annotates a picture something else took, which is how a browser tab
gets done; see WORKING FROM A BROWSER below.

The path written is printed on stdout. Exit 0 captured, 1 cancelled or no
display, 2 bad usage or a recipe that could not be understood -- in which case
nothing was captured and nothing was drawn.

COORDINATES
  Logical pixels from the top left corner of what is being captured, and
  never relative to the region:

    with --input      (0, 0) is the top left of that picture
    with --window     (0, 0) is the window's own top left corner. That
                      includes the invisible shadow a window draws around
                      itself -- 16 px of it on the browser measured here --
                      so a window is not the same rectangle as it looks
    with neither      (0, 0) is the top left of the whole virtual screen,
                      which is the frame a window manager reports in

  Two adjustments, for when the numbers to hand are in some other frame:

    --origin X,Y      call that point (0, 0) instead of the corner
    --scale FACTOR    the picture holds this many of its pixels per one of
                      yours, so a browser screenshot 1242 px wide of a 1720 px
                      viewport is --scale 0.7221
    --viewport WIDTH  or say the picture shows a page this many logical pixels
                      wide (window.innerWidth) and the scale is worked out
                      from the picture's own width; --scale wins if both given

  They move where marks land. None of them touches how marks are drawn: a
  width of 4 is 4 pixels of the picture, whatever ruler the coordinates came
  in on.

RECIPE
  A JSON object. Every key is optional.

    {
      "input":    "tab.png",               annotate this instead of capturing
      "window":   "Google Chrome",         or name a window; or neither, for
                                           the whole screen
      "origin":   [x, y],                  move where coordinates start
      "scale":    0.7221,                  picture pixels per one of yours
      "viewport": 1720,                    or the page width the picture shows
      "region":   [x, y, width, height],   all of it if left out
      "delay":    2,                       seconds to wait before capturing
      "output":   "docs/img/save.png",     -o wins over this
      "annotate": [ ... marks ... ]
    }

MARKS
  One mark per object, named by its key:

%(marks)s

  Alongside the mark, an entry may carry: %(params)s
    colour      %(colours)s
    width       stroke thickness, px             (default 4)
    size        step badge radius, or label size (defaults 15 and 20)
    block       pixelate block size, px          (default 14)
    text        what a label says; \n starts a new line
    background  true puts the text on a white box

  An example that marks a button and points at it:

    {"region": [100, 100, 900, 500],
     "annotate": [
       {"box": [150, 150, 350, 150], "colour": "red", "width": 4},
       {"arrow": [[650, 420], [520, 310]]},
       {"step": [200, 200]},
       {"label": [200, 480], "text": "Press Save", "background": true},
       {"redact": [160, 330, 300, 40]}
     ]}

WORKING FROM A BROWSER
  Let the browser take the picture, and annotate that.

  Nothing outside a browser can address a tab. A tab is not a window, and
  only the front tab of a window is being drawn at all, so a background tab
  has no pixels anywhere on the screen to photograph. Any attempt to find one
  from out here -- by window title, or by having the page mark itself in some
  colour -- is really a guess about which tab happens to be in front, and it
  is wrong the moment somebody switches tabs. A browser can capture the tab
  it means, front or not. So let it:

    1. the browser screenshots the tab, to a file
    2. --input that file, with --viewport for window.innerWidth (or --scale
       for the size it came out at)
    3. every coordinate is then the page's own, out of
       getBoundingClientRect(), with nothing to convert

    {"input": "tab.jpg",
     "viewport": 1720,
     "region": [300, 170, 1130, 180],
     "annotate": [{"box": [344, 198, 1032, 29]},
                  {"step": [332, 212]}]}

  With Claude in Chrome that is two tool calls, both from the session that
  has the Chrome tools connected (claude --chrome): one browser_batch holding
  a javascript_tool call for window.innerWidth and the rectangles, then
  computer with action "screenshot" and save_to_disk true, which names the
  file it wrote under /tmp/claude-chrome-screenshots-*/ -- a JPEG, which is
  fine, and of a background tab if that is the one asked for. Then one Bash
  call running the recipe above. Do not shell out to claude --chrome -p for
  the picture: a nested session can only hand back prose, and takes minutes
  to do what these two take seconds.

  Ask the page for the rectangles you want in the same breath as the
  screenshot, so the two cannot describe different scroll positions.

  --window is still the way to photograph a whole browser window as it really
  looks -- chrome, tabs and all, buried under everything else -- but for
  anything inside the page, the picture the browser took is the one that is
  certainly of the right tab.

REQUIREMENTS
  A live desktop session on this machine: it reads the actual screen. Over
  plain ssh, in a container or in CI there is no display and it exits 1.
  Under Wayland the capture goes through GNOME's screenshot interface, and
  --window does not work at all -- no program there may read another's
  window. It needs X11, and libwnck (gir1.2-wnck-3.0).

  --input still reads the screen not at all, but it draws through the same
  machinery as everything else and so still wants a display. It is quiet: no
  shutter and no notification, because nothing was photographed.
  A run takes a fraction of a second.

  Off until switched on: tick "Let a recipe drive captures" in the settings
  window (the sliders button on the overlay toolbar).

WORTH KNOWING
  This photographs whatever is really there, which may not be what you expect:
  a password manager, somebody's message, a token in a terminal. Name a window
  or a region rather than taking the whole screen, and redact anything
  sensitive in the same recipe -- redact replaces the pixels, so nothing of
  the original reaches the PNG. Pixelate only averages them, and averages
  leak.

  The shutter sound plays, so the person at the desk knows a shot was taken.
  Pass --no-clipboard unless you mean to replace what they last copied.\
"""
