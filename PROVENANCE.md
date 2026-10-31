# PROVENANCE

## Author and tooling

- Implemented by an AI coding agent (Claude, Anthropic; model "Opus 4.8"),
  driving the build, probing and tests.
- Work performed on 2026-10-31.
- Target/runtime: Python 3.15.2 (CPython), matching the reference build's
  recorded minor version and bytecode magic (`3 15 520e0d0a`).

## How the contract was derived

The reference implementation (`xmltodict` 1.0.4, a bytecode-only install in
`~/xmlrelay-oracle`) was used **only as a black box**: scripts added that folder
to `sys.path`, imported the module, and called only `parse`, `unparse` and
`ParsingInterrupted`. Behaviour was discovered by feeding many small inputs and
observing return values, written output, exceptions (recorded as
`(class name, message)`), and callback call sequences, then generalising the
rules and encoding them here.

No reference source was read by any route: not from site-packages, not via
`inspect`/`dis`/decompilers, not from GitHub, mirrors, package downloads, code
search or pages quoting it. The module itself was never introspected
(`dir`/`help`/`vars`/pydoc/attribute listing were not used on it).

## Independence: architecture chosen independently

The implementation structure, module split, class and method names were chosen
for this project. Two standard-library foundations are used — `xml.parsers.expat`
for decoding and `xml.sax.saxutils.XMLGenerator` for encoding — because the
public contract itself dictates them (a custom `expat=` object must be called as
`ParserCreate(encoding, separator)` and used through pyexpat, and the exact
escaping/quoting/declaration/stream-wrapping behaviour is that of
`XMLGenerator`). These choices were confirmed empirically against the reference
rather than recalled from its source. General knowledge of XML, Expat and
`saxutils` was used; recollection of the reference's own code was not, and no
point in the build required it.

## Information sources consulted

- The task description provided to the agent (the contract summary and the list
  of known traps).
- The reference build at `~/xmlrelay-oracle`, as a black box (see above).
- The Python standard library and its documented behaviour (`xml.parsers.expat`,
  `xml.sax.saxutils`, `codecs`, `marshal`, `io`, `types`).

## Independence rules: near-misses and how they were handled

These are the moments that came closest to the independence rules, recorded for
the audit:

1. **Oracle tracebacks printed to the terminal (twice).** Early probing scripts
   let an exception from an oracle call propagate and print a traceback, and a
   command-line probe captured the oracle's stderr traceback. In both cases the
   traceback showed only a file path and line numbers plus the exception line —
   **no source code** — but printing oracle tracebacks is against the "record
   errors only as (class, message)" rule. Subsequent probes wrapped every oracle
   call in `try/except` and recorded only `(type(e).__name__, str(e))`, and the
   command-line comparison keeps only the final exception line.
2. **An internal class name appeared in an error message.** While testing whether
   the undocumented `depth` keyword is accepted, the resulting `TypeError`
   message named an internal reference function/class. The message was observed
   as data (the keyword is not accepted) and is not relied upon; `xmlrelay`'s own
   error for unknown keywords is Python's default and is explicitly exempt from
   parity.

No point in the build involved reconstructing reference code from memory. Where a
behaviour felt familiar, it was still re-derived by probing smaller inputs rather
than assumed.

## Fresh review

A separate agent with no prior context, bound by the same independence rules,
reviewed the differential harness for uncovered channels, options and input
types and added `tests/differential/test_coverage_gaps_diff.py`. That review
surfaced four edge behaviours where `xmlrelay` diverged from the reference; each
was re-verified against the reference as a black box and corrected (empty-tuple
pretty layout; rendering scalar/text values before the start tag so decode
errors appear correctly in partial output; splitting the pretty per-child lead
around name validation; and including the gathered `xmlns` map in the callback
`path` under namespace processing). The added tests now pass against the
reference.

## Fix round 1

An external evaluation of `xmlrelay` against the reference (`xmltodict` 1.0.4)
reported seven behaviours that diverged. Each was described only as observable
input and output; none referenced reference source. Bound by the same
independence rules (black-box oracle use only, errors recorded as
`(class, message)`, no reference source read by any route), each finding was
re-confirmed against the oracle as a black box, given harness coverage for the
whole class of inputs (not just the reported example), fixed, and the full
differential suite rerun clean.

The seven findings, as before/after pairs verified against the oracle:

1. **`unparse` name validation.** Before: names were only checked for whitespace
   and `<`/`>`, so `{'?x': 'v'}` serialised to `<?x>v</?x>` and a non-string key
   raised `TypeError`. After: names (element, attribute, and `@xmlns` prefixes,
   the last validated as attribute names) are rejected with `ValueError` for a
   leading `?`/`!`, or `<`/`>`, `/`, a quote, `=`, or whitespace — first rule in
   that order wins — and a non-string key raises
   `ValueError('<kind> name must be a string')`.
2. **`unparse` comment validation.** Before: `{'#comment': 'a--b'}` emitted
   `<!--a--b-->`. After: comment text containing `--` raises
   `ValueError("Comment text cannot contain '--'")` and text ending in `-` raises
   `ValueError("Comment text cannot end with '-'")`; `bytes` are decoded first.
3. **`@xmlns` value conversion.** Before: `{'@xmlns': {'a': True}}` produced
   `xmlns:a="True"` and `bytes` values were rendered via `repr`. After: values
   convert like any attribute value — `True` -> `"true"`, `bytes` decoded with the
   output encoding and `bytes_errors`, `None` -> `""`.
4. **Selective `force_cdata`.** Before: any non-empty `force_cdata` forced every
   element. After: a container selects by membership and a string by substring
   (like `force_list`), so `force_cdata=('b',)` forces only `b`.
5. **`str` input and encoding.** Before: a `str` was encoded with the effective
   encoding but the parser was still told the document's declared encoding, so a
   declaration like `iso-8859-1` corrupted UTF-8 text. After: the effective
   encoding (the `encoding` argument, or UTF-8) is handed to the parser too,
   overriding the declaration; the same applies to `str` chunks from a generator.
6. **`namespaces` lookup.** Before: the map was probed with `in`, so a
   `defaultdict`'s default never applied. After: it is looked up by item access,
   so a mapping subclass with a `__missing__` default applies it.
7. **CLI `KeyboardInterrupt`.** Before: an interrupt during a `python -m xmlrelay`
   parse exited with a traceback and a signal status. After: it exits quietly
   with status `0`.

The harness gap that let these through was closed: generated and parametrised
inputs now include names covering every rejected character class and non-string
keys; comment text with `--` and with a trailing `-`; `@xmlns` dicts with bad keys
and with bool/bytes/`None` values; `str` (and generator-of-`str`) input whose
declaration names a non-UTF-8 encoding; `defaultdict`/dict-subclass `namespaces`;
every container type and a string passed to `force_cdata`; and a CLI
`KeyboardInterrupt` comparison. The oracle location is now read from
`XMLRELAY_ORACLE_DIR` (default `~/xmlrelay-oracle`), and the README documents how
to build the oracle and run the suite.

One further divergence surfaced during this round that is **outside** the seven
findings and was left unchanged: a top-level comment given as a *list* in
`pretty=True` mode places its newline separators differently from the reference
(mapping-level comment lists already match). It is recorded here so a later round
can address it deliberately.

## Notes on reproduced behaviour

Several deliberately permissive or surprising behaviours of the reference are
reproduced on purpose (entity handling, legal-but-unusual names such as a leading
digit or an empty string passing validation, the declaration written before an
`AttributeError` on non-dict input, ASCII-stream character references, namespace
mangling on `unparse`). These are faithful reproductions of the contract, not
oversights.
