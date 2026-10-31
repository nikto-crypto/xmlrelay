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

- `str` -- encoded with `encoding` (or UTF-8) before parsing, and that same
  encoding is handed to the parser, so it overrides any encoding named in the
  document's own XML declaration;
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
| `force_cdata` | `False` | Force text into `cdata_key` even for a leaf. Selects the same way as `force_list` (see below). |
| `force_list` | `None` | Force list wrapping for matching keys. See below. |
| `item_callback` | returns `True` | Called for each streamed item (see Streaming). |
| `item_depth` | `0` | Depth at which to stream instead of build (see Streaming). |
| `namespaces` | `None` | Prefix/URI remapping (see Namespaces). |
| `postprocessor` | `None` | `(path, key, value) -> (key, value) | None` run for every key. |
| `process_comments` | `False` | Capture comments into `comment_key`. |
| `process_namespaces` | `False` | Resolve namespaces through Expat. |
| `strip_whitespace` | `True` | Strip surrounding whitespace from text and comments. |
| `xml_attribs` | `True` | Include attributes in the result. |

`force_list` and `force_cdata` accept the same shapes: `True`/`False`, a string
or collection (a name is forced when `name in force_list`, so a string matches by
substring and a tuple/list/set/dict matches by membership), or a callable
(`force_list(path, key, value) -> bool`, `force_cdata(path, name, text) -> bool`).
A truthy value that is neither of these (for example `5`) raises `TypeError`,
matching the reference behaviour.

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
A list-valued text node becomes the `str()` of the list. The values inside an
`@xmlns` mapping are converted the same way (with `None` becoming an empty
string, as for any attribute value).

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
without `process_namespaces`. A mapped prefix is replaced, a falsy mapping drops
the prefix, and an unknown prefix is left unchanged. The lookup is by item access,
so a mapping subclass with a `__missing__` default -- for example a
`collections.defaultdict` -- has its default applied to otherwise-unknown
prefixes.

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
- On `unparse`, element and attribute names (including `@xmlns` prefixes, which
  are validated as attribute names) are rejected with a `ValueError` when they
  start with `?`/`!`, or contain `<`/`>`, `/`, a quote, `=`, or whitespace;
  non-string keys raise `ValueError` too. Unusual-but-legal names such as an
  empty string or a leading digit are still emitted as-is.
- Comment text is rejected with a `ValueError` when it contains `--` or ends with
  `-`.
- A non-`dict` passed to `unparse` raises `AttributeError` *after* the XML
  declaration has already been written to the output stream.
- A `KeyboardInterrupt` during a `python -m xmlrelay` parse exits quietly with
  status `0`.
- When writing to an ASCII stream, non-ASCII characters become numeric
  references, but the returned string for the same call keeps the raw
  characters.
- `namespaces` on `unparse` drops unmapped element prefixes and mangles unmapped
  attribute prefixes.

## Development

### Running the tests

```sh
pip install -e ".[test]"
pytest tests/unit          # standalone, needs nothing external
pytest tests                # also runs the differential suite (see below)
```

The unit suite stands on its own. The **differential** suite under
`tests/differential/` compares `xmlrelay` against a reference build (the
"oracle") on thousands of generated and curated inputs, asserting that return
values, raised exceptions, bytes written (including partial output on failure)
and callback sequences all match.

### The differential oracle

The oracle is the reference implementation (xmltodict 1.0.4) installed **as
bytecode only** and used strictly as a black box -- `xmlrelay` is an independent
reimplementation, so its own sources never read the reference. The oracle lives
outside the repository; its location is read from `XMLRELAY_ORACLE_DIR`
(default `~/xmlrelay-oracle`). Because it ships as compiled bytecode it only
loads on the exact Python minor version and magic number recorded in its
`ORACLE_PYTHON.txt`.

When the oracle is absent or the interpreter does not match, the differential
tests **skip**. Set `XMLRELAY_REQUIRE_ORACLE=1` to turn those skips into hard
failures (use this in CI so a run cannot silently pass without the comparison),
and `XMLRELAY_DIFF_SCALE` to scale the number of generated cases (e.g. `0.1` for
a quick local run).

Build the oracle once with:

```sh
ORACLE_DIR="${XMLRELAY_ORACLE_DIR:-$HOME/xmlrelay-oracle}"
tmp="$(mktemp -d)"
python -m pip install --target "$tmp" xmltodict==1.0.4
mkdir -p "$ORACLE_DIR"
TMP_XTD="$tmp" ORACLE_DIR="$ORACLE_DIR" python - <<'PY'
import glob, importlib.util, os, py_compile, shutil, sys
tmp, dst = os.environ["TMP_XTD"], os.environ["ORACLE_DIR"]
# Compile to bytecode only; the reference's source is never kept in the oracle.
py_compile.compile(os.path.join(tmp, "xmltodict.py"),
                   cfile=os.path.join(dst, "xmltodict.pyc"), doraise=True)
for info in glob.glob(os.path.join(tmp, "xmltodict-*.dist-info")):
    shutil.copytree(info, os.path.join(dst, os.path.basename(info)),
                    dirs_exist_ok=True)
with open(os.path.join(dst, "ORACLE_PYTHON.txt"), "w") as fh:
    fh.write("%d %d %s" % (sys.version_info.major, sys.version_info.minor,
                           importlib.util.MAGIC_NUMBER.hex()))
PY
rm -rf "$tmp"
```

Then run the full comparison:

```sh
XMLRELAY_REQUIRE_ORACLE=1 pytest tests -rs
```

## License

MIT. See [LICENSE](LICENSE).
