"""pin_canonical, the answer key: a dataset's raw papers and alias table, the flag, and the output the rules
give. It refuses an alias table with a cycle longer than 1 or an alias not in normalized form."""

from __future__ import annotations

from pathlib import Path

from contract import CanonicalizeInput, CanonicalizeOutput, PaperConcepts, PinOutput
from plugin.datasets import alias_list, load, paper_list
from plugin.rules import expected_papers


def pin_canonical(given: CanonicalizeInput, workspace: Path) -> PinOutput:
    """The workspace is unused: the data is bundled, and the tool writes nothing."""
    papers, entries = load(given.dataset)
    expected = expected_papers(papers, dict(entries), given.strip_plurals)
    return PinOutput(
        dataset=given.dataset,
        strip_plurals=given.strip_plurals,
        papers=paper_list(papers),
        aliases=alias_list(entries),
        expected=CanonicalizeOutput(
            dataset=given.dataset,
            strip_plurals=given.strip_plurals,
            papers=[PaperConcepts(paper_id=entry["paper_id"], concepts=entry["concepts"]) for entry in expected],
        ),
    )
