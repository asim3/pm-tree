"""Run the validator as `python -m pm_tree`, the same as the `pm-tree` command."""

import sys

from pm_tree.validate import main

sys.exit(main())
