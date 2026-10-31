# AGENTS.md

Guidance for automated agents and contributors working in this repository.

## What this project is

`xmlrelay` is a small, dependency-free library that converts XML to nested
Python dictionaries and back. The public surface is intentionally tiny:
`parse`, `unparse` and `ParsingInterrupted`, plus the `python -m xmlrelay`
command line.

## Layout

- `src/xmlrelay/_decode.py` -- `parse` and the Expat-driven `DocumentBuilder`.
- `src/xmlrelay/_encode.py` -- `unparse` and the `XMLGenerator`-based `Encoder`.
- `src/xmlrelay/_exceptions.py` -- `ParsingInterrupted`.
- `src/xmlrelay/__main__.py` -- the streaming command line.
- `tests/unit/` -- standalone tests with their own assertions.
- `tests/differential/` -- comparison tests against a reference build.

## Working rules

- Keep the public API and its documented behaviour stable. This library's job is
  to match a precise contract; behaviour changes must be deliberate.
- No third-party runtime dependencies. The standard library only.
- Prefer clear, direct code over cleverness. The module docstrings explain the
  non-obvious data-model rules; keep them accurate.
- Every behaviour change needs a unit test with an explicit expected value.

## Tests

- `pytest tests/unit` runs the standalone suite; it needs nothing external.
- `tests/differential` compares against a bytecode-only reference build that is
  not part of this repository. Those tests skip when the reference is absent or
  the interpreter does not match it. Set `XMLRELAY_REQUIRE_ORACLE=1` to turn
  those skips into failures, and `XMLRELAY_DIFF_SCALE` to scale the number of
  generated cases.

## Commits

Use Conventional Commits (see `CONTRIBUTING.md`). Releases are automated with
release-please.
