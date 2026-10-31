"""Command-line streaming front end for :mod:`xmlrelay`.

Usage::

    python -m xmlrelay <depth>

XML is read from standard input and parsed in streaming mode at the given
``item_depth``.  Each item that reaches that depth is written to standard
output as a ``marshal``-encoded ``(path, item)`` tuple.
"""

import marshal
import sys

from ._decode import parse


def main(argv):
    (raw_depth,) = argv
    depth = int(raw_depth)

    out = sys.stdout.buffer

    def deliver(path, item):
        marshal.dump((path, item), out)
        return True

    whole = parse(sys.stdin.buffer, item_depth=depth, item_callback=deliver)
    if depth == 0:
        deliver([], whole)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        # Interrupting a streaming parse exits quietly with a success status
        # rather than dumping a traceback.
        pass
