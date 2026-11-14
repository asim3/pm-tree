# CLAUDE.md

pm-tree is the owner's file-based project-management format (`pm/`) and its validator, published on PyPI as `pm-tree` so his project repos can install it. `README.md` says how to develop and release it; `src/pm_tree/README.md` is the guide.

- **It is for the owner's own projects** (owner, 2026-11-14). It is on PyPI only so his repos can install it. Don't generalise it, add configuration, or write documentation for other users.
- **The version is the owner's to set,** in `pyproject.toml`. Never change it, and add no bump logic, upgrade steps or version checks. A release is a tag he asks for (`README.md`, *Releasing*).
- **The guide, `src/pm_tree/README.md`, is the reference in every project repo,** printed with the templates by `pm-tree --guide`. A change to a rule changes the guide and the tests (every rule has a passing and a failing fixture), the templates when keys change, and `example/pm/` when it must show something new.
- **The guide and `--help` are written for an LLM, not a human** (owner, 2026-11-14), so any LLM tool can use the package. They address the LLM as "you", in steps and exact commands. A new option goes in both, which a test checks.
- **Nothing private goes in.** PyPI is public, so the code and the README can be read by anyone, although this repo is private. No names of the owner's ventures, clients or people, in code, tests or commit messages.
- **Commits** use the GitHub noreply address set in this repo's git config, never a personal email. Push to `main`; CI runs the tests on every push.
