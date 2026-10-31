"""Differential tests for the ``python -m xmlrelay`` command line."""

import pytest

from .compare import check_cli


@pytest.mark.parametrize(
    "args, stdin",
    [
        (["1"], b"<a><b>1</b><c>2</c></a>"),
        (["2"], b"<a><b>1</b><c>2</c></a>"),
        (["2"], b'<a><b x="1">t</b><c> u </c></a>'),
        (["1"], b"<r><a>1</a><a>2</a></r>"),
        (["0"], b"<a>x</a>"),
        (["-1"], b"<a><b>1</b></a>"),
        ([" 2"], b"<a><b>1</b></a>"),
        (["3"], b"<a><b>1</b></a>"),
    ],
)
def test_cli_streaming(args, stdin):
    check_cli(args, stdin)


@pytest.mark.parametrize(
    "args, stdin",
    [
        ([], b"<a/>"),
        (["1", "2"], b"<a/>"),
        (["2"], b"<a><b></a>"),
        (["notanint"], b"<a/>"),
    ],
)
def test_cli_errors(args, stdin):
    check_cli(args, stdin)


def test_cli_partial_before_error():
    # one item reaches depth 1 and is written before the mismatched tag fails
    check_cli(["1"], b"<r><a>1</a><b></r>")
