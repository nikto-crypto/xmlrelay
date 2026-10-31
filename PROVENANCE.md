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

## Notes on reproduced behaviour

Several deliberately permissive or surprising behaviours of the reference are
reproduced on purpose (entity handling, lax name validation, the declaration
written before an `AttributeError` on non-dict input, ASCII-stream character
references, namespace mangling on `unparse`). These are faithful reproductions of
the contract, not oversights.
