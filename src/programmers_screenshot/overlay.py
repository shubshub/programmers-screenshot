"""The full-screen overlay: a frozen screenshot you draw a selection on.

The screen is captured before this window appears and painted back as the
background, so menus and animations hold still while you work. Nothing is
captured until the Capture button (or Enter) says so.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import capture, painting, theme, toolbar as toolbar_module
from .geometry import Rect
from .tools import Canvas

HINT = "Drag to select  ·  Enter or Capture to take it  ·  Esc to cancel"

GRAB_RETRY_MS = 50
GRAB_ATTEMPTS = 20


class Overlay:
    """Runs a modal selection session and returns the chosen Rect, or None."""

    def __init__(self, pixbuf, bounds, tools):
        self.pixbuf = pixbuf
        self.bounds = bounds
        self.scale = capture.pixel_scale(pixbuf, bounds)

        self.tools = tools
        self.active_tool = tools[0]
        self.result = None
        self.surface = None
        self.pointer = None
        self._dragging = False
        self._pressed_button = None
        self._grab_attempts = 0

        self.window = self._build_window()
        # Everything chrome-related lives on one monitor: the one the pointer
        # was on when the hotkey fired, which is where the user is looking.
        self.monitor = self._active_monitor()
        self.toolbar = toolbar_module.Toolbar(tools, self.monitor)

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

    def _active_monitor(self):
        """The monitor under the pointer, in overlay coordinates."""
        display = Gdk.Display.get_default()
        x, y = capture.pointer_position(display)
        monitor = capture.monitor_at(display, x, y)
        return monitor.translated(-self.bounds.x, -self.bounds.y)

    def run(self):
        self.window.show_all()
        Gtk.main()
        return self.result

    # -- window plumbing ---------------------------------------------------

    def _on_realize(self, widget):
        gdk_window = widget.get_window()
        self.surface = Gdk.cairo_surface_create_from_pixbuf(self.pixbuf, 1, gdk_window)
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

    def _finish(self, rect):
        self.result = rect
        self.window.get_display().get_default_seat().ungrab()
        self.window.destroy()

    # -- intent ------------------------------------------------------------

    def _selection(self):
        return self.active_tool.selection()

    def _can_capture(self):
        return self._selection() is not None

    def _capture_now(self):
        rect = self._selection()
        if rect is not None:
            self._finish(rect)

    def _choose_tool(self, tool):
        if tool is not self.active_tool:
            self.active_tool = tool
            self.window.queue_draw()

    def _activate(self, button):
        if button.kind == toolbar_module.TOOL:
            self._choose_tool(button.tool)
        elif button.kind == toolbar_module.CAPTURE:
            self._capture_now()
        elif button.kind == toolbar_module.CANCEL:
            self._finish(None)

    # -- input -------------------------------------------------------------

    def _on_press(self, widget, event):
        if event.button != 1:
            self._finish(None)
            return True

        if self.toolbar.covers(event.x, event.y):
            # Remember which button went down so a press-then-drag-away does
            # not fire it; the release decides.
            self._pressed_button = self.toolbar.button_at(event.x, event.y)
            return True

        self._pressed_button = None
        self._dragging = True
        self.active_tool.press(event.x, event.y)
        widget.queue_draw()
        return True

    def _on_motion(self, widget, event):
        self.pointer = (event.x, event.y)

        if self._dragging:
            self.active_tool.drag(event.x, event.y)
            widget.queue_draw()
            return True

        over_bar = self.toolbar.covers(event.x, event.y)
        self._set_cursor("default" if over_bar else "crosshair")
        if self.toolbar.set_hover(event.x, event.y):
            widget.queue_draw()
        return True

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
            self.active_tool.release(event.x, event.y)
            widget.queue_draw()
        return True

    def _on_key(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key in ("Escape", "q"):
            self._finish(None)
        elif key in ("Return", "KP_Enter"):
            self._capture_now()
        else:
            return False
        return True

    # -- drawing -----------------------------------------------------------

    def _on_draw(self, widget, cr):
        cr.set_source_surface(self.surface, 0, 0)
        cr.paint()
        painting.use(cr, theme.SCREEN_DIM)
        cr.paint()

        canvas = Canvas(self.surface, self.bounds, self.scale)
        self.active_tool.draw(cr, canvas)

        if self._selection() is None:
            self._draw_guides(cr)
            self._draw_hint(cr)

        self.toolbar.draw(cr, self.active_tool, self._can_capture())
        return True

    def _draw_guides(self, cr):
        if self.pointer is None or self.toolbar.covers(*self.pointer):
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
        """A one-line reminder, low and centred on the active monitor."""
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_HINT)
        width, height = painting.text_size(cr, HINT)
        pad_x, pad_y = 14, 9
        box = Rect(
            self.monitor.x + (self.monitor.width - width - pad_x * 2) / 2,
            self.monitor.y + self.monitor.height * 0.86,
            width + pad_x * 2,
            height + pad_y * 2,
        )
        painting.fill_rounded(cr, box, theme.HINT_BG)
        painting.draw_text(cr, HINT, box.x + pad_x, box.y + pad_y, theme.HINT_TEXT)
