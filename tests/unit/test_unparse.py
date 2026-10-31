"""Unit tests for :func:`xmlrelay.unparse` with self-contained assertions."""

import io

import pytest

from xmlrelay import unparse

DECL = '<?xml version="1.0" encoding="utf-8"?>\n'


def body(result):
    assert result.startswith(DECL)
    return result[len(DECL):]


def test_basic():
    assert unparse({"a": {"@x": "1", "#text": "t"}}) == DECL + '<a x="1">t</a>'


def test_text_after_children():
    assert body(unparse({"a": {"b": "1", "#text": "t"}})) == "<a><b>1</b>t</a>"


def test_pretty():
    assert body(unparse({"a": {"b": "1", "#text": "t"}}, pretty=True)) == "<a>\n\t<b>1</b>\nt</a>"


def test_pretty_nested_indent():
    assert body(unparse({"a": {"b": {"c": "1"}}}, pretty=True)) == "<a>\n\t<b>\n\t\t<c>1</c>\n\t</b>\n</a>"


def test_pretty_int_indent():
    assert body(unparse({"a": {"b": "1"}}, pretty=True, indent=2)) == "<a>\n  <b>1</b>\n</a>"


def test_list_children():
    assert body(unparse({"a": {"b": [1, 2]}})) == "<a><b>1</b><b>2</b></a>"


def test_empty_list_root_is_declaration_only():
    assert unparse({"a": []}) == DECL


def test_multiple_roots_error():
    with pytest.raises(ValueError, match="exactly one root"):
        unparse({"a": "1", "b": "2"})


def test_list_root_multiple_roots_error():
    with pytest.raises(ValueError, match="multiple roots"):
        unparse({"a": [1, 2]})


def test_non_dict_raises_attribute_error():
    with pytest.raises(AttributeError):
        unparse("not a dict")


def test_full_document_false_no_declaration():
    assert unparse({"a": "1"}, full_document=False) == "<a>1</a>"


def test_short_empty_elements():
    assert body(unparse({"a": {"@x": "1"}}, short_empty_elements=True)) == '<a x="1"/>'


def test_short_empty_with_comment():
    assert body(unparse({"a": {"#comment": "x"}}, short_empty_elements=True)) == "<a<!--x-->/>"


# -- value conversion --------------------------------------------------------


def test_bool_values():
    assert body(unparse({"a": True})) == "<a>true</a>"
    assert body(unparse({"a": False})) == "<a>false</a>"


def test_numbers():
    assert body(unparse({"a": 1})) == "<a>1</a>"
    assert body(unparse({"a": 1.5})) == "<a>1.5</a>"


def test_bytes_decoded():
    assert body(unparse({"a": b"bytes"})) == "<a>bytes</a>"


def test_none_text_skipped():
    assert body(unparse({"a": None})) == "<a></a>"


def test_list_text_stringified():
    assert body(unparse({"a": {"#text": ["x", "y"]}})) == "<a>['x', 'y']</a>"


def test_expand_iter():
    assert body(unparse({"a": {"b": [1, [2, 3]]}}, expand_iter="item")) == (
        "<a><b>1</b><b><item>2</item><item>3</item></b></a>"
    )


# -- attributes --------------------------------------------------------------


def test_attr_quote_single_when_double_present():
    assert body(unparse({"a": {"@x": 'he said "hi"'}})) == "<a x='he said \"hi\"'></a>"


def test_attr_special_chars_charref():
    assert body(unparse({"a": {"@x": "l\nt\tr\r"}})) == '<a x="l&#10;t&#9;r&#13;"></a>'


def test_attr_none_is_empty():
    assert body(unparse({"a": {"@x": None}})) == '<a x=""></a>'


# -- comments ----------------------------------------------------------------


def test_comment_escaped():
    assert body(unparse({"a": {"#comment": "<&>"}})) == "<a><!--&lt;&amp;&gt;--></a>"


def test_comment_falsy_values():
    assert body(unparse({"a": {"#comment": 0}})) == "<a><!--0--></a>"
    assert body(unparse({"a": {"#comment": ""}})) == "<a></a>"
    assert body(unparse({"a": {"#comment": None}})) == "<a></a>"


def test_comment_list():
    assert body(unparse({"a": {"#comment": ["c1", "c2"]}})) == "<a><!--c1--><!--c2--></a>"


# -- names -------------------------------------------------------------------


def test_lax_names_emitted():
    assert body(unparse({"1a": "x"})) == "<1a>x</1a>"
    assert body(unparse({"": "x"})) == "<>x</>"


def test_name_whitespace_rejected():
    with pytest.raises(ValueError, match="whitespace not allowed"):
        unparse({"a b": "x"})


def test_name_angle_bracket_rejected():
    with pytest.raises(ValueError, match='"<" or ">" not allowed'):
        unparse({"<a": "x"})


# -- namespaces --------------------------------------------------------------


def test_namespace_drop_unmapped():
    assert body(unparse({"p:r": "1"}, namespaces={"x": "y"})) == "<r>1</r>"


def test_namespace_map():
    assert body(unparse({"a:b": "1"}, namespaces={"a": "z"})) == "<z:b>1</z:b>"


def test_xmlns_dict():
    assert body(unparse({"a": {"@xmlns": {"": "u", "p": None}}})) == '<a xmlns="u" xmlns:p=""></a>'


# -- encoding & bytes_errors -------------------------------------------------


def test_bytesio_ascii_charref():
    out = io.BytesIO()
    assert unparse({"a": "é"}, output=out, encoding="ascii") is None
    assert out.getvalue() == b'<?xml version="1.0" encoding="ascii"?>\n<a>&#233;</a>'


def test_return_string_keeps_raw_unicode():
    assert unparse({"a": "é"}, encoding="ascii") == '<?xml version="1.0" encoding="ascii"?>\n<a>é</a>'


def test_bytes_value_decoded_with_errors():
    result = unparse({"a": {"@x": "é".encode("utf-8")}}, encoding="ascii")
    assert result == '<?xml version="1.0" encoding="ascii"?>\n<a x="��"></a>'


def test_invalid_bytes_errors_reported_first():
    out = io.BytesIO()
    with pytest.raises(ValueError, match="Invalid bytes_errors handler"):
        unparse({"a": "1"}, output=out, bytes_errors="bogus")
    assert out.getvalue() == b""


# -- preprocessor ------------------------------------------------------------


def test_preprocessor_rename():
    assert body(unparse({"a": "1"}, preprocessor=lambda k, v: ("b", v))) == "<b>1</b>"


def test_preprocessor_drop():
    assert unparse({"a": "1"}, preprocessor=lambda k, v: None, full_document=False) == ""


# -- output streams ----------------------------------------------------------


def test_partial_output_on_error():
    out = io.BytesIO()
    with pytest.raises(ValueError):
        unparse({"a": "1", "b": "2"}, output=out)
    assert out.getvalue() == b'<?xml version="1.0" encoding="utf-8"?>\n<a>1</a>'


def test_write_only_stream_gets_bytes():
    class WriteOnly:
        def __init__(self):
            self.chunks = []

        def write(self, chunk):
            self.chunks.append(chunk)
            return len(chunk)

    sink = WriteOnly()
    assert unparse({"a": "t"}, output=sink) is None
    assert b"".join(sink.chunks) == b'<?xml version="1.0" encoding="utf-8"?>\n<a>t</a>'


# -- Fix round 1: element / attribute name validation -------------------------

_ELEMENT_NAME_ERRORS = [
    ("?x", 'Invalid element name: cannot start with "?" or "!"'),
    ("!x", 'Invalid element name: cannot start with "?" or "!"'),
    ("a<b", 'Invalid element name: "<" or ">" not allowed'),
    ("a>b", 'Invalid element name: "<" or ">" not allowed'),
    ("a/b", 'Invalid element name: "/" not allowed'),
    ("a'b", "Invalid element name: quotes not allowed"),
    ('a"b', "Invalid element name: quotes not allowed"),
    ("a=b", 'Invalid element name: "=" not allowed'),
    ("a b", "Invalid element name: whitespace not allowed"),
    ("a\tb", "Invalid element name: whitespace not allowed"),
    ("a\nb", "Invalid element name: whitespace not allowed"),
]


@pytest.mark.parametrize("name, message", _ELEMENT_NAME_ERRORS)
def test_element_name_rejected(name, message):
    with pytest.raises(ValueError) as exc:
        unparse({name: "v"}, full_document=False)
    assert str(exc.value) == message


@pytest.mark.parametrize(
    "name, message",
    [
        ("?<a b", 'Invalid element name: cannot start with "?" or "!"'),
        ("a <b", 'Invalid element name: "<" or ">" not allowed'),
        ("a/=b", 'Invalid element name: "/" not allowed'),
        ("x ?", "Invalid element name: whitespace not allowed"),
    ],
)
def test_element_name_first_rule_wins(name, message):
    with pytest.raises(ValueError) as exc:
        unparse({name: "v"}, full_document=False)
    assert str(exc.value) == message


@pytest.mark.parametrize(
    "name, message",
    [
        ("@?x", 'Invalid attribute name: cannot start with "?" or "!"'),
        ("@a<b", 'Invalid attribute name: "<" or ">" not allowed'),
        ("@a/b", 'Invalid attribute name: "/" not allowed'),
        ("@a'b", "Invalid attribute name: quotes not allowed"),
        ("@a=b", 'Invalid attribute name: "=" not allowed'),
        ("@a b", "Invalid attribute name: whitespace not allowed"),
    ],
)
def test_attribute_name_rejected(name, message):
    with pytest.raises(ValueError) as exc:
        unparse({"r": {name: "v"}}, full_document=False)
    assert str(exc.value) == message


def test_names_that_stay_valid():
    assert unparse({"1a": "v"}, full_document=False) == "<1a>v</1a>"
    assert unparse({"": "v"}, full_document=False) == "<>v</>"


@pytest.mark.parametrize("key", [1, None, 3.5, True])
def test_non_string_element_key(key):
    with pytest.raises(ValueError) as exc:
        unparse({key: "v"}, full_document=False)
    assert str(exc.value) == "element name must be a string"


def test_non_string_xmlns_key():
    with pytest.raises(ValueError) as exc:
        unparse({"r": {"@xmlns": {1: "u"}}}, full_document=False)
    assert str(exc.value) == "attribute name must be a string"


@pytest.mark.parametrize(
    "key, message",
    [
        ("m><bad", 'Invalid attribute name: "<" or ">" not allowed'),
        ("?x", 'Invalid attribute name: cannot start with "?" or "!"'),
        ("a=b", 'Invalid attribute name: "=" not allowed'),
        ("a b", "Invalid attribute name: whitespace not allowed"),
    ],
)
def test_xmlns_prefix_validated_as_attribute(key, message):
    with pytest.raises(ValueError) as exc:
        unparse({"r": {"@xmlns": {key: "u"}}}, full_document=False)
    assert str(exc.value) == message


# -- Fix round 1: comment validation -----------------------------------------


@pytest.mark.parametrize(
    "value, message",
    [
        ("a--b", "Comment text cannot contain '--'"),
        ("--", "Comment text cannot contain '--'"),
        ("a--b-", "Comment text cannot contain '--'"),  # "--" beats trailing "-"
        ("abc-", "Comment text cannot end with '-'"),
        ("-", "Comment text cannot end with '-'"),
        (b"a--b", "Comment text cannot contain '--'"),
        (b"xyz-", "Comment text cannot end with '-'"),
    ],
)
def test_comment_rejected(value, message):
    with pytest.raises(ValueError) as exc:
        unparse({"r": {"#comment": value, "x": "1"}}, full_document=False)
    assert str(exc.value) == message


def test_valid_comment_written():
    assert (
        unparse({"r": {"#comment": "abc", "x": "1"}}, full_document=False)
        == "<r><!--abc--><x>1</x></r>"
    )


# -- Fix round 1: @xmlns value conversion ------------------------------------


def test_xmlns_values_converted():
    assert (
        unparse({"r": {"@xmlns": {"a": True, "b": b"http://x/"}}}, full_document=False)
        == '<r xmlns:a="true" xmlns:b="http://x/"></r>'
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, "true"),
        (False, "false"),
        (None, ""),
        (5, "5"),
        (b"http://x/", "http://x/"),
    ],
)
def test_xmlns_single_value_conversion(value, expected):
    assert (
        unparse({"r": {"@xmlns": {"a": value}}}, full_document=False)
        == '<r xmlns:a="%s"></r>' % expected
    )
