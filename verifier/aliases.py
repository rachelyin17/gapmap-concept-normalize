"""get_aliases: a known dataset in; out, its alias table: sorted by alias, each alias once, every alias and
canonical form already normalized, and no cycle longer than 1."""

from .checks import dataset_problem, plain_aliases, result
from .rules import alias_problem


def verify_input(value):
    problem = dataset_problem(value.dataset)
    return result(False, problem) if problem else result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    entries = plain_aliases(output_value.aliases)
    problem = alias_problem(entries)
    if problem:
        return result(False, problem)
    protected = sum(alias == target for alias, target in entries)
    return result(True, "the alias table is well formed", aliases=len(entries), protected=protected)
