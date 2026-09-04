"""Undoable changes to the scene.

Undo works over actions rather than over items, so that setting the capture
region is undoable on exactly the same footing as drawing a stroke.
"""


class Action:
    """Something that happened to the scene, and can be taken back."""

    def apply(self, scene):
        raise NotImplementedError

    def revert(self, scene):
        raise NotImplementedError


class AddItem(Action):
    """Put an annotation on the scene. The common case, by far."""

    def __init__(self, item):
        self.item = item

    def apply(self, scene):
        scene.items.append(self.item)

    def revert(self, scene):
        scene.items.remove(self.item)


class ReplaceItem(Action):
    """Swap a mark for a changed copy of itself.

    How erasing works: the copy carries the holes. Items are cheap to build
    and both the drawing and capture paths assume a mark never changes under
    them, so handing back a new one is less to get wrong than editing in
    place.
    """

    def __init__(self, old, new):
        self.old = old
        self.new = new

    def apply(self, scene):
        scene.items[scene.items.index(self.old)] = self.new

    def revert(self, scene):
        scene.items[scene.items.index(self.new)] = self.old


class RemoveItem(Action):
    """Rub an annotation off the scene, remembering where it sat.

    The position matters: putting it back on the end would move it in front
    of everything drawn after it.
    """

    def __init__(self, item):
        self.item = item
        self._position = None

    def apply(self, scene):
        if self.item not in scene.items:
            # A text edit removes the old item while its replacement is being
            # typed, before this compound action enters the undo history.
            # Keep that already-applied removal idempotent when the action is
            # recorded by Scene.do().
            if self._position is None:
                self._position = scene.items.index(self.item)
            return
        self._position = scene.items.index(self.item)
        scene.items.pop(self._position)

    def revert(self, scene):
        scene.items.insert(self._position, self.item)


class Compound(Action):
    """Several changes that undo as one.

    A drag of the eraser touches whatever it sweeps over. Undoing that one
    mark at a time would mean pressing Ctrl+Z once per thing the drag
    happened to catch, which is not what the gesture felt like.
    """

    def __init__(self, changes):
        self.changes = list(changes)

    def apply(self, scene):
        for change in self.changes:
            change.apply(scene)

    def revert(self, scene):
        # Backwards: a later change may depend on an earlier one having
        # happened, as step renumbering does.
        for change in reversed(self.changes):
            change.revert(scene)


class SetRegion(Action):
    """Change what will be captured. A region of None means the whole screen."""

    def __init__(self, region):
        self.region = region
        self._previous = None

    def apply(self, scene):
        self._previous = scene.region
        scene.region = self.region

    def revert(self, scene):
        scene.region = self._previous
