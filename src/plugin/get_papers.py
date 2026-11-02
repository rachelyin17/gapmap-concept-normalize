"""get_papers: a dataset's raw papers for the agent, in file order, no keyword normalized."""

from __future__ import annotations

from pathlib import Path

from contract import DatasetInput, PapersOutput
from plugin.datasets import load, paper_list


def get_papers(given: DatasetInput, workspace: Path) -> PapersOutput:
    """The workspace is unused: the data is bundled, and the tool writes nothing."""
    papers, _ = load(given.dataset)
    return PapersOutput(papers=paper_list(papers))
