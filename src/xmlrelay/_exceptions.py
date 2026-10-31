"""Exceptions raised by :mod:`xmlrelay`."""


class ParsingInterrupted(Exception):
    """Raised to abort a parse when an ``item_callback`` asks it to stop.

    The decoder calls ``item_callback`` once for every element that reaches
    ``item_depth``.  When that callback returns a value that is falsy, the
    decoder stops immediately by raising this exception with no message.
    """


__all__ = ["ParsingInterrupted"]
