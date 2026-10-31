"""Differential tests for callback parity.

For ``item_callback``, ``postprocessor``, ``force_list`` and ``force_cdata``
(parse) and ``preprocessor`` (unparse) the two implementations must invoke the
callback the same number of times, in the same order, with equal arguments, and
must interpret the return value the same way.  Each test runs both sides with an
identical recording callback and compares the captured call logs plus the final
result.
"""

import copy

import pytest

import xmlrelay

from . import oracle
from .compare import _describe, invoke, snapshot_path


def _record_parse(xml, slot, behavior, **kwargs):
    ref = oracle.reference()
    log_ref, log_relay = [], []

    def make(log):
        def cb(*args):
            if len(args) == 3:
                path, key, value = args
                log.append(("3", snapshot_path(path), key, repr(value)))
            else:
                path, item = args
                log.append(("2", snapshot_path(path), repr(item)))
            return behavior(*args)

        return cb

    r_ref = invoke(ref.parse, xml, **dict(kwargs, **{slot: make(log_ref)}))
    r_relay = invoke(xmlrelay.parse, xml, **dict(kwargs, **{slot: make(log_relay)}))

    assert log_ref == log_relay, (
        "%s call log mismatch for %r\n  reference=%r\n  xmlrelay =%r"
        % (slot, xml, log_ref, log_relay)
    )
    assert _describe(r_ref) == _describe(r_relay), (
        "%s result mismatch for %r\n  reference=%r\n  xmlrelay =%r"
        % (slot, xml, r_ref, r_relay)
    )


DOCS = [
    '<a x="1"><!--c--><b>1</b>t</a>',
    '<a x="1"><b y="2">t</b><c>u</c></a>',
    "<r><a><b>1</b></a><a><b>2</b></a></r>",
    "<a>x<!--c1-->y<!--c2-->z</a>",
    '<p:a xmlns:p="u" p:c="1"><p:b>1</p:b></p:a>',
    "<a><b>1</b><b>2</b><b>3</b></a>",
]


@pytest.mark.parametrize("xml", DOCS)
def test_postprocessor_identity(xml):
    _record_parse(xml, "postprocessor", lambda p, k, v: (k, v), process_comments=True)


@pytest.mark.parametrize("xml", DOCS)
def test_force_list_callable(xml):
    _record_parse(xml, "force_list", lambda p, k, v: False, process_comments=True)
    _record_parse(xml, "force_list", lambda p, k, v: True, process_comments=True)


@pytest.mark.parametrize("xml", DOCS)
def test_force_cdata_callable(xml):
    _record_parse(xml, "force_cdata", lambda p, k, v: True, process_comments=True)
    _record_parse(xml, "force_cdata", lambda p, k, v: False, process_comments=True)


@pytest.mark.parametrize("depth", [1, 2, 3])
@pytest.mark.parametrize("xml", DOCS)
def test_item_callback(xml, depth):
    _record_parse(xml, "item_callback", lambda p, i: True, item_depth=depth)


def test_item_callback_interrupt():
    _record_parse("<a><b>1</b><b>2</b></a>", "item_callback", lambda p, i: False, item_depth=2)


def test_postprocessor_attr_drop():
    for behavior in [
        lambda p, k, v: None if k == "@x" else (k, v),
        lambda p, k, v: False if k == "@x" else (k, v),
        lambda p, k, v: (k, v),
    ]:
        _record_parse('<a x="1" y="2">t</a>', "postprocessor", behavior)


def test_postprocessor_two_char_pair():
    _record_parse("<a>t</a>", "postprocessor", lambda p, k, v: "kv" if k == "a" else (k, v))


# -- preprocessor (unparse) --------------------------------------------------


def _record_unparse(data, behavior, **kwargs):
    ref = oracle.reference()
    log_ref, log_relay = [], []

    def make(log):
        def pre(key, value):
            log.append((key, repr(value)))
            return behavior(key, value)

        return pre

    r_ref = invoke(ref.unparse, copy.deepcopy(data), preprocessor=make(log_ref), **kwargs)
    r_relay = invoke(
        xmlrelay.unparse, copy.deepcopy(data), preprocessor=make(log_relay), **kwargs
    )
    assert log_ref == log_relay, (
        "preprocessor call log mismatch for %r\n  reference=%r\n  xmlrelay =%r"
        % (data, log_ref, log_relay)
    )
    assert _describe(r_ref) == _describe(r_relay)


@pytest.mark.parametrize(
    "data",
    [
        {"a": {"b": "1", "c": "2"}},
        {"a": {"b": {"d": "1"}, "c": "2"}},
        {"root": {"item": [1, 2, 3]}},
    ],
)
def test_preprocessor_order(data):
    _record_unparse(data, lambda k, v: (k, v))
    _record_unparse(data, lambda k, v: (k, v), pretty=True)
