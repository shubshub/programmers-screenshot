"""The bar across the top: tools on the left, capture on the right."""

from dataclasses import dataclass

from . import painting, theme
from .geometry import Rect

TOOL = "tool"
CAPTURE = "capture"
CANCEL = "cancel"


@dataclass
class Button:
    kind: str
    rect: Rect
    tool: object = None  # set for TOOL buttons


class Toolbar:
    """Laid out across the top of one monitor, in overlay coordinates."""

    def __init__(self, tools, monitor):
        self.tools = tools
        self.rect = Rect(monitor.x, monitor.y, monitor.width, theme.BAR_HEIGHT)
        self.buttons = self._layout()
        self.hovered = None

    # -- layout ------------------------------------------------------------

    def _layout(self):
        buttons = []
        middle = self.rect.y + (theme.BAR_HEIGHT - theme.TOOL_BUTTON) / 2
        x = self.rect.x + theme.BAR_PADDING
        for tool in self.tools:
            buttons.append(
                Button(TOOL, Rect(x, middle, theme.TOOL_BUTTON, theme.TOOL_BUTTON), tool)
            )
            x += theme.TOOL_BUTTON + theme.TOOL_GAP

        capture_y = self.rect.y + (theme.BAR_HEIGHT - theme.CAPTURE_HEIGHT) / 2
        capture_x = self.rect.right - theme.BAR_PADDING - theme.CAPTURE_WIDTH
        buttons.append(
            Button(
                CAPTURE,
                Rect(capture_x, capture_y, theme.CAPTURE_WIDTH, theme.CAPTURE_HEIGHT),
            )
        )

        cancel_width = theme.CAPTURE_HEIGHT
        buttons.append(
            Button(
                CANCEL,
                Rect(
                    capture_x - theme.TOOL_GAP - cancel_width,
                    capture_y,
                    cancel_width,
                    theme.CAPTURE_HEIGHT,
                ),
            )
        )
        return buttons

    # -- hit testing -------------------------------------------------------

    def covers(self, x, y):
        """True if this point belongs to the bar rather than to the canvas."""
        return self.rect.contains(x, y)

    def button_at(self, x, y):
        for button in self.buttons:
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

    # -- drawing -----------------------------------------------------------

    def draw(self, cr, active_tool, can_capture):
        painting.use(cr, theme.BAR_BG)
        cr.rectangle(self.rect.x, self.rect.y, self.rect.width, self.rect.height)
        cr.fill()

        painting.use(cr, theme.BAR_EDGE)
        cr.set_line_width(1.0)
        cr.move_to(self.rect.x, self.rect.bottom - 0.5)
        cr.line_to(self.rect.right, self.rect.bottom - 0.5)
        cr.stroke()

        for button in self.buttons:
            if button.kind == TOOL:
                self._draw_tool(cr, button, button.tool is active_tool)
            elif button.kind == CAPTURE:
                self._draw_capture(cr, button, can_capture)
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
        button.tool.draw_icon(cr, button.rect, colour)

    def _draw_capture(self, cr, button, enabled):
        background = theme.CAPTURE_BG if enabled else theme.CAPTURE_BG_DISABLED
        if enabled and button is self.hovered:
            background = tuple(min(1.0, c + 0.08) for c in theme.CAPTURE_BG)
        painting.fill_rounded(cr, button.rect, background)

        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_UI)
        colour = theme.CAPTURE_TEXT if enabled else theme.CAPTURE_TEXT_DISABLED
        painting.draw_text_centred(cr, "Capture", button.rect, colour)

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
