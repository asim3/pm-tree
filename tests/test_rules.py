"""Every validator rule, each with at least one passing and one failing fixture.

A fixture is a change applied to pmtree.base_tree(). A passing fixture must produce no finding
at all. A failing fixture lists every finding it must produce, as (path under pm/, message
fragment), so a fixture that sets off unrelated findings fails too.
"""

from dataclasses import dataclass, field
from typing import Callable

import pytest

from pmtree import (
    FOLDER, M1, I1, I2, I3, I4, M2, I5, I6, I7,
    base_tree, doc, dump, issue, milestone, pop, put,
)

DROPPED = {"status": "dropped", "notes": [{"date": "2026-10-03", "text": "Not needed."}]}


@dataclass
class Case:
    change: Callable
    expected: list = field(default_factory=list)
    severity: str = "ERROR"


def chain(*changes):
    def apply(tree):
        for change in changes:
            change(tree)
    return apply


def ok(*changes):
    return Case(chain(*changes))


def bad(change, *expected, severity="ERROR"):
    return Case(change, list(expected), severity)


def add(path, content):
    return lambda tree: put(tree, path, content)


def remove(path):
    return lambda tree: pop(tree, path)


def move(old, new):
    return lambda tree: put(tree, new, pop(tree, old))


def rename_folder(old, new):
    return lambda tree: tree.update({new: tree.pop(old)})


def set_fields(path, **values):
    return lambda tree: doc(tree, path).update(values)


def set_links(path, **values):
    return lambda tree: doc(tree, path)["links"].update(values)


def edit(path, change):
    return lambda tree: change(doc(tree, path))


def replace(path, old, new):
    """Edit a document as text, for what a dict can't express: duplicate keys, unquoted dates."""
    def apply(tree):
        text = dump(doc(tree, path))
        assert old in text, f"{old!r} not in {path}"
        put(tree, path, text.replace(old, new, 1))
    return apply


def cycle_of(*ids):
    """Issues in M2 where each depends on the next and the last on the first."""
    def apply(tree):
        for n, issue_id in enumerate(ids):
            path = f"M2-later/{issue_id}-{'abcdefgh'[n]}.yaml"
            put(tree, path, issue(issue_id, f"Step {n}", depends_on=[ids[(n + 1) % len(ids)]]))
    return apply


ISSUE_STATUS_LIST = "todo, doing, blocked, done, dropped, duplicate"

RULES = {
    # Structure
    "pm-holds-only-milestone-folders": [
        ok(),
        bad(lambda tree: tree.update({"README.md": "notes\n"}), ("README.md", "only milestone folders belong here")),
        bad(lambda tree: tree.update({"notes": {}}), ("notes", "a milestone folder is named M<n>-<slug>")),
    ],
    "milestone-folder-name": [
        ok(rename_folder("M2-later", "M2-later-in-2027")),
        ok(lambda tree: tree.update({"M10-far": {"milestone.yaml": milestone("M10", "Far")}})),
        *[
            bad(rename_folder("M2-later", name), (name, "a milestone folder is named M<n>-<slug>"))
            for name in ("m2-later", "M02-later", "M0-later", "M2", "M2-Later", "M2_later", "M2--later")
        ],
    ],
    "milestone-folder-has-milestone-yaml": [
        ok(),
        bad(remove(M2), ("M2-later", "milestone.yaml is missing")),
    ],
    "milestone-folder-holds-only-milestone-yaml-and-issues": [
        ok(add(I5, issue("I-005", "First"))),
        bad(add("M2-later/notes.md", "notes\n"), ("M2-later/notes.md", "holds only milestone.yaml and issue files")),
        bad(add("M2-later/drafts", FOLDER), ("M2-later/drafts", "not folders")),
        bad(add("M2-later/I-005-first.yml", dump(issue("I-005", "First"))),
            ("M2-later/I-005-first.yml", "the extension must be .yaml")),
    ],
    # Parsing and types
    "files-are-valid-yaml": [
        ok(),
        bad(add(I5, "id: [I-005\n"), (I5, "invalid YAML")),
        bad(add(I5, "title: caf\xe9\n".encode("latin-1")), (I5, "not UTF-8")),
    ],
    "no-duplicate-keys": [
        ok(),  # text and done repeat across the items of a list, which is not a duplicate
        bad(replace(M2, "status: planned", "status: planned\nstatus: done"), (M2, "duplicate key status")),
        bad(replace(I3, "  done: false", "  done: false\n  done: true"), (I3, "duplicate key done")),
    ],
    "no-unknown-keys": [
        ok(),
        bad(set_fields(M2, owner="someone"), (M2, "unknown key owner")),
        bad(set_fields(M2, goal="What M2 delivers."), (M2, "unknown key goal")),
        bad(set_links(I3, blocks=["I-004"]), (I3, "unknown key links.blocks")),
        bad(set_fields(I3, created="2026-10-01"), (I3, "unknown key created")),
        bad(edit(I3, lambda d: d["acceptance"][0].update(by="someone")), (I3, "unknown key acceptance[0].by")),
        bad(edit(I3, lambda d: d["links"].update(parent="I-001")), (I3, "unknown key links.parent")),
        bad(replace(M2, "status: planned", "status: planned\n<<: {title: Merged.}"), (M2, "unknown key <<")),
    ],
    "no-missing-keys": [
        ok(),
        bad(edit(M2, lambda d: d.pop("spec")), (M2, "missing key spec")),
        bad(edit(I3, lambda d: d.pop("notes")), (I3, "missing key notes")),
        bad(edit(I3, lambda d: d["scope"].pop("out")), (I3, "missing key scope.out")),
        bad(edit(I3, lambda d: d["links"].pop("related")), (I3, "missing key links.related")),
        bad(edit(I3, lambda d: d["acceptance"][0].pop("done")), (I3, "missing key acceptance[0].done")),
    ],
    "types-are-exact": [
        ok(set_fields(I3, spec="section 4.2")),
        bad(edit(I3, lambda d: d["scope"].update({"in": None})), (I3, "scope.in must be a list, got null")),
        bad(set_fields(I3, title=["Export"]), (I3, "title must be a non-empty string, got a list")),
        bad(set_fields(I3, spec=4.2), (I3, "spec must be a non-empty string or null, got 4.2")),
        bad(set_fields(I3, links=[]), (I3, "links must be a mapping, got a list")),
        bad(set_fields(I3, notes=None), (I3, "notes must be a list, got null")),
        bad(add(I5, "- just\n- a list\n"), (I5, "the file must be a mapping, got a list")),
        bad(add(I5, ""), (I5, "the file must be a mapping, got null")),
    ],
    "booleans-are-true-or-false": [
        ok(edit(I3, lambda d: d["acceptance"][0].update(done=True))),
        *[
            bad(replace(I3, "done: false", f"done: {word}"),
                (I3, f"acceptance[0].done must be true or false, got '{word}'"))
            for word in ("yes", "no", "on", "off", "True", "FALSE")
        ],
        bad(set_fields(I3, acceptance=[{"text": "Shipped", "done": "true"}]),
            (I3, "acceptance[0].done must be true or false, got 'true'")),
    ],
    "enums-are-exact": [
        ok(add(I5, issue("I-005", "First", status="blocked", priority="low", repo="mobile", notes=[("2026-10-03", "Waiting on a provider.")])),
           set_fields(M2, status="active")),
        bad(set_fields(I3, status="Todo"), (I3, f"status must be one of {ISSUE_STATUS_LIST}, got 'Todo'")),
        bad(set_fields(I3, status="in-progress"), (I3, f"status must be one of {ISSUE_STATUS_LIST}")),
        bad(set_fields(I3, priority="urgent"), (I3, "priority must be one of high, medium, low, got 'urgent'")),
        bad(set_fields(I3, repo="Backend"), (I3, "repo must be one of backend, frontend, mobile, got 'Backend'")),
        bad(set_fields(I3, repo="web-backend"), (I3, "repo must be one of backend, frontend, mobile")),
        bad(set_fields(M2, status="Active"), (M2, "status must be one of planned, active, done, got 'Active'")),
    ],
    "dates-are-quoted-real-dates": [
        ok(),
        ok(edit(I2, lambda d: d["notes"].append({"date": "2028-02-29", "text": "Leap day."}))),
        bad(replace(I2, "'2026-10-02'", "2026-10-02"),
            (I2, 'notes[0].date must be a real date, quoted, as "YYYY-MM-DD", got an unquoted date 2026-10-02')),
        *[
            bad(edit(I2, lambda d, day=day: d["notes"][0].update(date=day)),
                (I2, f"notes[0].date must be a real date, quoted, as \"YYYY-MM-DD\", got '{day}'"))
            for day in ("2026-02-30", "2026-13-01", "2026-1-5", "02/11/2026", "2026-10-02T10:00", "")
        ],
    ],
    "strings-are-not-empty": [
        ok(),
        bad(set_fields(I3, title=""), (I3, "title must be a non-empty string, got ''")),
        bad(set_fields(M2, title="   "), (M2, "title must be a non-empty string, got '   '")),
        bad(set_fields(M2, spec=" \n"), (M2, "spec must be a non-empty string")),
        bad(set_fields(I3, context=""), (I3, "context must be a non-empty string")),
        bad(edit(I3, lambda d: d["acceptance"][0].update(text="")), (I3, "acceptance[0].text must be a non-empty")),
        bad(edit(I2, lambda d: d["notes"][0].update(text="")), (I2, "notes[0].text must be a non-empty")),
        bad(set_fields(I3, spec=""), (I3, "spec must be a non-empty string or null, got ''")),
        bad(edit(I2, lambda d: d["scope"]["in"].append("")), (I2, "scope.in[1] must be a non-empty string")),
    ],
    "acceptance-has-an-item": [
        ok(),
        bad(set_fields(I3, acceptance=[]), (I3, "acceptance must have at least one item")),
    ],
    # Identity
    "ids-have-the-right-form": [
        ok(add("M2-later/I-010-tenth.yaml", issue("I-010", "Tenth")),
           add("M2-later/I-100-hundredth.yaml", issue("I-100", "Hundredth")),
           add("M2-later/I-1000-thousandth.yaml", issue("I-1000", "Thousandth"))),
        *[
            bad(add(f"M2-later/{bad_id}-first.yaml", issue(bad_id, "First")),
                (f"M2-later/{bad_id}-first.yaml", f"id must be an issue ID like I-003, got '{bad_id}'"),
                (f"M2-later/{bad_id}-first.yaml", "the file name must be <id>-<slug>.yaml"))
            for bad_id in ("I-1", "I-01", "I-0042", "I-000", "i-001", "M2-01")
        ],
        bad(set_fields(M2, id="M02"), (M2, "id must be a milestone ID like M1, got 'M02'")),
    ],
    "file-name-is-id-and-slug": [
        ok(move(I3, "M1-core/I-003-export-2027.yaml")),
        bad(move(I3, "M1-core/I-008-export.yaml"),
            ("M1-core/I-008-export.yaml", "the file name must be I-003-<slug>.yaml")),
        bad(move(I3, "M1-core/I-003.yaml"), ("M1-core/I-003.yaml", "the file name must be I-003-<slug>.yaml")),
        bad(move(I3, "M1-core/I-003-Export_Now.yaml"),
            ("M1-core/I-003-Export_Now.yaml", "the file name must be I-003-<slug>.yaml")),
    ],
    "milestone-id-matches-folder": [
        ok(),
        bad(set_fields(M2, id="M3"), (M2, "id M3 does not match its folder M2-later")),
    ],
    "milestone-ids-are-unique": [
        ok(lambda tree: tree.update({"M3-more": {"milestone.yaml": milestone("M3", "More")}})),
        bad(lambda tree: tree.update({"M2-again": {"milestone.yaml": milestone("M2", "Again")}}),
            ("M2-again", "milestone ID M2 is also used by pm/M2-later"),
            ("M2-later", "milestone ID M2 is also used by pm/M2-again")),
    ],
    "issue-ids-are-unique": [
        ok(),
        ok(move(I3, "M2-later/I-003-export.yaml")),  # an issue moves to another milestone with its ID
        bad(add("M2-later/I-003-copy.yaml", issue("I-003", "Export copy")),
            (I3, "issue ID I-003 is also used by pm/M2-later/I-003-copy.yaml"),
            ("M2-later/I-003-copy.yaml", "issue ID I-003 is also used by pm/M1-core/I-003-export.yaml")),
        bad(add("M1-core/I-003-copy.yaml", issue("I-003", "Export copy")),
            (I3, "issue ID I-003 is also used by pm/M1-core/I-003-copy.yaml"),
            ("M1-core/I-003-copy.yaml", "issue ID I-003 is also used by pm/M1-core/I-003-export.yaml")),
        bad(add("M1-core/I-003-broken.yaml", "id: [\n"),
            (I3, "issue ID I-003 is also used by pm/M1-core/I-003-broken.yaml"),
            ("M1-core/I-003-broken.yaml", "issue ID I-003 is also used by pm/M1-core/I-003-export.yaml"),
            ("M1-core/I-003-broken.yaml", "invalid YAML")),
    ],
    "colliding-titles-warn": [
        ok(),
        ok(set_fields(I4, title="EXPORT!")),  # a duplicate may repeat the title of its original
        bad(add(I5, issue("I-005", "lead-FORM!")),
            (I2, "title is the same as I-005 (pm/M2-later/I-005-first.yaml)"),
            (I5, "title is the same as I-002 (pm/M1-core/I-002-form.yaml)"),
            severity="WARNING"),
        bad(set_fields(M2, title=" core. "),
            (M1, "title is the same as milestone M2 (pm/M2-later/milestone.yaml)"),
            (M2, "title is the same as milestone M1 (pm/M1-core/milestone.yaml)"),
            severity="WARNING"),
    ],
    # Links
    "links-hold-issue-ids": [
        ok(),
        bad(add(I5, issue("I-005", "First", depends_on=["M1-01"])),
            (I5, "links.depends_on[0] must be an issue ID like I-003, got 'M1-01'")),
        bad(add(I5, issue("I-005", "First", status="duplicate", duplicate_of=7)),
            (I5, "links.duplicate_of must be an issue ID like I-003 or null, got 7")),
    ],
    "linked-issues-exist": [
        ok(),
        bad(add(I5, issue("I-005", "First", related=["I-999"])),
            (I5, "links.related lists I-999, which does not exist")),
        bad(add(I5, issue("I-005", "First", status="duplicate", duplicate_of="I-999")),
            (I5, "links.duplicate_of is I-999, which does not exist")),
    ],
    "no-issue-links-to-itself": [
        ok(),
        bad(add(I5, issue("I-005", "First", related=["I-005"])), (I5, "links.related lists the issue itself")),
        bad(add(I5, issue("I-005", "First", depends_on=["I-005"])),
            (I5, "links.depends_on lists the issue itself")),
        bad(add(I5, issue("I-005", "First", status="duplicate", duplicate_of="I-005")),
            (I5, "links.duplicate_of is the issue itself")),
    ],
    "no-id-twice-in-a-list": [
        ok(),
        bad(set_links(I2, related=["I-003", "I-003"]), (I2, "links.related lists I-003 more than once")),
        bad(set_links(I2, depends_on=["I-001", "I-001"]), (I2, "links.depends_on lists I-001 more than once")),
    ],
    "related-is-written-on-one-issue": [
        ok(),
        ok(set_links(I2, related=[]), set_links(I3, related=["I-002"])),
        bad(set_links(I3, related=["I-002"]),
            (I2, "I-002 and I-003 (pm/M1-core/I-003-export.yaml) list each other in links.related; "
                 "keep the link on one of them")),
    ],
    "two-issues-share-one-relation": [
        ok(),
        bad(set_links(I1, related=["I-002"]),
            (I1, "I-001 and I-002 (pm/M1-core/I-002-form.yaml) share more than one relation "
                    "(dependency, related); keep one")),
        bad(set_links(I4, related=["I-003"]),
            (I3, "I-003 and I-004 (pm/M1-core/I-004-download.yaml) share more than one relation "
                    "(related, duplicate); keep one")),
    ],
    "no-depends-on-cycles": [
        ok(add(I5, issue("I-005", "First")),
           add(I6, issue("I-006", "Second", depends_on=["I-005"])),
           add(I7, issue("I-007", "Third", depends_on=["I-006"]))),
        bad(cycle_of("I-005", "I-006", "I-007"),
            ("M2-later/I-005-a.yaml", "depends_on cycle: I-005 -> I-006 -> I-007 -> I-005")),
        bad(cycle_of("I-006", "I-005"),
            ("M2-later/I-005-b.yaml", "depends_on cycle: I-005 -> I-006 -> I-005")),
    ],
    "later-milestone-dependencies-warn": [
        ok(add(I5, issue("I-005", "First", depends_on=["I-003"]))),  # a later milestone waits on an earlier one
        ok(add(I5, issue("I-005", "First", status="done", accepted=(True,))), set_fields(M2, status="active"),
           set_fields(I3, status="done", acceptance=[{"text": "Works", "done": True}]),
           set_links(I3, depends_on=["I-005"])),  # a done issue no longer waits
        ok(lambda tree: tree.update({"M10-far": {"milestone.yaml": milestone("M10", "Far"),
                                                 "I-005-far.yaml": issue("I-005", "Far", depends_on=["I-006"])}}),
           add(I6, issue("I-006", "Second"))),  # M10 comes after M2, not before it
        bad(chain(add(I5, issue("I-005", "First")), set_links(I3, depends_on=["I-005"])),
            (I3, "depends_on I-005 (pm/M2-later/I-005-first.yaml), which is in a later milestone, M2"),
            severity="WARNING"),
        bad(lambda tree: tree.update({"M10-far": {"milestone.yaml": milestone("M10", "Far"),
                                                  "I-005-far.yaml": issue("I-005", "Far")}}) or
            put(tree, I6, issue("I-006", "Second", depends_on=["I-005"])),
            (I6, "depends_on I-005 (pm/M10-far/I-005-far.yaml), which is in a later milestone, M10"),
            severity="WARNING"),
    ],
    "duplicate-of-set-only-for-duplicates": [
        ok(),
        bad(set_fields(I4, status="todo"), (I4, "links.duplicate_of is set, so status must be duplicate, not todo")),
        bad(add(I5, issue("I-005", "First", status="duplicate")),
            (I5, "status is duplicate, so links.duplicate_of must name the original issue")),
    ],
    "duplicate-of-names-an-original": [
        ok(add("M1-core/I-008-csv.yaml", issue("I-008", "CSV file", status="duplicate", duplicate_of="I-003"))),
        bad(add("M1-core/I-008-csv.yaml", issue("I-008", "CSV file", status="duplicate", duplicate_of="I-004")),
            ("M1-core/I-008-csv.yaml", "links.duplicate_of is I-004, which is itself a duplicate")),
    ],
    # State
    "done-needs-every-acceptance-item-done": [
        ok(),
        bad(edit(I1, lambda d: d["acceptance"][1].update(done=False)),
            (I1, "status is done, but acceptance[1] is not done")),
        bad(edit(I1, lambda d: [item.update(done=False) for item in d["acceptance"]]),
            (I1, "status is done, but acceptance[0], acceptance[1] are not done")),
    ],
    "doing-and-done-need-dependencies-done": [
        ok(),
        ok(set_fields(I2, status="done", acceptance=[{"text": "Works", "done": True}])),
        bad(set_fields(I1, status="todo"), (I2, "status is doing, but depends_on I-001 is todo")),
        bad(chain(set_fields(I1, **DROPPED),
                  set_fields(I2, status="done", acceptance=[{"text": "Works", "done": True}])),
            (I2, "status is done, but depends_on I-001 is dropped")),
    ],
    "open-issues-depend-on-no-dropped-or-duplicate-issue": [
        ok(add(I5, issue("I-005", "First", status="dropped", depends_on=["I-004"],
                         notes=[("2026-10-03", "Dropped with I-004.")]))),  # a closed issue may keep the link
        bad(add(I5, issue("I-005", "First", depends_on=["I-004"])),
            (I5, "depends_on I-004, which is a duplicate of I-003 (pm/M1-core/I-004-download.yaml); "
                 "depend on I-003 instead")),
        bad(chain(set_fields(I3, **DROPPED), add(I5, issue("I-005", "First", status="blocked", depends_on=["I-003"],
                                                          notes=[("2026-10-04", "Waiting on I-003.")]))),
            (I5, "depends_on I-003, which is dropped (pm/M1-core/I-003-export.yaml); remove the link")),
        bad(set_fields(I1, **DROPPED),
            (I2, "depends_on I-001, which is dropped (pm/M1-core/I-001-model.yaml); remove the link")),
    ],
    "blocked-and-dropped-say-why": [
        ok(add(I5, issue("I-005", "First", status="blocked", notes=[("2026-10-03", "Waiting on a provider.")]))),
        bad(add(I5, issue("I-005", "First", status="blocked")), (I5, "status is blocked, so notes must say why")),
        bad(set_fields(I3, status="dropped"), (I3, "status is dropped, so notes must say why")),
    ],
    "future-notes-warn": [
        ok(edit(I2, lambda d: d["notes"].append({"date": "2030-01-02", "text": "Tomorrow, by another clock."}))),
        bad(edit(I2, lambda d: d["notes"].append({"date": "2030-01-03", "text": "After tomorrow."})),
            (I2, "notes[1].date 2030-01-03 is in the future"), severity="WARNING"),
    ],
    "planned-milestone-has-no-started-issue": [
        ok(add(I5, issue("I-005", "First")), add(I6, issue("I-006", "Second", status="blocked", notes=[("2026-10-03", "Waiting on a provider.")]))),
        ok(add(I5, issue("I-005", "First", status="doing")), set_fields(M2, status="active")),
        bad(chain(add(I5, issue("I-005", "First", status="doing")),
                  add(I6, issue("I-006", "Second", status="done", accepted=(True,)))),
            (M2, "status is planned, but work has started on I-005 (doing), I-006 (done)")),
    ],
    "done-milestone-needs-everything-closed": [
        ok(add(I5, issue("I-005", "First", status="done", accepted=(True,))),
           add(I6, issue("I-006", "Second", status="dropped", notes=[("2026-10-03", "Not needed.")])),
           add(I7, issue("I-007", "Third", status="duplicate", duplicate_of="I-003")),
           set_fields(M2, status="done")),
        bad(chain(add(I5, issue("I-005", "First")), add(I6, issue("I-006", "Second", status="blocked", notes=[("2026-10-03", "Waiting on a provider.")])),
                  set_fields(M2, status="done")),
            (M2, "status is done, but I-005 (todo), I-006 (blocked) are still open")),
    ],
}

CASES = [
    pytest.param(case, id=f"{rule}-{'pass' if not case.expected else 'fail'}-{n}")
    for rule, cases in RULES.items()
    for n, case in enumerate(cases, 1)
]


def test_every_rule_has_a_passing_and_a_failing_fixture():
    for rule, cases in RULES.items():
        assert any(not case.expected for case in cases), f"{rule} has no passing fixture"
        assert any(case.expected for case in cases), f"{rule} has no failing fixture"


def test_the_base_tree_is_clean(check):
    assert check(base_tree()) == []


@pytest.mark.parametrize("case", CASES)
def test_rule(case, check):
    tree = base_tree()
    case.change(tree)
    findings = check(tree)
    shown = "\n".join(map(str, findings)) or "(no findings)"
    assert len(findings) == len(case.expected), shown
    for path, fragment in case.expected:
        assert any(
            f.severity == case.severity and f.path == f"pm/{path}" and fragment in f.message for f in findings
        ), f"expected {case.severity} pm/{path}: ...{fragment}... in\n{shown}"
