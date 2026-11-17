# CLAUDE.md

pm-tree is a file-based project-management format (`pm/`) and its validator, published on PyPI as `pm-tree`. It started as the format for the maintainer's own projects. `README.md` says how to develop and release it; `src/pm_tree/README.md` is the guide.

- **It is free for anyone** (maintainer, 2026-11-18). It is MIT-licensed (`LICENSE`), so anyone may use it, fork it, change it and share it, and improvements are welcome.
- **The version is the maintainer's to set,** in `pyproject.toml`. Never change it, and add no bump logic, upgrade steps or version checks. A release is a tag he asks for (`README.md`, *Releasing*).
- **The guide, `src/pm_tree/README.md`, is the reference in every project repo,** printed with the templates by `pm-tree --guide`. A change to a rule changes the guide and the tests (every rule has a passing and a failing fixture), the templates when keys change, and `example/pm/` when it must show something new.
- **The guide and `--help` are written for an LLM, not a human** (maintainer, 2026-11-14), so any LLM tool can use the package. They address the LLM as "you", in steps and exact commands. A new option goes in both, which a test checks.
- **Nothing private goes in.** This repo and PyPI are public, so the code, the README and the git history can be read by anyone. No names of the maintainer's ventures, clients or people, in code, tests or commit messages.
- **Commits** use the GitHub noreply address set in this repo's git config, never a personal email. Push to `main`; CI runs the tests on every push.
