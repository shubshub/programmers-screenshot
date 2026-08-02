"""The state of a selection session, and its undo history."""

from .actions import Action, AddItem


class Scene:
    """What has been marked out so far: an optional region, and annotations.

    Items are drawn, and captured, in the order they were made.
    """

    def __init__(self):
        self.region = None
        self.items = []
        self._done = []
        self._undone = []

    def do(self, change):
        """Apply an Action, or an Item meaning "add this".

        Returns True if anything happened, so callers can skip a redraw when
        a gesture produced nothing.
        """
        action = as_action(change)
        if action is None:
            return False
        action.apply(self)
        self._done.append(action)
        self._undone.clear()
        return True

    def undo(self):
        if not self._done:
            return False
        action = self._done.pop()
        action.revert(self)
        self._undone.append(action)
        return True

    def redo(self):
        if not self._undone:
            return False
        action = self._undone.pop()
        action.apply(self)
        self._done.append(action)
        return True

    @property
    def can_undo(self):
        return bool(self._done)

    @property
    def can_redo(self):
        return bool(self._undone)


def as_action(change):
    """Let a tool return a bare Item and mean "add this to the scene"."""
    if change is None:
        return None
    if isinstance(change, Action):
        return change
    return AddItem(change)
