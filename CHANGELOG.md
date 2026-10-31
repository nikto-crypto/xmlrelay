# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Conventional Commits](https://www.conventionalcommits.org/) together with
[release-please](https://github.com/googleapis/release-please) to manage
releases.

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
