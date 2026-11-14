"""Builders for the pm/ trees the tests write to disk.

A tree maps each name under pm/ to its content. A dict at the top level is a milestone folder.
Inside a folder, a dict is a YAML document, a str or bytes is written as it is, and FOLDER is
an empty subfolder.
"""

from pathlib import Path

import yaml

FOLDER = object()

M1 = "M1-core/milestone.yaml"
I1 = "M1-core/I-001-model.yaml"
I2 = "M1-core/I-002-form.yaml"
I3 = "M1-core/I-003-export.yaml"
I4 = "M1-core/I-004-download.yaml"
M2 = "M2-later/milestone.yaml"
I5 = "M2-later/I-005-first.yaml"
I6 = "M2-later/I-006-second.yaml"
I7 = "M2-later/I-007-third.yaml"


def milestone(id, title, *, status="planned"):
    return {"id": id, "title": title, "status": status, "spec": f"Milestones, {id}"}


def issue(
    id,
    title,
    *,
    status="todo",
    priority="medium",
    repo="backend",
    spec=None,
    scope_in=(),
    scope_out=(),
    accepted=(False,),
    depends_on=(),
    related=(),
    duplicate_of=None,
    notes=(),
):
    return {
        "id": id,
        "title": title,
        "status": status,
        "priority": priority,
        "repo": repo,
        "spec": spec,
        "context": f"Why {title} exists.",
        "scope": {"in": list(scope_in), "out": list(scope_out)},
        "acceptance": [{"text": f"Acceptance {n}", "done": done} for n, done in enumerate(accepted, 1)],
        "links": {
            "depends_on": list(depends_on),
            "related": list(related),
            "duplicate_of": duplicate_of,
        },
        "notes": [{"date": day, "text": text} for day, text in notes],
    }


def base_tree():
    """The valid tree every rule fixture starts from.

    I-002 depends on I-001, I-002 lists I-003 as related, and I-004 is a duplicate of I-003, each
    link written on one issue. M2 is an empty milestone for fixtures to add issues to.
    """
    return {
        "M1-core": {
            "milestone.yaml": milestone("M1", "Core", status="active"),
            "I-001-model.yaml": issue(
                "I-001", "Data model", status="done", spec="section 2", accepted=(True, True)
            ),
            "I-002-form.yaml": issue(
                "I-002",
                "Lead form",
                status="doing",
                priority="high",
                scope_in=["The form"],
                scope_out=["A CAPTCHA"],
                depends_on=["I-001"],
                related=["I-003"],
                notes=[("2026-10-02", "Started.")],
            ),
            "I-003-export.yaml": issue("I-003", "Export", priority="low"),
            "I-004-download.yaml": issue("I-004", "Download", status="duplicate", duplicate_of="I-003"),
        },
        "M2-later": {"milestone.yaml": milestone("M2", "Later")},
    }


def doc(tree, path):
    folder, name = path.split("/")
    return tree[folder][name]


def put(tree, path, content):
    folder, name = path.split("/")
    tree.setdefault(folder, {})[name] = content


def pop(tree, path):
    folder, name = path.split("/")
    return tree[folder].pop(name)


def dump(content):
    return yaml.safe_dump(content, sort_keys=False, allow_unicode=True)


def write_tree(root: Path, tree):
    root.mkdir()
    for name, entry in tree.items():
        if not isinstance(entry, dict):
            (root / name).write_text(entry, encoding="utf-8")
            continue
        (root / name).mkdir()
        for child, content in entry.items():
            path = root / name / child
            if content is FOLDER:
                path.mkdir()
            elif isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content if isinstance(content, str) else dump(content), encoding="utf-8")
