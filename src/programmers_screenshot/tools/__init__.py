"""The tools the toolbar offers, in the order they appear.

Adding a tool
-------------
1. Write the class in a new file in this directory. If it is a "drag from A to
   B" shape, subclass ShapeTool and implement make_item(); otherwise subclass
   Tool and handle begin/extend/finish.
2. Import it below and add it to ALL_TOOLS.

That is the whole job. The toolbar button, its icon, the settings row, the
preview, the undo entry and inclusion in the captured image all follow.
"""

from .base import ShapeTool, Tool
from .items import Item, Stroke
from .pen import PenTool
from .rectangle import RectangleTool

ALL_TOOLS = (RectangleTool, PenTool)

__all__ = [
    "ALL_TOOLS",
    "Item",
    "ShapeTool",
    "Stroke",
    "Tool",
    "build_tools",
]


def build_tools():
    """A fresh instance of every tool, for one overlay session."""
    return [factory() for factory in ALL_TOOLS]
