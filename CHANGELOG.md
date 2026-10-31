# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Conventional Commits](https://www.conventionalcommits.org/) together with
[release-please](https://github.com/googleapis/release-please) to manage
releases.

## [Unreleased]

### Fixed

Seven behaviours were brought back into line with the reference after an external
evaluation against `xmltodict` 1.0.4 reported them diverging (Fix round 1):

- `unparse` now validates element, attribute and `@xmlns`-prefix names, rejecting
  names that start with `?`/`!` or contain `<`/`>`, `/`, a quote, `=`, or
  whitespace, and raising `ValueError` on non-string keys.
- `unparse` now rejects comment text that contains `--` or ends with `-`.
- `unparse` now converts the values inside an `@xmlns` mapping like any other
  attribute value (`True` -> `"true"`, `bytes` decoded, `None` -> `""`).
- `parse` `force_cdata` now selects per name (container by membership, string by
  substring), matching `force_list`, instead of treating any non-empty value as
  "force all".
- `parse` now hands the effective encoding for `str` (and generator-of-`str`)
  input to the parser, so it overrides the document's own XML declaration.
- `parse` now looks `namespaces` up by item access, so a mapping subclass with a
  `__missing__` default (e.g. `collections.defaultdict`) has its default applied.
- `python -m xmlrelay` now exits quietly with status `0` on `KeyboardInterrupt`.

### Changed

- Documented how to build the differential oracle and run the suite, and made the
  oracle location configurable via `XMLRELAY_ORACLE_DIR`.

## [1.0.0] - 2026-10-31

### Added

- `parse` -- convert XML (from text, bytes, binary streams or generators) into
  nested dictionaries, with options for attributes, text, comments, namespaces,
  entity handling, list forcing, streaming and post-processing.
- `unparse` -- serialise nested dictionaries back to XML, with options for
  pretty printing, encoding, namespaces, comments, pre-processing and output
  streams.
- `ParsingInterrupted` -- raised when an `item_callback` stops a streaming parse.
- `python -m xmlrelay <depth>` -- a streaming command-line front end that emits
  `marshal`-encoded `(path, item)` records.
