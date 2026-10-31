"""Unit tests for :func:`xmlrelay.parse` with self-contained assertions."""

import io

import pytest

import xmlrelay
from xmlrelay import ParsingInterrupted, parse


def test_text_leaf():
    assert parse("<a>t</a>") == {"a": "t"}


def test_attributes_and_text():
    assert parse('<a x="1" y="2">t</a>') == {"a": {"@x": "1", "@y": "2", "#text": "t"}}


def test_repeated_children_become_list():
    assert parse("<a><b>1</b><b>2</b></a>") == {"a": {"b": ["1", "2"]}}


def test_distinct_children():
    assert parse("<a><b>1</b><c>2</c></a>") == {"a": {"b": "1", "c": "2"}}


def test_empty_elements_are_none():
    assert parse("<a/>") == {"a": None}
    assert parse("<a></a>") == {"a": None}
    assert parse("<a>   </a>") == {"a": None}


def test_whitespace_preserved_when_not_stripped():
    assert parse("<a> x </a>", strip_whitespace=False) == {"a": " x "}
    assert parse("<a>  </a>", strip_whitespace=False) == {"a": "  "}


def test_cdata_section():
    assert parse("<a>pre<![CDATA[mid]]>post</a>") == {"a": "premidpost"}


def test_attr_prefix_and_cdata_key():
    assert parse('<a x="1">t</a>', attr_prefix="@@", cdata_key="$t") == {
        "a": {"@@x": "1", "$t": "t"}
    }


def test_force_cdata():
    assert parse("<a>t</a>", force_cdata=True) == {"a": {"#text": "t"}}
    assert parse("<a/>", force_cdata=True) == {"a": None}


def test_xml_attribs_false_drops_attributes():
    assert parse('<a x="1"><b y="2">t</b></a>', xml_attribs=False) == {"a": {"b": "t"}}


def test_cdata_separator_joins_runs():
    assert parse("<a>x<b/>y</a>", cdata_separator="|") == {"a": {"b": None, "#text": "x|y"}}


def test_dict_constructor_propagates():
    from collections import OrderedDict

    result = parse('<a x="1"><b>2</b></a>', dict_constructor=OrderedDict)
    assert isinstance(result, OrderedDict)
    assert isinstance(result["a"], OrderedDict)


# -- input types -------------------------------------------------------------


def test_bytes_input():
    assert parse(b"<a>t</a>") == {"a": "t"}


def test_bytearray_input():
    assert parse(bytearray(b"<a>t</a>")) == {"a": "t"}


def test_memoryview_input():
    assert parse(memoryview(b"<a>t</a>")) == {"a": "t"}


def test_binary_file_input():
    assert parse(io.BytesIO(b"<a>t</a>")) == {"a": "t"}


def test_text_stream_rejected():
    with pytest.raises(TypeError):
        parse(io.StringIO("<a>t</a>"))


def test_generator_input():
    def chunks():
        yield "<a>ab"
        yield "cd</a>"

    assert parse(chunks(), cdata_separator="|") == {"a": "ab|cd"}


def test_list_input_rejected():
    with pytest.raises(TypeError):
        parse(["<a/>"])


def test_encoding_override():
    assert parse("<a>é</a>".encode("utf-8"), encoding="latin-1") == {"a": "Ã©"}


# -- force_list --------------------------------------------------------------


def test_force_list_true_lists_everything_but_attrs():
    assert parse('<a x="1"/>', force_list=True) == {"a": [{"@x": "1"}]}
    assert parse("<a>t</a>", force_list=True) == {"a": ["t"]}


def test_force_list_substring():
    assert parse("<a><it>1</it><item>2</item></a>", force_list="item") == {
        "a": {"it": ["1"], "item": ["2"]}
    }


def test_force_list_membership():
    assert parse("<a><b>1</b><c>2</c></a>", force_list=("b",)) == {
        "a": {"b": ["1"], "c": "2"}
    }


def test_force_list_truthy_non_callable_raises():
    with pytest.raises(TypeError):
        parse("<a><b>1</b></a>", force_list=5)


def test_force_list_callable():
    seen = []

    def rule(path, key, value):
        seen.append(key)
        return key == "b"

    assert parse("<a><b>1</b><c>2</c></a>", force_list=rule) == {
        "a": {"b": ["1"], "c": "2"}
    }
    assert "b" in seen


# -- comments ----------------------------------------------------------------


def test_comments_ignored_by_default():
    assert parse("<a><!--c-->t</a>") == {"a": "t"}


def test_comments_captured():
    assert parse("<a><!--c-->t</a>", process_comments=True) == {
        "a": {"#comment": "c", "#text": "t"}
    }


def test_comment_text_stripped():
    assert parse("<a><!--  hi  --></a>", process_comments=True) == {"a": {"#comment": "hi"}}


# -- namespaces --------------------------------------------------------------


def test_namespaces_mapping_without_process():
    assert parse('<a:b xmlns:a="x" a:c="1"/>', namespaces={"a": "z"}) == {
        "z:b": {"@xmlns:a": "x", "@z:c": "1"}
    }


def test_process_namespaces():
    assert parse('<a:b xmlns:a="x" a:c="1"/>', process_namespaces=True) == {
        "x:b": {"@x:c": "1", "@xmlns": {"a": "x"}}
    }


def test_namespace_separator():
    assert parse('<a:b xmlns:a="x"/>', process_namespaces=True, namespace_separator="|") == {
        "x|b": {"@xmlns": {"a": "x"}}
    }


# -- streaming ---------------------------------------------------------------


def test_streaming_delivers_items():
    collected = []

    def cb(path, item):
        collected.append(([n for n, _ in path], item))
        return True

    result = parse("<a><b>1</b><c>2</c></a>", item_depth=2, item_callback=cb)
    assert result is None
    assert collected == [(["a", "b"], "1"), (["a", "c"], "2")]


def test_streaming_item_with_attrs_loses_text():
    collected = []
    parse(
        '<a><b x="1">t</b></a>',
        item_depth=2,
        item_callback=lambda p, i: collected.append(i) or True,
    )
    assert collected == [{"@x": "1"}]


def test_streaming_text_not_stripped():
    collected = []
    parse(
        "<a><c> u </c></a>",
        item_depth=2,
        item_callback=lambda p, i: collected.append(i) or True,
    )
    assert collected == [" u "]


def test_item_callback_interrupt():
    with pytest.raises(ParsingInterrupted):
        parse("<a><b>1</b></a>", item_depth=1, item_callback=lambda p, i: False)


def test_negative_depth_is_full_parse():
    assert parse("<a><b>1</b></a>", item_depth=-1) == {"a": {"b": "1"}}


# -- postprocessor -----------------------------------------------------------


def test_postprocessor_can_rename():
    out = parse("<a><b>1</b></a>", postprocessor=lambda p, k, v: ("B", v) if k == "b" else (k, v))
    assert out == {"a": {"B": "1"}}


def test_postprocessor_drops_on_none():
    out = parse("<a><b>1</b></a>", postprocessor=lambda p, k, v: None if k == "b" else (k, v))
    assert out == {"a": None}


def test_postprocessor_attribute_falsy_drop():
    out = parse('<a x="1" y="2"/>', postprocessor=lambda p, k, v: None if k == "@x" else (k, v))
    assert out == {"a": {"@y": "2"}}


# -- entities ----------------------------------------------------------------


def test_internal_entity_disabled():
    with pytest.raises(ValueError, match="entities are disabled"):
        parse('<!DOCTYPE a [<!ENTITY e "V">]><a>&e;</a>')


def test_internal_entity_enabled():
    assert parse('<!DOCTYPE a [<!ENTITY e "V">]><a>&e;</a>', disable_entities=False) == {"a": "V"}


def test_external_dtd_entity_dropped():
    assert parse('<!DOCTYPE a SYSTEM "x.dtd"><a>&e;</a>') == {"a": None}


def test_custom_expat_module_is_used():
    import types
    import xml.parsers.expat as real

    calls = []

    class Fake:
        def ParserCreate(self, encoding, separator):
            calls.append((encoding, separator))
            return real.ParserCreate(encoding, separator)

    assert xmlrelay.parse("<a>t</a>", expat=Fake()) == {"a": "t"}
    assert calls == [(None, None)]
    assert isinstance(types, types.ModuleType)
