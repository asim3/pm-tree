#!/usr/bin/env python3
"""Check a pm/ folder against the pm-tree format.

    pm-tree [path] [--summary | --next-id | --guide | --docs]

README.md beside this file is the guide for the LLM that works in pm/: the format, every rule
and how to work. --guide prints it with the templates; --docs prints its folder.
Python 3.10+; the only runtime dependency is PyYAML, and --next-id also needs git.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from importlib.metadata import version
from pathlib import Path

import yaml
from yaml.constructor import ConstructorError

# The installed package's folder: this file, README.md, templates/ and example/.
PACKAGE_DIR = Path(__file__).resolve().parent

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
SLUG_RE = re.compile(SLUG)
MILESTONE_ID = r"M[1-9][0-9]*"
ISSUE_ID = r"I-(?:00[1-9]|0[1-9][0-9]|[1-9][0-9]{2,})"
MILESTONE_ID_RE = re.compile(MILESTONE_ID)
ISSUE_ID_RE = re.compile(ISSUE_ID)
MILESTONE_FOLDER_RE = re.compile(rf"({MILESTONE_ID})-{SLUG}")
ISSUE_FILE_RE = re.compile(rf"({ISSUE_ID})-{SLUG}\.yaml")
DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")

MILESTONE_STATUSES = ("planned", "active", "done")
ISSUE_STATUSES = ("todo", "doing", "blocked", "done", "dropped", "duplicate")
OPEN_STATUSES = ("todo", "doing", "blocked")
NEVER_DONE = ("dropped", "duplicate")  # closed without being done
CLOSED_STATUSES = ("done", *NEVER_DONE)
PRIORITIES = ("high", "medium", "low")
REPOS = ("backend", "frontend", "mobile")  # an issue's repo when pm/ has no config.yaml
CONFIG_FILE = "config.yaml"

# Each link key and the relation it records between two issues. A link is written on one of them.
RELATIONS = {
    "depends_on": "dependency",
    "related": "related",
    "duplicate_of": "duplicate",
}
RELATION_ORDER = ("dependency", "related", "duplicate")


# --- YAML loading ------------------------------------------------------------

BOOL_TAG = "tag:yaml.org,2002:bool"
MERGE_TAG = "tag:yaml.org,2002:merge"
TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"


@dataclass(frozen=True)
class UnquotedDate:
    """A plain scalar that YAML would read as a date, kept unparsed so the schema can reject it."""

    raw: str

    def __str__(self) -> str:
        return self.raw


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys and reads only true and false as booleans.

    yes/no/on/off stay strings, so the schema rejects them wherever a boolean is due. Merge keys
    (<<) stay plain keys, so the schema rejects them as unknown. Unquoted dates stay unparsed.
    """

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=True)
                try:
                    repeated = key in seen
                except TypeError:  # unhashable key; SafeLoader reports it below
                    continue
                if repeated:
                    raise ConstructorError(None, None, f"duplicate key {key}", key_node.start_mark)
                seen.add(key)
        return super().construct_mapping(node, deep=deep)

    def construct_bool(self, node):
        # Plain scalars arrive here only as true or false; anything else carried an explicit !!bool.
        if node.value not in ("true", "false"):
            raise ConstructorError(
                None, None, f"booleans must be true or false, not {node.value}", node.start_mark
            )
        return node.value == "true"

    def construct_unquoted_date(self, node):
        return UnquotedDate(node.value)


StrictLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag not in (BOOL_TAG, MERGE_TAG)]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
StrictLoader.add_implicit_resolver(BOOL_TAG, re.compile(r"^(?:true|false)$"), list("tf"))
StrictLoader.add_constructor(BOOL_TAG, StrictLoader.construct_bool)
StrictLoader.add_constructor(TIMESTAMP_TAG, StrictLoader.construct_unquoted_date)


def yaml_problem(err: yaml.YAMLError) -> str:
    """One line for a PyYAML error: what went wrong, and on which line."""
    if not isinstance(err, yaml.MarkedYAMLError):
        return str(err)
    text = " ".join(part for part in (err.context, err.problem) if part)
    mark = err.problem_mark or err.context_mark
    return f"{text} (line {mark.line + 1})" if mark else text


def load(path: Path, schema: Record) -> tuple[object, list[str]]:
    """Parse one file. Returns its content and its schema problems, or why it couldn't be read."""
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
    except UnicodeDecodeError:
        return None, ["the file is not UTF-8 text"]
    except yaml.YAMLError as err:
        return None, [f"invalid YAML: {yaml_problem(err)}"]
    return data, schema.check(data)


# --- Schema ------------------------------------------------------------------


def describe(value) -> str:
    """How a value that failed a check is shown in the message."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, UnquotedDate):
        return f"an unquoted date {value.raw}"
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, str) and len(value) > 40:
        value = value[:37] + "..."
    return repr(value)


class Leaf:
    """A scalar field. `want` says what it accepts, for the message."""

    want = ""

    def accepts(self, value) -> bool:
        raise NotImplementedError

    def check(self, value, where: str) -> list[str]:
        return [] if self.accepts(value) else [f"{where} must be {self.want}, got {describe(value)}"]


class Text(Leaf):
    want = "a non-empty string"

    def accepts(self, value):
        return isinstance(value, str) and bool(value.strip())


class OneOf(Leaf):
    def __init__(self, choices: tuple[str, ...]):
        self.choices = choices
        self.want = "one of " + ", ".join(choices)

    def accepts(self, value):
        return isinstance(value, str) and value in self.choices


class Flag(Leaf):
    want = "true or false"

    def accepts(self, value):
        return isinstance(value, bool)


class Ident(Leaf):
    def __init__(self, pattern: re.Pattern, want: str):
        self.pattern = pattern
        self.want = want

    def accepts(self, value):
        return isinstance(value, str) and self.pattern.fullmatch(value) is not None


class Date(Leaf):
    want = 'a real date, quoted, as "YYYY-MM-DD"'

    def accepts(self, value):
        match = DATE_RE.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            return False
        try:
            date(*(int(part) for part in match.groups()))
        except ValueError:
            return False
        return True


class Nullable(Leaf):
    def __init__(self, inner: Leaf):
        self.inner = inner
        self.want = f"{inner.want} or null"

    def accepts(self, value):
        return value is None or self.inner.accepts(value)


class ListOf:
    def __init__(self, item, at_least_one: bool = False, unique: bool = False):
        self.item = item
        self.at_least_one = at_least_one
        self.unique = unique

    def check(self, value, where: str) -> list[str]:
        if not isinstance(value, list):
            return [f"{where} must be a list, got {describe(value)}"]
        if self.at_least_one and not value:
            return [f"{where} must have at least one item"]
        problems = [p for n, item in enumerate(value) for p in self.item.check(item, f"{where}[{n}]")]
        if self.unique and not problems:
            repeated = sorted({item for item in value if value.count(item) > 1}, key=natural_key)
            problems += [f"{where} lists {item} more than once" for item in repeated]
        return problems


class Record:
    def __init__(self, fields: dict):
        self.fields = fields

    def check(self, value, where: str = "") -> list[str]:
        if not isinstance(value, dict):
            return [f"{where or 'the file'} must be a mapping, got {describe(value)}"]
        prefix = f"{where}." if where else ""
        problems = []
        for key, item in self.fields.items():
            if key in value:
                problems += item.check(value[key], prefix + key)
            else:
                problems.append(f"missing key {prefix}{key}")
        problems += [f"unknown key {prefix}{key}" for key in value if key not in self.fields]
        return problems


ISSUE_REF = Ident(ISSUE_ID_RE, "an issue ID like I-003")

MILESTONE_SCHEMA = Record({
    "id": Ident(MILESTONE_ID_RE, "a milestone ID like M1"),
    "title": Text(),
    "status": OneOf(MILESTONE_STATUSES),
    "spec": Text(),
})

CONFIG_SCHEMA = Record({
    "repos": ListOf(Ident(SLUG_RE, "a lowercase kebab-case slug, like backend"), at_least_one=True, unique=True),
})


def issue_schema(repo: Leaf) -> Record:
    """The issue schema, with the check for repo: the repos config.yaml lists, or REPOS without it."""
    return Record({
        "id": ISSUE_REF,
        "title": Text(),
        "status": OneOf(ISSUE_STATUSES),
        "priority": OneOf(PRIORITIES),
        "repo": repo,
        "spec": Nullable(Text()),
        "context": Text(),
        "scope": Record({"in": ListOf(Text()), "out": ListOf(Text())}),
        "acceptance": ListOf(Record({"text": Text(), "done": Flag()}), at_least_one=True),
        "links": Record({
            "depends_on": ListOf(ISSUE_REF, unique=True),
            "related": ListOf(ISSUE_REF, unique=True),
            "duplicate_of": Nullable(ISSUE_REF),
        }),
        "notes": ListOf(Record({"date": Date(), "text": Text()})),
    })


ISSUE_SCHEMA = issue_schema(OneOf(REPOS))  # for a pm/ with no config.yaml


# --- The tree ----------------------------------------------------------------


def milestone_number(milestone_id: str) -> int:
    return int(milestone_id[1:])


def natural_key(text) -> list:
    """Sort key that orders the numbers inside a string by value: M2 before M10."""
    return [int(part) if n % 2 else part for n, part in enumerate(re.split(r"(\d+)", str(text)))]


def normalise(title: str) -> str:
    """A title lowercased, with punctuation and whitespace stripped, for collision checks."""
    return "".join(char for char in title.casefold() if char.isalnum())


def declared_id(data, pattern: re.Pattern) -> str | None:
    """The file's own id, when it has one of the right form."""
    value = data.get("id") if isinstance(data, dict) else None
    return value if isinstance(value, str) and pattern.fullmatch(value) else None


def links_phrase(key: str, target: str) -> str:
    return f"links.{key} {'is' if key == 'duplicate_of' else 'lists'} {target}"


def joined(items: list[str]) -> str:
    """The items, comma-separated, with the verb that agrees with them."""
    return ", ".join(items) + (" is" if len(items) == 1 else " are")


@dataclass(frozen=True)
class Finding:
    severity: str  # ERROR or WARNING
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity} {self.path}: {self.message}"


@dataclass
class Issue:
    path: str
    milestone: str  # the ID of the milestone folder it is in
    data: dict  # passed the schema

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def title(self) -> str:
        return " ".join(self.data["title"].split())

    def links(self, key: str) -> list[str]:
        value = self.data["links"][key]
        if key == "duplicate_of":
            return [] if value is None else [value]
        return value

    def is_duplicate_pair(self, other: Issue) -> bool:
        return other.id in self.links("duplicate_of") or self.id in other.links("duplicate_of")


@dataclass
class Milestone:
    id: str  # from the folder name
    folder: str
    path: str | None = None  # its milestone.yaml, once found
    data: dict | None = None  # set only when milestone.yaml passed the schema
    issues: list[Issue] = field(default_factory=list)  # the folder's issue files that passed the schema


class Validator:
    """Checks one pm/ tree.

    Each file is checked on its own as it is read. The checks across files then run only on the
    issues that passed the schema and whose ID no other file claims, so one broken file doesn't
    set off errors in every file that links to it. config.yaml is read first, since it sets the
    repos an issue may name.
    """

    def __init__(self, root: Path, today: date | None = None):
        self.root = root
        self.today = today or date.today()  # for notes dated in the future
        self.findings: list[Finding] = []
        self.milestones: list[Milestone] = []
        self.issues: dict[str, Issue] = {}  # schema-valid, uniquely claimed issues by ID
        self.claims: dict[str, list[str]] = defaultdict(list)  # issue ID -> files claiming it
        self.issue_schema = ISSUE_SCHEMA  # until config.yaml names other repos

    def error(self, path: Path | str, message: str) -> None:
        self.findings.append(Finding("ERROR", Path(path).as_posix(), message))

    def warning(self, path: Path | str, message: str) -> None:
        self.findings.append(Finding("WARNING", Path(path).as_posix(), message))

    def run(self) -> Validator:
        if not self.root.is_dir():
            self.error(self.root, "is not a folder" if self.root.exists() else "does not exist")
            return self
        self.read_tree()
        self.check_links()
        self.check_relations()
        self.check_cycles()
        self.check_states()
        self.check_order()
        self.check_titles()
        self.findings.sort(key=lambda f: (natural_key(f.path), f.severity != "ERROR"))
        return self

    # Reading, with the checks on single files

    def read_tree(self) -> None:
        self.read_config()
        folders: dict[str, list[str]] = defaultdict(list)
        for entry in sorted(self.root.iterdir(), key=lambda p: natural_key(p.name)):
            match = MILESTONE_FOLDER_RE.fullmatch(entry.name)
            if entry.name == CONFIG_FILE and entry.is_file():
                continue
            if entry.name == "config.yml":
                self.error(entry, "the extension must be .yaml")
            elif not entry.is_dir():
                self.error(entry, f"only milestone folders and {CONFIG_FILE} belong here, not other files")
            elif match is None:
                self.error(entry, "a milestone folder is named M<n>-<slug>, e.g. M1-tenant-core")
            else:
                milestone = Milestone(match.group(1), entry.as_posix())
                self.read_milestone(entry, milestone)
                self.milestones.append(milestone)
                folders[milestone.id].append(milestone.folder)
        self.check_unique("milestone", folders)
        self.check_unique("issue", self.claims)
        for milestone in self.milestones:
            for issue in milestone.issues:
                if len(self.claims[issue.id]) == 1:
                    self.issues[issue.id] = issue

    def read_config(self) -> None:
        path = self.root / CONFIG_FILE
        if not path.is_file():
            return
        data, problems = load(path, CONFIG_SCHEMA)
        for problem in problems:
            self.error(path, problem)
        # Until config.yaml is fixed, repo is checked only as a string, so its error isn't repeated on every issue.
        self.issue_schema = issue_schema(Text() if problems else OneOf(tuple(data["repos"])))

    def read_milestone(self, folder: Path, milestone: Milestone) -> None:
        for entry in sorted(folder.iterdir(), key=lambda p: natural_key(p.name)):
            if entry.is_dir():
                self.error(entry, "a milestone folder holds only milestone.yaml and issue files, not folders")
            elif entry.name == "milestone.yaml":
                milestone.path = entry.as_posix()
                data, problems = load(entry, MILESTONE_SCHEMA)
                declared = declared_id(data, MILESTONE_ID_RE)
                if declared and declared != milestone.id:
                    self.error(entry, f"id {declared} does not match its folder {folder.name}")
                for problem in problems:
                    self.error(entry, problem)
                if not problems:
                    milestone.data = data
            elif entry.suffix == ".yaml":
                self.read_issue(entry, milestone)
            elif entry.suffix.lower() in (".yaml", ".yml"):
                self.error(entry, "the extension must be .yaml")
            else:
                self.error(entry, "a milestone folder holds only milestone.yaml and issue files")
        if milestone.path is None:
            self.error(folder, "milestone.yaml is missing")

    def read_issue(self, path: Path, milestone: Milestone) -> None:
        data, problems = load(path, self.issue_schema)
        declared = declared_id(data, ISSUE_ID_RE)
        name = ISSUE_FILE_RE.fullmatch(path.name)
        named = name.group(1) if name else None
        if declared and named != declared:
            self.error(path, f"the file name must be {declared}-<slug>.yaml, with a lowercase kebab-case slug")
        elif not declared and not named:
            self.error(path, "the file name must be <id>-<slug>.yaml, e.g. I-003-tenant-resolution.yaml")
        for problem in problems:
            self.error(path, problem)
        if declared or named:
            self.claims[declared or named].append(path.as_posix())
        if not problems:
            issue = Issue(path.as_posix(), milestone.id, data)
            milestone.issues.append(issue)
            self.check_issue(issue)

    def check_unique(self, kind: str, claims: dict[str, list[str]]) -> None:
        for claimed_id, paths in claims.items():
            for path in paths:
                others = [other for other in paths if other != path]
                if others:
                    self.error(path, f"{kind} ID {claimed_id} is also used by {', '.join(others)}")

    def check_issue(self, issue: Issue) -> None:
        for key in RELATIONS:
            if issue.id in issue.links(key):
                self.error(issue.path, links_phrase(key, "the issue itself"))
        duplicate_of = issue.data["links"]["duplicate_of"]
        if issue.status == "duplicate" and duplicate_of is None:
            self.error(issue.path, "status is duplicate, so links.duplicate_of must name the original issue")
        elif issue.status != "duplicate" and duplicate_of is not None:
            self.error(issue.path, f"links.duplicate_of is set, so status must be duplicate, not {issue.status}")
        if issue.status == "done":
            open_items = [f"acceptance[{n}]" for n, item in enumerate(issue.data["acceptance"]) if not item["done"]]
            if open_items:
                self.error(issue.path, f"status is done, but {joined(open_items)} not done")
        if issue.status in ("blocked", "dropped") and not issue.data["notes"]:
            self.error(issue.path, f"status is {issue.status}, so notes must say why")
        # Tomorrow, not today, leaves room for a clock in another time zone.
        tomorrow = self.today + timedelta(days=1)
        for n, note in enumerate(issue.data["notes"]):
            if date.fromisoformat(note["date"]) > tomorrow:
                self.warning(issue.path, f"notes[{n}].date {note['date']} is in the future")

    # Checks across files

    def check_links(self) -> None:
        for issue in self.issues.values():
            for key in RELATIONS:
                for target_id in issue.links(key):
                    # A link to the issue itself is reported by check_issue. A link to a file that failed its
                    # own checks is left out until that file is fixed.
                    if target_id != issue.id and target_id not in self.claims:
                        self.error(issue.path, f"{links_phrase(key, target_id)}, which does not exist")

    def check_relations(self) -> None:
        found: dict[frozenset, list[str]] = defaultdict(list)
        for issue in self.issues.values():
            for key in RELATIONS:
                for target_id in issue.links(key):
                    if target_id != issue.id and target_id in self.issues:
                        found[frozenset((issue.id, target_id))].append(RELATIONS[key])
        for pair, relations in found.items():
            first, second = sorted((self.issues[i] for i in pair), key=lambda i: natural_key(i.path))
            if len(set(relations)) > 1:
                names = ", ".join(r for r in RELATION_ORDER if r in relations)
                self.error(
                    first.path,
                    f"{first.id} and {second.id} ({second.path}) share more than one relation ({names}); keep one",
                )
            elif relations == ["related", "related"]:
                self.error(
                    first.path,
                    f"{first.id} and {second.id} ({second.path}) list each other in links.related; "
                    "keep the link on one of them",
                )

    def check_cycles(self) -> None:
        graph = {
            issue_id: [dep for dep in issue.links("depends_on") if dep in self.issues and dep != issue_id]
            for issue_id, issue in self.issues.items()
        }
        for cycle in find_cycles(graph):
            self.error(self.issues[cycle[0]].path, "depends_on cycle: " + " -> ".join(cycle + [cycle[0]]))

    def check_states(self) -> None:
        for issue in self.issues.values():
            for dep_id in issue.links("depends_on"):
                dep = self.issues.get(dep_id)
                if dep is None or dep is issue:
                    continue
                if issue.status in OPEN_STATUSES and dep.status == "dropped":
                    self.error(issue.path, f"depends_on {dep_id}, which is dropped ({dep.path}); remove the link")
                elif issue.status in OPEN_STATUSES and dep.status == "duplicate":
                    original = dep.data["links"]["duplicate_of"]
                    self.error(
                        issue.path,
                        f"depends_on {dep_id}, which is a duplicate of {original} ({dep.path}); "
                        f"depend on {original} instead",
                    )
                elif issue.status in ("doing", "done") and dep.status != "done":
                    self.error(issue.path, f"status is {issue.status}, but depends_on {dep_id} is {dep.status}")
            original = self.issues.get(issue.data["links"]["duplicate_of"])
            if original is not None and original is not issue and original.status == "duplicate":
                self.error(
                    issue.path,
                    f"links.duplicate_of is {original.id}, which is itself a duplicate ({original.path}); "
                    "point to the original issue",
                )
        for milestone in self.milestones:
            status = milestone.data["status"] if milestone.data is not None else None
            if status == "planned":
                started = [f"{i.id} ({i.status})" for i in milestone.issues if i.status in ("doing", "done")]
                if started:
                    self.error(milestone.path, f"status is planned, but work has started on {', '.join(started)}")
            elif status == "done":
                still_open = [f"{i.id} ({i.status})" for i in milestone.issues if i.status not in CLOSED_STATUSES]
                if still_open:
                    self.error(milestone.path, f"status is done, but {joined(still_open)} still open")

    def check_order(self) -> None:
        for issue in self.issues.values():
            if issue.status not in OPEN_STATUSES:
                continue
            for dep_id in issue.links("depends_on"):
                dep = self.issues.get(dep_id)
                if (
                    dep is not None
                    and dep.status not in NEVER_DONE
                    and milestone_number(dep.milestone) > milestone_number(issue.milestone)
                ):
                    self.warning(
                        issue.path,
                        f"depends_on {dep_id} ({dep.path}), which is in a later milestone, {dep.milestone}; "
                        "an issue waits only on its own milestone or an earlier one",
                    )

    def check_titles(self) -> None:
        milestones = [m for m in self.milestones if m.data is not None]
        for milestone, others in collisions(milestones, lambda m: m.data["title"]):
            names = ", ".join(f"milestone {o.id} ({o.path})" for o in others)
            self.warning(milestone.path, f"title is the same as {names}, ignoring case, spaces and punctuation")
        issues = [issue for milestone in self.milestones for issue in milestone.issues]
        for issue, others in collisions(issues, lambda i: i.data["title"], Issue.is_duplicate_pair):
            names = ", ".join(f"{o.id} ({o.path})" for o in others)
            self.warning(issue.path, f"title is the same as {names}, ignoring case, spaces and punctuation")


def collisions(items: list, title_of, exempt=lambda a, b: False):
    """Yield each item whose normalised title other items share, with those others."""
    groups = defaultdict(list)
    for item in items:
        groups[normalise(title_of(item))].append(item)
    for item in items:
        others = [o for o in groups[normalise(title_of(item))] if o is not item and not exempt(item, o)]
        if others:
            yield item, others


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """One cycle for each back edge a depth-first search meets, each starting at its lowest ID."""
    state: dict[str, str] = {}  # "open" while on the current path, "done" once explored
    cycles = []
    for start in sorted(graph, key=natural_key):
        if start in state:
            continue
        path, pending = [start], [iter(graph[start])]
        state[start] = "open"
        while pending:
            nxt = next(pending[-1], None)
            if nxt is None:
                state[path.pop()] = "done"
                pending.pop()
            elif state.get(nxt) == "open":
                cycle = path[path.index(nxt):]
                low = cycle.index(min(cycle, key=natural_key))
                cycles.append(cycle[low:] + cycle[:low])
            elif nxt not in state:
                state[nxt] = "open"
                path.append(nxt)
                pending.append(iter(graph[nxt]))
    return cycles


def validate(root: Path, today: date | None = None) -> Validator:
    return Validator(root, today).run()


# --- The next issue ID ---------------------------------------------------------


class NextIdError(Exception):
    """Why the issue numbers on the branches couldn't be read."""


def git(folder: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise NextIdError("--next-id needs git, which is not installed") from None
    if result.returncode:
        message = result.stderr.strip().splitlines() or [f"exit code {result.returncode}"]
        raise NextIdError(f"git {args[0]} failed: {message[0]}")
    return result.stdout


def next_issue_id(root: Path) -> str:
    """One above the highest issue number in root, and in the same folder on every local and remote branch."""
    if not root.is_dir():
        raise NextIdError("is not a folder" if root.exists() else "does not exist")
    names = [path.relative_to(root).as_posix() for path in root.glob("*/*.yaml")]
    for ref in git(root, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").split():
        # Run inside root, ls-tree lists only root's part of the branch, with paths relative to it.
        names += git(root, "ls-tree", "-r", "--name-only", ref).splitlines()
    numbers = []
    for name in names:
        folder, _, file = name.partition("/")
        match = ISSUE_FILE_RE.fullmatch(file)
        if match and MILESTONE_FOLDER_RE.fullmatch(folder):
            numbers.append(int(match.group(1)[2:]))
    return f"I-{max(numbers, default=0) + 1:03d}"


# --- CLI ---------------------------------------------------------------------


def summary(result: Validator) -> list[str]:
    """Per milestone: its status, issue counts by status, the open issues that are waiting, and, in an
    active milestone, the issues ready to start."""
    if not result.milestones:
        return ["no milestones"]
    lines = []
    for milestone in result.milestones:
        title = " ".join(milestone.data["title"].split())
        status = milestone.data["status"]
        lines.append(f"{milestone.id} {title}: {status}")
        counts = Counter(issue.status for issue in milestone.issues)
        breakdown = ", ".join(f"{counts[status]} {status}" for status in ISSUE_STATUSES if counts[status])
        lines.append(f"  issues: {len(milestone.issues)}" + (f" ({breakdown})" if breakdown else ""))
        waiting, ready = [], []
        for issue in milestone.issues:
            if issue.status in CLOSED_STATUSES:
                continue
            waits_on = [dep for dep in issue.links("depends_on") if result.issues[dep].status != "done"]
            if issue.status == "blocked" or waits_on:
                on = f" waits on {', '.join(waits_on)}" if waits_on else ""
                waiting.append(f"    {issue.id} ({issue.status}){on}: {issue.title}")
                if issue.status == "blocked":
                    # The latest note says why; of two on the same day, the one written last.
                    note = max(reversed(issue.data["notes"]), key=lambda note: note["date"])
                    waiting.append(f"      {note['date']}: {' '.join(note['text'].split())}")
            elif issue.status == "todo":
                ready.append(issue)
        lines.append("  waiting:" + ("" if waiting else " none"))
        lines += waiting
        if status == "active":
            ready.sort(key=lambda issue: (PRIORITIES.index(issue.data["priority"]), natural_key(issue.id)))
            lines.append("  ready:" + ("" if ready else " none"))
            lines += [f"    {issue.id} ({issue.data['priority']}): {issue.title}" for issue in ready]
    return lines


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


TEMPLATE_NAMES = ("milestone.yaml", "issue.yaml", "config.yaml")

HELP_EPILOG = """\
For an LLM: run `pm-tree --guide` and read all of it before you create, change
or close anything in pm/. It holds the format, every rule, how to work in pm/,
and the templates, for the version installed here.

In a session:
  git fetch
  pm-tree --summary     each milestone's state: what waits, and what is ready
  pm-tree --next-id     the ID a new issue takes
  pm-tree               before every commit that touches pm/

Output: the version, then one line per finding, as "ERROR <path>: <message>"
or "WARNING <path>: <message>", then the counts. The exit code is 1 on any
error and 0 otherwise, so warnings alone exit 0.
"""


def guide() -> str:
    """The guide for the LLM that works in pm/: README.md, then the templates."""
    parts = [(PACKAGE_DIR / "README.md").read_text(encoding="utf-8").rstrip("\n"), "", "## Templates"]
    for name in TEMPLATE_NAMES:
        template = (PACKAGE_DIR / "templates" / name).read_text(encoding="utf-8").rstrip("\n")
        parts += ["", f"### templates/{name}", "", "```yaml", template, "```"]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pm-tree",
        description="Check a pm/ folder, a project's milestones and issues, against the pm-tree format.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="pm",
        help="the pm/ folder (default: pm in the current folder); from another repo, the home repo's pm/",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--summary",
        action="store_true",
        help="validate, then, with no errors, print each milestone's status and issue counts, the issues that wait "
        "and what they wait on, and an active milestone's ready issues",
    )
    mode.add_argument(
        "--next-id",
        action="store_true",
        help="print the ID a new issue takes, counting the issues on every local and remote branch; run git fetch "
        "first (needs git; doesn't validate)",
    )
    mode.add_argument(
        "--guide",
        action="store_true",
        help="print the guide for LLMs, then the templates: the format, every rule, and how to work in pm/ "
        "(doesn't validate)",
    )
    mode.add_argument(
        "--docs",
        action="store_true",
        help="print the folder that holds this version's README.md (the guide), templates/ and example/ "
        "(doesn't validate)",
    )
    args = parser.parse_args(argv)

    print(f"pm-tree {version('pm-tree')}")
    if args.guide:
        print(guide())
        return 0
    if args.docs:
        print(PACKAGE_DIR)
        return 0
    if args.next_id:
        try:
            print(next_issue_id(Path(args.path)))
        except NextIdError as err:
            print(Finding("ERROR", Path(args.path).as_posix(), str(err)))
            return 1
        return 0
    result = validate(Path(args.path))
    for finding in result.findings:
        print(finding)
    errors = sum(finding.severity == "ERROR" for finding in result.findings)
    print(f"{plural(errors, 'error')}, {plural(len(result.findings) - errors, 'warning')}")
    if errors:
        return 1
    if args.summary:
        print()
        print("\n".join(summary(result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
