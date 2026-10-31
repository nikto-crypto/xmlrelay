# SPEC

This document records the behavioural contract `xmlrelay` implements, the
architecture chosen to implement it, and the strategy used to verify it. The
contract was derived by observing a reference build strictly as a black box
(calling only `parse`, `unparse` and `ParsingInterrupted`); none of its source
was read.

## 1. Goals

1. **Behavioural equivalence.** For the same arguments, `xmlrelay` produces the
   same return values (with identical `repr`, so key order and container types
   match), the same written bytes, the same exceptions, and the same callback
   sequences as the reference.
2. **Independent implementation.** The code is organised and named on its own
   terms; it shares no source with the reference.

## 2. Architecture

The public surface lives in `src/xmlrelay/`:

- `_exceptions.py` -- `ParsingInterrupted`.
- `_decode.py` -- `parse`, plus `DocumentBuilder`, an Expat event handler that
  grows a tree of mappings.
- `_encode.py` -- `unparse`, plus `Encoder`, which renders a mapping tree through
  `xml.sax.saxutils.XMLGenerator`.
- `__main__.py` -- the streaming command line.

### Why these two standard-library foundations

- **Parsing on Expat.** The contract requires a custom `expat=` object to be
  called as `ParserCreate(encoding, separator)` and driven through the normal
  pyexpat interface, so Expat is the natural engine. Several observable details
  (chunk boundaries for character data, the exact wording of malformed-input
  errors, encoding override for byte input, external-DTD handling) fall out of
  Expat for free when it is driven the same way.
- **Serialising on `XMLGenerator`.** The reference's escaping, attribute quoting,
  XML declaration, and output-stream wrapping (text stream vs. byte stream vs.
  write-only object) match `XMLGenerator` exactly, so building on it reproduces
  those for free. Pretty indentation, list expansion, comment placement,
  namespace remapping and name validation are layered on top.

## 3. Decoding contract (`parse`)

### 3.1 Input dispatch

- An object with a `.read` attribute is parsed with `ParseFile` as a binary
  stream (a text stream raises `TypeError`).
- A real generator is fed chunk by chunk (`str` chunks are encoded first).
- Anything else is parsed in a single call; `str` is encoded with `encoding` or
  UTF-8 first, and non-byte-like input (e.g. a list) raises Expat's `TypeError`.

`buffer_text` is enabled on the parser, which is what makes character-data
chunking match: a single parse call delivers one text run, while file and
generator input flush per read/chunk.

### 3.2 Tree assembly

`DocumentBuilder` maintains a live path of open elements, a stack of saved
parent state, the character-data runs of the current element, and the current
element's mapping.

- An element with attributes starts a mapping of `attr_prefix + name -> value`;
  otherwise it starts as `None`.
- Character data accumulates; at element end it is joined with `cdata_separator`
  and stripped when `strip_whitespace`.
- A pure text leaf becomes a string; an element with attributes/children/forced
  cdata gets its text under `cdata_key`; an empty element becomes `None`.
- Adding a key that already exists promotes the value to a list; a first
  occurrence consults `force_list`.
- Comments (when enabled) are attached immediately under `comment_key`, stripped
  when `strip_whitespace`.

### 3.3 Callbacks

- `postprocessor(path, key, value)` runs for every attribute, text node, comment
  and element, with the live path. Returning `None` drops the entry; for
  attributes any falsy return drops it; otherwise the result is unpacked as a
  pair.
- `force_list` and `force_cdata` callables receive the *parent* path
  (`path[:-1]`). `force_cdata` is consulted whenever an element has text, even if
  it also has attributes.
- `item_callback(path, item)` drives streaming (see below) and receives the live
  path.

### 3.4 Streaming

Let `L` be the number of open elements when an element closes. When `L` equals
`item_depth`, the element's value is delivered to `item_callback` and discarded;
a falsy return raises `ParsingInterrupted`. When `L` is greater, the element is
merged into its parent as usual. When `L` is smaller, it is discarded. A streamed
value is the element's mapping, or its *unstripped* joined text when it has no
mapping. `parse` returns the root accumulator, which is `None` once anything has
streamed.

### 3.5 Namespaces and entities

- `process_namespaces` turns on Expat namespace resolution; declarations are
  gathered into an `@xmlns` mapping placed after the regular attributes.
- `namespaces` remaps the leading segment of names (split on
  `namespace_separator`): a mapped value replaces it, a falsy mapping drops it,
  an unknown segment is left unchanged. It applies with or without
  `process_namespaces`.
- `disable_entities` (default) rejects entity declarations with
  `ValueError('entities are disabled')`. Undefined entities under an external DTD
  are silently dropped; undefined entities without a DTD raise Expat's error.

## 4. Encoding contract (`unparse`)

- `bytes_errors` is validated first; an unknown handler raises `ValueError`
  before anything is written.
- With `full_document`, the XML declaration is written, then exactly one root
  element is required: zero or more than one non-comment top-level key raises
  `Document must have exactly one root.`, while a single key whose value expands
  to several root elements raises `document with multiple roots`.
- Within an element, attributes come first (keys starting with `attr_prefix`,
  with a literal `@xmlns` dict expanded to declarations), then child elements and
  comments in document order, then text.
- Scalars convert as described in the README; a list value expands to repeated
  elements; a nested iterable becomes `str()` text unless `expand_iter` names a
  wrapper element.
- Pretty mode inserts `newl` + `indent * depth` around child items; an element
  has pretty structure when it has at least one child or comment whose value
  contributes members (an empty list/tuple contributes none).
- Element and attribute names are rejected only for whitespace or `<`/`>`.
- `preprocessor(key, value)` runs once per element key; `None` drops it.

## 5. Command line

`python -m xmlrelay <depth>` reads XML from standard input, parses it at the
given `item_depth`, and writes each streamed `(path, item)` as a `marshal`
record. A depth of `0` writes the whole document once as `([], document)`; a
negative depth writes nothing.

## 6. Verification strategy

- **Differential tests** (`tests/differential/`) run `xmlrelay` and the
  reference side by side and compare every channel: parse return values (by
  `repr`), `unparse` return strings, bytes written to binary/text/write-only
  streams (including partial output on failure), exception class and message,
  callback call logs, and command-line output decoded from `marshal`. Inputs come
  from Hypothesis (XML documents and unparse mappings), every input container
  type, every documented option alone and combined, curated realistic documents,
  and malformed input. The suite is gated on the reference's recorded Python
  minor version and bytecode magic; it skips when the reference is absent and
  fails instead when `XMLRELAY_REQUIRE_ORACLE=1`.
- **Unit tests** (`tests/unit/`) assert concrete expected values and stand alone
  without the reference.
