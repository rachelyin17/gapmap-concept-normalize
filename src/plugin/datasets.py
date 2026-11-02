"""The bundled datasets, data/<dataset>/papers.json and aliases.json, read and checked for every tool, and
built into the contract classes the tools return. This stays out of rules.py, which the verifier copies:
the verifier judges the papers and aliases the answer key pinned, and never reads these files."""

from __future__ import annotations

import json
from pathlib import Path

from contract import AliasEntry, Dataset, Paper
from plugin.rules import alias_problem, papers_problem

DATA = Path(__file__).resolve().parent / "data"


def load(dataset: Dataset) -> tuple[list[dict], list[tuple[str, str]]]:
    """A dataset's raw papers (in file order) and its alias table (sorted by alias), each checked: a
    malformed file, a repeated paper_id, an alias not in normalized form or a cycle longer than 1 raises."""
    folder = DATA / dataset.value
    papers = json.loads((folder / "papers.json").read_text(encoding="utf-8"))
    table = json.loads((folder / "aliases.json").read_text(encoding="utf-8"))
    if not isinstance(papers, list) or not all(isinstance(paper, dict) and set(paper) == {"paper_id", "keywords"} for paper in papers):
        raise TypeError(f"{dataset.value}/papers.json must be a list of {{paper_id, keywords}}")
    if not isinstance(table, dict):
        raise TypeError(f"{dataset.value}/aliases.json must map each alias to its canonical form")
    entries = sorted(table.items())
    problem = papers_problem(papers) or alias_problem(entries)
    if problem:
        raise ValueError(f"the {dataset.value} dataset: {problem}")
    return papers, entries


def paper_list(papers: list[dict]) -> list[Paper]:
    return [Paper(paper_id=paper["paper_id"], keywords=list(paper["keywords"])) for paper in papers]


def alias_list(entries: list[tuple[str, str]]) -> list[AliasEntry]:
    return [AliasEntry(alias=alias, canonical=target) for alias, target in entries]
