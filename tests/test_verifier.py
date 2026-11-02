"""The canonicalize-concepts verdict: the exact output holds every constraint on every dataset with and
without plural stripping; each kind of wrong, missing or malformed output fails with its own constraint,
score and message; the boundary cases come out as the rules say; plus the per-call checks."""

from __future__ import annotations

import copy
import json

import pytest
from helpers import DATASETS, WORKSPACE, concepts_of, failed, gold, pin_for, task_for, unchecked, verdict, with_concepts
from oracle import oracle
from slimconfig import build_output, plain_output

import verifier
from contract import AliasesOutput, CanonicalizeInput, DatasetInput, PapersOutput, PinOutput
from verifier.task import ORDER

# The edge-cases dataset's answer, worked out by hand from the rules.
EDGE_CASES = {
    False: {
        "E1": ["large language model", "llms"],
        "E10": ["c", "graphs neural network", "question answering", "speech recognition", "word embeddings"],
        "E2": [],
        "E3": [],
        "E4": ["bert", "decoder only model", "machine translation"],
        "E5": ["bias", "gender bias", "news", "physics", "time series"],
        "E6": ["case studies", "parallel corpus", "sentiment analysis", "ties", "word class"],
        "E9": ["gans", "gas", "lms", "nets", "policies", "transformers", "vaes"],
    },
    True: {
        "E1": ["large language model"],
        "E10": ["c", "graphs neural network", "question answering", "speech recognition", "word embedding", "word embeddings"],
        "E2": [],
        "E3": [],
        "E4": ["bert", "decoder only model", "machine translation"],
        "E5": ["bias", "gender bia", "news", "physics", "time series"],
        "E6": ["case study", "parallel corpus", "sentiment analysis", "ties", "word class"],
        "E9": ["gas", "generative adversarial network", "lms", "net", "policy", "transformer", "variational autoencoder"],
    },
}
EVERY_TASK = [(dataset, strip) for dataset in DATASETS for strip in (False, True)]


# Correct.


@pytest.mark.parametrize(("dataset", "strip"), EVERY_TASK)
def test_the_exact_output_holds_every_constraint(dataset: str, strip: bool) -> None:
    task = task_for(dataset, strip)
    found = verdict(task, gold(task))
    assert found["valid"] and found["score"] == 1.0, found["message"]
    assert found["message"].startswith(f"All {len(ORDER)} checks hold")
    assert [entry["ok"] for entry in found["details"]["constraints"]] == [True] * len(ORDER)
    assert len(json.dumps(found)) < 8000, "the verdict lands in the chat's context: keep it small"


@pytest.mark.parametrize(("dataset", "strip"), EVERY_TASK)
def test_the_answer_key_agrees_with_an_independent_oracle(dataset: str, strip: bool) -> None:
    pin = plain_output(pin_for(task_for(dataset, strip)))
    aliases = {entry["alias"]: entry["canonical"] for entry in pin["aliases"]}
    expected = oracle(pin["papers"], aliases, strip)
    assert pin["expected"]["papers"] == [{"paper_id": paper_id, "concepts": expected[paper_id]} for paper_id in sorted(expected)]


@pytest.mark.parametrize("strip", [False, True])
def test_the_edge_cases_answer_is_the_hand_worked_one(strip: bool) -> None:
    output = gold(task_for("edge-cases", strip))
    assert [entry["paper_id"] for entry in output["papers"]] == sorted(EDGE_CASES[strip]), "Python's string order: E10 before E2"
    assert {entry["paper_id"]: entry["concepts"] for entry in output["papers"]} == EDGE_CASES[strip]


def test_plural_stripping_changes_the_answer_on_every_dataset() -> None:
    for dataset in DATASETS:
        assert gold(task_for(dataset, False))["papers"] != gold(task_for(dataset, True))["papers"]


# Incorrect: valid structure, wrong concepts; the score is the share of papers that match.


def wrong(task: dict, paper_id: str, concepts: list[str]) -> dict:
    output = with_concepts(gold(task), paper_id, concepts)
    found = verdict(task, output)
    assert not found["valid"] and failed(found) == ["concepts-exact"]
    assert found["score"] == pytest.approx(1 - 1 / len(output["papers"]))
    assert found["details"]["mismatches"][0]["paper_id"] == paper_id
    return found


def test_a_missed_alias_fails_concepts_exact() -> None:
    found = wrong(task_for("edge-cases"), "E10", ["c", "graphs neural network", "qa", "speech recognition", "word embeddings"])
    assert found["message"] == "concepts-exact: 1 of 8 papers differ from the rules: E10 misses 'question answering' and has extra 'qa'"


def test_a_missed_alias_that_replaces_its_target_names_both_sides() -> None:
    found = wrong(task_for("edge-cases"), "E4", ["bert base", "decoder only model", "machine translation"])
    assert found["details"]["mismatches"] == [{"paper_id": "E4", "missing": ["bert"], "extra": ["bert base"]}]
    found = wrong(task_for("small"), "S06", ["benchmarks", "news", "qa", "reading comprehension"])
    assert "S06 misses 'question answering' and has extra 'qa'" in found["message"]


def test_a_chain_resolved_one_step_only_fails_concepts_exact() -> None:
    found = wrong(task_for("edge-cases"), "E4", ["bert", "decoder only model", "machine translation", "neural machine translation"])
    assert "E4 has extra 'neural machine translation'" in found["message"]
    found = wrong(task_for("standard"), "1706.03762", ["encoder decoder models", "machine translation", "neural machine translation", "self attention", "transformer"])
    assert found["details"]["mismatches"][0]["extra"] == ["neural machine translation"]


def test_a_three_step_chain_stopped_early_fails_concepts_exact() -> None:
    found = wrong(task_for("edge-cases"), "E4", ["bert", "decoder only transformer", "machine translation"])
    assert "E4 misses 'decoder only model' and has extra 'decoder only transformer'" in found["message"]


def test_plurals_stripped_while_the_flag_is_false_fail_concepts_exact() -> None:
    task = task_for("edge-cases", False)
    stripped = gold(task_for("edge-cases", True))
    output = with_concepts(gold(task), "E9", concepts_of(stripped, "E9"))
    output = with_concepts(output, "E1", concepts_of(stripped, "E1"))
    found = verdict(task, output)
    assert failed(found) == ["concepts-exact"] and found["score"] == pytest.approx(6 / 8)
    assert found["message"].startswith("concepts-exact: 2 of 8 papers differ from the rules: E1 misses 'llms'; E9 misses 'gans'")


def test_a_protected_word_singularized_fails_concepts_exact() -> None:
    found = wrong(task_for("edge-cases", True), "E5", ["bia", "gender bia", "new", "physic", "time sery"])
    assert found["details"]["mismatches"] == [{"paper_id": "E5", "missing": ["bias", "news", "physics", "time series"], "extra": ["bia", "new", "physic", "time sery"]}]


@pytest.mark.parametrize(("right", "stripped"), [("sentiment analysis", "sentiment analysi"), ("parallel corpus", "parallel corpu"), ("word class", "word clas")])
def test_a_kept_ending_wrongly_stripped_fails_concepts_exact(right: str, stripped: str) -> None:
    task = task_for("edge-cases", True)
    concepts = sorted(stripped if concept == right else concept for concept in concepts_of(gold(task), "E6"))
    found = wrong(task, "E6", concepts)
    assert found["details"]["mismatches"] == [{"paper_id": "E6", "missing": [right], "extra": [stripped]}]


def test_a_missed_ies_to_y_fails_concepts_exact() -> None:
    found = wrong(task_for("edge-cases", True), "E6", ["case studies", "parallel corpus", "sentiment analysis", "ties", "word class"])
    assert "E6 misses 'case study' and has extra 'case studies'" in found["message"]
    found = wrong(task_for("edge-cases", True), "E9", ["gas", "generative adversarial network", "lms", "net", "policies", "transformer", "variational autoencoder"])
    assert "E9 misses 'policy' and has extra 'policies'" in found["message"]


def test_every_paper_wrong_scores_zero_and_names_five() -> None:
    task = task_for("edge-cases", True)
    output = copy.deepcopy(gold(task))
    for entry in output["papers"]:
        entry["concepts"] = sorted({*entry["concepts"], "zzz"})
    found = verdict(task, output)
    assert failed(found) == ["concepts-exact"] and found["score"] == 0.0
    assert found["message"].count("has extra 'zzz'") == 5 and found["message"].endswith("; and 3 more")
    assert len(found["details"]["mismatches"]) == 8


# Missing.


def test_a_paper_omitted_fails_papers_and_scores_zero() -> None:
    task = task_for("standard")
    output = gold(task)
    output["papers"] = [entry for entry in output["papers"] if entry["paper_id"] != "1810.04805"]
    found = verdict(task, output)
    assert failed(found) == ["papers"] and found["score"] == 0.0
    assert found["message"] == "papers: paper 1810.04805 is missing"
    assert unchecked(found) == ["concepts-exact"]


def test_a_concept_omitted_fails_concepts_exact() -> None:
    found = wrong(task_for("standard", True), "2305.14314", ["alignment", "instruction tuning", "large language model"])
    assert "2305.14314 misses 'reinforcement learning from human feedback'" in found["message"]


@pytest.mark.parametrize("paper_id", ["E2", "E3"])
def test_a_paper_with_no_concepts_left_out_fails_papers(paper_id: str) -> None:
    task = task_for("edge-cases")
    output = gold(task)
    output["papers"] = [entry for entry in output["papers"] if entry["paper_id"] != paper_id]
    found = verdict(task, output)
    assert failed(found) == ["papers"] and found["score"] == 0.0
    assert f"paper {paper_id} is missing" in found["message"]


def test_no_answer_key_fails_first_and_scores_zero() -> None:
    task = task_for("small")
    found = verdict(task, gold(task), reference=None)
    assert failed(found) == ["answer-key"] and found["score"] == 0.0
    assert "pin_canonical never pinned" in found["message"]
    assert unchecked(found) == ["papers", "concepts-exact"]


# Malformed: any structural problem scores 0.


def malformed(task: dict, output: dict, constraint: str) -> dict:
    found = verdict(task, output)
    assert not found["valid"] and found["score"] == 0.0
    assert failed(found)[0] == constraint, found["message"]
    return found


def test_unsorted_concepts_fail_concepts_form() -> None:
    task = task_for("small")
    found = malformed(task, with_concepts(gold(task), "S03", ["prompting", "benchmarks", "large language model", "text generation"]), "concepts-form")
    assert found["message"] == "concepts-form: S03: the concepts are not sorted ascending (+1 more)"


def test_duplicate_concepts_fail_concepts_form() -> None:
    task = task_for("small")
    found = malformed(task, with_concepts(gold(task), "S03", ["benchmarks", "large language model", "large language model", "prompting", "text generation"]), "concepts-form")
    assert "S03: concept 'large language model' appears more than once" in found["message"]


@pytest.mark.parametrize(
    ("concept", "why"),
    [
        ("Large Language Model", "has characters outside [a-z0-9 ]: 'LM'"),
        ("large-language model", "has characters outside [a-z0-9 ]: '-'"),
        ("gpt-4", "has characters outside [a-z0-9 ]: '-'"),
        ("large  language model", "has a double space"),
        (" large language model", "has a leading or trailing space"),
        ("large language model ", "has a leading or trailing space"),
        ("", "is empty"),
    ],
)
def test_a_malformed_concept_fails_concepts_form(concept: str, why: str) -> None:
    task = task_for("edge-cases")
    found = malformed(task, with_concepts(gold(task), "E1", [concept]), "concepts-form")
    assert found["message"] == f"concepts-form: E1: concept {concept!r} {why} (+1 more)", "concepts-exact fails too"


def test_a_wrong_dataset_echo_fails_echo() -> None:
    task = task_for("small")
    output = {**gold(task), "dataset": "standard"}
    found = malformed(task, output, "echo")
    assert found["message"] == "echo: The output says dataset 'standard': copy dataset and strip_plurals from the task"


def test_a_wrong_flag_echo_fails_echo() -> None:
    task = task_for("edge-cases", True)
    found = malformed(task, {**gold(task), "strip_plurals": False}, "echo")
    assert "strip_plurals false" in found["message"]
    assert failed(found) == ["echo"], "the concepts themselves are right"


def test_an_unknown_paper_id_fails_papers() -> None:
    task = task_for("small")
    output = gold(task)
    output["papers"].append({"paper_id": "S99", "concepts": ["evaluation"]})
    found = malformed(task, output, "papers")
    assert found["message"] == "papers: paper 'S99' is not in the dataset"


def test_a_paper_listed_twice_fails_papers() -> None:
    task = task_for("small")
    output = gold(task)
    output["papers"].insert(1, copy.deepcopy(output["papers"][0]))
    found = malformed(task, output, "papers")
    assert found["message"] == "papers: paper S01 appears 2 times"


def test_papers_in_numeric_order_fail_papers() -> None:
    task = task_for("edge-cases")
    output = gold(task)
    output["papers"].sort(key=lambda entry: int(entry["paper_id"][1:]))
    found = malformed(task, output, "papers")
    assert found["message"] == "papers: the papers are not sorted by paper_id: E9 comes before E10"


def test_an_answer_key_for_another_flag_fails_answer_key() -> None:
    task = task_for("small", True)
    found = verdict(task, gold(task), reference=pin_for(task_for("small", False)))
    assert failed(found)[0] == "answer-key" and found["score"] == 0.0


def test_an_answer_key_whose_expected_output_disagrees_with_its_data_fails_answer_key() -> None:
    task = task_for("small")
    pin = plain_output(pin_for(task))
    pin["expected"]["papers"][0]["concepts"] = ["made up"]
    found = verdict(task, gold(task), reference=build_output(pin, PinOutput))
    assert failed(found)[0] == "answer-key" and "disagrees with the rules" in found["message"]


def test_the_verdict_recomputes_rather_than_trusting_the_pinned_expected_output() -> None:
    task = task_for("small")
    pin = plain_output(pin_for(task))
    pin["papers"][0]["keywords"].append("Few-Shot Learning")  # S03, without updating the expected output
    found = verdict(task, gold(task), reference=build_output(pin, PinOutput))
    assert failed(found) == ["answer-key"] and found["score"] == 0.0


# Boundary.


def test_a_keyword_empty_after_n3_is_dropped() -> None:
    papers = {"P": ["--", "+++", "!!!", "   ", "Attention"]}
    assert oracle([{"paper_id": "P", "keywords": papers["P"]}], {}, True) == {"P": ["attention"]}
    assert concepts_of(gold(task_for("edge-cases", True)), "E1") == ["large language model"], "E1's -- is dropped"
    assert concepts_of(gold(task_for("edge-cases")), "E3") == [], "E3's !!!, +++ and spaces are all dropped"


def test_papers_with_no_keywords_or_none_surviving_still_appear_empty() -> None:
    for strip in (False, True):
        output = gold(task_for("edge-cases", strip))
        assert concepts_of(output, "E2") == [] and concepts_of(output, "E3") == []
    assert pin_for(task_for("edge-cases")).papers[3].keywords == []


def test_raw_variants_collapse_to_one_concept() -> None:
    assert concepts_of(gold(task_for("edge-cases")), "E1") == ["large language model", "llms"], "three raw variants, one concept"
    assert concepts_of(gold(task_for("edge-cases", True)), "E1") == ["large language model"], "and LLMs joins them by P2"
    assert concepts_of(gold(task_for("small", True)), "S07") == ["evaluation", "hallucination", "large language model", "summarization"]


def test_a_four_letter_s_word_is_stripped_and_a_three_letter_one_kept() -> None:
    stripped = concepts_of(gold(task_for("edge-cases", True)), "E9")
    assert "net" in stripped and "nets" not in stripped
    assert {"gas", "lms"} <= set(stripped) and "language model" not in stripped, "lms is kept, so the lm alias never applies"


def test_ies_at_exactly_length_4_is_kept() -> None:
    concepts = concepts_of(gold(task_for("edge-cases", True)), "E6")
    assert "ties" in concepts and "tie" not in concepts and "ty" not in concepts
    assert "case study" in concepts and "policy" in concepts_of(gold(task_for("edge-cases", True)), "E9")


def test_an_alias_that_matches_only_after_singularizing() -> None:
    assert {"generative adversarial network", "variational autoencoder"} <= set(concepts_of(gold(task_for("edge-cases", True)), "E9"))
    assert {"gans", "vaes"} <= set(concepts_of(gold(task_for("edge-cases", False)), "E9"))
    assert concepts_of(gold(task_for("edge-cases", True)), "E1") == ["large language model"]
    assert "llms" in concepts_of(gold(task_for("edge-cases", False)), "E1")
    standard = concepts_of(gold(task_for("standard", True)), "1810.04805")
    assert "pretrained language model" in standard and "plms" not in standard


def test_an_alias_result_is_final_even_when_it_ends_in_s() -> None:
    assert {"word embedding", "word embeddings"} <= set(concepts_of(gold(task_for("edge-cases", True)), "E10"))


def test_only_the_last_word_is_singularized_and_protection_is_for_whole_keywords() -> None:
    assert "graphs neural network" in concepts_of(gold(task_for("edge-cases", True)), "E10")
    assert {"bias", "gender bia"} <= set(concepts_of(gold(task_for("edge-cases", True)), "E5"))


# The per-call checks.


def test_verify_input_accepts_every_dataset_and_flag() -> None:
    for dataset, strip in EVERY_TASK:
        assert verifier.verify_input("pin_canonical", build_output(task_for(dataset, strip), CanonicalizeInput))["valid"]
        for tool in ("get_papers", "get_aliases"):
            assert verifier.verify_input(tool, build_output({"dataset": dataset}, DatasetInput))["valid"]


def test_verify_input_refuses_what_the_contract_lets_through_unchecked() -> None:
    value = build_output(task_for("small"), CanonicalizeInput)
    object.__setattr__(value, "strip_plurals", 1)
    assert not verifier.verify_input("pin_canonical", value)["valid"]
    object.__setattr__(value, "strip_plurals", True)
    object.__setattr__(value, "dataset", "huge")
    found = verifier.verify_input("pin_canonical", value)
    assert not found["valid"] and "small, standard, edge-cases" in found["message"]


def test_the_contract_refuses_an_unknown_dataset_and_a_non_bool_flag() -> None:
    with pytest.raises(ValueError, match="not a valid Dataset"):
        build_output({"dataset": "huge", "strip_plurals": True}, CanonicalizeInput)
    with pytest.raises(ValueError, match="not a bool"):
        build_output({"dataset": "small", "strip_plurals": 1}, CanonicalizeInput)


@pytest.mark.parametrize("dataset", DATASETS)
def test_verify_output_holds_every_tool_on_every_dataset(dataset: str) -> None:
    from plugin import get_aliases, get_papers

    given = build_output({"dataset": dataset}, DatasetInput)
    assert verifier.verify_output("get_papers", given, get_papers(given, WORKSPACE), ".")["valid"]
    assert verifier.verify_output("get_aliases", given, get_aliases(given, WORKSPACE), ".")["valid"]
    for strip in (False, True):
        task = build_output(task_for(dataset, strip), CanonicalizeInput)
        assert verifier.verify_output("pin_canonical", task, pin_for(task_for(dataset, strip)), ".")["valid"]


@pytest.mark.parametrize(
    ("papers", "words"),
    [
        ([], "at least one paper"),
        ([{"paper_id": "A", "keywords": []}, {"paper_id": "A", "keywords": ["x"]}], "paper_id A repeated"),
        ([{"paper_id": "", "keywords": []}], "non-empty"),
        ([{"paper_id": "A", "keywords": ["naïve"]}], "not ASCII"),
    ],
)
def test_verify_output_refuses_malformed_papers(papers: list, words: str) -> None:
    given = build_output({"dataset": "small"}, DatasetInput)
    found = verifier.verify_output("get_papers", given, build_output({"papers": papers}, PapersOutput), ".")
    assert not found["valid"] and words in found["message"]


@pytest.mark.parametrize(
    ("aliases", "words"),
    [
        ([("LLM", "large language model")], "not in normalized form"),
        ([("llm", "Large Language Model")], "not in normalized form"),
        ([("llm", "")], "not in normalized form"),
        ([("b", "x"), ("a", "x")], "not sorted"),
        ([("a", "x"), ("a", "y")], "appears twice"),
        ([("a", "b"), ("b", "a")], "cycle"),
        ([("a", "b"), ("b", "c"), ("c", "a")], "cycle"),
    ],
)
def test_verify_output_refuses_malformed_alias_tables(aliases: list, words: str) -> None:
    given = build_output({"dataset": "small"}, DatasetInput)
    output = build_output({"aliases": [{"alias": alias, "canonical": target} for alias, target in aliases]}, AliasesOutput)
    found = verifier.verify_output("get_aliases", given, output, ".")
    assert not found["valid"] and words in found["message"]


def test_verify_output_accepts_self_mapped_and_chained_aliases() -> None:
    given = build_output({"dataset": "small"}, DatasetInput)
    output = build_output({"aliases": [{"alias": "a", "canonical": "b"}, {"alias": "b", "canonical": "b"}]}, AliasesOutput)
    found = verifier.verify_output("get_aliases", given, output, ".")
    assert found["valid"] and found["details"]["protected"] == 1


def test_verify_output_refuses_a_pin_whose_expected_output_is_wrong() -> None:
    task = task_for("edge-cases", True)
    pin = plain_output(pin_for(task))
    pin["expected"]["papers"][1]["concepts"] = []
    found = verifier.verify_output("pin_canonical", build_output(task, CanonicalizeInput), build_output(pin, PinOutput), ".")
    assert not found["valid"] and "disagrees with the rules" in found["message"]
