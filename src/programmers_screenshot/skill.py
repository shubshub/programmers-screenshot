"""Installing a skill, so an agent in any session knows this tool is here.

A recipe is no use to something that has never heard of it. The reference is
already written and cannot go stale -- --recipe-help generates it from the
parser's own table -- but nothing points anybody at it, and a session working
in some other project has no reason to guess this program exists.

So the skill is deliberately thin: what the three ways in are, how a browser
tab is done, and "run --recipe-help". Everything that could drift lives in the
generated help rather than in a copy of it that ages on disk.
"""

import os
import shutil
import sys

NAME = "programmers-screenshot"


def directory():
    """Where personal skills live. Replaced wholesale by the tests."""
    return os.path.expanduser(os.path.join("~", ".claude", "skills", NAME))


def path():
    return os.path.join(directory(), "SKILL.md")


def install():
    target = path()
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(SKILL)
    except OSError as error:
        sys.stderr.write("could not write the skill: %s\n" % error)
        return 1
    print(target)
    print("  a new session will offer it when a screenshot is wanted")
    print("  recipes are still off until switched on in the settings window")
    return 0


def uninstall():
    target = path()
    if not os.path.exists(target):
        print("no skill installed at %s" % target)
        return 0
    try:
        os.unlink(target)
        # Only the directory this put there, and only while it is empty:
        # somebody may have added their own notes beside it.
        if not os.listdir(directory()):
            shutil.rmtree(directory())
    except OSError as error:
        sys.stderr.write("could not remove the skill: %s\n" % error)
        return 1
    print("Removed %s" % target)
    return 0


SKILL = '''---
name: programmers-screenshot
description: >-
  Take an annotated screenshot from a description rather than by hand - an area
  of the screen, a named window even when buried, or a picture a browser took
  of a tab - with boxes, arrows, numbered step badges, labels, redaction and
  pixelation drawn into it. Use when asked to capture or screenshot something
  on screen, to point at or circle part of a page or window, or to produce
  documentation images. Linux desktop only.
---

`programmers-screenshot` takes an annotated shot from a JSON recipe, with
nobody at the keyboard.

## Read the reference first

```bash
programmers-screenshot --recipe-help
```

It is generated from the parser's own table, so it is never out of date, and
it covers every mark, every parameter, the coordinate frames and the exit
codes. What is below is only what to know before reading it.

## The three ways in

- `--region X,Y,W,H` - an area of the screen.
- `--window TITLE` - one window, even one completely buried under others.
  Nothing is raised and nothing on top of it gets into the picture.
  `--list-windows` shows what can be named. X11 only.
- `--input FILE --viewport WIDTH` - annotate a picture something else took,
  which is how a browser tab is done.

## A browser tab, with Claude in Chrome

Two tool calls, both from the session that has the Chrome tools connected
(`claude --chrome`, or `/chrome` in a running session). Never shell out to
`claude --chrome -p` for the picture: a nested session can only hand back
prose, so the path and every number has to be parsed out of a paragraph, and
it takes minutes to do what these two take seconds.

1. One `browser_batch`: a `javascript_tool` call returning `window.innerWidth`
   and the `getBoundingClientRect()` of each element wanted, then `computer`
   with `action: "screenshot"` and `save_to_disk: true`. The result names the
   file: `/tmp/claude-chrome-screenshots-*/screenshot-*.jpg`. A JPEG is fine.
   A background tab works; nothing has to be brought to the front.
2. One Bash call, with the rectangles used exactly as they came:

```bash
programmers-screenshot --input <that file> --viewport <innerWidth> -o out.png --no-clipboard --recipe - <<'EOF'
{"annotate": [{"box": [344, 198, 1032, 29], "colour": "red", "width": 3},
              {"step": [332, 212]}]}
EOF
```

`--viewport` is `window.innerWidth`; the scale is worked out from the picture's
own width, so nothing has to open the file to measure it. Ask the page for its
rectangles in the same batch as the screenshot, so the two cannot describe
different scroll positions. `--input` is quiet: no shutter, no notification,
because no screen was read.

Why `--input` and never `--window`: a tab is not a window, and only a
window's front tab is being drawn at all, so a background tab has no pixels on
the screen to photograph. Naming a window only guesses which tab is in front,
is wrong the moment somebody switches tabs, and needs the recipes switch,
which `--input` does not.

## Before it will run

Recipes are off until switched on, in the settings window - the sliders button
on the overlay toolbar. If it refuses, say so and let the person tick it. That
switch is their decision about what may photograph their screen, so do not
look for a way round it.

It reads a real screen, so it wants a live desktop session on this machine.
Over plain ssh, in a container or in CI there is no display and it exits 1.
`--input` reads no screen, but still draws through the same machinery.

## Care

This photographs whatever is really there, which may not be what was expected:
a password manager, somebody's message, a token in a terminal. Prefer a named
window or region to the whole screen, and `redact` anything sensitive in the
same recipe - a redaction replaces the pixels, so nothing of the original
reaches the PNG. Pixelation only averages them, and averages leak.

The shutter still sounds, which is how the person at the desk knows a shot was
taken. Pass `--no-clipboard` unless replacing what they last copied is meant.
'''
