"""Machine state: things the program worked out, not things you chose.

Kept apart from preferences.json deliberately. That file holds decisions —
where screenshots go, which toolbar you like — and is reasonable to open and
edit. This one holds bookkeeping: when we last asked GitHub about a release,
which version we already mentioned. Mixing the two would mean hand-editing
your settings around machine chatter.

Missing, unreadable or malformed all mean the same thing: nothing is known
yet. Nothing here is worth failing a screenshot over.
"""

import json
import os

from gi.repository import GLib


def path():
    return os.path.join(
        GLib.get_user_config_dir(), "programmers-screenshot", "state.json"
    )


def load():
    try:
        with open(path(), "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def save(values):
    target = path()
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(values, handle, indent=2, sort_keys=True)
    except OSError:
        pass  # bookkeeping; never worth interrupting anything for


def remember(**changes):
    """Update some keys, leaving the rest alone."""
    values = load()
    values.update(changes)
    save(values)
    return values
