"""The bar across the top.

Two rows. The first holds the tools on the left and capture on the right. The
second appears only while the active tool declares settings, and is laid out
from what the settings say about themselves — it knows nothing about which
tool it is serving.
"""

from dataclasses import dataclass

from . import painting, theme
from .geometry import Rect

TOOL = "tool"
CAPTURE = "capture"
CANCEL = "cancel"
SETTING = "setting"


@dataclass
class Button:
    kind: str
    rect: Rect
    tool: object = None     # TOOL buttons
    setting: object = None  # SETTING buttons
    value: object = None    # SETTING buttons


class Toolbar:
    """Laid out across the top of one monitor, in overlay coordinates."""

    def __init__(self, tools, monitor, values):
        self.tools = tools
        self.values = values
        self.monitor = monitor
        self.rect = Rect(monitor.x, monitor.y, monitor.width, theme.BAR_HEIGHT)
        self.buttons = self._layout_tools()
        self.settings_rect = None
        self.setting_buttons = []
        self.hovered = None
        self.show_settings_for(tools[0] if tools else None)

    # -- layout ------------------------------------------------------------

    def _layout_tools(self):
        buttons = []
        middle = self.rect.y + (theme.BAR_HEIGHT - theme.TOOL_BUTTON) / 2
        x = self.rect.x + theme.BAR_PADDING
        for tool in self.tools:
            buttons.append(
                Button(TOOL, Rect(x, middle, theme.TOOL_BUTTON, theme.TOOL_BUTTON), tool=tool)
            )
            x += theme.TOOL_BUTTON + theme.TOOL_GAP

        capture_y = self.rect.y + (theme.BAR_HEIGHT - theme.CAPTURE_HEIGHT) / 2
        capture_x = self.rect.right - theme.BAR_PADDING - theme.CAPTURE_WIDTH
        buttons.append(
            Button(CAPTURE, Rect(capture_x, capture_y, theme.CAPTURE_WIDTH,
                                 theme.CAPTURE_HEIGHT))
        )
        cancel_width = theme.CAPTURE_HEIGHT
        buttons.append(
            Button(CANCEL, Rect(capture_x - theme.TOOL_GAP - cancel_width, capture_y,
                                cancel_width, theme.CAPTURE_HEIGHT))
        )
        return buttons

    def show_settings_for(self, tool):
        """Rebuild the second row for a tool. No settings means no row."""
        settings = getattr(tool, "settings", ()) if tool else ()
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
        return self.settings_rect is not None and self.settings_rect.contains(x, y)

    def button_at(self, x, y):
        for button in self.buttons + self.setting_buttons:
            if button.rect.contains(x, y):
                return button
        return None

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
            return button.tool.label or None
        if button.kind == CANCEL:
            return "Close without capturing"
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

        below = self.settings_rect.bottom if self.settings_rect else self.rect.bottom
        x = button.rect.x + (button.rect.width - box_width) / 2
        left = self.monitor.x + 4
        right = self.monitor.right - box_width - 4
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

        for button in self.buttons:
            if button.kind == TOOL:
                self._draw_tool(cr, button, button.tool is active_tool)
            elif button.kind == CAPTURE:
                self._draw_capture(cr, button)
            else:
                self._draw_cancel(cr, button)

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
        button.tool.draw_icon(cr, button.rect, colour)

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
