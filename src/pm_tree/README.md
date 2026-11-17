# pm-tree

This guide is for you, the LLM working in a project that tracks its work in `pm/`. It is not written for a human reader. Read all of it before you create, change or close anything in `pm/`.

`pm-tree --guide` prints this guide, followed by the templates. It describes the version your repo pins, which `pm-tree` prints on its first line.

pm-tree is two things: a file-based project-management format, and `pm-tree`, a strict validator for it. Both are designed for you, the LLM, first.

## What pm/ is

- `pm/` is the main interface between the maintainer and you. The maintainer reviews `pm/`, not the code.
- It holds one folder per milestone, and one YAML file per issue. It also holds `config.yaml` when the project's repos are not `backend`, `frontend` and `mobile`.
- It lives in the home repo: the first repo `config.yaml` lists, or `backend` without it. A project with one repo counts it as its home repo.
- You work from the issues, and you keep them up to date as you work.
- You close issues and milestones on your own judgment. Ask the maintainer only when one needs them, such as for a decision.
- Each fact is written once. A milestone's goal and gate criteria stay in the project's `SPEC.md`. Each link between two issues is written on one of them.
- History comes from git, so the files hold no dates and no assignees. The only dates are the ones inside notes.

## Commands

Run the copy your repo pins: `.venv/bin/pm-tree`, or `pm-tree` in the environment where the dev requirements are installed.

| Command | Validates `pm/` | Prints, after the version line | Exit code |
|---|---|---|---|
| `pm-tree [path]` | yes | one line per finding, then the counts | 1 on any error, 0 otherwise |
| `pm-tree --summary [path]` | yes | the findings and the counts; with no errors, each milestone's state | 1 on any error, 0 otherwise |
| `pm-tree --json [path]`, `pm-tree --summary --json [path]` | yes | instead of the version line and the text, one JSON document (see *--json*) | 1 on any error, 0 otherwise |
| `pm-tree --next-id [path]` | no | the ID a new issue takes; outside a git repo, a warning first | 1 if git can't read the branches, 0 otherwise |
| `pm-tree --guide` | no | this guide, then the templates | 0 |
| `pm-tree --docs` | no | the folder that holds this version's `README.md` (this guide), `templates/` and `example/` | 0 |

`path` is the `pm/` folder, and defaults to `pm` in the current folder. The validator needs Python 3.10+ and PyYAML, which pip installs with it. `--next-id` also uses git when `path` is in a git repo.

### Validating

The output of `pm-tree`:

- The first line is the installed version.
- Then one line per finding, sorted by path, as `ERROR <path>: <message>` or `WARNING <path>: <message>`.
- The last line is the count of errors and warnings.

Warnings alone exit 0.

```
pm-tree 1.2.0
ERROR pm/M1-tenant-core/I-002-tenant-resolution.yaml: status is doing, but depends_on I-001 is todo
WARNING pm/M2-lead-capture/I-007-lead-export.yaml: title is the same as I-012 (pm/M2-lead-capture/I-012-export-leads-to-csv.yaml), ignoring case, spaces and punctuation
1 error, 1 warning
```

### --summary

`--summary` validates first. If there are errors, it prints them and exits 1. Otherwise it prints, for each milestone:

- its status, and its issue counts by status;
- every open issue that is waiting, with the IDs it waits on. An issue is waiting when its status is `blocked`, or when it has a `depends_on` issue that isn't done. A blocked issue is also shown with its latest note, which says why;
- for an active milestone, its ready issues: the `todo` issues that wait on nothing, by priority and then by ID.

From `example/pm/`:

```
M2 Lead capture: active
  issues: 5 (2 todo, 1 doing, 1 blocked, 1 done)
  waiting:
    I-008 (blocked): Spam protection on the lead form
      2026-10-10: Blocked until a CAPTCHA provider is chosen.
    I-009 (todo) waits on I-006: Email the tenant about each new lead
  ready:
    I-007 (low): Export leads to CSV
```

### --json

`--json` prints one JSON document instead of the text, for a program to read. Use it on its own, as `pm-tree --json`, or as `pm-tree --summary --json`. It doesn't work with the other options. The exit codes are the same. There is no version line, because the version is in the document.

From `example/pm/`, with `--summary`, showing M2 only:

```json
{
  "version": "1.2.0",
  "findings": [],
  "errors": 0,
  "warnings": 0,
  "milestones": [
    {
      "id": "M2",
      "path": "pm/M2-lead-capture/milestone.yaml",
      "title": "Lead capture",
      "status": "active",
      "issues": {"total": 5, "todo": 2, "doing": 1, "blocked": 1, "done": 1, "dropped": 0, "duplicate": 0},
      "waiting": [
        {
          "id": "I-008",
          "path": "pm/M2-lead-capture/I-008-form-spam-protection.yaml",
          "status": "blocked",
          "title": "Spam protection on the lead form",
          "waits_on": [],
          "note": {"date": "2026-10-10", "text": "Blocked until a CAPTCHA provider is chosen."}
        },
        {
          "id": "I-009",
          "path": "pm/M2-lead-capture/I-009-new-lead-email.yaml",
          "status": "todo",
          "title": "Email the tenant about each new lead",
          "waits_on": ["I-006"],
          "note": null
        }
      ],
      "ready": [
        {"id": "I-007", "path": "pm/M2-lead-capture/I-007-lead-export.yaml", "priority": "low", "title": "Export leads to CSV"}
      ]
    }
  ]
}
```

| Key | Value |
|---|---|
| `version` | The installed version. |
| `findings` | One object per finding, sorted by path, with `severity` (`ERROR` or `WARNING`), `path` and `message`. |
| `errors`, `warnings` | The counts. |
| `milestones` | Only with `--summary`. One object per milestone, in order, and `[]` when there are none. `null` when there are errors. |
| `id`, `path`, `title`, `status` | The milestone. `path` is its `milestone.yaml`. |
| `issues` | `total`, and the count of each issue status, `0` included. |
| `waiting` | The open issues that wait, each with `id`, `path`, `status`, `title`, `waits_on` and `note`. `waits_on` holds the `depends_on` IDs that aren't done. `note` is a blocked issue's latest note, as `date` and `text`, and `null` for any other issue. |
| `ready` | In an active milestone, the ready issues, by priority and then by ID, each with `id`, `path`, `priority` and `title`. `null` in a milestone that isn't active. |

### --next-id

`--next-id` doesn't validate. After the version line, it prints the ID a new issue takes: one above the highest issue number in `path`. It counts the files there, and the same folder on every local and remote branch. If git can't read the branches, it prints the error and exits 1.

When `path` isn't in a git repo, there are no branches to count, so it counts only the files in `path`. It prints a warning before the ID and exits 0 (see *Without git*). The same happens when git isn't installed, unless `path` is in a git repo after all. Its branches can't be read then, so that is an error.

```
pm-tree 1.2.0
WARNING pm: is not in a git repo, so only its own issue files were counted
I-011
```

## How to work in pm/

### At the start of a session

1. Run `git fetch`.
2. Run `pm-tree --summary`. If it reports errors, fix them first (see *Fix the findings*).
3. Choose from the `ready` list of an active milestone, unless the maintainer has named the issue.
4. Before you start an issue, look in its repo for a branch with its ID, such as `git branch -a --list '*I-007-*'`. If there is one, the issue is already being worked on.

### Start an issue

1. Make a branch named after it, as `<id>-<slug>` like its file: `I-007-lead-export`. A branch that works on several issues starts with all their IDs: `I-004-I-005-tenant-fields`.
2. If its milestone is `planned`, set the milestone to `active`. A `planned` milestone holds no issue that is `doing` or `done`.
3. Set the issue's `status` to `doing`. Every issue in its `depends_on` must already be `done`.

### Finish an issue

1. Set an acceptance item's `done` to `true` once that outcome holds.
2. Set `status` to `done`. Every acceptance item must be `done: true`, and every `depends_on` issue must be `done`.
3. For an issue whose `repo` is the home repo, the status change goes in the same commit as the code that closes it.
4. For an issue in another repo, commit the code in its own repo first. Then commit the change that closes the issue in the home repo (see *Work from another repo*). Both commits start with the issue ID.

### Create an issue

1. Run `git fetch`, then `pm-tree --next-id`. Use the ID it prints. Never number an issue by hand, and never reuse a number: a closed issue keeps its file, so its number stays taken.
2. Copy the issue template to `pm/M<n>-<slug>/<id>-<slug>.yaml`, and replace every value. `pm-tree --guide` prints the template at its end; it is also `templates/issue.yaml` in the folder `pm-tree --docs` prints.
3. Write each link once, on one of its two issues:
   - a dependency on the issue that waits;
   - a duplicate on the issue that repeats the other;
   - a related link on either of the two.
4. Work that needs two repos becomes one issue for each, joined by `depends_on`.
5. Run `pm-tree`.

A new issue is made on a branch, which can't see the new issues on other branches. So two sessions that number issues at the same time can still take the same number. The branch merged second is first rebased onto `main`, so its pipeline reports the clash. Its issue then takes a new number before it merges. An ID is final once it is on `main`.

### Block, drop or mark a duplicate

- **Blocked or dropped:** set the status, and add a note that says why. Both statuses need at least one note.
- **Duplicate:** set `status` to `duplicate` and `duplicate_of` to the original issue. The original must not itself be a duplicate.
- **What depended on it:** an open issue can't depend on a `dropped` or `duplicate` issue, since neither will ever be done. Remove the link, or make it name the original issue instead of the duplicate.

A note is a quoted `date`, in the form `YYYY-MM-DD`, and a non-empty `text`:

```yaml
notes:
  - date: "2026-10-02"
    text: Blocked until a CAPTCHA provider is chosen.
```

### Move an issue to another milestone

Move its file into that milestone's folder. Nothing in the file changes. The commit reads like `I-007: move to M2`.

### When closed work is needed again

A closed issue is never reopened. When done work turns out broken, or dropped work is needed after all, make a new issue for it, with a `related` link to the old one.

### Close a milestone

Set the milestone's `status` to `done` once its gate criteria in `SPEC.md` are met. Every issue in its folder must be `done`, `dropped` or `duplicate`.

### Find what links to an issue

Each link is written on one issue only. To find what waits on I-003, or what repeats it, search `pm/` for `I-003`.

### Fix the findings

- Each file is first checked on its own. A file that fails to parse, or breaks the schema, stays out of the checks across files until it is fixed. So do issues whose ID another file also claims. That way, one broken file doesn't set off errors in every file that links to it.
- So fix the errors and run `pm-tree` again. New errors can appear once a fixed file rejoins the checks across files.
- An error about two issues is reported on one of them, and names the other's file.
- The three warnings are listed under *Rules*, each with what it means.

### Work from another repo

- A product with several repos keeps one `pm/` for all of them, in its home repo. One `pm/` and one run of issue numbers then cover every repo, so an issue in one repo can depend on an issue in another.
- Open the home repo beside yours. In Claude Code, use `--add-dir`, or `permissions.additionalDirectories` in your repo's settings. In another tool, open the home repo's folder the way it adds a second folder.
- Run the home repo's own `pm-tree` on its `pm/`, so one version checks the whole product. When the repos sit side by side: `../<home-repo>/.venv/bin/pm-tree ../<home-repo>/pm`.
- Commit in the home repo only the `pm/` files you changed. Stage them by name, never with `git add -A` or `git commit -a`, so you can't sweep up work there that isn't finished.
- They go in a commit of their own, on a branch made from the home repo's `main`, and reach `main` through a merge request.
- When the home repo's checkout isn't on `main`, ask the maintainer first.

### Set up pm/ in a new project

1. `pm/` lives in the home repo: the backend, or the only repo of a project with one.
2. Add `pm-tree==<version>` to the home repo's dev requirements.
3. Create `pm/`, with one milestone folder for each milestone in `SPEC.md`. Make each milestone and issue from the templates.
4. If the project's repos are not `backend`, `frontend` and `mobile`, make `pm/config.yaml` from its template. List every repo, the home repo first. Work that isn't software, such as documents or approvals, still names the repo it is kept in.
5. Run `pm-tree` in CI as one of the home repo's static checks, so every push checks `pm/`. Its job runs `pm-tree` in the environment the dev requirements are installed in.
6. CI counts `pm/` as documentation, so a merge that changes only `pm/` releases nothing. A pipeline that lists its paths must list `pm/` among the ones that don't deploy.

The home repo, beside its code:

```
SPEC.md                    # the project's spec, which milestones and issues point into
requirements-dev.txt       # pins pm-tree, such as pm-tree==1.2.0
pm/
  config.yaml              # only when the repos are not backend, frontend and mobile
  M1-<slug>/
    milestone.yaml
    I-001-<slug>.yaml
    I-002-<slug>.yaml
  M2-<slug>/
    ...
```

### Without git

`pm/` also works in a folder that isn't a git repo:

- `pm-tree` and `pm-tree --summary` never use git, so they work the same.
- `pm-tree --next-id` counts only the issue files in `pm/`, and warns that it did.
- Skip every step that runs git: `git fetch`, branches, commits and merge requests.

What is lost without git:

- **History.** The files hold no dates and no assignees, because git records who changed what, and when. Without git, nothing does.
- **Numbering across copies.** With no branches to count, `--next-id` can't see issues added in another copy of `pm/`. Add issues in one copy only, or two copies can take the same number.

### Move to a new version of pm-tree

- The pin is exact, never a range. A new version can add a rule that an existing `pm/` breaks. With a range, every repo's pipeline would start failing at once, on merge requests that never touched `pm/`.
- A repo moves to a new version when its pin is raised. The pin is raised in a merge request of its own, which also fixes what the new rules find.

## Commits and merge requests

- Nothing is pushed to `main` directly. Every change, to `pm/` as to code, reaches it through a merge request.
- The merge method is GitLab's merge commit with semi-linear history. So a branch is rebased onto `main` before it merges, and its pipeline validates `pm/` as `main` will hold it.
- Branches are named after their issues (see *Start an issue*).
- Every commit that touches an issue starts with its ID, such as `I-003: status doing → done` or `I-007: move to M2`. A commit that touches several issues starts with all their IDs: `I-004, I-005: move to M3`.
- A merge request's title starts with its issue IDs the same way, so `main` keeps them when the merge request is squashed.
- Run `pm-tree` before every commit that touches `pm/`.

## Naming

| What | Form | Examples |
|---|---|---|
| Milestone ID | `M<n>`: `M`, then a whole number from 1, with no leading zeros | `M1`, `M12` |
| Milestone folder | `M<n>-<slug>` | `M1-tenant-core` |
| Issue ID | `I-<nnn>`: `I`, a hyphen, then the issue number. Numbers run across the whole project, not per milestone. The number has at least three digits, is zero-padded below 100, and has no other leading zeros. | `I-003`, `I-042`, `I-1204` |
| Issue file | `<id>-<slug>.yaml` | `I-003-tenant-resolution.yaml` |
| Slug | lowercase kebab-case: words of `a-z` and `0-9` joined by single hyphens | `tenant-resolution` |
| Repo | a slug | `backend`, `web-app` |

The extension is always `.yaml`, never `.yml`.

An issue's folder is its milestone.

## config.yaml

`pm/config.yaml` is optional. Without it, the repos are `backend`, `frontend` and `mobile`, and `backend` is the home repo. Make it only when the project's repos are different. Its one key is required.

```yaml
repos:                     # at least one, each a slug, listed once
  - backend                # the home repo comes first
  - frontend
  - mobile
```

| Key | Value |
|---|---|
| `repos` | The project's repos, at least one. Each is a slug and is listed once. An issue's `repo` is one of them. The first is the home repo, which holds `pm/`. |

When a project gains a repo, add it to `repos` before an issue names it. Without `config.yaml`, first make it with all three default repos, then add the new one.

## milestone.yaml

Every key is required.

```yaml
id: M1
title: Tenant core
status: planned            # planned | active | done
spec: "Milestones, M1"     # where SPEC.md defines this milestone
```

| Key | Value |
|---|---|
| `id` | The milestone ID. It matches the folder. |
| `title` | A non-empty string. |
| `status` | `planned`, `active` or `done`. |
| `spec` | A non-empty string: where `SPEC.md` defines the milestone. |

A milestone's goal and gate criteria are written only in `SPEC.md`.

## Issue file

Every key is required. An empty value is `null` or `[]`, as shown.

```yaml
id: I-003
title: Tenant resolution from request domain
status: todo               # todo | doing | blocked | done | dropped | duplicate
priority: high             # high | medium | low
repo: backend              # a repo from config.yaml; without it, backend | frontend | mobile
spec: "section 4.2"        # string or null
context: >                 # non-empty
  Why this exists.
scope:
  in: [Resolve tenant from Host header]     # list, may be empty
  out: [Custom-domain TLS]                  # list, may be empty
acceptance:                # at least one item
  - text: Unknown domain returns 404
    done: false
links:                     # issue IDs only
  depends_on: [I-001]
  related: [I-012]
  duplicate_of: null       # issue ID or null
notes:                     # may be empty, except when blocked or dropped
  - date: "2026-10-02"     # quoted, valid YYYY-MM-DD
    text: Decision or blocker.
```

| Key | Value |
|---|---|
| `id` | The issue ID. It matches the file name. |
| `title` | A non-empty string. |
| `status` | `todo`, `doing`, `blocked`, `done`, `dropped` or `duplicate`. |
| `priority` | `high`, `medium` or `low`. |
| `repo` | The repo the issue's work is committed in: one that `config.yaml` lists, or, without it, `backend`, `frontend` or `mobile`. Work outside the code goes under the home repo, and so does every issue of a project with one repo. |
| `spec` | Where `SPEC.md` covers this issue, as a non-empty string, or `null`. |
| `context` | A non-empty string: why the issue exists. |
| `scope.in`, `scope.out` | Lists of non-empty strings: what the issue delivers, and what it leaves out. Either may be `[]`. |
| `acceptance` | At least one item. Each item has a non-empty `text` and `done`, which is `true` or `false`. |
| `links.depends_on` | Issues that must be done before this one can start. |
| `links.related` | Related issues, with no order between them. |
| `links.duplicate_of` | The issue this one repeats, or `null`. |
| `notes` | Decisions and blockers, each with a quoted `date` and a non-empty `text`. May be `[]`, except for a `blocked` or `dropped` issue, which needs a note that says why. |

## Rules

The validator checks every rule below. Each one is an error, except the three marked as warnings.

### Structure

- `pm/` contains only milestone folders, and `config.yaml` when the project has one.
- A milestone folder contains exactly one `milestone.yaml`, plus issue files, and nothing else.

### Parsing and types

- Files are UTF-8 YAML, loaded with a strict loader built on PyYAML's SafeLoader.
- Duplicate keys are rejected. (By default, PyYAML silently keeps the last one.)
- Unknown keys, missing keys and wrong types are rejected. A merge key (`<<`) counts as an unknown key.
- Booleans are the literals `true` and `false`. `yes`, `no`, `on`, `off`, `True` and `FALSE` are rejected, and so is a quoted `"true"`.
- Enum fields hold an exact string from their list, so `Done` is rejected.
- Dates are quoted strings that are real dates in the form `YYYY-MM-DD`. An unquoted date, `"2026-02-30"` and `"2026-1-5"` are all rejected.
- `title`, `context`, a milestone's `spec` and every `text` are non-empty strings, and so are an issue's `spec`, when it isn't `null`, and every `scope` item. A string of only spaces counts as empty.
- `acceptance` has at least one item.

### Config

- `config.yaml` has one key, `repos`: a list of at least one slug, with no slug listed twice.
- An issue's `repo` is one of the repos `config.yaml` lists. Without `config.yaml`, it is `backend`, `frontend` or `mobile`.
- While `config.yaml` has errors, an issue's `repo` is checked only as a non-empty string, so the error isn't repeated on every issue. Fix `config.yaml` first; errors about `repo` can appear once it passes.

### Identity

- An issue's file name is its `id`, a hyphen, a slug, and `.yaml`.
- The `id` in `milestone.yaml` matches its folder.
- Milestone IDs are unique across `pm/`, and so are issue IDs.
- IDs have the forms given under *Naming*.
- **Warning:** two titles that are the same once they are lowercased and stripped of punctuation and whitespace. Milestone titles are compared with milestone titles, and issue titles with issue titles. An issue and the issue it duplicates may share a title, because the duplicate link already records it.

### Links

- Every linked ID is an existing issue, and no issue links to itself.
- No list holds the same ID twice.
- Two issues share at most one relation: a dependency, related, or duplicate.
- A related link is written on one of its two issues, not on both.
- `depends_on` has no cycles.
- **Warning:** an open issue (`todo`, `doing` or `blocked`) depends on an issue in a later milestone, one with a higher number. Its own milestone can't be done until the later one has started, so one of the two issues is in the wrong milestone.
- `duplicate_of` is set if, and only if, the status is `duplicate`.
- The issue named in `duplicate_of` is not itself a duplicate.

### State

- `done` requires every acceptance item to be `done: true`.
- `doing` or `done` requires every `depends_on` issue to be `done`.
- An open issue doesn't depend on a `dropped` or `duplicate` issue.
- `blocked` or `dropped` requires at least one note, which says why.
- **Warning:** a note dated after tomorrow, by the clock of the machine that runs the validator. Tomorrow, not today, leaves room for a clock in another time zone.
- A milestone that is `planned` has no issue that is `doing` or `done`.
- A milestone that is `done` requires every issue in its folder to be `done`, `dropped` or `duplicate`.

## Common mistakes

The validator rejects each of these:

| Wrong | Right |
|---|---|
| `I-001-model.yml` | `I-001-model.yaml` |
| `date: 2026-10-02` | `date: "2026-10-02"` |
| `done: yes`, `done: True`, `done: "true"` | `done: true` |
| `status: Done`, `priority: High` | `status: done`, `priority: high` |
| `I-1`, `I-0042`, `M01` | `I-001`, `I-042`, `M1` |
| a related link written on both issues | on one of them |
| a key the format doesn't have, such as a goal, an assignee or a due date | the goal in `SPEC.md`, and the history in git |
| `config.yml`, or a `repo` that `config.yaml` doesn't list | `config.yaml`, listing every repo an issue names |
| `blocked` or `dropped` with no note | a note that says why |
| `done` with an acceptance item still `false` | every item `done: true` first |

The validator can't see these, so check them yourself:

| Wrong | Right |
|---|---|
| an issue numbered by hand | the ID `pm-tree --next-id` prints, after `git fetch` |
| a closed issue set back to `todo` or `doing` | a new issue, `related` to the old one |
| an acceptance item set to `done: true` before its outcome holds | `true` only once it holds |
| a milestone set to `done` before its gate criteria in `SPEC.md` are met | `done` only once they are |
| home repo files staged with `git add -A` from another repo | only your `pm/` files, staged by name |

## The package

As installed, in the folder `pm-tree --docs` prints:

```
pm_tree/
  README.md                # this guide
  validate.py              # the validator: Python 3.10+, needs only PyYAML (and git for --next-id in a git repo)
  templates/milestone.yaml
  templates/issue.yaml
  templates/config.yaml
  example/pm/              # a small valid tree that uses every field, status, repo and link type
```

The version is in the package's `pyproject.toml`, and the validator prints it first. pm-tree's maintainer sets it by hand.
