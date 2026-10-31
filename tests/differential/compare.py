"""Channel-by-channel comparison helpers for differential tests.

Every helper runs both the reference build and :mod:`xmlrelay` on identical
inputs and asserts the observable behaviour matches: return values (by repr, so
key order and container types count), raised exceptions (class and message),
bytes written to an output stream (including partial output on failure), and
the exact sequence of callback invocations.
"""

import copy
import io
import marshal
import signal
import subprocess
import sys
import time

import xmlrelay

from . import oracle

# Running tallies of how many differential comparisons each channel has made.
# A session-end hook in conftest prints these so the suite can evidence the
# number of generated cases exercised.
COUNTS = {"parse": 0, "unparse": 0, "cli": 0}


def invoke(fn, *args, **kwargs):
    """Call ``fn`` and capture either its value or its exception identity."""
    try:
        return ("value", fn(*args, **kwargs))
    except Exception as exc:
        return ("error", (type(exc).__name__, str(exc)))


def _describe(outcome):
    kind, payload = outcome
    if kind == "error":
        return "error", payload
    return "value", repr(payload)


# -- parse -------------------------------------------------------------------


def check_parse(xml_input, **kwargs):
    """Compare ``parse`` on both builds.

    ``xml_input`` may be a plain reusable value (str/bytes/...) or a zero-arg
    factory (for single-use inputs such as streams and generators) that is
    called once per implementation so each side gets a fresh object.
    """
    ref = oracle.reference()
    COUNTS["parse"] += 1

    def fresh():
        return xml_input() if callable(xml_input) else xml_input

    expected = invoke(ref.parse, fresh(), **kwargs)
    actual = invoke(xmlrelay.parse, fresh(), **kwargs)
    assert _describe(expected) == _describe(actual), (
        "parse mismatch for %r %r\n  reference=%r\n  xmlrelay =%r"
        % (xml_input, kwargs, expected, actual)
    )
    return expected, actual


# -- unparse (return value) --------------------------------------------------


def check_unparse(input_dict, **kwargs):
    ref = oracle.reference()
    COUNTS["unparse"] += 1
    expected = invoke(ref.unparse, copy.deepcopy(input_dict), **kwargs)
    actual = invoke(xmlrelay.unparse, copy.deepcopy(input_dict), **kwargs)
    assert _describe(expected) == _describe(actual), (
        "unparse mismatch for %r %r\n  reference=%r\n  xmlrelay =%r"
        % (input_dict, kwargs, expected, actual)
    )
    return expected, actual


# -- unparse (output stream) -------------------------------------------------


class _WriteOnly:
    """A stream exposing only ``write`` (no ``read``/``seek``/``encoding``)."""

    def __init__(self):
        self._chunks = []

    def write(self, chunk):
        self._chunks.append(chunk)
        return len(chunk)

    def value(self):
        if not self._chunks:
            return b""
        joiner = b"" if isinstance(self._chunks[0], bytes) else ""
        return joiner.join(self._chunks)


def _new_stream(kind):
    if kind == "bytes":
        return io.BytesIO(), lambda s: s.getvalue()
    if kind == "text":
        return io.StringIO(), lambda s: s.getvalue()
    if kind == "writeonly":
        s = _WriteOnly()
        return s, lambda s: s.value()
    raise ValueError(kind)


def _run_to_stream(unparse_fn, input_dict, kind, kwargs):
    stream, read_back = _new_stream(kind)
    try:
        returned = unparse_fn(copy.deepcopy(input_dict), output=stream, **kwargs)
        return ("value", returned, read_back(stream))
    except Exception as exc:
        return ("error", (type(exc).__name__, str(exc)), read_back(stream))


def check_unparse_stream(input_dict, kind, **kwargs):
    ref = oracle.reference()
    COUNTS["unparse"] += 1
    expected = _run_to_stream(ref.unparse, input_dict, kind, kwargs)
    actual = _run_to_stream(xmlrelay.unparse, input_dict, kind, kwargs)
    # returned value: None on success for both; identity of error; written bytes
    assert expected[0] == actual[0] and expected[1:] == actual[1:], (
        "unparse(output=%s) mismatch for %r %r\n  reference=%r\n  xmlrelay =%r"
        % (kind, input_dict, kwargs, expected, actual)
    )
    return expected, actual


# -- callbacks ---------------------------------------------------------------


def snapshot_path(path):
    """Freeze a live callback path into a comparable value."""
    return [(name, dict(attrs) if attrs is not None else None) for name, attrs in path]


# -- command line ------------------------------------------------------------


def _decode_marshal(blob):
    items = []
    buffer = io.BytesIO(blob)
    try:
        while True:
            items.append(marshal.load(buffer))
    except EOFError:
        pass
    return items


def _run_cli(module, args, stdin_bytes, extra_path):
    env = {"PYTHONPATH": extra_path}
    import os

    full_env = dict(os.environ)
    full_env.update(env)
    proc = subprocess.run(
        [sys.executable, "-m", module, *args],
        input=stdin_bytes,
        capture_output=True,
        env=full_env,
    )
    return proc


def check_cli(args, stdin_bytes):
    import os

    oracle.reference()  # trigger skip/fail logic
    COUNTS["cli"] += 1
    repo_src = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "src",
    )
    ref_proc = _run_cli("xmltodict", args, stdin_bytes, oracle.ORACLE_DIR)
    relay_proc = _run_cli("xmlrelay", args, stdin_bytes, repo_src)

    assert ref_proc.returncode == relay_proc.returncode, (
        "CLI exit code mismatch args=%r: reference=%d xmlrelay=%d\n%s\n%s"
        % (
            args,
            ref_proc.returncode,
            relay_proc.returncode,
            ref_proc.stderr.decode("utf-8", "replace"),
            relay_proc.stderr.decode("utf-8", "replace"),
        )
    )
    assert _decode_marshal(ref_proc.stdout) == _decode_marshal(relay_proc.stdout), (
        "CLI stdout (decoded) mismatch args=%r" % (args,)
    )
    if ref_proc.returncode != 0:
        # last line of each traceback carries the exception class + message
        ref_last = ref_proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1]
        relay_last = (
            relay_proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1]
        )
        assert ref_last == relay_last, (
            "CLI error line mismatch args=%r\n  reference=%r\n  xmlrelay =%r"
            % (args, ref_last, relay_last)
        )


def _interrupt_cli(module, extra_path):
    """Start the CLI, let it block on stdin, send SIGINT, and capture the exit."""
    import os

    full_env = dict(os.environ)
    full_env["PYTHONPATH"] = extra_path
    proc = subprocess.Popen(
        [sys.executable, "-m", module, "1"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
    )
    # Give the child time to reach the blocking read on stdin, then interrupt.
    time.sleep(0.8)
    proc.send_signal(signal.SIGINT)
    try:
        out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        proc.kill()
        out, err = proc.communicate()
    return proc.returncode, out, err


def check_cli_keyboard_interrupt():
    """A SIGINT during a streaming parse must behave identically on both builds."""
    import os

    oracle.reference()  # trigger skip/fail logic
    COUNTS["cli"] += 1
    repo_src = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "src",
    )
    ref = _interrupt_cli("xmltodict", oracle.ORACLE_DIR)
    relay = _interrupt_cli("xmlrelay", repo_src)
    assert ref == relay, (
        "CLI KeyboardInterrupt mismatch\n  reference=%r\n  xmlrelay =%r"
        % (ref, relay)
    )
    return ref, relay
