"""Differential tests for :func:`xmlrelay.unparse`."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from . import strategies as S
from .strategies import examples
from .compare import check_unparse, check_unparse_stream

STREAM_KINDS = ["bytes", "text", "writeonly"]


# -- generated inputs --------------------------------------------------------


@settings(max_examples=examples(3000), deadline=None)
@given(data=S.unparse_inputs())
def test_generated_roundtrip_value(data):
    check_unparse(data)


@settings(max_examples=examples(2500), deadline=None)
@given(
    data=S.unparse_inputs(),
    pretty=st.booleans(),
    short=st.booleans(),
)
def test_generated_pretty_short(data, pretty, short):
    check_unparse(data, pretty=pretty, short_empty_elements=short)


@settings(max_examples=examples(2000), deadline=None)
@given(
    data=S.unparse_inputs(),
    indent=st.sampled_from(["\t", "  ", 2, 4, ""]),
    newl=st.sampled_from(["\n", "\r\n", ""]),
)
def test_generated_pretty_indent(data, indent, newl):
    check_unparse(data, pretty=True, indent=indent, newl=newl)


@settings(max_examples=examples(1500), deadline=None)
@given(data=S.unparse_inputs(), encoding=st.sampled_from(["utf-8", "ascii", "latin-1"]))
def test_generated_encoding(data, encoding):
    check_unparse(data, encoding=encoding)


@settings(max_examples=examples(1000), deadline=None)
@given(data=S.unparse_inputs(), kind=st.sampled_from(STREAM_KINDS))
def test_generated_stream(data, kind):
    check_unparse_stream(data, kind)


# -- structural rules --------------------------------------------------------


def test_text_after_children_pretty():
    check_unparse({"a": {"b": "1", "#text": "t"}}, pretty=True)


def test_multiple_roots_error():
    check_unparse({"a": "1", "b": "2"})


def test_multiple_roots_from_list():
    check_unparse({"a": [1, 2]})


def test_empty_list_root():
    check_unparse({"a": []})


def test_zero_roots():
    check_unparse({})
    check_unparse({"#comment": "c"})


def test_non_dict_input():
    check_unparse("not a dict")
    check_unparse([1])
    check_unparse(None)


def test_full_document_false():
    check_unparse({"a": "1", "b": "2"}, full_document=False)
    check_unparse({}, full_document=False)


@pytest.mark.parametrize("kind", STREAM_KINDS)
def test_partial_output_on_error(kind):
    check_unparse_stream({"a": "1", "b": "2"}, kind)
    check_unparse_stream({"a": [1, 2]}, kind)
    check_unparse_stream("not a dict", kind)


# -- values ------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, 1, 1.5, b"bytes", "text", [1, 2], ["x", "y"], (1, 2)],
)
def test_scalar_values(value):
    check_unparse({"a": value})
    check_unparse({"a": {"#text": value}})
    check_unparse({"a": {"@x": value}})


def test_nested_list_without_expand():
    check_unparse({"a": {"b": [1, [2, 3]]}})


@pytest.mark.parametrize("ei", ["item", "x"])
def test_expand_iter(ei):
    check_unparse({"a": {"b": [1, [2, [3, 4]]]}}, expand_iter=ei)


# -- comments ----------------------------------------------------------------


@pytest.mark.parametrize("value", ["c", "<&>", 0, False, "", None, ["c1", "c2"]])
def test_comment_values(value):
    check_unparse({"a": {"#comment": value, "b": "1"}})
    check_unparse({"a": {"#comment": value, "b": "1"}}, pretty=True)


def test_comment_in_short_empty():
    check_unparse({"a": {"#comment": "x"}}, short_empty_elements=True)


# -- attributes & names ------------------------------------------------------


def test_attr_quote_selection():
    check_unparse({"a": {"@x": 'he said "hi"'}})
    check_unparse({"a": {"@x": "it's \"both\""}})
    check_unparse({"a": {"@x": "line\ntab\tcr\r"}})


@pytest.mark.parametrize("name", ["1a", "", "a.b", "-a", "a&b", "a:b", "a b", "<a", "a>"])
def test_name_validation(name):
    check_unparse({name: "x"})
    check_unparse({"a": {"@" + name: "1"}})


# -- namespaces --------------------------------------------------------------


def test_ns_drop_and_mangle():
    check_unparse({"p:r": "1"}, namespaces={"x": "y"})
    check_unparse({"r": {"@p:key": "1"}}, namespaces={"x": "y"})
    check_unparse({"a:b": "1"}, namespaces={"a": "z"})
    check_unparse({"z:b": {"@z:c": "1"}}, namespaces={"a": "z"})


def test_xmlns_dict():
    check_unparse({"a": {"@xmlns": {"": "u", "p": None}}})
    check_unparse({"a": {"@x": "1", "@xmlns": {"p": "u"}}})
    check_unparse({"a": {"@xmlns": "u"}})
    check_unparse({"a": {"@xmlns": {}}})


def test_custom_attr_prefix_xmlns():
    check_unparse({"r": {"!xmlns": {"p": "u"}}}, attr_prefix="!")


# -- bytes_errors ------------------------------------------------------------


@pytest.mark.parametrize(
    "be", ["replace", "strict", "ignore", "backslashreplace", "xmlcharrefreplace", "bogus"]
)
def test_bytes_errors(be):
    check_unparse({"a": {"@x": "é".encode("utf-8")}}, encoding="ascii", bytes_errors=be)
    check_unparse({"a": b"\xff\xfe"}, encoding="ascii", bytes_errors=be)


def test_bytes_errors_reported_first():
    check_unparse({"a": "1"}, bytes_errors="bogus")


# -- preprocessor ------------------------------------------------------------


def test_preprocessor_rename():
    check_unparse({"a": {"b": "1", "c": "2"}}, preprocessor=lambda k, v: ("X", v) if k == "b" else (k, v))


def test_preprocessor_drop():
    check_unparse({"a": {"b": "1", "c": "2"}}, preprocessor=lambda k, v: None if k == "b" else (k, v))
    check_unparse(
        {"a": {"b": "1", "c": "2"}},
        preprocessor=lambda k, v: None if k == "b" else (k, v),
        pretty=True,
    )


def test_preprocessor_to_comment_key():
    check_unparse({"x": "1"}, preprocessor=lambda k, v: ("#comment", v), full_document=False)


# -- curated round-trips -----------------------------------------------------

_CURATED = [
    {"config": {"@version": "1.0", "server": {"@host": "h", "@port": 8080}, "flags": {"debug": True}}},
    {"rss": {"@version": "2.0", "channel": {"title": "F", "item": [{"title": "a"}, {"title": "b"}]}}},
    {"note": {"to": "A", "from": "B", "#comment": "hi", "body": "x & y"}},
    {"a": {"@xmlns": {"": "urn:x"}, "b": {"#text": "v"}}},
    {"doc": {"list": {"item": [1, 2, 3]}, "#text": "trailing"}},
]


@pytest.mark.parametrize("data", _CURATED)
@pytest.mark.parametrize("pretty", [False, True])
def test_curated(data, pretty):
    check_unparse(data, pretty=pretty)
    for kind in STREAM_KINDS:
        check_unparse_stream(data, kind, pretty=pretty)
