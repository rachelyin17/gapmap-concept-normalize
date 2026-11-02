"""pin_canonical, the answer key: its input, and the data it pins, checked by hand. The expected output it
carries is never trusted: it must equal the rules applied to the pinned papers and aliases."""

from .checks import dataset_problem, flag_problem, plain_aliases, plain_concepts, plain_papers, result
from .rules import alias_problem, expected_papers, papers_problem


def verify_input(value):
    problem = dataset_problem(value.dataset) or flag_problem(value.strip_plurals)
    return result(False, problem) if problem else result(True, "input is valid")


def pin_problem(arguments, pin):
    """What is wrong with the answer key for the task ``arguments``, or None: the task's dataset and flag,
    well-formed papers and alias table, and an expected output equal to the rules' on them."""
    if pin.dataset != arguments.dataset or pin.strip_plurals != arguments.strip_plurals:
        return (
            f"the answer key is for dataset {pin.dataset.value} with strip_plurals {pin.strip_plurals}, not "
            f"{arguments.dataset.value} with {arguments.strip_plurals}"
        )
    papers = plain_papers(pin.papers)
    problem = papers_problem(papers) or alias_problem(plain_aliases(pin.aliases))
    if problem:
        return f"the pinned data is malformed: {problem}"
    expected = pin.expected
    if expected.dataset != pin.dataset or expected.strip_plurals != pin.strip_plurals:
        return "the answer key's expected output echoes another dataset or flag"
    if plain_concepts(expected.papers) != expected_papers(papers, dict(plain_aliases(pin.aliases)), pin.strip_plurals):
        return "the answer key's expected output disagrees with the rules applied to its own papers and aliases"
    return None


def verify_output(input_value, output_value, workspace):
    problem = pin_problem(input_value, output_value)
    if problem:
        return result(False, problem)
    concepts = sum(len(paper.concepts) for paper in output_value.expected.papers)
    return result(True, "the answer key is pinned", papers=len(output_value.papers), concepts=concepts)
