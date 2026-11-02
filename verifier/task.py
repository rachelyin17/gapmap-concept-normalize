"""The canonicalize-concepts verdict: 6 constraints, in order, on the answer key, the task, and the submitted
concepts. The verdict is valid only when every one holds. Any failure among the first 5 (the answer key and
the output's structure) scores 0; otherwise the score is the share of papers whose concept list is exactly
the one the rules give.

The rules are applied here to the raw papers and aliases the answer key pinned, never read from the expected
output it carries (the answer-key constraint holds only when that output agrees with them)."""

from .checks import (
    constraint,
    dataset_problem,
    flag_problem,
    plain_aliases,
    plain_concepts,
    plain_papers,
    result,
    summary,
)
from .pin import pin_problem
from .rules import MOST_NAMED, concept_problem, expected_papers

TEXT = {
    "answer-key": "The answer key pinned this task's dataset and flag, its papers and its alias table",
    "task-input": "The task names a known dataset and a true or false strip_plurals",
    "echo": "The output echoes the task's dataset and strip_plurals",
    "papers": "Every paper appears exactly once, none unknown, sorted by paper_id",
    "concepts-form": "Every concept list is sorted and unique, each concept a normalized form",
    "concepts-exact": "Each paper's concepts are the ones the rules give",
}
ORDER = tuple(TEXT)
GATES = ORDER[:5]  # the answer key and the output's structure: any failure scores 0


def named(items):
    """Up to MOST_NAMED items joined by "; ", and how many more."""
    shown = "; ".join(items[:MOST_NAMED])
    return shown + (f"; and {len(items) - MOST_NAMED} more" if len(items) > MOST_NAMED else "")


def flag(value):
    return "true" if value else "false"


def paper_problems(known, ids):
    """What is wrong with the submitted paper ids against the pinned ones, in words: missing, repeated,
    unknown, then unsorted."""
    problems = [f"paper {paper_id} is missing" for paper_id in known if paper_id not in ids]
    problems += [f"paper {paper_id} appears {ids.count(paper_id)} times" for paper_id in sorted(set(ids)) if ids.count(paper_id) > 1]
    problems += [f"paper {paper_id!r} is not in the dataset" for paper_id in sorted(set(ids) - set(known))]
    if not problems and ids != sorted(ids):
        first = next(index for index in range(len(ids) - 1) if ids[index] > ids[index + 1])
        problems.append(f"the papers are not sorted by paper_id: {ids[first]} comes before {ids[first + 1]}")
    return problems


def form_problems(submitted):
    """What is wrong with each submitted concept list, in words: a malformed concept, a repeat, or an order
    other than ascending."""
    problems = []
    for entry in submitted:
        concepts = entry["concepts"]
        bad = [(concept, concept_problem(concept)) for concept in concepts if concept_problem(concept)]
        repeated = sorted({concept for concept in concepts if concepts.count(concept) > 1})
        if bad:
            problems.append(f"{entry['paper_id']}: concept {bad[0][0]!r} {bad[0][1]}")
        elif repeated:
            problems.append(f"{entry['paper_id']}: concept {repeated[0]!r} appears more than once")
        elif concepts != sorted(concepts):
            problems.append(f"{entry['paper_id']}: the concepts are not sorted ascending")
    return problems


def mismatches(expected, submitted):
    """Each expected paper whose submitted list differs, with the concepts it misses and has in excess."""
    given = {entry["paper_id"]: entry["concepts"] for entry in submitted}
    found = []
    for entry in expected:
        got = given.get(entry["paper_id"], [])
        if got != entry["concepts"]:
            want = set(entry["concepts"])
            found.append({"paper_id": entry["paper_id"], "missing": sorted(want - set(got)), "extra": sorted(set(got) - want)})
    return found


def described(mismatch):
    parts = []
    if mismatch["missing"]:
        parts.append(f"misses {', '.join(map(repr, mismatch['missing']))}")
    if mismatch["extra"]:
        parts.append(f"has extra {', '.join(map(repr, mismatch['extra']))}")
    return f"{mismatch['paper_id']} {' and '.join(parts) or 'is not sorted and unique'}"


def verify_task(arguments, output, reference, workspace):
    """The verdict on a submitted CanonicalizeOutput (see the module's docstring)."""
    checks = {}
    details = {}

    def put(identifier, ok, expected=None, actual=None, message=""):
        checks[identifier] = constraint(identifier, TEXT[identifier], ok, expected, actual, message)

    def skip(identifier, *needs):
        """Not checked: one of the checks it needs did not hold."""
        blocking = [need for need in needs if checks[need]["ok"] is not True]
        checks[identifier] = constraint(identifier, TEXT[identifier], None, message=f"Not checked: {' and '.join(blocking)} did not hold.")

    def hold(*identifiers):
        return all(checks[identifier]["ok"] is True for identifier in identifiers)

    # 1-2: the answer key and the task.
    if reference is None:
        put("answer-key", False, message="No answer key: pin_canonical never pinned the dataset.")
    else:
        problem = pin_problem(arguments, reference)
        put("answer-key", problem is None, message=problem and problem[0].upper() + problem[1:])
    problem = dataset_problem(arguments.dataset) or flag_problem(arguments.strip_plurals)
    put("task-input", problem is None, message=problem)

    # 3-5: the output's structure.
    want = {"dataset": arguments.dataset.value, "strip_plurals": arguments.strip_plurals}
    got = {"dataset": output.dataset.value, "strip_plurals": output.strip_plurals}
    wrong = [f"{key} {flag(got[key]) if key == 'strip_plurals' else repr(got[key])}" for key in want if got[key] != want[key]]
    put("echo", not wrong, want, got, f"The output says {' and '.join(wrong)}: copy dataset and strip_plurals from the task")
    submitted = plain_concepts(output.papers)
    ids = [entry["paper_id"] for entry in submitted]
    if hold("answer-key"):
        known = sorted(paper.paper_id for paper in reference.papers)
        problems = paper_problems(known, ids)
        put("papers", not problems, known, ids, named(problems))
    else:
        skip("papers", "answer-key")
    problems = form_problems(submitted)
    put("concepts-form", not problems, None, problems or None, named(problems))

    # 6: the concepts, recomputed from the pinned raw data.
    if hold("answer-key", "task-input", "papers"):
        expected = expected_papers(plain_papers(reference.papers), dict(plain_aliases(reference.aliases)), arguments.strip_plurals)
        found = mismatches(expected, submitted)
        details.update(papers=len(expected), matched=len(expected) - len(found), mismatches=found)
        message = f"{len(found)} of {len(expected)} papers differ from the rules: {named([described(item) for item in found])}"
        wanted = {entry["paper_id"]: entry["concepts"] for entry in expected}
        given = {entry["paper_id"]: entry["concepts"] for entry in submitted}
        differing = [item["paper_id"] for item in found]
        put("concepts-exact", not found, {key: wanted[key] for key in differing}, {key: given[key] for key in differing}, message)
    else:
        skip("concepts-exact", "answer-key", "task-input", "papers")

    constraints = [checks[identifier] for identifier in ORDER]
    if not all(checks[identifier]["ok"] is True for identifier in GATES):
        return result(False, summary(constraints), score=0.0, constraints=constraints, **details)
    if checks["concepts-exact"]["ok"] is not True:
        return result(False, summary(constraints), score=details["matched"] / details["papers"], constraints=constraints, **details)
    concepts = sum(len(entry["concepts"]) for entry in submitted)
    message = (
        f"All {len(ORDER)} checks hold: {len(submitted)} papers, {concepts} concepts, on the {want['dataset']} dataset "
        f"with strip_plurals {flag(want['strip_plurals'])}."
    )
    return result(True, message, score=1.0, constraints=constraints, **details)
