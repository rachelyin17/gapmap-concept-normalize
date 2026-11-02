"""The tools as the agent and the host call them, the bundled datasets, the MCP server over stdio, and the
plugin's layout: one rules module shared byte for byte, a verifier of standard-library code, and a manifest
that restates every rule."""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output, output_schema

from contract import TOOLS, CanonicalizeInput, Dataset, DatasetInput, Tool
from plugin import datasets, get_aliases, get_papers, pin_canonical

ROOT = Path(__file__).resolve().parents[1]


def test_get_papers_gives_the_raw_papers_in_file_order(tmp_path: Path) -> None:
    papers = get_papers(build_output({"dataset": "edge-cases"}, DatasetInput), tmp_path).papers
    raw = json.loads((datasets.DATA / "edge-cases" / "papers.json").read_text(encoding="utf-8"))
    assert [(paper.paper_id, paper.keywords) for paper in papers] == [(paper["paper_id"], paper["keywords"]) for paper in raw]


def test_get_aliases_gives_the_table_sorted_by_alias(tmp_path: Path) -> None:
    aliases = get_aliases(build_output({"dataset": "standard"}, DatasetInput), tmp_path).aliases
    assert [entry.alias for entry in aliases] == sorted(entry.alias for entry in aliases)
    assert {entry.alias: entry.canonical for entry in aliases}["nmt"] == "neural machine translation"


@pytest.mark.parametrize("dataset", list(Dataset))
def test_every_dataset_is_small_ascii_and_valid(dataset: Dataset) -> None:
    papers, entries = datasets.load(dataset)
    # The agent applies the rules in its reasoning, capped at about 2,000 tokens a reply: 12 papers and 58
    # keywords overran it before submit, 8 and 40 fit.
    assert 6 <= len(papers) <= 8
    assert 35 <= sum(len(paper["keywords"]) for paper in papers) <= 42
    assert all(keyword.isascii() for paper in papers for keyword in paper["keywords"])
    assert any(alias == target for alias, target in entries), "each table protects at least one word"


def test_the_edge_cases_dataset_has_every_boundary_case() -> None:
    papers, entries = datasets.load(Dataset.EDGE_CASES)
    keywords = {keyword for paper in papers for keyword in paper["keywords"]}
    aliases = dict(entries)
    assert any(paper["keywords"] == [] for paper in papers)
    assert {"--", "+++", "Ties", "Nets", "Gas", "LLMs", "Sentiment Analysis", "Parallel Corpus", "Word Class", "News"} <= keywords
    assert aliases["news"] == "news" and "llms" not in aliases and aliases["llm"] == "large language model"
    assert sum(1 for alias, target in entries if target in aliases and aliases[target] != target) >= 2, "chains"


def write_dataset(folder: Path, papers: list, aliases: dict) -> None:
    folder.mkdir(parents=True)
    (folder / "papers.json").write_text(json.dumps(papers), encoding="utf-8")
    (folder / "aliases.json").write_text(json.dumps(aliases), encoding="utf-8")


@pytest.mark.parametrize(
    ("aliases", "words"),
    [({"a": "b", "b": "a"}, "cycle"), ({"LLM": "large language model"}, "not in normalized form"), ({"gpt-4": "gpt 4"}, "not in normalized form")],
)
def test_pin_canonical_refuses_a_cyclic_or_unnormalized_alias_table(tmp_path: Path, monkeypatch, aliases: dict, words: str) -> None:
    write_dataset(tmp_path / "small", [{"paper_id": "A", "keywords": ["x"]}], aliases)
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    with pytest.raises(ValueError, match=words):
        pin_canonical(build_output({"dataset": "small", "strip_plurals": True}, CanonicalizeInput), tmp_path)
    with pytest.raises(ValueError, match=words):
        get_aliases(build_output({"dataset": "small"}, DatasetInput), tmp_path)


def test_pin_canonical_refuses_repeated_paper_ids(tmp_path: Path, monkeypatch) -> None:
    write_dataset(tmp_path / "small", [{"paper_id": "A", "keywords": []}, {"paper_id": "A", "keywords": []}], {})
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    with pytest.raises(ValueError, match="repeated"):
        pin_canonical(build_output({"dataset": "small", "strip_plurals": False}, CanonicalizeInput), tmp_path)


def test_pin_canonical_echoes_the_task(tmp_path: Path) -> None:
    pin = pin_canonical(build_output({"dataset": "standard", "strip_plurals": True}, CanonicalizeInput), tmp_path)
    assert pin.dataset is Dataset.STANDARD and pin.strip_plurals is True
    assert pin.expected.dataset is Dataset.STANDARD and pin.expected.strip_plurals is True
    assert [paper.paper_id for paper in pin.expected.papers] == sorted(paper.paper_id for paper in pin.papers)


async def talk(workspace, script):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "plugin"],
        cwd=str(ROOT),
        env={**os.environ, "NANOAGENT_WORKSPACE": str(workspace), "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)])},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return await script(session)


def test_the_server_offers_every_tool_and_answers_over_stdio(tmp_path: Path) -> None:
    async def script(session):
        offered = {tool.name: tool for tool in (await session.list_tools()).tools}
        assert set(offered) == {tool.value for tool in Tool}
        for tool, (given, made) in TOOLS.items():
            assert offered[tool.value].inputSchema == output_schema(given)
            assert offered[tool.value].outputSchema == output_schema(made)
        papers = await session.call_tool("get_papers", {"dataset": "small"})
        assert not papers.isError and len(papers.structuredContent["papers"]) == 8
        aliases = await session.call_tool("get_aliases", {"dataset": "small"})
        assert not aliases.isError and aliases.structuredContent["aliases"][0] == {"alias": "cv", "canonical": "computer vision"}
        pin = await session.call_tool("pin_canonical", {"dataset": "edge-cases", "strip_plurals": True})
        assert not pin.isError and pin.structuredContent["expected"]["papers"][0] == {"paper_id": "E1", "concepts": ["large language model"]}
        bad = await session.call_tool("get_papers", {"dataset": "huge"})
        assert bad.isError and "'huge' is not one of" in bad.content[0].text

    anyio.run(talk, tmp_path, script)
    assert list(tmp_path.iterdir()) == [], "the tools never write the workspace"


def test_the_verifier_and_the_server_share_one_rules_module() -> None:
    assert (ROOT / "verifier" / "rules.py").read_bytes() == (ROOT / "src" / "plugin" / "rules.py").read_bytes()


def test_the_verifier_imports_only_the_standard_library_and_the_contract() -> None:
    for path in (ROOT / "verifier").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                assert top == "contract" or top in sys.stdlib_module_names, f"{path.name} imports {name}"


def test_the_manifest_restates_every_rule_and_names_every_tool() -> None:
    manifest = (ROOT / "nanoagent.yaml").read_text(encoding="utf-8")
    for rule in ("N1.", "N2.", "N3.", "N4.", "N5.", "A1.", "A2.", "P1.", "P2.", "D1."):
        assert f"      {rule} " in manifest, rule
    for tool in Tool:
        assert f"  {tool.value}:\n    description:" in manifest
    assert "tools: [get_papers, get_aliases]" in manifest and "reference: pin_canonical" in manifest
    assert "hosts: []" in manifest and "write: [workspace]" in manifest and "spec: nanoagent.plugin/v0001" in manifest


def test_ui_draws_every_output_from_its_schema() -> None:
    assert sorted(path.name for path in (ROOT / "ui").iterdir()) == ["renderers.css", "renderers.js"]
    assert (ROOT / "ui" / "renderers.js").read_text(encoding="utf-8").strip() == "export default {};"
    assert (ROOT / "ui" / "renderers.css").read_text(encoding="utf-8") == ""


def test_every_tool_is_its_own_module_taking_its_input_and_the_workspace() -> None:
    import inspect

    from plugin.__main__ import IMPLEMENTATIONS

    assert set(IMPLEMENTATIONS) == set(Tool)
    for tool, implementation in IMPLEMENTATIONS.items():
        assert implementation.__module__ == f"plugin.{tool.value}"
        parameters = list(inspect.signature(implementation).parameters.values())
        assert [parameter.name for parameter in parameters] == ["given", "workspace"]
        assert parameters[0].annotation == TOOLS[tool][0].__name__ and parameters[1].annotation == "Path"
