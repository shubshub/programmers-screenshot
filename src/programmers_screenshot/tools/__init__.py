"""The tools the toolbar offers, in the order they appear.

Adding a tool
-------------
1. Write the class in a new file in this directory. If it is a "drag from A to
   B" shape, subclass ShapeTool and implement make_item(); for any other drag,
   subclass DragTool and implement complete(). Only reach for Tool directly if
   the gesture is not a drag at all.
2. Import it below and add it to ALL_TOOLS.

That is the whole job. The toolbar button, its icon, the settings row, the
preview, the undo entry and inclusion in the captured image all follow.
"""

from .base import DragTool, ShapeTool, Tool
from .items import (
    Arrow,
    Box,
    Ellipse,
    Highlight,
    Item,
    Line,
    Redaction,
    Shape,
    Stroke,
)
from .highlight import HighlighterTool
from .line import LineTool
from .pen import PenTool
from .pixelate import PixelateTool
from .rectangle import RectangleTool
from .redact import RedactTool
from .step import StepTool
from .text import TextTool

ALL_TOOLS = (
    RectangleTool,
    PenTool,
    HighlighterTool,
    LineTool,
    RedactTool,
    PixelateTool,
    StepTool,
    TextTool,
)

__all__ = [
    "ALL_TOOLS",
    "Arrow",
    "Box",
    "DragTool",
    "Ellipse",
    "Highlight",
    "Item",
    "Line",
    "Redaction",
    "Shape",
    "ShapeTool",
    "Stroke",
    "Tool",
    "build_tools",
]


def build_tools():
    """A fresh instance of every tool, for one overlay session."""
    return [factory() for factory in ALL_TOOLS]
