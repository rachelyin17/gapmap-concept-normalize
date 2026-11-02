"""Shared verdict helpers: a result, the ordered constraint list the task verdict carries, the input checks
the tools share, and plain forms of the contract instances the rules work on."""

from contract import Dataset

from .rules import DATASETS

MOST = 10  # list entries a constraint's expected or actual shows


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def compact(value):
    """A value small enough for a verdict: lists cut to MOST entries, mappings to MOST keys."""
    if isinstance(value, list) and len(value) > MOST:
        return value[:MOST] + [f"… {len(value) - MOST} more"]
    if isinstance(value, dict) and len(value) > MOST:
        return {**dict(list(value.items())[:MOST]), "…": f"{len(value) - MOST} more"}
    return value


def constraint(identifier, text, ok, expected=None, actual=None, message=""):
    """One constraint's entry, always with the same keys: ok is True (holds), False (fails) or None (not
    checked: a check it needs did not hold); expected and actual where they say something, else None;
    and message, why it fails or why it was not checked ("" when it holds)."""
    return {
        "id": identifier,
        "constraint": text,
        "ok": ok,
        "expected": compact(expected),
        "actual": compact(actual),
        "message": "" if ok is True else (message or text),
    }


def summary(constraints):
    """A failed verdict's message: the first failing constraint (or, when none fails, the first not
    checked), its id and why, then how many more fail: "papers: E2 is missing (+1 more)"."""
    failed = [entry for entry in constraints if entry["ok"] is False]
    first = failed[0] if failed else next(entry for entry in constraints if entry["ok"] is not True)
    reason = first["message"].removesuffix(".")
    return f"{first['id']}: {reason}" + (f" (+{len(failed) - 1} more)" if len(failed) > 1 else "")


def dataset_problem(dataset):
    """What is wrong with a contract Dataset value, or None."""
    value = dataset.value if isinstance(dataset, Dataset) else dataset
    return None if value in DATASETS else f"dataset must be one of {', '.join(DATASETS)}, not {value!r}"


def flag_problem(flag):
    return None if type(flag) is bool else f"strip_plurals must be true or false, not {flag!r}"


def plain_papers(papers):
    """Contract Papers as plain {paper_id, keywords}."""
    return [{"paper_id": paper.paper_id, "keywords": list(paper.keywords)} for paper in papers]


def plain_aliases(aliases):
    """Contract AliasEntries as [(alias, canonical)], in their order."""
    return [(entry.alias, entry.canonical) for entry in aliases]


def plain_concepts(papers):
    """Contract PaperConcepts as plain {paper_id, concepts}, in their order."""
    return [{"paper_id": paper.paper_id, "concepts": list(paper.concepts)} for paper in papers]
