"""The templates hold the full key set the validator enforces, in the schema's order.

The issue template starts with no notes, so a copy can't keep a made-up dated note. It shows a
note's keys in a comment instead, and the tests read them from there.
"""

import pytest
import yaml
from conftest import PACKAGE_DIR

from pm_tree import validate

TEMPLATES = {
    "milestone.yaml": validate.MILESTONE_SCHEMA,
    "issue.yaml": validate.ISSUE_SCHEMA,
}


def schema_shape(item):
    if isinstance(item, validate.Record):
        return [(key, schema_shape(value)) for key, value in item.fields.items()]
    if isinstance(item, validate.ListOf):
        return [schema_shape(item.item)]
    return "value"


def template_shape(value):
    if isinstance(value, dict):
        return [(key, template_shape(item)) for key, item in value.items()]
    if isinstance(value, list):
        # An empty list can only stand for a list of plain values; a list of mappings must
        # show one item, so its keys are in the template.
        shapes = [template_shape(item) for item in value] or ["value"]
        assert all(shape == shapes[0] for shape in shapes), "list items differ in shape"
        return [shapes[0]]
    return "value"


def load(name):
    text = (PACKAGE_DIR / "templates" / name).read_text(encoding="utf-8")
    return yaml.load(text, Loader=validate.StrictLoader)


def commented_notes():
    """The notes list the issue template shows in its closing comment."""
    lines = (PACKAGE_DIR / "templates" / "issue.yaml").read_text(encoding="utf-8").splitlines()
    block = lines[lines.index("# notes:"):]
    assert all(line.startswith("# ") for line in block)
    return yaml.load("\n".join(line[2:] for line in block), Loader=validate.StrictLoader)["notes"]


def with_commented_notes(name):
    data = load(name)
    if name == "issue.yaml":
        data["notes"] = commented_notes()
    return data


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_keys_match_the_schema(name):
    assert template_shape(with_commented_notes(name)) == schema_shape(TEMPLATES[name])


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_values_pass_the_schema(name):
    assert TEMPLATES[name].check(load(name)) == []
    assert TEMPLATES[name].check(with_commented_notes(name)) == []


def test_issue_template_starts_with_no_notes():
    assert load("issue.yaml")["notes"] == []
    assert len(commented_notes()) == 1


def test_shape_comparison_catches_a_missing_key():
    data = load("issue.yaml")
    del data["links"]["related"]
    assert template_shape(data) != schema_shape(validate.ISSUE_SCHEMA)
