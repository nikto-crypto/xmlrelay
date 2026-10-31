"""Additional differential cases filling coverage gaps.

These target channels / options / input types that the other differential
modules do not exercise:

* ``dict_constructor`` (OrderedDict and a repr-visible dict subclass) on parse;
* exotic parse inputs -- memoryview over a slice, generators that mix ``str``
  and ``bytes`` chunks or yield empty chunks;
* ``cdata_separator`` interacting with comments and CDATA section boundaries;
* the streaming quirks (a streamed element with attributes drops its text;
  streamed text is *not* whitespace-stripped) observed through ``item_callback``;
* ``postprocessor`` acting on comments and on the ``@xmlns`` mapping;
* ``namespaces`` mapping a prefix to the empty string (drop) on parse;
* ``force_list`` as a dict and as a callable returning non-bool values;
* non-list/tuple iterables (set, frozenset, range) as ``unparse`` values,
  including the empty-iterable pretty-layout edge;
* custom ``cdata_key`` / ``comment_key`` on ``unparse``;
* partial output when a name-validation error fires mid-document.
"""

from collections import OrderedDict

import io

import pytest

from .compare import check_parse, check_unparse, check_unparse_stream
from .test_callbacks_diff import _record_parse

STREAM_KINDS = ["bytes", "text", "writeonly"]


# -- dict_constructor --------------------------------------------------------


class _LoudDict(dict):
    """A dict subclass whose repr is distinguishable from a plain dict."""

    def __repr__(self):
        return "_LoudDict(%s)" % dict.__repr__(self)


_DC_DOCS = [
    '<a x="1"><b>1</b><b>2</b><c>t</c></a>',
    '<p:a xmlns:p="u" p:c="1"><p:b>1</p:b></p:a>',
    "<a><b>1</b><!--c--><b>2</b>t</a>",
    "<a/>",
]


@pytest.mark.parametrize("doc", _DC_DOCS)
@pytest.mark.parametrize("ctor", [OrderedDict, _LoudDict])
def test_dict_constructor(doc, ctor):
    # repr carries the container type, so a plain-dict leak anywhere diverges.
    check_parse(doc, dict_constructor=ctor, process_comments=True)
    check_parse(doc, dict_constructor=ctor, process_namespaces=True)
    check_parse(doc, dict_constructor=ctor, force_list=True, process_comments=True)


# -- exotic parse inputs -----------------------------------------------------

_SAMPLE = '<a x="1"><b>hi</b><b>café</b><c/></a>'


def test_input_memoryview_slice():
    raw = b"xx" + _SAMPLE.encode("utf-8") + b"yy"
    check_parse(lambda: memoryview(raw)[2:-2])


def test_input_generator_mixed_str_bytes():
    def chunks():
        yield "<a>ab"
        yield b"cd"
        yield "</a>"

    check_parse(lambda: chunks())
    check_parse(lambda: chunks(), cdata_separator="|")


def test_input_generator_empty_chunks():
    def chunks():
        yield ""
        yield b""
        yield "<a>x"
        yield ""
        yield "y</a>"
        yield b""

    check_parse(lambda: chunks())
    check_parse(lambda: chunks(), cdata_separator="|")


def test_input_empty_generator():
    def chunks():
        return
        yield  # pragma: no cover

    check_parse(lambda: chunks())


# -- cdata_separator interactions --------------------------------------------


@pytest.mark.parametrize("sep", ["", "|", "--"])
def test_cdata_separator_across_cdata_sections(sep):
    # a text run, a CDATA section, and another text run inside one element
    check_parse("<a>x<![CDATA[y]]>z</a>", cdata_separator=sep)
    check_parse("<a><![CDATA[p]]><![CDATA[q]]></a>", cdata_separator=sep)


@pytest.mark.parametrize("sep", ["", "|", "--"])
def test_cdata_separator_across_comments(sep):
    # comments interrupt the character-data runs
    check_parse("<a>x<!--c-->y</a>", cdata_separator=sep)
    check_parse("<a>x<!--c-->y</a>", cdata_separator=sep, process_comments=True)
    check_parse(
        "<a>x<!--c-->y</a>",
        cdata_separator=sep,
        process_comments=True,
        strip_whitespace=False,
    )


@pytest.mark.parametrize("sep", ["", "|"])
def test_cdata_separator_streamed_value(sep):
    # a streamed leaf joins runs with cdata_separator and is NOT stripped
    _record_parse(
        "<a> x <![CDATA[y]]> z </a>",
        "item_callback",
        lambda p, i: True,
        item_depth=1,
        cdata_separator=sep,
    )


# -- streaming quirks --------------------------------------------------------


def test_streamed_element_with_attrs_drops_text():
    # element at item_depth has attributes -> delivered value is attrs, text lost
    _record_parse(
        '<r><row id="1">text</row><row id="2">more</row></r>',
        "item_callback",
        lambda p, i: True,
        item_depth=2,
    )


def test_streamed_text_not_stripped():
    _record_parse(
        "<r><row>  spaced  </row><row>\n\t</row></r>",
        "item_callback",
        lambda p, i: True,
        item_depth=2,
    )


def test_streamed_depth_equals_leaf_with_children():
    # item_depth equals the depth of an element that has children+text+attrs
    _record_parse(
        '<a><b x="1">t<c>u</c>tail</b></a>',
        "item_callback",
        lambda p, i: True,
        item_depth=2,
    )


def test_streamed_depth_beyond_tree():
    _record_parse(
        "<a><b>1</b></a>",
        "item_callback",
        lambda p, i: True,
        item_depth=5,
    )


# -- postprocessor on comments / xmlns ---------------------------------------


def test_postprocessor_on_comment():
    doc = "<a><!--keep--><b>1</b></a>"
    _record_parse(doc, "postprocessor", lambda p, k, v: (k, v), process_comments=True)
    # drop the comment
    _record_parse(
        doc,
        "postprocessor",
        lambda p, k, v: None if k == "#comment" else (k, v),
        process_comments=True,
    )
    # rewrite the comment into a 2-char pair
    _record_parse(
        doc,
        "postprocessor",
        lambda p, k, v: "cc" if k == "#comment" else (k, v),
        process_comments=True,
    )


def test_postprocessor_on_xmlns():
    doc = '<p:a xmlns:p="u" p:c="1">t</p:a>'
    _record_parse(
        doc,
        "postprocessor",
        lambda p, k, v: (k, v),
        process_namespaces=True,
    )


def test_postprocessor_attr_two_char_string():
    # a 2-char string return is unpacked as (k, v) for attributes too
    _record_parse(
        '<a x="1">t</a>',
        "postprocessor",
        lambda p, k, v: "kv" if k == "@x" else (k, v),
    )


# -- namespaces mapping to empty string --------------------------------------


def test_namespaces_map_to_empty_string():
    # a falsy ("" ) mapping drops the prefix, like None does
    check_parse('<a:b xmlns:a="x" a:c="1"/>', namespaces={"a": ""})
    check_parse(
        '<a:b xmlns:a="x" a:c="1"/>',
        process_namespaces=True,
        namespaces={"x": ""},
    )


def test_namespaces_process_custom_sep_and_map():
    check_parse(
        '<a:b xmlns:a="urn:x" a:c="1"><a:d>t</a:d></a:b>',
        process_namespaces=True,
        namespace_separator="|",
        namespaces={"urn:x": "Z"},
    )


# -- force_list shapes -------------------------------------------------------


def test_force_list_dict():
    check_parse("<a><b>1</b><c>2</c></a>", force_list={"b": True, "c": False})
    check_parse("<a><b>1</b><c>2</c></a>", force_list={"b": 0})


@pytest.mark.parametrize("ret", ["yes", "", 1, 0, None, ["x"]])
def test_force_list_callable_non_bool(ret):
    check_parse("<a><b>1</b><c>2</c></a>", force_list=lambda p, k, v: ret)


# -- unparse: non-list/tuple iterables ---------------------------------------


def test_unparse_set_value():
    check_unparse({"a": {"b": {1}}})
    check_unparse({"a": {"b": frozenset(["x"])}})


def test_unparse_range_value():
    check_unparse({"a": {"b": range(3)}})
    check_unparse({"a": {"b": range(3)}}, expand_iter="i")


@pytest.mark.parametrize("empty", [set(), frozenset(), range(0)])
def test_unparse_empty_iterable_pretty(empty):
    # the reference treats an empty set/range as content (unlike []),
    # which changes pretty layout; xmlrelay agrees for these.
    check_unparse({"a": {"b": empty, "#text": "t"}}, pretty=True)
    check_unparse({"a": {"b": empty, "c": "1"}}, pretty=True)


def test_unparse_empty_list_pretty():
    check_unparse({"a": {"b": [], "#text": "t"}}, pretty=True)
    check_unparse({"a": {"b": [], "c": "1"}}, pretty=True)


def test_unparse_empty_tuple_pretty():
    check_unparse({"a": {"b": (), "#text": "t"}}, pretty=True)


# -- unparse: custom cdata_key / comment_key ---------------------------------


def test_unparse_custom_cdata_key():
    data = {"a": {"@x": "1", "$t": "body"}}
    check_unparse(data, cdata_key="$t")
    check_unparse(data, cdata_key="$t", pretty=True)


def test_unparse_custom_comment_key():
    data = {"a": {"!!": "a comment", "b": "1"}}
    check_unparse(data, comment_key="!!")
    check_unparse(data, comment_key="!!", pretty=True)


def test_unparse_xmlns_non_dict_value():
    check_unparse({"a": {"@xmlns": 5}})
    check_unparse({"a": {"@xmlns": "u"}})


# -- unparse: partial output on mid-document name error ----------------------


@pytest.mark.parametrize("kind", STREAM_KINDS)
def test_unparse_partial_on_bad_child_name(kind):
    # first child writes, second child has an invalid name -> error mid-stream
    data = {"root": {"good": "1", "bad name": "2"}}
    check_unparse_stream(data, kind)


@pytest.mark.parametrize("kind", STREAM_KINDS)
def test_unparse_partial_on_bad_child_name_pretty(kind):
    data = {"root": {"good": "1", "bad name": "2"}}
    check_unparse_stream(data, kind, pretty=True)


@pytest.mark.parametrize("kind", STREAM_KINDS)
def test_unparse_partial_on_bad_attr_name(kind):
    data = {"root": {"@ok": "1", "@bad<name": "2", "child": "c"}}
    check_unparse_stream(data, kind)


# -- unparse: encode-time bytes error mid-document (strict) -------------------


@pytest.mark.parametrize("kind", STREAM_KINDS)
def test_unparse_partial_on_strict_bytes_error(kind):
    data = {"root": {"a": "ok", "b": b"\xff\xfe"}}
    check_unparse_stream(data, kind, encoding="ascii", bytes_errors="strict")
