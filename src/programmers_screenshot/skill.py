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
- `--input FILE --viewport WIDTH --dpr RATIO` - annotate a picture something
  else took, which is how a browser tab is done.

## A browser tab, with Claude in Chrome

Two tool calls, from the session that has the Chrome tools connected
(`claude --chrome`; `/chrome` opens the extension's settings). About two
seconds a shot.

1. One `browser_batch`: a `javascript_tool` call returning `innerWidth`,
   `devicePixelRatio` and the `getBoundingClientRect()` of each element wanted,
   then `computer` with `action: "screenshot"` and `save_to_disk: true`. The
   result names the file, `/tmp/claude-chrome-screenshots-*/screenshot-*.jpg`,
   and its size. A JPEG is fine.
2. One Bash call, with the rectangles used exactly as they came:

```bash
programmers-screenshot --input <that file> --viewport <innerWidth> --dpr <devicePixelRatio> -o out.png --no-clipboard --recipe - <<'EOF'
{"region": [0, 60, 1000, 640],
 "annotate": [{"box": [4, 84, 790, 202], "colour": "red", "width": 3},
              {"step": [20, 100]}]}
EOF
```

The scale is worked out from the picture's own width, the viewport and the
pixel ratio, so nothing has to open the file to measure it. Pass all three: at
a page zoom other than 100% the saved picture is cropped to 1/dpr of the
viewport, and the width alone lands every mark short by that much. Never
estimate a scale by eye from the picture; two different wrong factors each
looked right once. A `region` trims a sticky header. `--input` is quiet: no
shutter, no notification, because no screen was read.

What goes wrong, and what to do instead:

- Do not scroll in the capture batch. A capture straight after a scroll can be
  a stale frame of an earlier position, while the rectangles from the same
  batch describe the final one. If the target is off-screen, rearrange the DOM
  so it is on-screen at `scrollTo(0, 0)` - hide the other rows, move the
  container to the top - then `computer` `wait` 2 seconds, then capture. A
  `Page.captureScreenshot` timeout follows a big DOM change; wait 2 seconds
  and retry once.
- No async wrapper in `javascript_tool`: `(async () => ...)()` comes back as
  `{}`. Top-level `await` works, and synchronous code is safest. Return an
  object or a `JSON.stringify` string.
- A background tab is fine on a light page. On a heavy one it gave blank saves
  and timeouts; use `tabs_create_mcp`, which is active by default, and wait 2
  seconds after navigating.
- If this session was not started with `--chrome` it has no Chrome tools, and
  the fallback is a nested `claude --chrome -p`, at about 75 seconds a shot.
  Script it completely - fixed JavaScript, no page clicks, no scrolling, a
  one-line JSON reply naming the file - and let it decide nothing; a sub-agent
  left to scroll and look is what takes an hour. Name the tools exactly in
  `--allowedTools`: `mcp__claude-in-chrome__tabs_create_mcp`,
  `mcp__claude-in-chrome__navigate`, `mcp__claude-in-chrome__javascript_tool`
  (not `javascript`), `mcp__claude-in-chrome__computer`,
  `mcp__claude-in-chrome__browser_batch`, `mcp__claude-in-chrome__tabs_context_mcp`.

Why `--input` and not `--window`: a tab is not a window, and only a window's
front tab is being drawn at all, so a background tab has no pixels on the
screen to photograph. `--window "... - Google Chrome"` does capture the whole
window perfectly, so it is a fair fallback when the tab can be kept in front
for two seconds; but the front tab changes under you, and it needs the recipes
switch, which `--input` does not.

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
