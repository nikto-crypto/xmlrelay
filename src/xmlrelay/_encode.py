"""Turn nested Python mappings back into XML.

The heavy lifting of escaping, attribute quoting and the XML declaration is
delegated to :class:`xml.sax.saxutils.XMLGenerator`; this module decides the
document shape -- element order, list expansion, comment placement, namespace
remapping and optional pretty indentation -- on top of it.  The public entry
point is :func:`unparse`.
"""

import codecs
import io
from xml.sax.saxutils import XMLGenerator, escape

__all__ = ["unparse"]

_ABSENT = object()


def _is_series(value):
    """True for values that unfold into several sibling elements."""
    if isinstance(value, (str, bytes, dict)):
        return False
    return hasattr(value, "__iter__")


def _unfold(value):
    """Yield the members ``value`` contributes as sibling elements."""
    if _is_series(value):
        return value
    return (value,)


def _has_members(value):
    """Whether ``value`` contributes any element (for pretty layout).

    An empty list or tuple contributes nothing.  Every other value -- including
    an empty set, range or generator, which cannot be cheaply inspected -- is
    treated as contributing content.
    """
    if isinstance(value, (list, tuple)):
        return bool(value)
    return True


class Encoder:
    """Render a mapping tree through an :class:`XMLGenerator` sink."""

    def __init__(
        self,
        sink,
        full_document,
        comment_key="#comment",
        encoding="utf-8",
        attr_prefix="@",
        bytes_errors="replace",
        cdata_key="#text",
        expand_iter=None,
        indent="\t",
        namespace_separator=":",
        namespaces=None,
        newl="\n",
        preprocessor=None,
        pretty=False,
    ):
        self.sink = sink
        self.full_document = full_document
        self.comment_key = comment_key
        self.encoding = encoding
        self.attr_prefix = attr_prefix
        self.bytes_errors = bytes_errors
        self.cdata_key = cdata_key
        self.expand_iter = expand_iter
        self.indent = " " * indent if isinstance(indent, int) else indent
        self.namespace_separator = namespace_separator
        self.namespaces = namespaces
        self.newl = newl
        self.preprocessor = preprocessor
        self.pretty = pretty

    # -- scalar conversion ----------------------------------------------

    def _stringify(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, bytes):
            return value.decode(self.encoding, self.bytes_errors)
        return str(value)

    def _attr_text(self, value):
        if value is None:
            return ""
        return self._stringify(value)

    # -- name handling ---------------------------------------------------

    def _remap(self, name, is_attr):
        table = self.namespaces
        if not table:
            return name
        sep = self.namespace_separator
        try:
            head, tail = name.rsplit(sep, 1)
        except ValueError:
            return name
        swap = table.get(head)
        if swap:
            return swap + sep + tail
        return tail[1:] if is_attr else tail

    def _check_name(self, name, kind):
        for ch in name:
            if ch.isspace():
                raise ValueError("Invalid %s name: whitespace not allowed" % kind)
        if "<" in name or ">" in name:
            raise ValueError('Invalid %s name: "<" or ">" not allowed' % kind)

    # -- top level -------------------------------------------------------

    def run(self, data):
        roots = 0
        for key, value in data.items():
            if key == self.comment_key:
                self._write_comment(value)
                if self.pretty:
                    self.sink.ignorableWhitespace(self.newl)
                continue
            if self.preprocessor is not None:
                revised = self.preprocessor(key, value)
                if revised is None:
                    continue
                key, value = revised
            if self.full_document and roots >= 1:
                raise ValueError("Document must have exactly one root.")
            roots += 1
            self._write_series(key, value, 0, root=True)
        if self.full_document and roots != 1:
            raise ValueError("Document must have exactly one root.")

    # -- element emission ------------------------------------------------

    def _write_series(self, name, value, depth, root=False, lead=None):
        first = True
        for member in _unfold(value):
            if root and self.full_document and not first:
                raise ValueError("document with multiple roots")
            first = False
            if lead is not None:
                self.sink.ignorableWhitespace(lead)
            self._write_member(name, member, depth)

    def _write_member(self, name, content, depth):
        if isinstance(content, dict):
            self._write_mapping(name, content, depth)
        elif _is_series(content):
            if self.expand_iter:
                tag = self._open(name)
                self._write_series(self.expand_iter, content, depth + 1)
                self.sink.endElement(tag)
            else:
                self._write_scalar(name, str(content))
        else:
            self._write_scalar(name, content)

    def _write_scalar(self, name, content):
        tag = self._open(name)
        if content is not None:
            self.sink.characters(self._stringify(content))
        self.sink.endElement(tag)

    def _open(self, name):
        tag = self._remap(name, False)
        self._check_name(tag, "element")
        self.sink.startElement(tag, {})
        return tag

    def _write_mapping(self, name, mapping, depth):
        attrs = {}
        has_content = False
        for key, value in mapping.items():
            if key == self.cdata_key:
                continue
            if key == self.comment_key:
                if _has_members(value):
                    has_content = True
                continue
            if key == "@xmlns" and isinstance(value, dict):
                for prefix, uri in value.items():
                    field = "xmlns" if prefix == "" else "xmlns:" + prefix
                    attrs[field] = "" if uri is None else str(uri)
                continue
            if key.startswith(self.attr_prefix):
                field = self._remap(key[len(self.attr_prefix):], True)
                self._check_name(field, "attribute")
                attrs[field] = self._attr_text(value)
                continue
            if _has_members(value):
                has_content = True

        tag = self._remap(name, False)
        self._check_name(tag, "element")
        self.sink.startElement(tag, attrs)

        text = _ABSENT
        for key, value in mapping.items():
            if key == self.cdata_key:
                text = value
                continue
            lead = self.newl + self.indent * (depth + 1) if self.pretty else None
            if key == self.comment_key:
                self._write_comment(value, lead=lead)
                continue
            if key == "@xmlns" and isinstance(value, dict):
                continue
            if key.startswith(self.attr_prefix):
                continue
            child_key, child_value = key, value
            if self.preprocessor is not None:
                revised = self.preprocessor(child_key, child_value)
                if revised is None:
                    continue
                child_key, child_value = revised
            self._write_series(child_key, child_value, depth + 1, lead=lead)

        rendered = None
        if text is not _ABSENT and text is not None:
            rendered = self._stringify(text)
        if self.pretty and has_content:
            self.sink.ignorableWhitespace(self.newl)
            if rendered:
                self.sink.characters(rendered)
            self.sink.ignorableWhitespace(self.indent * depth)
        elif rendered:
            self.sink.characters(rendered)

        self.sink.endElement(tag)

    # -- comments --------------------------------------------------------

    def _comment_body(self, value):
        if value is None:
            return None
        body = self._stringify(value)
        if body == "":
            return None
        return body

    def _write_comment(self, value, lead=None):
        for piece in _unfold(value):
            body = self._comment_body(piece)
            if body is None:
                continue
            if lead is not None:
                self.sink.ignorableWhitespace(lead)
            self.sink._write("<!--" + escape(body) + "-->")


def unparse(
    input_dict,
    output=None,
    encoding="utf-8",
    full_document=True,
    short_empty_elements=False,
    comment_key="#comment",
    **options,
):
    """Serialise ``input_dict`` to XML.

    With ``output`` omitted the XML is returned as a string; otherwise it is
    written to ``output`` (a text, binary or write-only stream) and ``None`` is
    returned.  See the project README for the available keyword options.
    """
    bytes_errors = options.get("bytes_errors", "replace")
    try:
        codecs.lookup_error(bytes_errors)
    except LookupError:
        raise ValueError("Invalid bytes_errors handler: " + str(bytes_errors))

    collect = output is None
    destination = io.StringIO() if collect else output

    sink = XMLGenerator(
        destination,
        encoding=encoding,
        short_empty_elements=short_empty_elements,
    )
    if full_document:
        sink.startDocument()

    encoder = Encoder(
        sink,
        full_document,
        comment_key=comment_key,
        encoding=encoding,
        **options,
    )
    encoder.run(input_dict)

    if full_document:
        sink.endDocument()

    if collect:
        return destination.getvalue()
    return None
