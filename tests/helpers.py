"""A task, its answer key, its gold output and the verdict on an output, as the host would run them."""

from __future__ import annotations

import copy
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import CanonicalizeInput, CanonicalizeOutput, Dataset, PinOutput
from plugin import pin_canonical

TASK = "canonicalize-concepts"
DATASETS = [dataset.value for dataset in Dataset]
WORKSPACE = Path(".")  # the tools take the workspace and leave it untouched
PINNED = object()  # the verdict's default reference: the task's own answer key


def task_for(dataset: str, strip_plurals: bool = False) -> dict:
    return {"dataset": dataset, "strip_plurals": strip_plurals}


def pin_for(task: dict):
    return pin_canonical(build_output(task, CanonicalizeInput), WORKSPACE)


def gold(task: dict) -> dict:
    return plain_output(pin_for(task).expected)


def verdict(task: dict, output: dict, reference=PINNED, workspace: str = ".") -> dict:
    """The verdict, with every value built from plain JSON as the verifier's sandbox builds it."""
    reference = build_output(plain_output(pin_for(task)), PinOutput) if reference is PINNED else reference
    return verifier.verify_task(TASK, build_output(task, CanonicalizeInput), build_output(output, CanonicalizeOutput), reference, workspace)


def with_concepts(output: dict, paper_id: str, concepts: list[str]) -> dict:
    """``output`` with one paper's concepts replaced."""
    changed = copy.deepcopy(output)
    next(entry for entry in changed["papers"] if entry["paper_id"] == paper_id)["concepts"] = concepts
    return changed


def concepts_of(output: dict, paper_id: str) -> list[str]:
    return next(entry["concepts"] for entry in output["papers"] if entry["paper_id"] == paper_id)


def failed(found: dict) -> list[str]:
    return [entry["id"] for entry in found["details"]["constraints"] if entry["ok"] is False]


def unchecked(found: dict) -> list[str]:
    return [entry["id"] for entry in found["details"]["constraints"] if entry["ok"] is None]
