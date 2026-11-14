"""The command line: output format, exit codes, the default path, --summary, --next-id, and the example."""

import os
import subprocess
import sys
from importlib.metadata import entry_points, version
from pathlib import Path

from conftest import PACKAGE_DIR
from pmtree import I1, I3, I5, I7, base_tree, doc, dump, issue, milestone, put, write_tree

from pm_tree import validate

VERSION = version("pm-tree")
EXAMPLE = PACKAGE_DIR / "example" / "pm"


def run(*args, cwd, env=None):
    result = subprocess.run(
        [sys.executable, "-m", "pm_tree", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.returncode, result.stdout.splitlines()


def git(cwd, *args):
    """Run git in a scratch repo, with an identity of its own and no signing."""
    subprocess.run(
        ["git", "-c", "user.name=pm-tree", "-c", "user.email=pm-tree@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def write_issue(repo, path, content):
    (repo / "pm" / path).write_text(dump(content), encoding="utf-8")


def repo_with_base_tree(path):
    """A git repo whose main holds the base tree, I-001 to I-004, in pm/."""
    path.mkdir()
    git(path, "init", "-b", "main")
    write_tree(path / "pm", base_tree())
    git(path, "add", "pm")
    git(path, "commit", "-m", "pm")
    return path


def test_version_is_1_0_0():
    assert VERSION == "1.0.0"


def test_the_command_is_pm_tree():
    (command,) = entry_points(group="console_scripts", name="pm-tree")
    assert command.value == "pm_tree.validate:main"


def test_docs_prints_the_folder_of_the_readme_templates_and_example(tmp_path):
    assert run("--docs", cwd=tmp_path) == (0, [f"pm-tree {VERSION}", str(PACKAGE_DIR)])
    for name in ("README.md", "templates/milestone.yaml", "templates/issue.yaml", "example/pm"):
        assert (PACKAGE_DIR / name).exists(), name


def test_example_has_no_errors_or_warnings():
    assert validate.validate(EXAMPLE).findings == []


def test_example_uses_every_status_priority_repo_and_link_type():
    result = validate.validate(EXAMPLE)
    issues = [i for m in result.milestones for i in m.issues]
    assert {m.data["status"] for m in result.milestones} == set(validate.MILESTONE_STATUSES)
    assert {i.status for i in issues} == set(validate.ISSUE_STATUSES)
    assert {i.data["priority"] for i in issues} == set(validate.PRIORITIES)
    assert {i.data["repo"] for i in issues} == set(validate.REPOS)
    assert all(any(i.links(key) for i in issues) for key in validate.RELATIONS)
    assert any(i.data["spec"] is None for i in issues) and any(i.data["spec"] for i in issues)
    assert any(i.data["notes"] for i in issues) and any(not i.data["notes"] for i in issues)
    assert any(not i.data["scope"]["in"] for i in issues) and any(i.data["scope"]["out"] for i in issues)


def test_clean_tree_prints_version_and_counts(tmp_path):
    write_tree(tmp_path / "pm", base_tree())
    assert run(cwd=tmp_path) == (0, [f"pm-tree {VERSION}", "0 errors, 0 warnings"])


def test_path_defaults_to_pm_in_the_current_folder(tmp_path):
    assert run(cwd=tmp_path) == (1, [f"pm-tree {VERSION}", "ERROR pm: does not exist", "1 error, 0 warnings"])


def test_path_argument(tmp_path):
    write_tree(tmp_path / "plan", base_tree())
    assert run("plan", cwd=tmp_path)[0] == 0
    (tmp_path / "file").write_text("x")
    assert run("file", cwd=tmp_path) == (1, [f"pm-tree {VERSION}", "ERROR file: is not a folder", "1 error, 0 warnings"])


def test_findings_are_sorted_by_path_and_errors_exit_1(tmp_path):
    tree = base_tree()
    doc(tree, I3)["priority"] = "urgent"  # found while reading I-003
    doc(tree, I1)["status"] = "todo"  # found later, on I-002, which is doing
    put(tree, I5, issue("I-005", "Lead form"))  # a warning on I-002 and I-005
    tree["M10-far"] = {"milestone.yaml": milestone("M10", "Far", status="Done")}
    write_tree(tmp_path / "pm", tree)
    code, lines = run(cwd=tmp_path)
    assert code == 1
    assert lines[0] == f"pm-tree {VERSION}"
    assert lines[-1] == "3 errors, 2 warnings"
    paths = [line.split(" ", 1)[1].split(": ", 1)[0] for line in lines[1:-1]]
    assert paths == [
        "pm/M1-core/I-002-form.yaml",
        "pm/M1-core/I-002-form.yaml",
        "pm/M1-core/I-003-export.yaml",
        "pm/M2-later/I-005-first.yaml",
        "pm/M10-far/milestone.yaml",
    ]
    assert [line.split(" ", 1)[0] for line in lines[1:3]] == ["ERROR", "WARNING"]


def test_warnings_alone_exit_0(tmp_path):
    tree = base_tree()
    put(tree, I5, issue("I-005", "Lead form"))
    write_tree(tmp_path / "pm", tree)
    code, lines = run(cwd=tmp_path)
    assert code == 0
    assert lines[-1] == "0 errors, 2 warnings"
    assert all(line.startswith("WARNING ") for line in lines[1:-1])


def test_summary_of_the_example():
    code, lines = run(str(EXAMPLE), "--summary", cwd=PACKAGE_DIR)
    assert code == 0
    assert lines == [
        f"pm-tree {VERSION}",
        "0 errors, 0 warnings",
        "",
        "M1 Tenant core: done",
        "  issues: 4 (2 done, 1 dropped, 1 duplicate)",
        "  waiting: none",
        "M2 Lead capture: active",
        "  issues: 5 (2 todo, 1 doing, 1 blocked, 1 done)",
        "  waiting:",
        "    I-008 (blocked): Spam protection on the lead form",
        "      2026-10-10: Blocked until a CAPTCHA provider is chosen.",
        "    I-009 (todo) waits on I-006: Email the tenant about each new lead",
        "  ready:",
        "    I-007 (low): Export leads to CSV",
        "M3 Reporting: planned",
        "  issues: 1 (1 todo)",
        "  waiting:",
        "    I-010 (todo) waits on I-009: Leads by source report",
    ]


def test_summary_lists_a_blocked_issue_with_what_it_waits_on_and_its_latest_note(tmp_path):
    tree = base_tree()
    notes = [("2026-10-05", "Still waiting,\n  on the provider."), ("2026-10-03", "Why."), ("2026-10-05", "Older.")]
    put(tree, I5, issue("I-005", "First", status="blocked", depends_on=["I-002"], notes=notes))
    write_tree(tmp_path / "pm", tree)
    code, lines = run("--summary", cwd=tmp_path)
    assert code == 0
    assert lines[lines.index("M2 Later: planned"):] == [
        "M2 Later: planned",
        "  issues: 1 (1 blocked)",
        "  waiting:",
        "    I-005 (blocked) waits on I-002: First",
        "      2026-10-05: Older.",
    ]


def test_summary_lists_ready_issues_of_active_milestones_by_priority(tmp_path):
    tree = base_tree()
    put(tree, "M1-core/I-005-first.yaml", issue("I-005", "First", priority="high"))
    put(tree, "M1-core/I-006-second.yaml", issue("I-006", "Second", priority="high", depends_on=["I-002"]))
    put(tree, "M1-core/I-007-third.yaml", issue("I-007", "Third", priority="low", depends_on=["I-001"]))
    put(tree, "M2-later/I-008-planned.yaml", issue("I-008", "Planned"))  # ready, but M2 is only planned
    write_tree(tmp_path / "pm", tree)
    code, lines = run("--summary", cwd=tmp_path)
    assert code == 0
    assert lines[3:] == [
        "M1 Core: active",
        "  issues: 7 (4 todo, 1 doing, 1 done, 1 duplicate)",
        "  waiting:",
        "    I-006 (todo) waits on I-002: Second",
        "  ready:",
        "    I-005 (high): First",
        "    I-003 (low): Export",
        "    I-007 (low): Third",
        "M2 Later: planned",
        "  issues: 1 (1 todo)",
        "  waiting: none",
    ]


def test_summary_of_an_active_milestone_with_nothing_ready(tmp_path):
    tree = base_tree()
    doc(tree, I3)["status"] = "doing"
    write_tree(tmp_path / "pm", tree)
    code, lines = run("--summary", cwd=tmp_path)
    assert code == 0
    assert lines[lines.index("M1 Core: active"):lines.index("M2 Later: planned")] == [
        "M1 Core: active",
        "  issues: 4 (2 doing, 1 done, 1 duplicate)",
        "  waiting: none",
        "  ready: none",
    ]


def test_summary_with_errors_prints_them_and_exits_1(tmp_path):
    tree = base_tree()
    doc(tree, I3)["priority"] = "urgent"
    write_tree(tmp_path / "pm", tree)
    code, lines = run("--summary", cwd=tmp_path)
    assert code == 1
    assert lines == [
        f"pm-tree {VERSION}",
        "ERROR pm/M1-core/I-003-export.yaml: priority must be one of high, medium, low, got 'urgent'",
        "1 error, 0 warnings",
    ]


def test_summary_of_an_empty_pm(tmp_path):
    Path(tmp_path / "pm").mkdir()
    assert run("--summary", cwd=tmp_path) == (0, [f"pm-tree {VERSION}", "0 errors, 0 warnings", "", "no milestones"])


def test_next_id_counts_the_working_tree_and_every_local_and_remote_branch(tmp_path):
    origin = repo_with_base_tree(tmp_path / "origin")
    git(origin, "switch", "-c", "pushed")
    write_issue(origin, I7, issue("I-007", "Third"))
    git(origin, "add", "pm")
    git(origin, "commit", "-m", "I-007")
    git(origin, "switch", "main")
    git(tmp_path, "clone", "-q", str(origin), "clone")
    clone = tmp_path / "clone"
    assert run("--next-id", cwd=clone) == (0, [f"pm-tree {VERSION}", "I-008"])  # origin/pushed has I-007

    git(clone, "switch", "-c", "local")
    write_issue(clone, "M2-later/I-012-local.yaml", issue("I-012", "Local"))
    git(clone, "add", "pm")
    git(clone, "commit", "-m", "I-012")
    git(clone, "switch", "main")
    assert run("--next-id", cwd=clone) == (0, [f"pm-tree {VERSION}", "I-013"])  # the local branch has I-012

    write_issue(clone, "M2-later/I-099-unsaved.yaml", issue("I-099", "Unsaved"))
    assert run("pm", "--next-id", cwd=clone) == (0, [f"pm-tree {VERSION}", "I-100"])  # not yet committed


def test_next_id_of_an_empty_pm_is_i_001(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "pm").mkdir()
    assert run("--next-id", cwd=tmp_path) == (0, [f"pm-tree {VERSION}", "I-001"])


def test_next_id_outside_a_git_repo_exits_1(tmp_path):
    write_tree(tmp_path / "pm", base_tree())
    code, lines = run("--next-id", cwd=tmp_path, env={"GIT_CEILING_DIRECTORIES": str(tmp_path)})
    assert code == 1
    assert lines[0] == f"pm-tree {VERSION}"
    assert lines[1].startswith("ERROR pm: git for-each-ref failed: fatal: not a git repository")
    assert len(lines) == 2


def test_next_id_of_a_missing_folder_exits_1(tmp_path):
    assert run("--next-id", cwd=tmp_path) == (1, [f"pm-tree {VERSION}", "ERROR pm: does not exist"])
