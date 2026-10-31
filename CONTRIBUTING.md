# Contributing to xmlrelay

Thanks for your interest in improving `xmlrelay`.

## Development setup

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
```

Run the unit tests (these need no external fixtures):

```sh
pytest tests/unit
```

Run the full matrix locally with [tox](https://tox.wiki/):

```sh
tox
```

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Each commit message must start with a type, optionally a scope, and a short
description:

```
<type>[optional scope]: <description>
```

Common types:

- `feat:` a new feature
- `fix:` a bug fix
- `docs:` documentation only
- `test:` adding or correcting tests
- `refactor:` a code change that neither fixes a bug nor adds a feature
- `chore:`, `build:`, `ci:` tooling and infrastructure

A breaking change is marked with `!` after the type (for example `feat!:`) or
with a `BREAKING CHANGE:` footer. Releases and the changelog are generated from
these messages by release-please, so accurate types matter.

## Pull requests

1. Fork and branch from `main`.
2. Add tests for any behaviour change.
3. Make sure `pytest tests/unit` passes.
4. Keep the public API and its documented behaviour stable unless the change is
   intentional and described as breaking.
5. Open a pull request with a clear description.

## Code style

The repository ships a `.pre-commit-config.yaml`. Install the hooks with
`pre-commit install` to format and lint changes automatically.
