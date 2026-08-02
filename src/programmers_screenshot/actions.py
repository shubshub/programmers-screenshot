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
