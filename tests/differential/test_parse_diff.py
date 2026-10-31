"""Differential tests for :func:`xmlrelay.parse`.

Covers Hypothesis-generated documents, every input container type, each
documented option alone and combined, a curated set of realistic documents,
and malformed / hostile input.
"""

import io

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from . import strategies as S
from .strategies import examples
from .compare import check_parse


# -- generated documents -----------------------------------------------------


@settings(max_examples=examples(3000), deadline=None)
@given(xml=S.xml_documents(allow_ns=False))
def test_generated_plain(xml):
    check_parse(xml)


@settings(max_examples=examples(2000), deadline=None)
@given(xml=S.xml_documents(allow_ns=True))
def test_generated_namespaced(xml):
    check_parse(xml, process_namespaces=True)
    check_parse(xml)


@settings(max_examples=examples(3000), deadline=None)
@given(
    xml=S.xml_documents(allow_ns=False),
    strip=st.booleans(),
    fcdata=st.booleans(),
    xattr=st.booleans(),
    sep=st.sampled_from(["", "|", " "]),
)
def test_generated_option_matrix(xml, strip, fcdata, xattr, sep):
    check_parse(
        xml,
        strip_whitespace=strip,
        force_cdata=fcdata,
        xml_attribs=xattr,
        cdata_separator=sep,
    )


@settings(max_examples=examples(1000), deadline=None)
@given(xml=S.xml_documents(allow_ns=False), comments=st.booleans())
def test_generated_comments(xml, comments):
    check_parse(xml, process_comments=comments)


@settings(max_examples=examples(1000), deadline=None)
@given(
    xml=S.xml_documents(allow_ns=False),
    prefix=st.sampled_from(["@", "@@", "", "_attr_"]),
    ckey=st.sampled_from(["#text", "$t", "TEXT"]),
)
def test_generated_renamed_keys(xml, prefix, ckey):
    check_parse(xml, attr_prefix=prefix, cdata_key=ckey)


# -- input container types ---------------------------------------------------

_SAMPLE = '<a x="1"><b>hi</b><b>café</b><c/></a>'


def test_input_str():
    check_parse(_SAMPLE)


def test_input_bytes():
    check_parse(_SAMPLE.encode("utf-8"))


def test_input_bytearray():
    check_parse(bytearray(_SAMPLE.encode("utf-8")))


def test_input_memoryview():
    check_parse(memoryview(_SAMPLE.encode("utf-8")))


def test_input_binary_file():
    check_parse(lambda: io.BytesIO(_SAMPLE.encode("utf-8")))


def test_input_text_file_is_rejected():
    # a text stream must raise the same TypeError on both sides
    check_parse(lambda: io.StringIO(_SAMPLE))


def test_input_list_is_rejected():
    check_parse(lambda: [_SAMPLE])


def test_input_iterator_is_rejected():
    check_parse(lambda: iter([_SAMPLE]))


@pytest.mark.parametrize("sep", ["", "|"])
def test_input_generator_str(sep):
    def chunks():
        yield "<a>ab"
        yield "cd</a>"

    check_parse(lambda: chunks(), cdata_separator=sep)


@pytest.mark.parametrize("sep", ["", "|"])
def test_input_generator_bytes(sep):
    def chunks():
        yield b"<a>ab"
        yield b"cd</a>"

    check_parse(lambda: chunks(), cdata_separator=sep)


@pytest.mark.parametrize("length", [100, 8192, 8200, 16384, 16385, 25000])
def test_chunk_boundary_split(length):
    body = "x" * length
    doc = "<a>%s</a>" % body
    check_parse(lambda: io.BytesIO(doc.encode("utf-8")), cdata_separator="|")
    check_parse(doc, cdata_separator="|")
    check_parse(doc.encode("utf-8"), cdata_separator="|")


# -- encoding ----------------------------------------------------------------


def test_encoding_override_bytes():
    check_parse("<a>é</a>".encode("utf-8"), encoding="latin-1")


def test_encoding_declared():
    doc = '<?xml version="1.0" encoding="iso-8859-1"?><a>é</a>'.encode("iso-8859-1")
    check_parse(doc)


# -- force_list --------------------------------------------------------------


@pytest.mark.parametrize(
    "fl",
    [True, False, None, "item", "b", ("b",), ["b", "c"], {"b"}, 5],
)
def test_force_list_values(fl):
    check_parse("<a><b>1</b><it>2</it><c>3</c></a>", force_list=fl)


def test_force_list_callable():
    def rule(path, key, value):
        return key in ("b", "#text")

    check_parse("<a x='1'><b>1</b>t</a>".replace("'", '"'), force_list=rule)


# -- namespaces --------------------------------------------------------------


def test_namespaces_mapping_without_process():
    check_parse('<a:b xmlns:a="x" a:c="1"/>', namespaces={"a": "z"})


def test_namespaces_process():
    check_parse('<a:b xmlns:a="x" a:c="1" d="2">t</a:b>', process_namespaces=True)


def test_namespaces_process_and_map():
    check_parse(
        '<a:b xmlns:a="x" a:c="1"/>',
        process_namespaces=True,
        namespaces={"x": "z"},
    )
    check_parse(
        '<a:b xmlns:a="x" a:c="1"/>',
        process_namespaces=True,
        namespaces={"x": None},
    )


@pytest.mark.parametrize("sep", [":", "|", ""])
def test_namespace_separator(sep):
    check_parse('<a:b xmlns:a="x"/>', process_namespaces=True, namespace_separator=sep)


def test_namespaces_default_ns():
    check_parse('<root xmlns="http://d"><child>1</child></root>', process_namespaces=True)


# -- streaming ---------------------------------------------------------------


@pytest.mark.parametrize("depth", [-1, 0, 1, 2, 3])
def test_streaming_depth_return(depth):
    # without a callback the default keeps everything; we compare the return
    check_parse("<a><b x='1'>t</b><c> u </c></a>".replace("'", '"'), item_depth=depth)


def test_streaming_comment_after_root():
    check_parse("<a>x</a><!--z-->", item_depth=1, process_comments=True)


# -- entities & DTD ----------------------------------------------------------


def test_entity_internal_disabled():
    check_parse('<!DOCTYPE a [<!ENTITY e "V">]><a>&e;</a>')


def test_entity_internal_enabled():
    check_parse('<!DOCTYPE a [<!ENTITY e "V">]><a>&e;</a>', disable_entities=False)


def test_entity_external_dtd_dropped():
    check_parse('<!DOCTYPE a SYSTEM "x.dtd"><a>&e;</a>')


def test_entity_undefined_no_dtd():
    check_parse("<a>&undefined;</a>")


def test_builtin_entities():
    check_parse("<a>&amp;&lt;&gt;&apos;&quot;</a>")


# -- malformed / hostile -----------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "<a><b></a>",
        "<a>",
        "</a>",
        "not xml at all",
        "<a><</a>",
        "<a b=></a>",
        "",
        "<>",
        "<a>&#x110000;</a>",
    ],
)
def test_malformed(bad):
    check_parse(bad)


# -- curated realistic documents --------------------------------------------

_CURATED = [
    '<?xml version="1.0"?><config><server host="localhost" port="8080"/><debug>true</debug></config>',
    '<rss version="2.0"><channel><title>Feed</title><item><title>One</title></item>'
    "<item><title>Two</title></item></channel></rss>",
    '<svg xmlns="http://www.w3.org/2000/svg" width="10"><rect x="0" y="0"/></svg>',
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soap:Body><m:Get xmlns:m='urn:x'><m:Id>42</m:Id></m:Get></soap:Body></soap:Envelope>",
    '<note><to>A</to><from>B</from><body>Hi &amp; bye</body><!-- a note --></note>',
    "<a><![CDATA[<raw> & stuff]]></a>",
    "<mixed>text<b>bold</b>more<i>it</i>tail</mixed>",
    "<empties><a/><b></b><c>  </c></empties>",
]


@pytest.mark.parametrize("doc", _CURATED)
def test_curated(doc):
    check_parse(doc)
    check_parse(doc, process_comments=True)
    check_parse(doc, process_namespaces=True)
    check_parse(doc, force_list=True)
    check_parse(doc, strip_whitespace=False)
