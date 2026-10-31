"""xmlrelay -- convert between XML and ordered Python mappings.

``parse`` reads XML into nested dictionaries; ``unparse`` writes nested
dictionaries back out as XML.  ``ParsingInterrupted`` is raised when a parse
is stopped early by an ``item_callback``.
"""

from ._decode import parse
from ._encode import unparse
from ._exceptions import ParsingInterrupted

__all__ = ["parse", "unparse", "ParsingInterrupted"]

__version__ = "1.1.0"
