# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Conventional Commits](https://www.conventionalcommits.org/) together with
[release-please](https://github.com/googleapis/release-please) to manage
releases.

## [1.1.0](https://github.com/nikto-crypto/xmlrelay/compare/xmlrelay-v1.0.0...xmlrelay-v1.1.0) (2026-10-31)


### Features

* implement XML &lt;-&gt; dict parse and unparse with CLI ([b236d12](https://github.com/nikto-crypto/xmlrelay/commit/b236d12c270faa7df93e42f7b4eb6896074731b0))


### Bug Fixes

* align four edge behaviors with the reference ([67e9c69](https://github.com/nikto-crypto/xmlrelay/commit/67e9c69c077348e5492404ea6e955ce9f8e9da0a))
* align seven behaviors with the reference (Fix round 1) ([03c7c82](https://github.com/nikto-crypto/xmlrelay/commit/03c7c82be22e87a949d0766e07a5b1df604c8c85))


### Documentation

* add README, SPEC, PROVENANCE and project docs ([a8c8d16](https://github.com/nikto-crypto/xmlrelay/commit/a8c8d166d3d87be5c902175310bd5d9dd2fd6971))
* document the oracle build/suite and record Fix round 1 ([8de08b4](https://github.com/nikto-crypto/xmlrelay/commit/8de08b4bef520dc5b71899f825bc5068afbd7875))
* record the fresh-review round in PROVENANCE ([9220b5c](https://github.com/nikto-crypto/xmlrelay/commit/9220b5c85655e14413c01562658f71e2895b6f1f))

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
