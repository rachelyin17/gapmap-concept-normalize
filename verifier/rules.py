"""The canonicalization rules (N1 to D1) and the checks every tool, the answer key and the verifier hold data
to. Standard library only: verifier/rules.py is a byte-for-byte copy, and a test enforces it."""

DATASETS = ("small", "standard", "edge-cases")
SEPARATORS = "-_/"  # N2: each becomes a space
ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyz0123456789 ")  # N3: everything else is deleted
KEPT_ENDINGS = ("ss", "us", "is")  # P1: a last word ending so is never singularized
MOST_NAMED = 5  # entries a problem message names


def shown(value):
    return repr(value) if isinstance(value, str) else str(value)


def normalize(keyword):
    """N1 to N4: the keyword lowercased, separators turned into spaces, every other character outside
    [a-z0-9 ] deleted, runs of spaces collapsed and the ends stripped. "" means N5 drops it."""
    text = keyword.lower()
    for separator in SEPARATORS:
        text = text.replace(separator, " ")
    text = "".join(character for character in text if character in ALLOWED)
    return " ".join(word for word in text.split(" ") if word)


def resolve(form, aliases):
    """A1: (the form after following the alias chain, whether the form is a key at all). A key that maps to
    itself stops the chain; a cycle longer than 1 raises (alias_problem refuses such a table first)."""
    if form not in aliases:
        return form, False
    seen = {form}
    while form in aliases and aliases[form] != form:
        form = aliases[form]
        if form in seen:
            raise ValueError(f"the alias table has a cycle through {form!r}")
        seen.add(form)
    return form, True


def singular(word):
    """P1 on one word: ies -> y when longer than 4 (a 4-letter ies word such as ties is kept); a word ending
    in ss, us or is is kept; otherwise a final s goes when the word is longer than 3."""
    if word.endswith("ies"):
        return word[:-3] + "y" if len(word) > 4 else word
    if word.endswith(KEPT_ENDINGS):
        return word
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def canonical(keyword, aliases, strip_plurals):
    """One raw keyword's final form, or None when N5 drops it."""
    form = normalize(keyword)
    if not form:
        return None
    final, aliased = resolve(form, aliases)
    if aliased or not strip_plurals:  # A2
        return final
    head, _, last = form.rpartition(" ")
    singularized = f"{head} {singular(last)}" if head else singular(last)
    return resolve(singularized, aliases)[0]  # P2


def concepts_of(keywords, aliases, strip_plurals):
    """D1: a paper's final forms, unique and sorted."""
    found = {canonical(keyword, aliases, strip_plurals) for keyword in keywords}
    return sorted(found - {None})


def expected_papers(papers, aliases, strip_plurals):
    """Every paper's concepts, as plain {paper_id, concepts}, sorted by paper_id."""
    return [
        {"paper_id": paper["paper_id"], "concepts": concepts_of(paper["keywords"], aliases, strip_plurals)}
        for paper in sorted(papers, key=lambda paper: paper["paper_id"])
    ]


def concept_problem(text):
    """What keeps ``text`` from being a final form, or None: a non-empty run of [a-z0-9] words joined by
    single spaces."""
    if not isinstance(text, str) or not text:
        return "is empty"
    outside = sorted({character for character in text if character not in ALLOWED})
    if outside:
        return f"has characters outside [a-z0-9 ]: {''.join(outside)!r}"
    if text != text.strip(" "):
        return "has a leading or trailing space"
    if "  " in text:
        return "has a double space"
    return None


def papers_problem(papers):
    """What is wrong with raw papers (plain {paper_id, keywords}), or None: non-empty unique ids, and
    keyword lists of ASCII strings."""
    ids = [paper["paper_id"] for paper in papers]
    if not all(isinstance(paper_id, str) and paper_id for paper_id in ids):
        return "every paper_id must be a non-empty string"
    repeated = sorted({paper_id for paper_id in ids if ids.count(paper_id) > 1})
    if repeated:
        return f"paper_id {', '.join(repeated[:MOST_NAMED])} repeated"
    for paper in papers:
        keywords = paper["keywords"]
        if not isinstance(keywords, list) or not all(isinstance(keyword, str) for keyword in keywords):
            return f"{paper['paper_id']}: keywords must be a list of strings"
        odd = [keyword for keyword in keywords if not keyword.isascii()]
        if odd:
            return f"{paper['paper_id']}: keyword {shown(odd[0])} is not ASCII"
    return None


def alias_problem(entries):
    """What is wrong with an alias table given as [(alias, canonical)], or None: every alias and canonical
    form already normalized and non-empty, each alias once, sorted by alias, and no cycle longer than 1
    (a key mapping to itself marks a protected word)."""
    for alias, target in entries:
        for role, text in (("alias", alias), ("canonical form", target)):
            if not isinstance(text, str) or not text or normalize(text) != text:
                return f"{role} {shown(text)} is not in normalized form (rules N1 to N4)"
    keys = [alias for alias, _ in entries]
    if len(set(keys)) != len(keys):
        return "an alias appears twice"
    if keys != sorted(keys):
        return "the aliases are not sorted"
    aliases = dict(entries)
    for alias in keys:
        try:
            resolve(alias, aliases)
        except ValueError as error:
            return str(error)
    return None
