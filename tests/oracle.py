"""An independent implementation of the rules, written from the task's instructions alone with regular
expressions (it imports nothing of the plugin), so the tests compare two readings of the same rules."""

import re


def final_form(raw, aliases, strip_plurals):
    """One raw keyword's final form, or None when it is dropped."""
    form = raw.lower()
    form = re.sub(r"[-_/]", " ", form)
    form = re.sub(r"[^a-z0-9 ]", "", form)
    form = re.sub(r" +", " ", form).strip(" ")
    if form == "":
        return None
    if form in aliases:
        return follow(form, aliases)
    if not strip_plurals:
        return form
    *head, last = form.split(" ")
    if re.search(r"ies$", last):
        last = last[:-3] + "y" if len(last) > 4 else last
    elif re.search(r"(ss|us|is)$", last):
        pass
    elif re.search(r"s$", last) and len(last) > 3:
        last = last[:-1]
    form = " ".join([*head, last])
    return follow(form, aliases) if form in aliases else form


def follow(form, aliases):
    for _ in range(len(aliases) + 1):
        if form not in aliases or aliases[form] == form:
            return form
        form = aliases[form]
    raise AssertionError(f"the alias table has a cycle through {form!r}")


def oracle(papers, aliases, strip_plurals):
    """{paper_id: its concepts} for raw papers [{paper_id, keywords}] and an alias mapping."""
    return {
        paper["paper_id"]: sorted({form for form in (final_form(raw, aliases, strip_plurals) for raw in paper["keywords"]) if form is not None})
        for paper in papers
    }
