"""Baking a scene into a picture, with nobody watching.

The overlay is one way to build a scene: a person marking things out with a
mouse. Nothing about turning that scene into a PNG needs a window, a toolbar
or a pointer, though, and a recipe has no person behind it at all. That part
lives here, and the overlay owns one of these rather than being one.
"""

import cairo
import gi

gi.require_version("Gdk", "3.0")

from gi.repository import Gdk  # noqa: E402

from . import capture
from .geometry import Rect
from .scene import Scene


class Canvas:
    """What a tool needs in order to paint itself onto the overlay.

    The scene is here so a preview can depend on what has already been placed
    — a step counter has to show the number it is about to take.
    """

    def __init__(self, surface, bounds, scale, scene):
        self.surface = surface
        self.bounds = bounds
        self.scale = scale
        self.scene = scene


class Renderer:
    """A frozen screen, the marks made on it, and the picture that makes."""

    def __init__(self, pixbuf, bounds):
        self.pixbuf = pixbuf
        self.bounds = bounds
        self.scale = capture.pixel_scale(pixbuf, bounds)
        self.scene = Scene()
        self._surface = None

    @property
    def surface(self):
        """The frozen screen as a cairo surface.

        Made on demand rather than at realize time, so that rendering does not
        depend on the window having been mapped first.
        """
        if self._surface is None:
            self._surface = Gdk.cairo_surface_create_from_pixbuf(self.pixbuf, 1, None)
        return self._surface

    @surface.setter
    def surface(self, surface):
        """The overlay hands one over when its window is realized, so that X
        can keep it server-side. Nothing else needs to set it."""
        self._surface = surface

    def canvas(self):
        return Canvas(self.surface, self.bounds, self.scale, self.scene)

    def capture_region(self):
        """What Capture would take: the region, or everything."""
        return self.scene.region or Rect(0, 0, self.bounds.width, self.bounds.height)

    def render(self):
        """Bake the frozen screen plus every annotation into a pixbuf."""
        region = self.capture_region()
        width = max(1, int(round(region.width * self.scale)))
        height = max(1, int(round(region.height * self.scale)))

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
        cr = cairo.Context(surface)

        # The frozen screen is already in physical pixels, so place it in
        # device space; the annotations are in logical pixels, so scale first.
        cr.save()
        cr.translate(-region.x * self.scale, -region.y * self.scale)
        cr.set_source_surface(self.surface, 0, 0)
        cr.paint()
        cr.restore()

        cr.scale(self.scale, self.scale)
        cr.translate(-region.x, -region.y)
        for item in self.scene.items:
            item.draw(cr)
        surface.flush()

        return Gdk.pixbuf_get_from_surface(surface, 0, 0, width, height)
