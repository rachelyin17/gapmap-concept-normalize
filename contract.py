"""Each tool's and task's typed input and output (see nanoagent.plugin.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_CANONICAL = "pin_canonical"
    GET_PAPERS = "get_papers"
    GET_ALIASES = "get_aliases"


class Task(Enum):
    CANONICALIZE_CONCEPTS = "canonicalize-concepts"


class Dataset(Enum):
    SMALL = "small"
    STANDARD = "standard"
    EDGE_CASES = "edge-cases"


DATASET = "Which bundled dataset: small (simple cases), standard (realistic NLP keywords) or edge-cases (every boundary case)"
PAPER_ID = "The paper's id, unique within the dataset"
CONCEPT = "A final form: lowercase words of a-z and 0-9 joined by single spaces"


@dataclass
class DatasetInput(Output):
    dataset: Annotated[Dataset, DATASET]


@dataclass
class CanonicalizeInput(Output):
    dataset: Annotated[Dataset, DATASET]
    strip_plurals: Annotated[bool, "Whether rule P1 (plural stripping of the last word) is applied"]


@dataclass
class Paper(Output):
    paper_id: Annotated[str, PAPER_ID]
    keywords: Annotated[list[str], "The raw keywords, ASCII, as extracted from the paper; may be empty"]


@dataclass
class PapersOutput(Output):
    papers: Annotated[list[Paper], "Every paper of the dataset with its raw keywords"]


@dataclass
class AliasEntry(Output):
    alias: Annotated[str, "A keyword already in normalized form (rules N1 to N4)"]
    canonical: Annotated[str, "What the alias resolves to; the alias itself marks a protected word"]


@dataclass
class AliasesOutput(Output):
    aliases: Annotated[list[AliasEntry], "The dataset's alias table, sorted by alias"]


@dataclass
class PaperConcepts(Output):
    paper_id: Annotated[str, PAPER_ID]
    concepts: Annotated[list[Annotated[str, CONCEPT]], "The paper's final forms, unique and sorted ascending; [] when none survive"]


@dataclass
class CanonicalizeOutput(Output):
    dataset: Annotated[Dataset, "The task's dataset, copied unchanged"]
    strip_plurals: Annotated[bool, "The task's strip_plurals, copied unchanged"]
    papers: Annotated[list[PaperConcepts], "One entry per paper get_papers returns, sorted by paper_id ascending"]


@dataclass
class PinOutput(Output):
    dataset: Dataset
    strip_plurals: bool
    papers: Annotated[list[Paper], "The dataset's raw papers"]
    aliases: Annotated[list[AliasEntry], "The dataset's alias table, sorted by alias"]
    expected: Annotated[CanonicalizeOutput, "The output the rules give on these papers and aliases"]


TOOLS = {
    Tool.PIN_CANONICAL: (CanonicalizeInput, PinOutput),
    Tool.GET_PAPERS: (DatasetInput, PapersOutput),
    Tool.GET_ALIASES: (DatasetInput, AliasesOutput),
}
TASKS = {
    Task.CANONICALIZE_CONCEPTS: (CanonicalizeInput, CanonicalizeOutput),
}
