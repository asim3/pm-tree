from datetime import date
from pathlib import Path

import pytest
from pmtree import write_tree

from pm_tree import validate

PACKAGE_DIR = validate.PACKAGE_DIR  # the installed package: README.md, templates/ and example/

TODAY = date(2030, 1, 1)  # the rule fixtures' today, so their notes are never in the future


@pytest.fixture
def check(tmp_path, monkeypatch):
    """Write a tree to pm/ in a fresh folder and return the validator's findings for it."""
    monkeypatch.chdir(tmp_path)

    def run(tree):
        write_tree(Path("pm"), tree)
        return validate.validate(Path("pm"), today=TODAY).findings

    return run
