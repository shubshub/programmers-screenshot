"""Tool settings: the knobs on the second toolbar row.

Settings are declarative so the bar can lay them out and draw them without
knowing which tool it is serving. A setting says what its options are and how
to paint one; the toolbar does the arithmetic.

Values are shared by key rather than per tool, so choosing red for the pen
leaves an arrow red too.
"""

from . import painting, theme


class Setting:
    """One knob. Subclasses decide what an option looks like."""

    def __init__(self, key, label, default):
        self.key = key
        self.label = label
        self.default = default

    def options(self):
        """The values this setting can take, in display order."""
        raise NotImplementedError

    def option_width(self):
        return theme.SETTINGS_OPTION

    def draw_option(self, cr, box, value, active):
        raise NotImplementedError


class ColourSetting(Setting):
    """A row of swatches."""

    def __init__(self, key="colour", label="Colour", default=None, swatches=None):
        swatches = tuple(swatches if swatches is not None else theme.PALETTE)
        super().__init__(key, label, default if default is not None else swatches[0])
        self.swatches = swatches

    def options(self):
        return self.swatches

    def draw_option(self, cr, box, value, active):
        centre_x = box.x + box.width / 2
        centre_y = box.y + box.height / 2
        painting.circle(cr, centre_x, centre_y, theme.SWATCH_RADIUS, value)
        painting.circle_outline(
            cr, centre_x, centre_y, theme.SWATCH_RADIUS, theme.SWATCH_EDGE, 1.0
        )
        if active:
            painting.circle_outline(
                cr, centre_x, centre_y, theme.SWATCH_RADIUS + 3,
                theme.SWATCH_RING, 1.6,
            )


class ChoiceSetting(Setting):
    """Segmented buttons, labelled with text."""

    def __init__(self, key, label, default, options):
        super().__init__(key, label, default)
        self._options = tuple(options)  # ((value, caption), ...)

    def options(self):
        return tuple(value for value, _caption in self._options)

    def caption(self, value):
        for candidate, caption in self._options:
            if candidate == value:
                return caption
        return str(value)

    def draw_option(self, cr, box, value, active):
        if active:
            painting.fill_rounded(cr, box, theme.ACCENT_SOFT, 4)
        painting.select_font(cr, theme.FONT_UI, theme.FONT_SIZE_SETTING)
        colour = theme.ACCENT if active else theme.SETTINGS_MARK
        painting.draw_text_centred(cr, self.caption(value), box, colour)


class WidthSetting(ChoiceSetting):
    """Line thickness, drawn as dots of the size you would get."""

    def draw_option(self, cr, box, value, active):
        if active:
            painting.fill_rounded(cr, box, theme.ACCENT_SOFT, 4)
        radius = min(value, theme.SETTINGS_OPTION - 12) / 2.0
        painting.circle(
            cr,
            box.x + box.width / 2,
            box.y + box.height / 2,
            max(1.5, radius),
            theme.ACCENT if active else theme.SETTINGS_MARK,
        )


class SettingValues:
    """Current value of every setting, keyed by setting key."""

    def __init__(self):
        self._values = {}

    def get(self, setting):
        return self._values.get(setting.key, setting.default)

    def set(self, setting, value):
        self._values[setting.key] = value

    def snapshot(self, settings):
        """A plain dict for a tool, taken when a gesture starts.

        Handing the tool a copy means a stroke keeps the colour it began with
        even if the setting changes before it is finished.
        """
        return {setting.key: self.get(setting) for setting in settings}


# Shared instances, so every tool that wants a colour gets the same one.
COLOUR = ColourSetting()
WIDTH = WidthSetting(
    "width", "Width", 4, ((2, "S"), (4, "M"), (8, "L"), (16, "XL"))
)
