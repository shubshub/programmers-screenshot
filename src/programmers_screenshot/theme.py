"""Every colour and measurement the overlay draws with, in one place."""

# Colours are (r, g, b) or (r, g, b, a), 0..1, ready to splat into cairo.
ACCENT = (0.25, 0.62, 1.0)
ACCENT_SOFT = (0.25, 0.62, 1.0, 0.22)

SCREEN_DIM = (0, 0, 0, 0.55)
GUIDE_LINE = (1, 1, 1, 0.28)

# Opaque: at 95% the screen behind bled through and made the controls hard
# to read against bright content.
BAR_BG = (0.08, 0.09, 0.11)
BAR_EDGE = (1, 1, 1, 0.12)
BUTTON_HOVER = (1, 1, 1, 0.10)
BUTTON_ICON = (0.92, 0.93, 0.95)
BUTTON_ICON_ACTIVE = ACCENT

CAPTURE_BG = ACCENT
CAPTURE_BG_DISABLED = (1, 1, 1, 0.10)
CAPTURE_TEXT = (1, 1, 1)
CAPTURE_TEXT_DISABLED = (1, 1, 1, 0.35)

LABEL_BG = (0, 0, 0, 0.78)
LABEL_TEXT = (1, 1, 1)
HINT_BG = (0, 0, 0, 0.72)
HINT_TEXT = (1, 1, 1, 0.92)

TOOLTIP_BG = (0, 0, 0, 0.88)
TOOLTIP_TEXT = (1, 1, 1, 0.95)

SETTINGS_BG = (0.13, 0.14, 0.17)
SETTINGS_LABEL = (1, 1, 1, 0.55)
SETTINGS_MARK = (0.92, 0.93, 0.95)
SWATCH_RING = (1, 1, 1, 0.92)
SWATCH_EDGE = (0, 0, 0, 0.35)

# What annotations can be drawn in. Red first: it is what people reach for.
PALETTE = (
    (0.91, 0.24, 0.24),
    (0.98, 0.68, 0.13),
    (0.30, 0.76, 0.36),
    (0.25, 0.62, 1.00),
    (1.00, 1.00, 1.00),
    (0.08, 0.08, 0.09),
)
# Swatches are unlabelled on the bar, so these are what a tooltip says.
PALETTE_NAMES = ("Red", "Amber", "Green", "Blue", "White", "Black")

# Layout, in logical pixels.
BAR_HEIGHT = 46
BAR_PADDING = 8
TOOL_BUTTON = 34
TOOL_GAP = 6
CAPTURE_WIDTH = 104
CAPTURE_HEIGHT = 32
CORNER_RADIUS = 6
HANDLE_SIZE = 4

SETTINGS_HEIGHT = 40
SETTINGS_OPTION = 26
SETTINGS_OPTION_GAP = 5
SETTINGS_GROUP_GAP = 26
SWATCH_RADIUS = 9

TOOLTIP_PADDING = 7
TOOLTIP_GAP = 6

FONT_UI = "sans-serif"
FONT_MONO = "monospace"
FONT_SIZE_UI = 13
FONT_SIZE_LABEL = 13
FONT_SIZE_HINT = 14
FONT_SIZE_SETTING = 12
FONT_SIZE_TOOLTIP = 12
