"""Turn XML into nested Python mappings.

The work is driven by an Expat parser.  A single :class:`DocumentBuilder`
instance subscribes to the parser's element, text, comment and namespace
events and grows a tree of mappings as those events arrive.  The public
entry point is :func:`parse`.
"""

import types
from xml.parsers import expat as _expat

from ._exceptions import ParsingInterrupted

__all__ = ["parse"]


def _always_keep(path, item):
    """Default ``item_callback``: never interrupt a streamed parse."""
    return True


class DocumentBuilder:
    """Assemble a mapping tree from a stream of Expat parser events.

    The builder keeps three parallel stacks:

    * ``trail`` -- one ``(name, raw_attrs_or_None)`` tuple per element that is
      currently open.  It is handed, live and unmodified, to user callbacks.
    * ``saved`` -- the ``(mapping, text_runs)`` pair of each enclosing element,
      restored when a child closes.
    * ``runs`` -- the character-data fragments collected for the open element.

    ``current`` holds the mapping (or ``None``) being built for the innermost
    open element.
    """

    def __init__(
        self,
        item_depth=0,
        item_callback=_always_keep,
        xml_attribs=True,
        attr_prefix="@",
        cdata_key="#text",
        force_cdata=False,
        cdata_separator="",
        postprocessor=None,
        dict_constructor=dict,
        strip_whitespace=True,
        namespace_separator=":",
        namespaces=None,
        force_list=None,
        comment_key="#comment",
    ):
        self.item_depth = item_depth
        self.item_callback = item_callback
        self.xml_attribs = xml_attribs
        self.attr_prefix = attr_prefix
        self.cdata_key = cdata_key
        self.force_cdata = force_cdata
        self.cdata_separator = cdata_separator
        self.postprocessor = postprocessor
        self.new_map = dict_constructor
        self.strip_whitespace = strip_whitespace
        self.namespace_separator = namespace_separator
        self.namespaces = namespaces
        self.force_list = force_list
        self.comment_key = comment_key

        self.trail = []
        self.saved = []
        self.runs = []
        self.current = None
        self._ns_waiting = None

    # -- name handling ---------------------------------------------------

    def _rename(self, name):
        """Apply the ``namespaces`` prefix/URI remapping to a single name.

        Without a ``namespaces`` map the name is returned verbatim.  Otherwise
        the leading segment (prefix or expanded URI, split on the configured
        separator) is looked up: a mapped value replaces it, a ``None`` mapping
        strips it, and an unknown segment leaves the name unchanged.
        """
        table = self.namespaces
        if table is None:
            return name
        try:
            head, tail = name.rsplit(self.namespace_separator, 1)
        except ValueError:
            return name
        if head in table:
            replacement = table[head]
            if replacement:
                return replacement + self.namespace_separator + tail
            return tail
        return name

    # -- parser event handlers ------------------------------------------

    def declare_namespace(self, prefix, uri):
        """Record one ``xmlns`` declaration until its element opens."""
        if self._ns_waiting is None:
            self._ns_waiting = self.new_map()
        self._ns_waiting[prefix or ""] = uri

    def open_element(self, name, attrs):
        label = self._rename(name)
        self.trail.append((label, attrs or None))
        self.saved.append((self.current, self.runs))

        built = None
        if self.xml_attribs:
            for raw_name, raw_value in attrs.items():
                field = self.attr_prefix + self._rename(raw_name)
                if self.postprocessor is not None:
                    verdict = self.postprocessor(self.trail, field, raw_value)
                    if not verdict:
                        continue
                    field, raw_value = verdict
                if built is None:
                    built = self.new_map()
                built[field] = raw_value
            if self._ns_waiting:
                field = self.attr_prefix + "xmlns"
                value = self._ns_waiting
                keep = True
                if self.postprocessor is not None:
                    verdict = self.postprocessor(self.trail, field, value)
                    if not verdict:
                        keep = False
                    else:
                        field, value = verdict
                if keep:
                    if built is None:
                        built = self.new_map()
                    built[field] = value

        self._ns_waiting = None
        self.current = built
        self.runs = []

    def feed_text(self, fragment):
        self.runs.append(fragment)

    def feed_comment(self, text):
        if self.strip_whitespace:
            text = text.strip()
        self.current = self._attach(self.current, self.comment_key, text)

    def close_element(self, name):
        label = self.trail[-1][0]
        reached = len(self.trail)

        if reached == self.item_depth:
            delivered = self.current
            if delivered is None:
                delivered = self.cdata_separator.join(self.runs) if self.runs else None
            if not self.item_callback(self.trail, delivered):
                raise ParsingInterrupted()

        parent_map, parent_runs = self.saved.pop()

        if reached > self.item_depth:
            text = self.cdata_separator.join(self.runs)
            if self.strip_whitespace:
                text = text.strip()
            finished = self.current
            self.current = parent_map
            self.runs = parent_runs

            if text:
                force = self._wants_cdata(label, text)
                if finished is None and not force:
                    value = text
                else:
                    if finished is None:
                        finished = self.new_map()
                    finished = self._attach(finished, self.cdata_key, text)
                    value = finished
            else:
                value = finished

            self.current = self._attach(self.current, label, value)
        else:
            self.current = parent_map
            self.runs = parent_runs

        self.trail.pop()

    # -- policy helpers --------------------------------------------------

    def _wants_cdata(self, name, text):
        rule = self.force_cdata
        if callable(rule):
            return rule(self.trail[:-1], name, text)
        return bool(rule)

    def _wants_list(self, key, value):
        rule = self.force_list
        if not rule:
            return False
        if isinstance(rule, bool):
            return rule
        try:
            return key in rule
        except TypeError:
            return rule(self.trail[:-1], key, value)

    def _attach(self, container, key, value):
        """Add ``key``/``value`` to ``container``, honouring the callbacks.

        A ``postprocessor`` may rewrite or drop the pair.  A repeated key is
        collapsed into a list; a first-time key consults ``force_list``.
        """
        if self.postprocessor is not None:
            revised = self.postprocessor(self.trail, key, value)
            if revised is None:
                return container
            key, value = revised
        if container is None:
            container = self.new_map()
        if key in container:
            held = container[key]
            if isinstance(held, list):
                held.append(value)
            else:
                container[key] = [held, value]
        elif self._wants_list(key, value):
            container[key] = [value]
        else:
            container[key] = value
        return container


def parse(
    xml_input,
    encoding=None,
    expat=_expat,
    process_namespaces=False,
    namespace_separator=":",
    disable_entities=True,
    process_comments=False,
    **options,
):
    """Parse XML into a nested mapping.

    ``xml_input`` may be text, a bytes-like object, a readable binary stream,
    or a generator yielding text/bytes chunks.  See the project README for the
    full menu of keyword options forwarded through ``options``.
    """
    builder = DocumentBuilder(namespace_separator=namespace_separator, **options)

    separator = namespace_separator if process_namespaces else None
    parser = expat.ParserCreate(encoding, separator)

    parser.buffer_text = True
    parser.ordered_attributes = False
    parser.StartElementHandler = builder.open_element
    parser.EndElementHandler = builder.close_element
    parser.CharacterDataHandler = builder.feed_text
    if process_namespaces:
        parser.StartNamespaceDeclHandler = builder.declare_namespace
    if process_comments:
        parser.CommentHandler = builder.feed_comment
    if disable_entities:
        def _no_entities(*_ignored):
            raise ValueError("entities are disabled")

        parser.EntityDeclHandler = _no_entities

    if hasattr(xml_input, "read"):
        parser.ParseFile(xml_input)
    elif isinstance(xml_input, types.GeneratorType):
        for chunk in xml_input:
            if isinstance(chunk, str):
                chunk = chunk.encode(encoding or "utf-8")
            parser.Parse(chunk, False)
        parser.Parse(b"", True)
    else:
        if isinstance(xml_input, str):
            xml_input = xml_input.encode(encoding or "utf-8")
        parser.Parse(xml_input, True)

    return builder.current
