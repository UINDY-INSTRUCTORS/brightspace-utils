# brightspace-utils

Tools for getting course material into and out of Brightspace (D2L) without clicking through
the web UI.

## Tools

| Tool | Purpose |
|---|---|
| [`rubric-sync/`](rubric-sync/) | Convert a `RUBRIC.md` into a Brightspace-importable rubric package (`.zip`) |
| [`folder-feedback/`](folder-feedback/) | Per-student folders in Brightspace's naming, zipped for bulk feedback upload *(unverified)* |

## Setup

This is a [uv](https://docs.astral.sh/uv/) project. One environment serves every tool.

```bash
uv sync                  # creates .venv/ with the dependencies in uv.lock
uv run pytest            # run all tests
uv run rubric-sync/convert_rubric_to_d2l.py RUBRIC.md -v
```

`uv run` works from any directory inside the repo. The project uses uv-managed Python only
(`python-preference = "only-managed"`), so it never picks up conda's or the system interpreter.

## Conventions for tools added here

- **One directory per tool**, with its own `README.md` and a CLI entry point.
- **Dependencies go in `pyproject.toml`** via `uv add <package>`, commented with the tool
  that needs them. Commit `uv.lock` with the change.
- **Tests** live in the tool's `tests/` directory; add the tool to `testpaths` and
  `pythonpath` in `pyproject.toml` so `uv run pytest` finds them.
- **No absolute paths.** Anything a test needs lives in that tool's `tests/fixtures/`.
- **No credentials or student data in the repo.** This repo is public. Anything that talks
  to the D2L Valence API reads its keys from the environment; classlist and roster exports
  are gitignored.
