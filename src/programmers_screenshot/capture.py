"""Getting pixels off the screen, on X11 and on Wayland."""

import contextlib
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


def _wnck():
    """libwnck, or None if it is not installed.

    Imported here rather than at the top of the file: only --window needs it,
    and everything else works perfectly well without it on the machine.
    """
    try:
        gi.require_version("Wnck", "3.0")
        from gi.repository import Wnck
    except (ImportError, ValueError):
        return None
    return Wnck


def windows():
    """Every ordinary window, bottom of the stack upwards.

    Each one as (title, Rect, xid). The rectangle is where it sits on the
    screen, which is only of interest for telling two windows apart -- a
    capture of one does not depend on where it is.
    """
    wnck = _wnck()
    if wnck is None:
        raise CaptureError(
            "naming a window needs libwnck: sudo apt install gir1.2-wnck-3.0"
        )
    screen = wnck.Screen.get_default()
    if screen is None:
        raise CaptureError("no window list available; this needs an X11 session")
    screen.force_update()
    found = []
    for window in screen.get_windows_stacked():
        if window.get_window_type() != wnck.WindowType.NORMAL:
            continue
        box = window.get_client_window_geometry()
        found.append((
            window.get_name(),
            Rect(box.xp, box.yp, box.widthp, box.heightp),
            window.get_xid(),
        ))
    return found


def describe_windows():
    """Every window --window could name, one per line."""
    return "\n".join(
        "  %4d x %-4d at %5d,%-5d  %s" % (r.width, r.height, r.x, r.y, title)
        for title, r, _xid in windows()
    )


def _match(wanted):
    """The one open window whose title contains `wanted`."""
    matches = [entry for entry in windows() if wanted.lower() in entry[0].lower()]
    if not matches:
        raise CaptureError(
            "no window has %r in its title. Open right now:\n%s"
            % (wanted, describe_windows())
        )
    if len(matches) > 1:
        raise CaptureError(
            "%r matches %d windows, so it is not clear which one you mean:\n%s"
            % (wanted, len(matches), "\n".join("  %s" % m[0] for m in matches))
        )
    return matches[0]


def _grab(display, xid):
    """One window's pixels as (pixbuf, bounds), or (None, None) if unreadable.

    Unreadable in practice means minimised: nothing is being drawn, so there
    is nothing there to read.
    """
    gi.require_version("GdkX11", "3.0")
    from gi.repository import GdkX11

    window = GdkX11.X11Window.foreign_new_for_display(display, xid)
    if window is None:
        return None, None
    bounds = Rect(0, 0, window.get_width(), window.get_height())
    pixbuf = Gdk.pixbuf_get_from_window(
        window, 0, 0, int(bounds.width), int(bounds.height)
    )
    return (pixbuf, bounds) if pixbuf is not None else (None, None)


def _require_x11(display):
    if not is_x11(display):
        raise CaptureError(
            "naming a window needs an X11 session; under Wayland no program "
            "may read another's window"
        )


def capture_window(display, wanted):
    """Grab one window by a piece of its title, whatever is stacked over it.

    Returns (pixbuf, bounds) with bounds at the origin, so a region and every
    mark in a recipe are relative to the window's own top left corner instead
    of to the screen. Nothing else has to change: the renderer only ever knew
    about a picture and a rectangle.

    Under a compositor -- and GNOME always is one -- every window is redirected
    to an offscreen pixmap of its own, so this reads the real window even when
    it is completely buried. That is the whole point of naming one: nothing
    has to be raised, nothing is disturbed, and whatever is lying on top of it
    stays out of the picture.
    """
    _require_x11(display)
    title, _where, xid = _match(wanted)
    pixbuf, bounds = _grab(display, xid)
    if pixbuf is None:
        raise CaptureError(
            "could not read the pixels of %r -- if it is minimised, there is "
            "nothing there to capture" % title
        )
    return pixbuf, bounds


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


def _grab_from_root(bounds):
    root = Gdk.get_default_root_window()
    return Gdk.pixbuf_get_from_window(
        root, int(bounds.x), int(bounds.y), int(bounds.width), int(bounds.height)
    )


def _grab_from_gnome_shell():
    """Wayland has no root window; ask the compositor instead.

    The Shell reports back the path it actually wrote to, which is not always
    the one we asked for. Both get removed: what it leaves behind is the raw
    screen, so a copy surviving in /tmp would outlive any redaction drawn on
    the capture we keep.
    """
    handle, path = tempfile.mkstemp(prefix="programmers-screenshot-", suffix=".png")
    os.close(handle)
    written_to = None  # bound before the try: the error path reaches `finally`
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
        with contextlib.suppress(OSError):
            os.unlink(path)
        if written_to and written_to != path:
            with contextlib.suppress(OSError):
                os.unlink(written_to)
