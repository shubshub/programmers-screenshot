"""The full-screen overlay: a frozen screenshot you mark up and then capture.

The screen is captured before this window appears and painted back as the
background, so menus and animations hold still while you work. Nothing is
captured until the Capture button (or Enter) says so; until then the tools
just build up a scene.
"""

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import capture, painting, preferences, theme, toolbar as toolbar_module
from .geometry import Rect, union
from .actions import SetRegion
from .scene import Scene
from .settings import SettingValues

HINT = "Drag to mark a region  ·  Enter or Capture takes it  ·  Esc to cancel"

GRAB_RETRY_MS = 50
GRAB_ATTEMPTS = 20
DAMAGE_MARGIN = 8  # px of slack round a partial redraw


def _shift_held(event):
    """Whether Shift was down for a pointer event, which constrains a drag."""
    return bool(event.state & Gdk.ModifierType.SHIFT_MASK)


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


class Overlay:
    """Runs a modal session and returns the captured pixbuf, or None."""

    def __init__(self, pixbuf, bounds, tools):
        self.pixbuf = pixbuf
        self.bounds = bounds
        self.scale = capture.pixel_scale(pixbuf, bounds)

        self.tools = tools
        self.active_tool = tools[0]
        self.scene = Scene()
        self.values = SettingValues()

        self.result = None
        self._surface = None
        self.pointer = None
        self._dragging = False
        self._pressed_button = None
        self._last_damage = None
        self._grab_attempts = 0

        self.window = self._build_window()
        # A bar on every monitor, so the controls are wherever you are looking.
        # The one the pointer started on comes first and counts as primary.
        self.monitors = self._overlay_monitors()
        self.monitor = self.monitors[0]
        self.toolbars = toolbar_module.Toolbars(tools, self.monitors, self.values)

    # -- setup -------------------------------------------------------------

    def _build_window(self):
        display = Gdk.Display.get_default()
        # An override-redirect window can be placed exactly, which matters on
        # multi-monitor X11. Wayland allows neither, so settle for fullscreen.
        on_x11 = capture.is_x11(display)
        window = Gtk.Window(
            type=Gtk.WindowType.POPUP if on_x11 else Gtk.WindowType.TOPLEVEL
        )
        window.set_app_paintable(True)
        window.set_decorated(False)
        window.set_keep_above(True)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_default_size(int(self.bounds.width), int(self.bounds.height))

        if on_x11:
            window.move(int(self.bounds.x), int(self.bounds.y))
            window.resize(int(self.bounds.width), int(self.bounds.height))
        else:
            window.fullscreen()

        window.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
        )
        window.connect("realize", self._on_realize)
        window.connect("map-event", self._on_map)
        window.connect("draw", self._on_draw)
        window.connect("button-press-event", self._on_press)
        window.connect("button-release-event", self._on_release)
        window.connect("motion-notify-event", self._on_motion)
        window.connect("key-press-event", self._on_key)
        window.connect("destroy", lambda *_: Gtk.main_quit())
        return window

    def _overlay_monitors(self):
        """Every monitor in overlay coordinates, the pointer's one first."""
        display = Gdk.Display.get_default()
        x, y = capture.pointer_position(display)
        offset = (-self.bounds.x, -self.bounds.y)
        active = capture.monitor_at(display, x, y).translated(*offset)
        monitors = [rect.translated(*offset) for rect in capture.monitor_rects(display)]
        if not monitors:
            return [active]
        monitors.sort(key=lambda rect: rect != active)  # stable: active first
        return monitors

    def run(self):
        self.window.show_all()
        Gtk.main()
        return self.result

    # -- window plumbing ---------------------------------------------------

    @property
    def surface(self):
        """The frozen screen as a cairo surface.

        Made on demand rather than at realize time, so that rendering does not
        depend on the window having been mapped first.
        """
        if self._surface is None:
            self._surface = Gdk.cairo_surface_create_from_pixbuf(self.pixbuf, 1, None)
        return self._surface

    def _on_realize(self, widget):
        # Remake it against the window, which lets X keep it server-side.
        self._surface = Gdk.cairo_surface_create_from_pixbuf(
            self.pixbuf, 1, widget.get_window()
        )
        self._set_cursor("crosshair")

    def _on_map(self, widget, event):
        self._grab_attempts = 0
        GLib.idle_add(self._take_grab)
        return False

    def _take_grab(self):
        """Own the pointer and keyboard. The hotkey that launched us may still
        hold a grab, so retry briefly before giving up and running without."""
        seat = self.window.get_display().get_default_seat()
        status = seat.grab(
            self.window.get_window(),
            Gdk.SeatCapabilities.ALL,
            True,
            self._cursor("crosshair"),
            None,
            None,
            None,
        )
        if status == Gdk.GrabStatus.SUCCESS:
            return False
        self._grab_attempts += 1
        if self._grab_attempts < GRAB_ATTEMPTS:
            GLib.timeout_add(GRAB_RETRY_MS, self._take_grab)
        return False

    def _cursor(self, name):
        return Gdk.Cursor.new_from_name(self.window.get_display(), name)

    def _set_cursor(self, name):
        gdk_window = self.window.get_window()
        if gdk_window is not None:
            gdk_window.set_cursor(self._cursor(name))

    def _finish(self, result):
        self.result = result
        self.window.get_display().get_default_seat().ungrab()
        self.window.destroy()

    def canvas(self):
        return Canvas(self.surface, self.bounds, self.scale, self.scene)

    # -- intent ------------------------------------------------------------

    def capture_region(self):
        """What Capture would take: the region, or everything."""
        return self.scene.region or Rect(0, 0, self.bounds.width, self.bounds.height)

    def _capture_now(self):
        # Anything half-finished has to join the scene first: render() draws
        # the scene and nothing else, so uncommitted work would be missing
        # from the image.
        self.scene.do(self.active_tool.commit())
        self._finish(self.render())

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

    def _choose_tool(self, tool):
        if tool is self.active_tool:
            return
        self.scene.do(self.active_tool.commit())
        self.active_tool.cancel()
        self.active_tool = tool
        self.toolbars.show_settings_for(tool)
        self.window.queue_draw()

    def _activate(self, button):
        if button.kind == toolbar_module.TOOL:
            self._choose_tool(button.tool)
        elif button.kind == toolbar_module.CAPTURE:
            self._capture_now()
        elif button.kind == toolbar_module.CANCEL:
            self._finish(None)
        elif button.kind == toolbar_module.SETTINGS:
            self._edit_preferences()
        elif button.kind == toolbar_module.SETTING:
            self.values.set(button.setting, button.value)
            self.active_tool.settings_changed(
                self.values.snapshot(self.active_tool.settings)
            )
            self.window.queue_draw()

    def _edit_preferences(self):
        """Open the settings window, getting out of its way first.

        Two things stop a dialog working over this overlay. It holds a grab on
        the pointer and the keyboard, so a window opened underneath it gets no
        events. And on X11 the overlay is override-redirect: it bypasses the
        window manager and sits above everything, so a dialog opened over it
        maps for a frame and is then buried, leaving the program apparently
        frozen in the dialog's own event loop with no reachable way out.

        Neither is worth fighting. Drop the grab, hide the overlay for as long
        as the window is up, and put it back afterwards. The screen underneath
        is a still image either way, so there is nothing to see meanwhile.
        Showing the window again re-runs map-event, which retakes the grab.
        """
        self.window.get_display().get_default_seat().ungrab()
        self.window.hide()
        try:
            preferences.edit()
        finally:
            self.window.show()
        # The pointer was elsewhere the whole time, so any hover is stale.
        self.toolbars.set_hover(-1, -1)
        self.window.queue_draw()

    # -- input -------------------------------------------------------------

    def _on_press(self, widget, event):
        if event.button != 1:
            self._finish(None)
            return True

        if self.toolbars.covers(event.x, event.y):
            # Remember which button went down so a press-then-drag-away does
            # not fire it; the release decides.
            self._pressed_button = self.toolbars.button_at(event.x, event.y)
            return True

        self._pressed_button = None
        # Clicking away is how a tool with lingering state is told it is done.
        self.scene.do(self.active_tool.commit())

        # Starting a new region drops the old one there and then. Leaving it
        # on the scene meant it stayed drawn nowhere near the new gesture, and
        # the new drag appeared to rub it out as it swept across.
        dropped = self.active_tool.sets_region and self.scene.region is not None
        if dropped:
            self.scene.do(SetRegion(None))

        was_idle = self._idle()
        self._dragging = True
        self._last_damage = None
        # Some tools need to read the frozen screen when the gesture ends, and
        # only drawing is handed a canvas. Give them one for the whole gesture.
        self.active_tool.canvas = self.canvas()
        self.active_tool.begin(
            (event.x, event.y), self.values.snapshot(self.active_tool.settings)
        )
        if was_idle or dropped:
            # The hint, the guides and the old region all sit outside any
            # damage the gesture will report, so repaint the lot once.
            self.window.queue_draw()
        else:
            self._redraw_gesture()
        return True

    def _on_motion(self, widget, event):
        previous = self.pointer
        self.pointer = (event.x, event.y)

        if self._dragging:
            self.active_tool.extend((event.x, event.y), _shift_held(event))
            self._redraw_gesture()
            return True

        over_bar = self.toolbars.covers(event.x, event.y)
        self._set_cursor("default" if over_bar else "crosshair")
        if self.toolbars.set_hover(event.x, event.y):
            widget.queue_draw()
        else:
            self._redraw_guides(previous)
        return True

    def _redraw_guides(self, previous):
        """Move the crosshair without repainting the whole screen.

        Two thin strips per position: the lines are long but only a few pixels
        thick, so this stays cheap even across a 5360px screen.
        """
        if not self._idle():
            return
        width, height = int(self.bounds.width), int(self.bounds.height)
        for point in (previous, self.pointer):
            if point is None:
                continue
            x, y = int(point[0]), int(point[1])
            self.window.queue_draw_area(0, y - 2, width, 5)
            self.window.queue_draw_area(x - 2, 0, 5, height)

    def _on_release(self, widget, event):
        if event.button != 1:
            return True

        if self._pressed_button is not None:
            button = self._pressed_button
            self._pressed_button = None
            if button.rect.contains(event.x, event.y):
                self._activate(button)
            return True

        if self._dragging:
            self._dragging = False
            self.scene.do(
                self.active_tool.finish((event.x, event.y), _shift_held(event))
            )
            self._last_damage = None
            widget.queue_draw()
        return True

    def _on_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)

        # The active tool gets first refusal. Typing needs Enter and Escape,
        # which would otherwise capture and close.
        if self.active_tool.key_press(key, event.string, control, shift):
            self._redraw_gesture()
            return True

        if control and key in ("z", "Z"):
            changed = self.scene.redo() if shift else self.scene.undo()
            if changed:
                self.window.queue_draw()
            return True
        if control and key in ("y", "Y"):
            if self.scene.redo():
                self.window.queue_draw()
            return True
        if key == "Escape":
            if self._dragging:
                self._dragging = False
                self.active_tool.cancel()
                self.window.queue_draw()
            else:
                self._finish(None)
            return True
        if key in ("Return", "KP_Enter"):
            self._capture_now()
            return True
        return False

    # -- drawing -----------------------------------------------------------

    def _gesture_damage(self):
        """Everything the gesture in progress paints, chrome included."""
        areas = []
        bounds = self.active_tool.bounds()
        if bounds is not None:
            areas.append(bounds)
        pending = self.active_tool.pending_region()
        if pending is not None:
            areas.append(painting.region_damage(pending))
        return union(areas) if areas else None

    def _redraw_gesture(self):
        """Repaint only where the gesture is.

        A full repaint of the virtual screen per motion event is far too slow
        for freehand; the rectangle tool got away with it, the pen does not.
        The previous damage goes in too, so whatever the gesture has just moved
        off gets painted back.
        """
        damage = self._gesture_damage()
        if damage is None:
            self.window.queue_draw()
            return
        area = union([damage, self._last_damage] if self._last_damage else [damage])
        self._last_damage = damage
        self.window.queue_draw_area(
            int(area.x - DAMAGE_MARGIN),
            int(area.y - DAMAGE_MARGIN),
            int(area.width + DAMAGE_MARGIN * 2),
            int(area.height + DAMAGE_MARGIN * 2),
        )

    def _on_draw(self, widget, cr):
        canvas = self.canvas()

        painting.draw_frozen_screen(cr, canvas)
        painting.use(cr, theme.SCREEN_DIM)
        cr.paint()

        # A region being dragged out stands in for the committed one, so that
        # only one area is ever undimmed and the annotations stay on top of it.
        region = self.active_tool.pending_region() or self.scene.region
        if region is not None:
            painting.draw_region(cr, canvas, region)

        for item in self.scene.items:
            item.draw(cr)

        self.active_tool.preview(cr, canvas)

        if self._idle():
            self._draw_guides(cr)
            self._draw_hint(cr)

        self.toolbars.draw(cr, self.active_tool)
        if not self._dragging:
            # Hover is not tracked mid-gesture, so it would be stale.
            self.toolbars.draw_tooltip(cr)
        return True

    def _idle(self):
        """Nothing marked out and nothing in progress: show the guides."""
        return (
            not self._dragging
            and self.scene.region is None
            and not self.scene.items
            and self.active_tool.bounds() is None
        )

    def _draw_guides(self, cr):
        if self.pointer is None or self.toolbars.covers(*self.pointer):
            return
        x, y = self.pointer
        painting.use(cr, theme.GUIDE_LINE)
        cr.set_line_width(1.0)
        cr.move_to(0, y + 0.5)
        cr.line_to(self.bounds.width, y + 0.5)
        cr.move_to(x + 0.5, 0)
        cr.line_to(x + 0.5, self.bounds.height)
        cr.stroke()

    def _draw_hint(self, cr):
        """A one-line reminder, low and centred on every monitor.

        Repeated rather than left on one screen: with a toolbar everywhere,
        a screen with controls but no instructions reads as broken. It goes
        away as soon as anything is marked out.
        """
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_HINT)
        width, height = painting.text_size(cr, HINT)
        pad_x, pad_y = 14, 9
        for monitor in self.monitors:
            box = Rect(
                monitor.x + (monitor.width - width - pad_x * 2) / 2,
                monitor.y + monitor.height * 0.86,
                width + pad_x * 2,
                height + pad_y * 2,
            )
            painting.fill_rounded(cr, box, theme.HINT_BG)
            painting.draw_text(cr, HINT, box.x + pad_x, box.y + pad_y, theme.HINT_TEXT)
