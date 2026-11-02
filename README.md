# GapMap Concept Normalize

A NanoAgent plugin (spec `nanoagent.plugin/v0001`), with the structure of the
reference plugin, [arxiv-source](https://github.com/zeyuyang8/arxiv-source). GapMap counts how often research
concepts appear in papers, and how often they appear together. Raw keywords come
in surface variants of one concept ("LLMs", "Large Language Models",
"large-language-model"), and left apart they split every count. In this plugin's task,
`canonicalize-concepts`, the agent turns each paper's raw keyword list into a
sorted, deduplicated list of **canonical concepts**. It uses fixed normalization rules and
the dataset's bundled alias table. Every rule is deterministic, so each input has
exactly one correct output, and the verifier recomputes it from the raw data.

The plugin id is prefixed with `gapmap-` to avoid collisions on the marketplace.

## Tools

| Tool | Does | Code |
|---|---|---|
| `pin_canonical` | The answer key, hidden from the agent. It returns the dataset's raw papers, its alias table, the flag and the `CanonicalizeOutput` the rules give. It refuses an alias table with a cycle longer than 1, or an alias or canonical form that is not in normalized form | `src/plugin/pin_canonical.py` |
| `get_papers` | A dataset's papers, `{paper_id, keywords}`, in file order, with the keywords exactly as extracted | `src/plugin/get_papers.py` |
| `get_aliases` | A dataset's alias table, `{alias, canonical}`, sorted by alias | `src/plugin/get_aliases.py` |

No tool normalizes a keyword for the agent; otherwise the task would be trivial.
The data is bundled, so the plugin reads no network. Its tools never write,
though the manifest grants the standard `write: [workspace]`.

### Task

| Task | Input | Runner |
|---|---|---|
| `canonicalize-concepts` | `dataset` (`small`, `standard` or `edge-cases`) and `strip_plurals` (bool) | `agent`, with `get_papers` and `get_aliases`; reference `pin_canonical` |

The agent makes three calls: `get_papers`, `get_aliases`, then `submit` with
`{dataset, strip_plurals, papers}`. Each entry of `papers` is
`{paper_id, concepts}`, with one entry for every paper, sorted by `paper_id` in Python's
default string order (`E10` comes before `E2`). `concepts` is sorted and unique, and is
`[]` for a paper with no surviving keywords.

## The rules

Each raw keyword goes through these rules in order (the manifest's `instructions` restate them):

- **N1** lowercase (`str.lower()`; keywords are ASCII); **N2** each `-`, `_`, `/` becomes a space;
  **N3** delete every character outside `a-z`, `0-9` and space; **N4** collapse runs of spaces and strip the ends;
  **N5** drop the keyword if nothing is left.
- **A1** if the form is an alias key, replace it with its value, and repeat while the value is a key that maps
  to something different (chains); a key mapping to itself stops the chain. **A2** if A1 changed the keyword,
  or the keyword is a self-mapped (protected) key, it is final: skip P1.
- **P1** (only with `strip_plurals` and when A1 did not apply; the last word only). For a word ending in `ies`:
  longer than 4 letters, `ies` → `y`; otherwise it is kept (`ties`). A word ending in `ss`, `us` or `is` is kept.
  Any other word ending in `s` and longer than 3 letters loses the `s`. **P2** look the singularized keyword up
  in the alias table and resolve it as in A1.
- **D1** per paper: collect the final forms, dedupe, sort ascending.

The spec's literal P1 sends a 4-letter `ies` word (`ties`) on to the general
`s` rule (→ `tie`), but its boundary tests keep `ties` unchanged. The plugin
follows the tests: an `ies` word of 4 letters or fewer is kept, and the
instructions say so in P1.

`src/plugin/rules.py` holds the rules in standard-library code, and
`verifier/rules.py` is a byte-for-byte copy (a test enforces it).
`tests/oracle.py` is a second, independent implementation written with regular
expressions, and the answer key must agree with it on every dataset and flag.

## Datasets

Each dataset is `src/plugin/data/<dataset>/papers.json` (a list of
`{paper_id, keywords}`) and `aliases.json` (a map from alias to canonical
form). Every alias and canonical form is already normalized, and no cycle is
longer than 1. They are small, because the agent applies the rules by hand in its reasoning,
which the hosted model caps at about 2,000 tokens a reply: 12 papers and 58
keywords overran it before the agent could submit, while 8 papers and about 40
keywords fit.

| Dataset | Papers | Keywords | Aliases | Contents |
|---|---|---|---|---|
| `small` | 8 | 40 | 7 | Simple cases for smoke tests: acronyms, plurals, one protected word (`news`) |
| `standard` | 8 | 39 | 16 | Realistic NLP keywords on arXiv ids: a two-step chain (`nmt` → `neural machine translation` → `machine translation`), aliases reached only after singularizing (`PLMs`, `Pre-trained Language Models`) |
| `edge-cases` | 8 | 37 | 18 | Every boundary case below, several to a paper |

`edge-cases` packs the boundary cases into 8 papers:

| Paper | Cases |
|---|---|
| E1 | `--` dropped; three raw variants of `large language model` collapse; `LLMs` reaches the `llm` alias only after singularizing |
| E2 | No keywords at all |
| E3 | `!!!`, `+++` and spaces: no keyword survives |
| E4 | Chains: `nmt` (two steps), `gpt` (three), `bert base` → protected `bert` |
| E5 | Protected `news`, `time series`, `physics`, `bias`; `gender bias` still becomes `gender bia` |
| E6 | `analysis`, `corpus`, `class` kept; `studies` → `study`; `ties` kept |
| E9 | `GANs`, `VAEs` reach aliases after singularizing; 4-letter `nets` stripped, 3-letter `gas` and `lms` kept (so the `lm` alias never applies); `policies` → `policy` |
| E10 | `Q&A`, `C++`, `speech_recognition`; an alias result ending in `s` stays final beside the stripped raw form; only the last word of `graphs neural network` is singularized |

The ids skip E7 and E8 on purpose: in Python's string order `E10` comes before
`E2`, so numeric order is the wrong order.

## Verifier

`verifier/task.py` judges the submission against 6 constraints, in order. Each
entry of `details.constraints` is `{id, constraint, ok, expected, actual,
message}`. `ok` is `true` (holds), `false` (fails) or `null` (not checked, because a
check it needs failed).

| # | id | What it checks | Example failure message |
|---|---|---|---|
| 1 | `answer-key` | The answer key pinned this task's dataset and flag, well-formed papers and aliases, and an expected output equal to the rules applied to them | No answer key: pin_canonical never pinned the dataset. |
| 2 | `task-input` | The dataset is a known one and the flag a bool | dataset must be one of small, standard, edge-cases, not 'huge' |
| 3 | `echo` | `dataset` and `strip_plurals` are the task's | The output says strip_plurals false: copy dataset and strip_plurals from the task |
| 4 | `papers` | Every paper exactly once, none unknown, sorted by `paper_id` | paper E2 is missing |
| 5 | `concepts-form` | Every list sorted and unique; every concept non-empty, `[a-z0-9 ]` only, no double, leading or trailing space | E1: concept 'gpt-4' has characters outside [a-z0-9 ]: '-' |
| 6 | `concepts-exact` | Each paper's list equals the one recomputed from the pinned raw papers and aliases | 1 of 8 papers differ from the rules: E10 misses 'question answering' and has extra 'qa' |

How it is scored:

- **Valid** only when all 6 hold; the score is then 1.0.
- **Score 0** when any of 1 to 5 fails: the answer key or the output's structure is wrong.
- **Otherwise** the score is the share of papers whose list matches exactly. The message names up to 5
  mismatched papers with their missing and extra concepts; `details.mismatches` lists every one.

The verifier never trusts the expected output inside the pin: it recomputes from
the pinned raw data with standard-library code, and the answer key fails if the
two disagree. `verify_input` checks that the dataset is a known one and the flag
a bool. `verify_output` checks the shape of each tool's output: unique non-empty
ids and ASCII keywords for `get_papers`; a sorted, normalized, acyclic table for
`get_aliases`; and the whole answer key, recomputed, for `pin_canonical`.

## Limitations

- **A short `ies` word is kept.** P1 turns `ies` into `y` only in a last word longer than 4 letters, and leaves a
  shorter one unchanged rather than passing it to the plain `s` rule: `ties` stays `ties` (not `tie`), and so do
  `lies` and `pies`.
- **The plural rules are heuristic.** `news` becomes `new` and `bias` becomes `bia` unless the alias table protects
  them, `robotics` becomes `robotic`, and an irregular plural (`criteria`, `indices`) is never singularized.
- **Protection is for whole keywords.** A self-mapped `bias` protects the keyword `bias`, not the last word of
  `gender bias`, which still becomes `gender bia` (edge-cases E5).
- **Alias results are final.** An alias whose canonical form is plural (`word vectors` → `word embeddings`) skips
  P1, so with `strip_plurals` it can sit beside the singularized raw form (`word embedding`, edge-cases E10). Curated
  tables should map to singular forms, as `standard` does.
- **ASCII only.** Raw keywords must be ASCII; `get_papers` and the answer key refuse any other keyword.
- **Synonym quality** depends entirely on the hand-curated alias table: nothing merges true synonyms it does not list.
- **Only the last word** of a keyword is singularized: `graphs neural network` keeps its first plural.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (no hosts; the workspace), tools, the task and its instructions
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml   # the datasets ship as package data
├── uv.lock
├── .gitignore
├── .env             # needed environment variable names (none here)
├── src/plugin/      # the MCP server (__main__.py); one module per tool (get_papers.py, get_aliases.py,
│                    #   pin_canonical.py), each (input, workspace) -> output; the rules (rules.py); the
│                    #   bundled datasets (data/) and their loading and checks (datasets.py)
├── tests/           # the verdict (test_verifier.py), the rules, the tools and server, an independent oracle
├── ui/              # renderers.js exports {}, so every output is drawn from its JSON Schema
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier: one module per tool, the task's 6 constraints in task.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```
