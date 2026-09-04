"""Machine state: things the program worked out, not things you chose.

Kept apart from preferences.json deliberately. That file holds decisions —
where screenshots go, which toolbar you like — and is reasonable to open and
edit. This one holds bookkeeping: when we last asked GitHub about a release,
which version we already mentioned. Mixing the two would mean hand-editing
your settings around machine chatter.

Missing, unreadable or malformed all mean the same thing: nothing is known
yet. Nothing here is worth failing a screenshot over.
"""

import contextlib

from .paths import config_file, read_json, write_json


def path():
    return config_file("state.json")


def load():
    return read_json(path())


def save(values):
    with contextlib.suppress(OSError):  # bookkeeping; never worth a failure
        write_json(path(), values)


def remember(**changes):
    """Update some keys, leaving the rest alone."""
    values = load()
    values.update(changes)
    save(values)
    return values
