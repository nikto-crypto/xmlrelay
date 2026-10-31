"""Differential coverage for the Fix round 1 findings.

These cases close the harness gap that let seven divergences from the reference
go unnoticed.  Each section targets one finding and exercises the whole class of
inputs, not just the reported example:

1. unparse name validation (element / attribute / @xmlns-prefix names, every
   rejected character class, rule precedence, and non-string keys);
2. unparse comment validation ("--" anywhere, a trailing "-", and bytes);
3. @xmlns values converted like any other attribute value;
4. selective ``force_cdata`` (every container type, a str by substring, a
   callable and a bare bool);
5. str (and generator-of-str) input whose declaration names a non-UTF-8 encoding;
6. ``namespaces`` maps looked up by item access (dict subclasses with defaults);
7. a KeyboardInterrupt during a CLI parse exiting quietly.
"""

import sys
from collections import defaultdict

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from . import strategies as S
from .strategies import examples
from .compare import (
    check_cli_keyboard_interrupt,
    check_parse,
    check_unparse,
    check_unparse_stream,
)

STREAM_KINDS = ["bytes", "text", "writeonly"]


# -- Finding 1: unparse name validation --------------------------------------


@settings(max_examples=examples(3000), deadline=None)
@given(data=S.unparse_name_inputs())
def test_name_inputs_value(data):
    check_unparse(data, full_document=False)
    check_unparse(data)


@settings(max_examples=examples(1500), deadline=None)
@given(data=S.unparse_name_inputs(), kind=st.sampled_from(STREAM_KINDS))
def test_name_inputs_stream(data, kind):
    # partial output on the error path must match too
    check_unparse_stream(data, kind)


@pytest.mark.parametrize("name", S._BAD_NAMES + S._VALID_EDGE_NAMES)
def test_element_name_each_class(name):
    check_unparse({name: "v"}, full_document=False)
    check_unparse({"r": {name: "v"}}, full_document=False)


@pytest.mark.parametrize("name", S._BAD_NAMES + S._VALID_EDGE_NAMES)
def test_attribute_name_each_class(name):
    check_unparse({"r": {"@" + name: "v", "c": "1"}}, full_document=False)


@pytest.mark.parametrize("key", S._NON_STRING_KEYS)
def test_non_string_keys(key):
    check_unparse({key: "v"}, full_document=False)
    check_unparse({"r": {key: "v"}}, full_document=False)
    check_unparse({"r": {"@xmlns": {key: "u"}}}, full_document=False)


@pytest.mark.parametrize("key", S._BAD_XMLNS_KEYS)
def test_xmlns_bad_prefix(key):
    check_unparse({"r": {"@xmlns": {key: "u"}}}, full_document=False)


# -- Finding 2: unparse comment validation -----------------------------------


@settings(max_examples=examples(1500), deadline=None)
@given(
    data=S.unparse_comment_inputs(),
    pretty=st.booleans(),
    kind=st.sampled_from(STREAM_KINDS),
)
def test_comment_inputs_stream(data, pretty, kind):
    check_unparse(data, pretty=pretty)
    check_unparse_stream(data, kind, pretty=pretty)


@pytest.mark.parametrize("body", S._BAD_COMMENTS + S._OK_COMMENTS)
def test_comment_each_case(body):
    check_unparse({"r": {"#comment": body, "x": "1"}}, full_document=False)
    check_unparse({"r": {"#comment": body, "x": "1"}}, full_document=False, pretty=True)


# -- Finding 3: @xmlns value conversion --------------------------------------


@pytest.mark.parametrize("value", S._XMLNS_VALUES)
def test_xmlns_value_conversion(value):
    check_unparse({"r": {"@xmlns": {"a": value}}}, full_document=False)


def test_xmlns_mixed_values():
    check_unparse(
        {"r": {"@xmlns": {"a": True, "b": b"http://x/", "c": None, "": 5}}},
        full_document=False,
    )


# -- Finding 4: selective force_cdata ----------------------------------------


_FORCE_CDATA = [
    ("b",),
    ["b"],
    {"b"},
    frozenset({"b"}),
    {"b": True},
    "b",
    "bc",
    True,
    False,
    None,
    (),
    "",
]


@pytest.mark.parametrize("rule", _FORCE_CDATA)
def test_force_cdata_shapes(rule):
    check_parse("<a><b>1</b><c>2</c></a>", force_cdata=rule)
    check_parse("<a><bc>1</bc><c>2</c></a>", force_cdata=rule)


def test_force_cdata_callable():
    check_parse(
        "<a><b>1</b><c>2</c></a>",
        force_cdata=lambda path, key, value: key == "b",
    )


# -- Finding 5: str input encoding overrides the declaration -----------------

_ISO_DOC = '<?xml version="1.0" encoding="iso-8859-1"?><a>café</a>'
_ASCII_DOC = '<?xml version="1.0" encoding="ascii"?><a>café</a>'


@pytest.mark.parametrize("doc", [_ISO_DOC, _ASCII_DOC])
@pytest.mark.parametrize("encoding", [None, "utf-8", "iso-8859-1", "latin-1"])
def test_str_input_declaration_override(doc, encoding):
    kwargs = {} if encoding is None else {"encoding": encoding}
    check_parse(doc, **kwargs)


@pytest.mark.parametrize("encoding", [None, "utf-8"])
def test_generator_str_declaration_override(encoding):
    kwargs = {} if encoding is None else {"encoding": encoding}
    check_parse(lambda: (c for c in [_ISO_DOC]), **kwargs)


# -- Finding 6: namespace maps looked up by item access ----------------------

_NS_DOC = '<a xmlns="http://u/"><b/></a>'


class _PrefixDict(dict):
    def __missing__(self, key):
        return "p"


def test_namespaces_defaultdict_none():
    check_parse(
        _NS_DOC,
        process_namespaces=True,
        namespaces=defaultdict(lambda: None),
    )


def test_namespaces_defaultdict_const():
    check_parse(
        _NS_DOC,
        process_namespaces=True,
        namespaces=defaultdict(lambda: "NS"),
    )


def test_namespaces_dict_subclass_missing():
    check_parse(_NS_DOC, process_namespaces=True, namespaces=_PrefixDict())


def test_namespaces_plain_dict_unknown_unchanged():
    check_parse(_NS_DOC, process_namespaces=True, namespaces={"http://other/": "o"})


# -- Finding 7: CLI KeyboardInterrupt ----------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGINT semantics")
def test_cli_keyboard_interrupt():
    check_cli_keyboard_interrupt()
