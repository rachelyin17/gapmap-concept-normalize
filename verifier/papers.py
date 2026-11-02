"""get_papers: a known dataset in; out, its raw papers: non-empty unique ids, each with a list of ASCII
keywords (possibly empty)."""

from .checks import dataset_problem, plain_papers, result
from .rules import papers_problem


def verify_input(value):
    problem = dataset_problem(value.dataset)
    return result(False, problem) if problem else result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    papers = plain_papers(output_value.papers)
    if not papers:
        return result(False, "a dataset has at least one paper")
    problem = papers_problem(papers)
    if problem:
        return result(False, problem)
    return result(True, "the papers are well formed", papers=len(papers), keywords=sum(len(paper["keywords"]) for paper in papers))
