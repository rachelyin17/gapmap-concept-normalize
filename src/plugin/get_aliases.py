"""get_aliases: a dataset's alias table for the agent, sorted by alias."""

from __future__ import annotations

from pathlib import Path

from contract import AliasesOutput, DatasetInput
from plugin.datasets import alias_list, load


def get_aliases(given: DatasetInput, workspace: Path) -> AliasesOutput:
    """The workspace is unused: the data is bundled, and the tool writes nothing."""
    _, entries = load(given.dataset)
    return AliasesOutput(aliases=alias_list(entries))
