"""The rules one at a time: normalization (N1 to N5), alias chains and protected words (A1, A2), plural
stripping of the last word (P1, P2), and the per-paper set (D1)."""

from __future__ import annotations

import pytest

from plugin.rules import alias_problem, canonical, concept_problem, concepts_of, normalize, resolve, singular


@pytest.mark.parametrize(
    ("raw", "form"),
    [
        ("Large Language Models", "large language models"),
        ("large-language-model", "large language model"),
        ("LARGE_LANGUAGE/MODEL", "large language model"),
        ("  Multi---Task   Learning  ", "multi task learning"),
        ("Q&A", "qa"),
        ("C++", "c"),
        ("GPT-4", "gpt 4"),
        ("Word2Vec", "word2vec"),
        ("it's", "its"),
        ("tab\there", "tabhere"),
        ("--", ""),
        ("+++", ""),
        ("", ""),
    ],
)
def test_normalize_follows_n1_to_n4(raw: str, form: str) -> None:
    assert normalize(raw) == form


def test_an_empty_form_is_dropped() -> None:
    assert canonical("--", {}, True) is None and canonical("!!!", {}, False) is None


ALIASES = {"nmt": "neural machine translation", "neural machine translation": "machine translation", "news": "news", "bert base": "bert", "bert": "bert"}


def test_resolve_follows_chains_and_stops_at_a_self_mapped_key() -> None:
    assert resolve("nmt", ALIASES) == ("machine translation", True)
    assert resolve("bert base", ALIASES) == ("bert", True)
    assert resolve("news", ALIASES) == ("news", True)
    assert resolve("transformer", ALIASES) == ("transformer", False)


def test_resolve_refuses_a_cycle() -> None:
    with pytest.raises(ValueError, match="cycle"):
        resolve("a", {"a": "b", "b": "a"})


@pytest.mark.parametrize(
    ("word", "singularized"),
    [
        ("studies", "study"),
        ("flies", "fly"),
        ("ties", "ties"),
        ("lies", "lies"),
        ("analysis", "analysis"),
        ("corpus", "corpus"),
        ("class", "class"),
        ("loss", "loss"),
        ("nets", "net"),
        ("gans", "gan"),
        ("gas", "gas"),
        ("lms", "lms"),
        ("is", "is"),
        ("s", "s"),
        ("news", "new"),
        ("bias", "bia"),
        ("model", "model"),
    ],
)
def test_singular_follows_p1(word: str, singularized: str) -> None:
    assert singular(word) == singularized


def test_plurals_are_stripped_only_with_the_flag_and_only_without_an_alias() -> None:
    aliases = {"news": "news", "word vectors": "word embeddings", "llm": "large language model"}
    assert canonical("News", aliases, True) == "news"
    assert canonical("Word Vectors", aliases, True) == "word embeddings", "A2: an alias result is final"
    assert canonical("Word Embeddings", aliases, True) == "word embedding"
    assert canonical("Word Embeddings", aliases, False) == "word embeddings"
    assert canonical("LLMs", aliases, True) == "large language model", "P2"
    assert canonical("LLMs", aliases, False) == "llms"


def test_only_the_last_word_is_singularized() -> None:
    assert canonical("Graphs Neural Networks", {}, True) == "graphs neural network"


def test_d1_dedupes_and_sorts() -> None:
    aliases = {"llm": "large language model"}
    assert concepts_of(["LLM", "Large-Language Model", "--", "Attention", "attention"], aliases, False) == ["attention", "large language model"]
    assert concepts_of([], aliases, True) == []


@pytest.mark.parametrize(("text", "ok"), [("gpt 4", True), ("a", True), ("", False), ("A", False), ("a  b", False), (" a", False), ("a-b", False)])
def test_concept_problem(text: str, ok: bool) -> None:
    assert (concept_problem(text) is None) is ok


def test_alias_problem_allows_self_maps_and_refuses_longer_cycles() -> None:
    assert alias_problem([("a", "b"), ("b", "b")]) is None
    assert "cycle" in alias_problem([("a", "b"), ("b", "c"), ("c", "a")])
    assert alias_problem([("a b", "c d")]) is None
    assert "normalized" in alias_problem([("a  b", "c")])
