"""Load the reference implementation for differential testing.

The reference is a bytecode-only build kept outside the repository (default
``~/xmlrelay-oracle``).  Because it ships as compiled bytecode it only loads on
the exact Python minor version and magic number recorded in its
``ORACLE_PYTHON.txt``.  When it cannot be loaded the differential tests skip --
unless ``XMLRELAY_REQUIRE_ORACLE=1`` is set, which turns every such skip into a
hard failure so CI cannot silently pass without the comparison.

Only ``parse``, ``unparse`` and ``ParsingInterrupted`` are ever touched on the
reference module; it is used strictly as a behavioural black box.
"""

import importlib.util
import os
import sys

import pytest

ORACLE_DIR = os.environ.get(
    "XMLRELAY_ORACLE_DIR", os.path.expanduser("~/xmlrelay-oracle")
)
_REQUIRE = os.environ.get("XMLRELAY_REQUIRE_ORACLE") == "1"

_reference = None
_skip_reason = None


def _current_magic():
    return importlib.util.MAGIC_NUMBER.hex()


def _load():
    global _reference, _skip_reason
    if _reference is not None or _skip_reason is not None:
        return

    stamp = os.path.join(ORACLE_DIR, "ORACLE_PYTHON.txt")
    if not os.path.isdir(ORACLE_DIR) or not os.path.isfile(stamp):
        _skip_reason = "reference build not present at %s" % ORACLE_DIR
        return

    with open(stamp) as handle:
        fields = handle.read().split()
    want_major, want_minor, want_magic = fields[0], fields[1], fields[2]

    if (str(sys.version_info.major), str(sys.version_info.minor)) != (
        want_major,
        want_minor,
    ):
        _skip_reason = "reference needs Python %s.%s, running %d.%d" % (
            want_major,
            want_minor,
            sys.version_info.major,
            sys.version_info.minor,
        )
        return
    if _current_magic() != want_magic:
        _skip_reason = "reference bytecode magic %s != %s" % (
            want_magic,
            _current_magic(),
        )
        return

    if ORACLE_DIR not in sys.path:
        sys.path.insert(0, ORACLE_DIR)
    try:
        import xmltodict as reference  # noqa: PLC0415  (intentional late import)
    except Exception as exc:  # pragma: no cover - defensive
        _skip_reason = "reference import failed: %r" % (exc,)
        return
    _reference = reference


def reference():
    """Return the loaded reference module, or skip/fail if unavailable."""
    _load()
    if _reference is None:
        if _REQUIRE:
            pytest.fail("XMLRELAY_REQUIRE_ORACLE=1 but " + (_skip_reason or "?"))
        pytest.skip(_skip_reason or "reference unavailable")
    return _reference
