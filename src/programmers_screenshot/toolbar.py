"""The bar across the top.

Two rows. The first holds the tools on the left and capture on the right. The
second appears only while the active tool declares settings, and is laid out
from what the settings say about themselves — it knows nothing about which
tool it is serving.

Toolbars, above them, holds one bar per monitor and keeps them in step, so
the overlay can talk to the lot as though there were one. PaletteToolbar is
the same controls in a rectangle you drag around instead: the tools in a
grid rather than a row, and one of it however many screens there are.
"""

import collections
import math
from dataclasses import dataclass

from . import painting, theme
from .geometry import Rect

TOOL = "tool"
CAPTURE = "capture"
CANCEL = "cancel"
SETTINGS = "settings"   # the preferences window
SETTING = "setting"    # one knob on the second row
VARIANT = "variant"    # a sub-tool, offered in a flyout

BAR = "bar"
PALETTE = "palette"

#: An open sub-tool flyout: the button it hangs off, the panel, and what
#: is in it.
Flyout = collections.namedtuple("Flyout", "button rect buttons")


class Toolbars:
    """One bar per monitor, kept in step.

    The overlay talks to this the way it used to talk to a single bar. The
    tools, the settings and the scene stay single, so every bar is a view of
    the same state: pick a tool on one and it lights up on all of them.
    """

    def __init__(self, tools, monitors, values, mode=BAR, origin=None,
                 chosen=None):
        self.mode = mode
        #: group name -> the member last picked from it. Shared by every bar,
        #: so choosing on one screen shows on the others.
        self.chosen = {} if chosen is None else chosen
        if mode == PALETTE:
            # One, not one each. You put it where you want it, and copies on
            # the other screens would be clutter you could not get rid of.
            self.bars = [PaletteToolbar(tools, monitors[0], values, origin,
                                        self.chosen, monitors)]
        else:
            self.bars = [Toolbar(tools, monitor, values, None, self.chosen)
                         for monitor in monitors]

    @property
    def palette(self):
        """The floating palette, or None in bar mode."""
        return self.bars[0] if self.mode == PALETTE else None

    def grab_at(self, x, y):
        """True if this point is the palette's drag handle."""
        palette = self.palette
        return palette is not None and palette.grab_rect.contains(x, y)

    def shown(self, button):
        """Which tool a button stands for right now."""
        return self.bars[0].shown(button)

    def choose_member(self, button):
        """Remember a member as its group's current pick."""
        self.chosen[button.tool.group] = button.tool

    def close_flyouts(self):
        changed = False
        for bar in self.bars:
            if bar.flyout is not None:
                bar.flyout = None
                changed = True
        return changed

    @property
    def primary(self):
        """The bar on the monitor the pointer started on; first in the list."""
        return self.bars[0]

    def covers(self, x, y):
        return any(bar.covers(x, y) for bar in self.bars)

    def button_at(self, x, y):
        for bar in self.bars:
            button = bar.button_at(x, y)
            if button is not None:
                return button
        return None

    def show_settings_for(self, tool):
        for bar in self.bars:
            bar.show_settings_for(tool)

    def set_hover(self, x, y):
        """Every bar is told, so the one being left stops looking hovered."""
        changed = False
        for bar in self.bars:
            if bar.set_hover(x, y):
                changed = True
        return changed

    def draw(self, cr, active_tool):
        for bar in self.bars:
            bar.draw(cr, active_tool)

    def draw_tooltip(self, cr):
        # Only the hovered bar has anything to say, so this draws at most one.
        for bar in self.bars:
            bar.draw_tooltip(cr)

    def draw_flyouts(self, cr):
        for bar in self.bars:
            bar.draw_flyout(cr)


@dataclass
class Button:
    kind: str
    rect: Rect
    tool: object = None      # TOOL and tool-VARIANT buttons
    setting: object = None   # SETTING and setting-VARIANT buttons
    value: object = None     # SETTING and setting-VARIANT buttons
    members: object = None   # TOOL buttons standing for a group of tools


def grouped(tools):
    """Fold neighbouring tools that share a group into one entry each.

    Neighbouring, not gathered from all over: the order of the toolbar is
    deliberate, and a group assembled from tools at either end of it would
    move buttons around behind the reader's back.
    """
    entries = []
    for tool in tools:
        if (tool.group is not None and entries
                and entries[-1][0].group == tool.group):
            entries[-1].append(tool)
        else:
            entries.append([tool])
    return entries


class Toolbar:
    """Laid out across the top of one monitor, in overlay coordinates."""

    def __init__(self, tools, monitor, values, origin=None, chosen=None,
                 monitors=None):
        #: The tools this bar offers, ungrouped. Layout works from entries;
        #: this is what the suite reads to check every bar shows the same list.
        self.tools = tools
        self.entries = grouped(tools)
        self.values = values
        self.monitor = monitor
        #: Every monitor, for anything that can move between them.
        self.monitors = list(monitors) if monitors else [monitor]
        self.chosen = {} if chosen is None else chosen
        self.settings_rect = None
        self.setting_buttons = []
        self.hovered = None
        #: A Flyout while a sub-tool flyout is open, None the rest of the time.
        self.flyout = None
        self.place(origin)
        self.show_settings_for(tools[0] if tools else None)

    def place(self, origin=None):
        """Work out where the controls sit. `origin` is ignored by a bar,
        which is always across the top of its monitor."""
        self.rect = Rect(
            self.monitor.x, self.monitor.y, self.monitor.width, theme.BAR_HEIGHT
        )
        self.buttons = self._layout_tools()

    # -- layout ------------------------------------------------------------

    def _layout_tools(self):
        buttons = []
        middle = self.rect.y + (theme.BAR_HEIGHT - theme.TOOL_BUTTON) / 2
        x = self.rect.x + theme.BAR_PADDING
        for members in self.entries:
            buttons.append(Button(
                TOOL, Rect(x, middle, theme.TOOL_BUTTON, theme.TOOL_BUTTON),
                tool=members[0],
                members=members if len(members) > 1 else None,
            ))
            x += theme.TOOL_BUTTON + theme.TOOL_GAP

        capture_y = self.rect.y + (theme.BAR_HEIGHT - theme.CAPTURE_HEIGHT) / 2
        capture_x = self.rect.right - theme.BAR_PADDING - theme.CAPTURE_WIDTH
        buttons.append(
            Button(CAPTURE, Rect(capture_x, capture_y, theme.CAPTURE_WIDTH,
                                 theme.CAPTURE_HEIGHT))
        )
        # Right to left: Capture, Cancel, Settings.
        square = theme.CAPTURE_HEIGHT
        cancel_x = capture_x - theme.TOOL_GAP - square
        buttons.append(
            Button(CANCEL, Rect(cancel_x, capture_y, square, theme.CAPTURE_HEIGHT))
        )
        buttons.append(
            Button(SETTINGS, Rect(cancel_x - theme.TOOL_GAP - square, capture_y,
                                  square, theme.CAPTURE_HEIGHT))
        )
        return buttons

    @staticmethod
    def row_settings(tool):
        """The settings that belong on the row rather than in a flyout.

        A tool's variants are offered on its own button, so repeating them
        here would be the same choice in two places.
        """
        settings = getattr(tool, "settings", ()) if tool else ()
        variants = getattr(tool, "variants", None)
        return tuple(s for s in settings if s is not variants)

    def show_settings_for(self, tool):
        """Rebuild the second row for a tool. No settings means no row."""
        self.flyout = None
        settings = self.row_settings(tool)
        if not settings:
            self.settings_rect = None
            self.setting_buttons = []
            return

        self.settings_rect = Rect(
            self.rect.x, self.rect.bottom, self.rect.width, theme.SETTINGS_HEIGHT
        )
        self.setting_buttons = []
        x = self.settings_rect.x + theme.BAR_PADDING + 2
        top = self.settings_rect.y + (
            theme.SETTINGS_HEIGHT - theme.SETTINGS_OPTION
        ) / 2

        for setting in settings:
            x += self._label_width(setting) + 8
            for value in setting.options():
                width = setting.option_width()
                self.setting_buttons.append(
                    Button(
                        SETTING,
                        Rect(x, top, width, theme.SETTINGS_OPTION),
                        setting=setting,
                        value=value,
                    )
                )
                x += width + theme.SETTINGS_OPTION_GAP
            x += theme.SETTINGS_GROUP_GAP - theme.SETTINGS_OPTION_GAP

    @staticmethod
    def _label_width(setting):
        # Estimated rather than measured: laying out needs a width before
        # there is a cairo context to ask, and the labels are short.
        return int(len(setting.label) * 6.6)

    # -- hit testing -------------------------------------------------------

    def covers(self, x, y):
        """True if this point belongs to the bar rather than to the canvas."""
        if self.rect.contains(x, y):
            return True
        if self.settings_rect is not None and self.settings_rect.contains(x, y):
            return True
        return self.flyout is not None and self.flyout.rect.contains(x, y)

    def button_at(self, x, y):
        # The flyout first: it is drawn over everything else, so it has to be
        # hit before whatever it is covering.
        if self.flyout is not None:
            for button in self.flyout.buttons:
                if button.rect.contains(x, y):
                    return button
        for button in self.buttons + self.setting_buttons:
            if button.rect.contains(x, y):
                return button
        return None

    # -- sub-tool flyouts ---------------------------------------------------

    def current_monitor(self):
        """The screen these controls are on. A bar never leaves its own."""
        return self.monitor

    def shown(self, button):
        """The tool this button currently stands for.

        A group shows whichever member was last picked from it, so the common
        case stays one click. First member until something is picked.
        """
        if not button.members:
            return button.tool
        return self.chosen.get(button.members[0].group, button.members[0])

    @staticmethod
    def has_flyout(button):
        return bool(button.members) or getattr(button.tool, "variants", None)

    @staticmethod
    def flyout_marker(button):
        """The corner of a tool button that opens its flyout.

        A marker rather than click-and-hold: several tools act on release, so
        holding already means something, and a corner you can see beats a
        gesture you cannot.
        """
        size = 9.0
        rect = button.rect
        return Rect(rect.right - size, rect.bottom - size, size, size)

    def open_flyout(self, button):
        """Lay the alternatives out beside the button, on whichever side fits.

        Two kinds share this: a group of tools, and one tool's variants. They
        differ only in what each entry carries and how it draws.
        """
        setting = None if button.members else button.tool.variants
        options = list(button.members) if button.members else list(setting.options())
        step = theme.SETTINGS_OPTION + theme.SETTINGS_OPTION_GAP
        width = theme.FLYOUT_PADDING * 2 + theme.SETTINGS_OPTION
        height = theme.FLYOUT_PADDING * 2 + step * len(options) - \
            theme.SETTINGS_OPTION_GAP

        screen = self.current_monitor()
        x = button.rect.right + theme.FLYOUT_GAP
        if x + width > screen.right:
            x = button.rect.x - theme.FLYOUT_GAP - width   # no room; other side
        y = min(button.rect.y, max(screen.y, screen.bottom - height))

        rect = Rect(x, y, width, height)
        buttons = []
        for index, option in enumerate(options):
            spot = Rect(x + theme.FLYOUT_PADDING,
                        y + theme.FLYOUT_PADDING + index * step,
                        theme.SETTINGS_OPTION, theme.SETTINGS_OPTION)
            if setting is None:
                buttons.append(Button(VARIANT, spot, tool=option))
            else:
                buttons.append(Button(VARIANT, spot, tool=button.tool,
                                      setting=setting, value=option))
        self.flyout = Flyout(button, rect, buttons)

    def draw_flyout(self, cr):
        if self.flyout is None:
            return
        painting.fill_rounded(cr, self.flyout.rect, theme.SETTINGS_BG, 5)
        painting.use(cr, theme.BAR_EDGE)
        cr.set_line_width(1.0)
        painting.rounded_rect(cr, self.flyout.rect, 5)
        cr.stroke()
        for button in self.flyout.buttons:
            if button is self.hovered:
                painting.fill_rounded(cr, button.rect, theme.BUTTON_HOVER, 4)
            if button.setting is None:
                # A member of a group: it draws its own icon.
                picked = self.chosen.get(button.tool.group) is button.tool
                colour = theme.BUTTON_ICON_ACTIVE if picked else theme.BUTTON_ICON
                button.tool.draw_icon(cr, button.rect, colour)
            else:
                picked = self.values.get(button.setting) == button.value
                button.setting.draw_option(cr, button.rect, button.value, picked)

    def set_hover(self, x, y):
        """Returns True if the hovered button changed, meaning: redraw."""
        button = self.button_at(x, y) if self.covers(x, y) else None
        if button is self.hovered:
            return False
        self.hovered = button
        return True

    # -- tooltips ----------------------------------------------------------

    def tooltip_for(self, button):
        """What to say about a button, or None if it speaks for itself."""
        if button is None:
            return None
        if button.kind == TOOL:
            return self.shown(button).label or None
        if button.kind == CANCEL:
            return "Close without capturing"
        if button.kind == SETTINGS:
            return "Settings"
        if button.kind == VARIANT:
            if button.setting is None:
                return button.tool.label or None
            return button.setting.caption(button.value)
        if button.kind == SETTING and not button.setting.draws_caption:
            return button.setting.caption(button.value)
        return None  # Capture is already a word

    def tooltip_box(self, cr, text, button):
        """Below the whole bar, centred on the button, kept on the monitor.

        Below the bar rather than below the button, so a tooltip for a tool
        never lands on top of the settings row.
        """
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_TOOLTIP)
        width, height = painting.text_size(cr, text)
        box_width = width + theme.TOOLTIP_PADDING * 2
        box_height = height + theme.TOOLTIP_PADDING * 2

        screen = self.current_monitor()
        below = self.settings_rect.bottom if self.settings_rect else self.rect.bottom
        x = button.rect.x + (button.rect.width - box_width) / 2
        left = screen.x + 4
        right = screen.right - box_width - 4
        return Rect(
            min(max(x, left), max(left, right)),
            below + theme.TOOLTIP_GAP,
            box_width,
            box_height,
        )

    def draw_tooltip(self, cr):
        """Drawn after everything else, so it sits over the dimmed screen."""
        text = self.tooltip_for(self.hovered)
        if not text:
            return
        box = self.tooltip_box(cr, text, self.hovered)
        painting.fill_rounded(cr, box, theme.TOOLTIP_BG, 4)
        painting.draw_text(
            cr,
            text,
            box.x + theme.TOOLTIP_PADDING,
            box.y + theme.TOOLTIP_PADDING,
            theme.TOOLTIP_TEXT,
        )

    # -- drawing -----------------------------------------------------------

    def draw(self, cr, active_tool):
        painting.use(cr, theme.BAR_BG)
        cr.rectangle(self.rect.x, self.rect.y, self.rect.width, self.rect.height)
        cr.fill()

        self._draw_buttons(cr, active_tool)

        if self.settings_rect is not None:
            self._draw_settings(cr)
            bottom = self.settings_rect.bottom
        else:
            bottom = self.rect.bottom

        painting.use(cr, theme.BAR_EDGE)
        cr.set_line_width(1.0)
        cr.move_to(self.rect.x, bottom - 0.5)
        cr.line_to(self.rect.right, bottom - 0.5)
        cr.stroke()

    def _draw_buttons(self, cr, active_tool):
        """Every button on this bar, each drawn as whatever kind it is."""
        for button in self.buttons:
            if button.kind == TOOL:
                self._draw_tool(cr, button, button.tool is active_tool)
            elif button.kind == CAPTURE:
                self._draw_capture(cr, button)
            elif button.kind == SETTINGS:
                self._draw_settings_button(cr, button)
            else:
                self._draw_cancel(cr, button)

    def _draw_tool(self, cr, button, active):
        if active:
            painting.fill_rounded(cr, button.rect, theme.ACCENT_SOFT)
            painting.use(cr, theme.ACCENT)
            painting.rounded_rect(cr, button.rect)
            cr.set_line_width(1.0)
            cr.stroke()
        elif button is self.hovered:
            painting.fill_rounded(cr, button.rect, theme.BUTTON_HOVER)

        colour = theme.BUTTON_ICON_ACTIVE if active else theme.BUTTON_ICON
        if button.members:
            # A group wears the icon of whichever member is current, so the
            # button says which tool it is rather than which family.
            self.shown(button).draw_icon(cr, button.rect, colour)
            self._draw_flyout_marker(cr, button, colour)
            return
        variants = getattr(button.tool, "variants", None)
        if variants is None:
            button.tool.draw_icon(cr, button.rect, colour)
        else:
            # Show which variant is chosen, the way a paint program does, so
            # the button says what it will actually draw. The setting already
            # knows how to paint one; active=False because the button draws
            # its own selected state above.
            variants.draw_option(cr, button.rect, self.values.get(variants), False)
            self._draw_flyout_marker(cr, button, colour)

    @staticmethod
    def _draw_flyout_marker(cr, button, colour):
        """A small wedge in the corner: there is more behind this one."""
        marker = Toolbar.flyout_marker(button)
        painting.use(cr, colour)
        cr.move_to(marker.right - 1, marker.bottom - 1)
        cr.line_to(marker.right - 1, marker.y + 2)
        cr.line_to(marker.x + 2, marker.bottom - 1)
        cr.close_path()
        cr.fill()

    def _draw_capture(self, cr, button):
        background = theme.CAPTURE_BG
        if button is self.hovered:
            background = tuple(min(1.0, channel + 0.08) for channel in background)
        painting.fill_rounded(cr, button.rect, background)
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_UI)
        painting.draw_text_centred(cr, "Capture", button.rect, theme.CAPTURE_TEXT)

    def _draw_cancel(self, cr, button):
        if button is self.hovered:
            painting.fill_rounded(cr, button.rect, theme.BUTTON_HOVER)
        rect = button.rect
        cx, cy, arm = rect.x + rect.width / 2, rect.y + rect.height / 2, 5
        painting.use(cr, theme.BUTTON_ICON)
        cr.set_line_width(1.6)
        cr.move_to(cx - arm, cy - arm)
        cr.line_to(cx + arm, cy + arm)
        cr.move_to(cx + arm, cy - arm)
        cr.line_to(cx - arm, cy + arm)
        cr.stroke()

    def _draw_settings_button(self, cr, button):
        """Three sliders. A cog is the convention but needs a lot of cairo to
        read as one at 32px; sliders survive the size."""
        if button is self.hovered:
            painting.fill_rounded(cr, button.rect, theme.BUTTON_HOVER)
        rect = button.rect
        left, right = rect.x + 9, rect.right - 9
        painting.use(cr, theme.BUTTON_ICON)
        cr.set_line_width(1.4)
        for offset, along in ((-5, 0.62), (0, 0.34), (5, 0.54)):
            y = rect.y + rect.height / 2 + offset
            cr.move_to(left, y)
            cr.line_to(right, y)
            cr.stroke()
            painting.circle(cr, left + (right - left) * along, y, 2.2,
                            theme.BUTTON_ICON)

    def _draw_settings(self, cr):
        rect = self.settings_rect
        painting.use(cr, theme.SETTINGS_BG)
        cr.rectangle(rect.x, rect.y, rect.width, rect.height)
        cr.fill()

        drawn_labels = set()
        for button in self.setting_buttons:
            setting = button.setting
            if id(setting) not in drawn_labels:
                drawn_labels.add(id(setting))
                self._draw_setting_label(cr, setting, button.rect)
            if button is self.hovered:
                painting.fill_rounded(cr, button.rect, theme.BUTTON_HOVER, 4)
            active = self.values.get(setting) == button.value
            setting.draw_option(cr, button.rect, button.value, active)

    @staticmethod
    def _draw_setting_label(cr, setting, first_option):
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_SETTING)
        width, height = painting.text_size(cr, setting.label)
        painting.draw_text(
            cr,
            setting.label,
            first_option.x - 8 - width,
            first_option.y + (first_option.height - height) / 2,
            theme.SETTINGS_LABEL,
        )


class PaletteToolbar(Toolbar):
    """The same controls as a bar, in a rectangle you can drag around.

    Tools in a grid rather than a row, so it stays roughly square instead of
    stretching into a bar. Capture stays a full-width button: it is the point
    of the program and should not be the thing you have to hunt for.
    """

    def place(self, origin=None):
        pad = theme.PALETTE_PADDING
        step = theme.TOOL_BUTTON + theme.TOOL_GAP
        columns = theme.PALETTE_COLUMNS
        rows = self._rows()

        width = pad * 2 + columns * step - theme.TOOL_GAP
        grid_height = rows * step - theme.TOOL_GAP
        height = (theme.PALETTE_GRAB + pad + grid_height
                  + theme.PALETTE_ROW_GAP + theme.CAPTURE_HEIGHT + pad)

        x, y = origin if origin else self._default_origin(width)
        self.rect = self._clamped(Rect(x, y, width, height))
        self.buttons = self._layout_tools()

    def _rows(self):
        """How many rows of tools the grid comes to."""
        return math.ceil(len(self.entries) / theme.PALETTE_COLUMNS)

    def _default_origin(self, width):
        """Top left of the monitor, in far enough not to look like an accident."""
        return (self.monitor.x + 40, self.monitor.y + 60)

    def _clamped(self, rect):
        """Keep the grab strip on a screen -- any screen.

        Dragged somewhere with no screen under it the palette could not be got
        back without editing the config by hand, so the handle always stays
        reachable. Against whichever monitor it is nearest, not the one it
        started on: clamping to that one meant it could never be dragged to
        another, which on two screens made the palette useless on one of them.

        Nearest rather than the union of all of them, because a union spans
        the gaps in a stepped or mismatched layout, and the palette could be
        dropped into one and half vanish.
        """
        margin = 40.0
        screen = self._nearest(Rect(rect.x, rect.y, rect.width,
                                    theme.PALETTE_GRAB))
        x = min(max(rect.x, screen.x - rect.width + margin),
                screen.right - margin)
        y = min(max(rect.y, screen.y), screen.bottom - theme.PALETTE_GRAB)
        return Rect(x, y, rect.width, rect.height)

    def _nearest(self, grab):
        """The monitor the grab strip is most on, or closest to."""
        best, most = self.monitors[0], 0.0
        for screen in self.monitors:
            across = min(grab.right, screen.right) - max(grab.x, screen.x)
            down = min(grab.bottom, screen.bottom) - max(grab.y, screen.y)
            overlap = max(0.0, across) * max(0.0, down)
            if overlap > most:
                best, most = screen, overlap
        if most:
            return best
        # Nothing under it at all, which a stepped layout allows: fall back to
        # whichever centre is closest rather than leaving it stranded.
        centre = (grab.x + grab.width / 2, grab.y + grab.height / 2)
        return min(self.monitors, key=lambda s: (
            (s.x + s.width / 2 - centre[0]) ** 2
            + (s.y + s.height / 2 - centre[1]) ** 2))

    def current_monitor(self):
        """The screen the palette is on now, for tooltips and flyouts."""
        return self._nearest(self.grab_rect)

    def move_to(self, x, y):
        """Put the palette here, then rebuild everything that sat on it."""
        self.rect = self._clamped(Rect(x, y, self.rect.width, self.rect.height))
        self.buttons = self._layout_tools()
        active = self.flyout.button.tool if self.flyout else None
        self.flyout = None
        self._relayout_settings()
        return active

    @property
    def grab_rect(self):
        return Rect(self.rect.x, self.rect.y, self.rect.width, theme.PALETTE_GRAB)

    def _layout_tools(self):
        pad = theme.PALETTE_PADDING
        step = theme.TOOL_BUTTON + theme.TOOL_GAP
        buttons = []
        for index, members in enumerate(self.entries):
            row, column = divmod(index, theme.PALETTE_COLUMNS)
            buttons.append(Button(
                TOOL,
                Rect(self.rect.x + pad + column * step,
                     self.rect.y + theme.PALETTE_GRAB + pad + row * step,
                     theme.TOOL_BUTTON, theme.TOOL_BUTTON),
                tool=members[0],
                members=members if len(members) > 1 else None,
            ))

        rows = self._rows()
        bottom = (self.rect.y + theme.PALETTE_GRAB + pad
                  + rows * step - theme.TOOL_GAP + theme.PALETTE_ROW_GAP)
        square = theme.CAPTURE_HEIGHT
        inner = self.rect.width - pad * 2
        buttons.append(Button(
            CAPTURE,
            Rect(self.rect.x + pad, bottom,
                 inner - (square + theme.TOOL_GAP) * 2, theme.CAPTURE_HEIGHT),
        ))
        buttons.append(Button(
            SETTINGS,
            Rect(self.rect.right - pad - square * 2 - theme.TOOL_GAP, bottom,
                 square, theme.CAPTURE_HEIGHT),
        ))
        buttons.append(Button(
            CANCEL,
            Rect(self.rect.right - pad - square, bottom, square,
                 theme.CAPTURE_HEIGHT),
        ))
        return buttons

    # -- settings, stacked underneath rather than strung along a row --------

    def show_settings_for(self, tool):
        self.flyout = None
        self._settings_for = self.row_settings(tool)
        self._relayout_settings()

    def _relayout_settings(self):
        settings = self._settings_for
        if not settings:
            self.settings_rect = None
            self.setting_buttons = []
            return

        pad = theme.PALETTE_PADDING
        step = theme.SETTINGS_OPTION + theme.SETTINGS_OPTION_GAP
        rows = len(settings)
        height = pad * 2 + rows * step - theme.SETTINGS_OPTION_GAP

        self.settings_rect = Rect(
            self.rect.x, self.rect.bottom, self.rect.width, height
        )
        self.setting_buttons = []
        for row, setting in enumerate(settings):
            x = self.settings_rect.x + pad
            y = self.settings_rect.y + pad + row * step
            for value in setting.options():
                width = setting.option_width()
                self.setting_buttons.append(Button(
                    SETTING, Rect(x, y, width, theme.SETTINGS_OPTION),
                    setting=setting, value=value,
                ))
                x += width + theme.SETTINGS_OPTION_GAP

    def draw(self, cr, active_tool):
        painting.fill_rounded(cr, self.whole(), theme.BAR_BG, 6)
        self._draw_grab(cr)
        self._draw_buttons(cr, active_tool)
        if self.settings_rect is not None:
            self._draw_settings(cr)
        painting.use(cr, theme.BAR_EDGE)
        cr.set_line_width(1.0)
        painting.rounded_rect(cr, self.whole(), 6)
        cr.stroke()

    def whole(self):
        """The palette and its settings block, as one rounded rectangle."""
        if self.settings_rect is None:
            return self.rect
        return Rect(self.rect.x, self.rect.y, self.rect.width,
                    self.settings_rect.bottom - self.rect.y)

    def _draw_grab(self, cr):
        """Three lines, the usual sign for something you can pick up."""
        grab = self.grab_rect
        painting.use(cr, theme.SETTINGS_LABEL)
        cr.set_line_width(1.0)
        middle = grab.y + grab.height / 2
        for offset in (-3, 0, 3):
            cr.move_to(grab.x + grab.width / 2 - 12, middle + offset + 0.5)
            cr.line_to(grab.x + grab.width / 2 + 12, middle + offset + 0.5)
        cr.stroke()

    def tooltip_box(self, cr, text, button):
        """Below the palette, or above it when it is near the bottom."""
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_TOOLTIP)
        width, height = painting.text_size(cr, text)
        box_width = width + theme.TOOLTIP_PADDING * 2
        box_height = height + theme.TOOLTIP_PADDING * 2

        # The screen it is on now, not the one it started on: the palette
        # can be dragged to another, and a tooltip clamped to the wrong one
        # lands nowhere near its button.
        screen = self.current_monitor()
        whole = self.whole()
        y = whole.bottom + theme.TOOLTIP_GAP
        if y + box_height > screen.bottom:
            y = whole.y - theme.TOOLTIP_GAP - box_height
        x = button.rect.x + (button.rect.width - box_width) / 2
        left = screen.x + 4
        right = screen.right - box_width - 4
        return Rect(min(max(x, left), max(left, right)), y, box_width, box_height)
