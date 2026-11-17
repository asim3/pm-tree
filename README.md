# pm-tree

A file-based project-management format, and a strict validator for it. A project tracks its milestones and issues in `pm/`, with one YAML file per issue, and Claude Code works from them.

It started as the format for its maintainer's own projects. It is free for anyone to use, fork and improve, under the MIT licence (see *Licence*).

- **The guide:** [src/pm_tree/README.md](src/pm_tree/README.md), the format, every rule and how to work in `pm/`. It is written for the LLM that works in a project, not for a human, and is also the package's page on PyPI. `pm-tree --guide` prints the installed copy, with the templates.
- **In a project:** pin `pm-tree==<version>` in the backend's dev requirements, then run `pm-tree`, `pm-tree --summary`, `pm-tree --next-id` or `pm-tree --guide`.

## Developing pm-tree

```
python3 -m venv .venv
.venv/bin/pip install -e . pytest
.venv/bin/python -m pytest
```

- `tests/test_rules.py` gives every rule at least one passing and one failing fixture. Each fixture is a small change to a valid base tree. A failing fixture lists every finding it must produce, so it fails if it sets off anything else. The fixtures run with a fixed today, 2030-01-01, so their notes are never in the future.
- `tests/test_templates.py` checks that the templates hold the schema's full key set, in its order, and that their values pass the schema. The issue template starts with no notes, so a copy can't keep a made-up dated note; it shows a note in a comment, which the test reads.
- `tests/test_cli.py` checks the output format, the exit codes, the `pm-tree` command, `--summary`, `--json`, whose example in the guide must be the real output, `--guide`, `--docs`, `--help`, and `--next-id` in scratch git repos, outside one, and with no git installed. It checks that the guide names every option `--help` lists. It also checks that `example/pm/` validates with no errors and no warnings and uses every status, priority, repo and link type.

CI runs the tests on Python 3.10 and 3.14 on every push and pull request.

## Releasing

1. The maintainer sets the new version in `pyproject.toml`. PyPI never accepts the same version twice, and a published version can be yanked but never replaced, so a fix is always a new version.
2. Commit it and push `main`.
3. Tag that commit `v<version>`, such as `v1.0.1`, and push the tag. CI runs the tests, builds the package and publishes it to PyPI.

PyPI trusts this repo's `.github/workflows/ci.yml` to publish `pm-tree` (trusted publishing), so no token is kept anywhere.

Each project repo moves to the new version when its pin is raised, in a merge request of its own (see *Move to a new version of pm-tree* in the guide).

## Licence

MIT, in `LICENSE`. Anyone may use pm-tree, fork it, change it and share it, and improvements are welcome. `pyproject.toml` declares it as `license = "MIT"`, so PyPI shows it, and every wheel and sdist carries the file.
