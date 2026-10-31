# xmlrelay

`xmlrelay` converts XML to nested Python dictionaries and back again. Parsing is
driven by the standard library's Expat parser; serialization is layered on top
of `xml.sax.saxutils.XMLGenerator`. The library has no third-party runtime
dependencies and targets Python 3.9 and newer.

```python
import xmlrelay

xmlrelay.parse('<order id="7"><item>pen</item><item>ink</item></order>')
# {'order': {'@id': '7', 'item': ['pen', 'ink']}}

xmlrelay.unparse({'order': {'@id': '7', 'item': ['pen', 'ink']}})
# '<?xml version="1.0" encoding="utf-8"?>\n<order id="7"><item>pen</item><item>ink</item></order>'
```

## Installation

```sh
pip install xmlrelay
```

To work on the project, install it with its test extra:

```sh
pip install -e ".[test]"
```

## The data model

A parsed document is a tree of dictionaries:

- An element's attributes become keys prefixed with `@` (`attr_prefix`).
- An element's text becomes the key `#text` (`cdata_key`) when the element also
  has attributes or child elements, or the element's value directly when it is a
  pure text leaf.
- Repeated sibling elements with the same name collapse into a list.
- An empty element becomes `None`.
- Comments, when enabled, become the key `#comment` (`comment_key`).

```python
xmlrelay.parse('<a/>')                       # {'a': None}
xmlrelay.parse('<a>text</a>')                # {'a': 'text'}
xmlrelay.parse('<a x="1">text</a>')          # {'a': {'@x': '1', '#text': 'text'}}
xmlrelay.parse('<a><b>1</b><b>2</b></a>')    # {'a': {'b': ['1', '2']}}
```

## `parse`

```python
parse(xml_input, encoding=None, expat=<pyexpat>, process_namespaces=False,
      namespace_separator=':', disable_entities=True, process_comments=False,
      **options)
```

`xml_input` may be:

- `str` -- encoded with `encoding` (or UTF-8) before parsing;
- `bytes`, `bytearray` or `memoryview` -- fed directly;
- any object with a `.read` attribute -- treated as a **binary** file (a text
  stream raises `TypeError`);
- a generator yielding `str` or `bytes` chunks -- fed chunk by chunk. Other
  iterables such as lists or `iter(...)` are **not** treated as chunk streams.

### Keyword options

| Option | Default | Meaning |
| --- | --- | --- |
| `attr_prefix` | `'@'` | Prefix added to attribute names. |
| `cdata_key` | `'#text'` | Key used for element text. |
| `cdata_separator` | `''` | Joins the character-data fragments of an element. |
| `comment_key` | `'#comment'` | Key used for comments. |
| `dict_constructor` | `dict` | Factory used for every mapping that is built. |
| `force_cdata` | `False` | Force text into `cdata_key` even for a leaf. Accepts a callable `(path, name, text) -> bool`. |
| `force_list` | `None` | Force list wrapping for matching keys. See below. |
| `item_callback` | returns `True` | Called for each streamed item (see Streaming). |
| `item_depth` | `0` | Depth at which to stream instead of build (see Streaming). |
| `namespaces` | `None` | Prefix/URI remapping (see Namespaces). |
| `postprocessor` | `None` | `(path, key, value) -> (key, value) | None` run for every key. |
| `process_comments` | `False` | Capture comments into `comment_key`. |
| `process_namespaces` | `False` | Resolve namespaces through Expat. |
| `strip_whitespace` | `True` | Strip surrounding whitespace from text and comments. |
| `xml_attribs` | `True` | Include attributes in the result. |

`force_list` accepts several shapes: `True`/`False`, a string or collection
(a key is forced when `key in force_list`, so a string matches by substring), or
a callable `(path, key, value) -> bool`. A truthy value that is neither of these
(for example `5`) raises `TypeError`, matching the reference behaviour.

`postprocessor` is called for attributes, text, comments and elements. Returning
`None` drops the entry (for attributes, any falsy value drops it); any other
return is unpacked as a `(key, value)` pair.

`path` passed to callbacks is a list of `(name, attributes_or_None)` tuples,
where the attribute dictionary is the raw one Expat produced (keys are neither
prefixed nor namespace-mapped).

## `unparse`

```python
unparse(input_dict, output=None, encoding='utf-8', full_document=True,
        short_empty_elements=False, comment_key='#comment', **options)
```

With `output` omitted the XML is returned as a string. When `output` is given,
the XML is written to it (a binary, text or write-only stream) and `None` is
returned; a write-only or binary stream receives encoded bytes, a text stream
receives text.

### Keyword options

| Option | Default | Meaning |
| --- | --- | --- |
| `attr_prefix` | `'@'` | Prefix that marks attribute keys. |
| `bytes_errors` | `'replace'` | Error handler used to decode `bytes` values. Validated before anything is written. |
| `cdata_key` | `'#text'` | Key holding element text. |
| `expand_iter` | `None` | Element name used to expand a nested iterable found inside a list. |
| `indent` | `'\t'` | Indentation unit for pretty output (an `int` means that many spaces). |
| `namespace_separator` | `':'` | Separator used for namespace remapping. |
| `namespaces` | `None` | Prefix remapping applied to names (see Namespaces). |
| `newl` | `'\n'` | Line separator for pretty output. |
| `preprocessor` | `None` | `(key, value) -> (key, value) | None` run for each element key. |
| `pretty` | `False` | Indent the output. |

Scalar conversion: `True`/`False` become `true`/`false`, `bytes` are decoded
with `encoding` and `bytes_errors`, and everything else becomes `str(value)`.
A list-valued text node becomes the `str()` of the list.

## Streaming

With `item_depth` greater than zero, `parse` does not build the whole document.
Instead, every element that reaches that depth is handed to `item_callback` as
`(path, item)` and then discarded, which keeps memory flat for large documents.
`parse` returns `None` in this mode. A callback that returns a falsy value
raises `ParsingInterrupted`.

```python
def handle(path, item):
    print(path, item)
    return True

xmlrelay.parse('<rows><row>1</row><row>2</row></rows>',
               item_depth=2, item_callback=handle)
# [('rows', None), ('row', None)] 1
# [('rows', None), ('row', None)] 2
```

Note two quirks preserved from the reference: a streamed element that has
attributes delivers only its attributes (its text is dropped), and streamed text
is **not** whitespace-stripped.

## Namespaces

With `process_namespaces=True`, Expat resolves namespaces and element/attribute
names are reported as `URI<separator>local`. Declared namespaces are collected
into an `@xmlns` mapping placed after the regular attributes.

```python
xmlrelay.parse('<a:b xmlns:a="urn:x" a:c="1"/>', process_namespaces=True)
# {'urn:x:b': {'@urn:x:c': '1', '@xmlns': {'a': 'urn:x'}}}
```

The `namespaces` option remaps the leading segment of names and applies even
without `process_namespaces`. A mapped prefix is replaced, a `None` mapping drops
the prefix, and an unknown prefix is left unchanged.

## Round-tripping

For common documents, `unparse(parse(x))` reproduces the content. Because the
data model is lossy in places (mixed-content ordering, insignificant whitespace),
a byte-for-byte round trip is not guaranteed, but the structure is stable.

## Command line

```sh
python -m xmlrelay <depth>
```

Reads XML from standard input, parses it in streaming mode at `item_depth`
`<depth>`, and writes each delivered `(path, item)` tuple to standard output as
a `marshal`-encoded record. A depth of `0` emits the whole document once as
`([], document)`; a negative depth emits nothing.

## Known quirks

`xmlrelay` deliberately mirrors the behaviour of its reference, including edges
that are more permissive or more surprising than you might expect:

- Entity declarations are rejected (`disable_entities=True` by default) with a
  `ValueError`, but an undefined entity under an external DTD is silently
  dropped.
- On `unparse`, element and attribute names are only checked for whitespace and
  `<`/`>`; other unusual names (an empty string, a leading digit) are emitted
  as-is.
- A non-`dict` passed to `unparse` raises `AttributeError` *after* the XML
  declaration has already been written to the output stream.
- When writing to an ASCII stream, non-ASCII characters become numeric
  references, but the returned string for the same call keeps the raw
  characters.
- `namespaces` on `unparse` drops unmapped element prefixes and mangles unmapped
  attribute prefixes.

## License

MIT. See [LICENSE](LICENSE).
