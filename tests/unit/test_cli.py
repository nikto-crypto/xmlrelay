"""Unit tests for the ``python -m xmlrelay`` command line."""

import io
import marshal
import subprocess
import sys


def _decode(blob):
    items = []
    buffer = io.BytesIO(blob)
    try:
        while True:
            items.append(marshal.load(buffer))
    except EOFError:
        pass
    return items


def _run(args, stdin_bytes):
    return subprocess.run(
        [sys.executable, "-m", "xmlrelay", *args],
        input=stdin_bytes,
        capture_output=True,
    )


def test_stream_depth_two():
    proc = _run(["2"], b"<a><b>1</b><c>2</c></a>")
    assert proc.returncode == 0
    assert _decode(proc.stdout) == [
        ([("a", None), ("b", None)], "1"),
        ([("a", None), ("c", None)], "2"),
    ]


def test_depth_zero_emits_whole_document():
    proc = _run(["0"], b"<a>x</a>")
    assert proc.returncode == 0
    assert _decode(proc.stdout) == [([], {"a": "x"})]


def test_negative_depth_emits_nothing():
    proc = _run(["-1"], b"<a><b>1</b></a>")
    assert proc.returncode == 0
    assert proc.stdout == b""


def test_leading_space_argument_accepted():
    proc = _run([" 2"], b"<a><b>1</b></a>")
    assert proc.returncode == 0
    assert _decode(proc.stdout) == [([("a", None), ("b", None)], "1")]


def test_missing_argument_fails():
    proc = _run([], b"<a/>")
    assert proc.returncode != 0
    assert b"ValueError" in proc.stderr


def test_extra_argument_fails():
    proc = _run(["1", "2"], b"<a/>")
    assert proc.returncode != 0
    assert b"ValueError" in proc.stderr


def test_bad_xml_exits_nonzero_with_partial_output():
    proc = _run(["2"], b"<r><a>1</a><b></r>")
    assert proc.returncode != 0
    assert _decode(proc.stdout) == [([("r", None), ("a", None)], "1")]
    assert b"ExpatError" in proc.stderr
