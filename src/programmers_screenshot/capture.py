"""Getting pixels off the screen, on X11 and on Wayland."""

import os
import tempfile

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, Gio, GLib  # noqa: E402

from .geometry import Rect, union


class CaptureError(RuntimeError):
    """The screen could not be read at all."""


def is_x11(display):
    return type(display).__name__.startswith("X11")


def monitor_rects(display):
    return [
        Rect.from_geometry(display.get_monitor(i).get_geometry())
        for i in range(display.get_n_monitors())
    ]


def screen_bounds(display):
    """The virtual screen: one rectangle covering every monitor."""
    monitors = monitor_rects(display)
    if monitors:
        return union(monitors)
    root = Gdk.get_default_root_window()
    return Rect(0, 0, root.get_width(), root.get_height())


def monitor_at(display, x, y):
    """The monitor containing a point, falling back to the primary one."""
    monitor = display.get_monitor_at_point(int(x), int(y))
    if monitor is None:
        monitor = display.get_primary_monitor() or display.get_monitor(0)
    return Rect.from_geometry(monitor.get_geometry())


def pointer_position(display):
    _screen, x, y = display.get_default_seat().get_pointer().get_position()
    return x, y


def capture_screen(display):
    """Grab the whole virtual screen. Returns (pixbuf, bounds)."""
    bounds = screen_bounds(display)
    pixbuf = _grab_from_root(bounds) if is_x11(display) else None
    if pixbuf is None:
        pixbuf = _grab_from_gnome_shell()
    if pixbuf is None:
        raise CaptureError(
            "could not capture the screen: no X11 root access, and "
            "org.gnome.Shell.Screenshot is unavailable"
        )
    return pixbuf, bounds


def pixel_scale(pixbuf, bounds):
    """Physical pixels per logical pixel, so crops land in the right place."""
    if not bounds.width:
        return 1.0
    return pixbuf.get_width() / float(bounds.width)


def crop(pixbuf, rect, scale):
    """Cut a logical-pixel rectangle out of a physical-pixel pixbuf."""
    whole = Rect(0, 0, pixbuf.get_width(), pixbuf.get_height())
    region = rect.scaled(scale).rounded().clipped_to(whole)
    if not region:
        return None
    source = GdkPixbuf.Pixbuf.new_subpixbuf(
        pixbuf, int(region.x), int(region.y), int(region.width), int(region.height)
    )
    return source.copy()


def _grab_from_root(bounds):
    root = Gdk.get_default_root_window()
    return Gdk.pixbuf_get_from_window(
        root, int(bounds.x), int(bounds.y), int(bounds.width), int(bounds.height)
    )


def _grab_from_gnome_shell():
    """Wayland has no root window; ask the compositor instead."""
    handle, path = tempfile.mkstemp(prefix="programmers-screenshot-", suffix=".png")
    os.close(handle)
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.gnome.Shell.Screenshot",
            "/org/gnome/Shell/Screenshot",
            "org.gnome.Shell.Screenshot",
            None,
        )
        succeeded, written_to = proxy.call_sync(
            "Screenshot",
            GLib.Variant("(bbs)", (False, False, path)),
            Gio.DBusCallFlags.NONE,
            10000,
            None,
        ).unpack()
        return GdkPixbuf.Pixbuf.new_from_file(written_to) if succeeded else None
    except GLib.Error:
        return None
    finally:
        _unlink(path)


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass
