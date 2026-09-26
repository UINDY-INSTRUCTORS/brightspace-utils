# brightspace-utils

Tools for getting course material into and out of Brightspace (D2L) without clicking through
the web UI.

## Tools

| Tool | Purpose |
|---|---|
| [`rubric-sync/`](rubric-sync/) | Convert a `RUBRIC.md` into a Brightspace-importable rubric package (`.zip`) |

## Conventions for tools added here

- **One directory per tool**, with its own `README.md` and a CLI entry point.
- **No absolute paths.** Anything a test needs lives in that tool's `tests/fixtures/`.
- **Declare dependencies in the script.** If a tool needs third-party packages, use a
  [PEP 723](https://peps.python.org/pep-0723/) inline header and the `uv run --script`
  shebang rather than assuming a shared interpreter:

  ```python
  #!/usr/bin/env -S uv run --script
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["requests"]
  # ///
  ```

  `rubric-sync` is stdlib-only, so it runs under any Python 3.11+.
- **No credentials in the repo.** This repo is public. Anything that talks to the D2L
  Valence API reads its keys from the environment.
