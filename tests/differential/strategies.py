"""Hypothesis strategies that produce XML documents and unparse inputs.

Rather than emit raw bytes and hope for well-formedness, the XML strategy
builds a small element tree and renders it with correct escaping.  That keeps
documents valid while still exercising attributes, namespaces, comments, CDATA,
mixed content, whitespace, non-ASCII text and both shallow and deep nesting.
"""

import os

from hypothesis import strategies as st


def examples(n):
    """Scale a per-test example budget by ``XMLRELAY_DIFF_SCALE`` (default 1).

    Lets a quick local run shrink the budget without editing the tests, while
    the default keeps the generated-case totals above the required floor.
    """
    scale = float(os.environ.get("XMLRELAY_DIFF_SCALE", "1"))
    return max(1, int(round(n * scale)))

# A compact pool of legal XML names (and some namespaced ones).
_PLAIN_NAMES = ["a", "b", "item", "it", "Node", "x1", "root", "child", "e"]
_NS_NAMES = ["p:a", "p:b", "q:item", "ns:val"]

_names = st.sampled_from(_PLAIN_NAMES)
_names_with_ns = st.sampled_from(_PLAIN_NAMES + _NS_NAMES)

# Text fragments: ordinary words, whitespace, non-ASCII, markup-significant.
_text_atoms = st.sampled_from(
    [
        "hello",
        "  spaced  ",
        "\n\t",
        "café",
        "日本語",
        "a & b < c > d",
        '"quotes"',
        "line1\nline2",
        "0",
        "",
        "x" * 20,
    ]
)

_attr_values = st.sampled_from(
    ['1', "2", 'he said "hi"', "a'b", "a&b<c", "café", "\t\n", ""]
)


def _escape_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(value):
    value = _escape_text(value)
    return value.replace('"', "&quot;")


def _render(node):
    kind = node[0]
    if kind == "text":
        return _escape_text(node[1])
    if kind == "cdata":
        return "<![CDATA[%s]]>" % node[1]
    if kind == "comment":
        return "<!--%s-->" % node[1]
    # element
    _, name, attrs, children = node
    attr_s = "".join(' %s="%s"' % (k, _escape_attr(v)) for k, v in attrs)
    if not children:
        return "<%s%s/>" % (name, attr_s)
    inner = "".join(_render(c) for c in children)
    return "<%s%s>%s</%s>" % (name, attr_s, inner, name)


@st.composite
def _element(draw, allow_ns, depth):
    name = draw(_names_with_ns if allow_ns else _names)
    attr_keys = draw(st.lists(_names, min_size=0, max_size=3, unique=True))
    if allow_ns:
        # occasionally declare a namespace so prefixes resolve
        if draw(st.booleans()):
            attr_keys = ["xmlns:p"] + [k for k in attr_keys if k != "xmlns:p"]
    attrs = [(k, draw(_attr_values)) for k in attr_keys]

    children = []
    if depth > 0:
        count = draw(st.integers(min_value=0, max_value=3))
        for _ in range(count):
            choice = draw(st.integers(min_value=0, max_value=4))
            if choice == 0:
                children.append(("text", draw(_text_atoms)))
            elif choice == 1:
                children.append(("cdata", draw(st.sampled_from(["abc", "x]x", ""]))))
            elif choice == 2:
                children.append(
                    ("comment", draw(st.sampled_from(["c", "a & b", "x"])))
                )
            else:
                children.append(draw(_element(allow_ns, depth - 1)))
    else:
        if draw(st.booleans()):
            children.append(("text", draw(_text_atoms)))
    return ("element", name, attrs, children)


@st.composite
def xml_documents(draw, allow_ns=True, max_depth=4):
    """A well-formed XML document string with a single root element."""
    root = draw(_element(allow_ns, max_depth))
    return _render(root)


# -- unparse inputs ----------------------------------------------------------

_scalars = st.one_of(
    st.text(max_size=12),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, width=16),
    st.booleans(),
    st.none(),
    st.binary(max_size=8),
)


def _leafy():
    return st.one_of(
        _scalars,
        st.lists(st.one_of(_scalars, st.integers()), max_size=3),
    )


@st.composite
def _mapping(draw, depth):
    mapping = {}
    # attributes
    for key in draw(st.lists(st.sampled_from(["x", "y", "z"]), max_size=2, unique=True)):
        mapping["@" + key] = draw(st.one_of(_scalars, st.integers()))
    # optional comment
    if draw(st.booleans()):
        mapping["#comment"] = draw(st.sampled_from(["c", "a<b", "", None, 0, False]))
    # text
    if draw(st.booleans()):
        mapping["#text"] = draw(_leafy())
    # children
    for key in draw(st.lists(st.sampled_from(["a", "b", "item"]), max_size=3, unique=True)):
        if depth > 0 and draw(st.booleans()):
            mapping[key] = draw(_mapping(depth - 1))
        else:
            mapping[key] = draw(_leafy())
    return mapping


@st.composite
def unparse_inputs(draw, max_depth=3):
    """A single-root mapping suitable for ``unparse`` with ``full_document``."""
    return {draw(st.sampled_from(["root", "a", "doc"])): draw(_mapping(max_depth))}


# -- name / comment / xmlns edge inputs (Fix round 1) ------------------------

# One name per rejected character class, plus multi-rule names (to exercise the
# first-rule-wins ordering) and names that must stay valid.
_BAD_NAMES = [
    "?x",       # starts with "?"
    "!x",       # starts with "!"
    "a<b",      # contains "<"
    "a>b",      # contains ">"
    "a/b",      # contains "/"
    "a'b",      # contains a single quote
    'a"b',      # contains a double quote
    "a=b",      # contains "="
    "a b",      # contains a space
    "a\tb",     # contains a tab
    "a\nb",     # contains a newline
    "?<a b",    # start-rule wins over "<" and whitespace
    "a <b",     # "<" wins over whitespace
    "a/=b",     # "/" wins over "="
    "x ?",      # whitespace wins (no leading "?")
]
_VALID_EDGE_NAMES = ["1a", "", "a.b", "-a", "a:b", "x1"]
_NON_STRING_KEYS = [1, None, 3.5, True, (1, 2)]

# Comment bodies: ones that must be rejected, and ones that stay valid.
_BAD_COMMENTS = ["a--b", "abc-", "a--b-", "-", "--", b"a--b", b"xyz-"]
_OK_COMMENTS = ["abc", "a & b", "", None, 0, False, b"ok", ["c1", "c2"]]

# @xmlns values are converted like any other attribute value.
_XMLNS_VALUES = [True, False, None, b"http://x/", 5, "u"]
# @xmlns keys are validated as attribute names.
_BAD_XMLNS_KEYS = ["m><bad", "?x", "!x", "a=b", "a b", "a/b", "a'b"]


@st.composite
def unparse_name_inputs(draw):
    """A single-root mapping whose names/keys stress the validation rules.

    Covers rule-breaking and valid-edge element and attribute names, non-string
    keys, and ``@xmlns`` dicts with bad keys and with bool/bytes/None/int values.
    """
    shape = draw(st.integers(min_value=0, max_value=6))
    name = draw(st.sampled_from(_BAD_NAMES + _VALID_EDGE_NAMES))
    if shape == 0:  # root element name
        return {name: draw(st.sampled_from(["v", {"#text": "v"}, {"c": "1"}]))}
    if shape == 1:  # child element name
        return {"r": {name: "v"}}
    if shape == 2:  # attribute name
        return {"r": {"@" + name: "v", "c": "1"}}
    if shape == 3:  # non-string key (treated as an element name)
        return {"r": {draw(st.sampled_from(_NON_STRING_KEYS)): "v"}}
    if shape == 4:  # non-string root key
        return {draw(st.sampled_from(_NON_STRING_KEYS)): "v"}
    if shape == 5:  # @xmlns prefix (validated as an attribute name)
        key = draw(st.sampled_from(_BAD_XMLNS_KEYS + ["", "p"]))
        return {"r": {"@xmlns": {key: draw(st.sampled_from(_XMLNS_VALUES))}}}
    # non-string @xmlns key
    return {"r": {"@xmlns": {draw(st.sampled_from(_NON_STRING_KEYS)): "u"}}}


@st.composite
def unparse_comment_inputs(draw):
    """A single-root mapping carrying a comment (valid or rule-breaking)."""
    value = draw(st.sampled_from(_BAD_COMMENTS + _OK_COMMENTS))
    return {"r": {"#comment": value, "x": "1"}}
