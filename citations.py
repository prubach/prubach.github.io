import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Dict, Optional

PUBS_JSON = "_data/publications.json"

@dataclass
class CitingWork:
    title: Optional[str]
    doi: Optional[str]
    year: Optional[int]
    alex_id: Optional[str]
    publisher: Optional[str]
    source: str


@dataclass
class CitationSource:
    count: int = 0
    citing_works: List[CitingWork] = field(default_factory=list)


@dataclass
class Publication:
    title: str
    doi: str
    citations: Dict[str, CitationSource] = field(default_factory=dict)


class Publications:
    threshold = 0.9

    def __init__(self):
        self.load_publications()

    def load_publications(self):
        with open(PUBS_JSON, "r", encoding="utf-8") as f:
            pub_files = json.load(f)
            self.publications = pub_files['publications']

    @staticmethod
    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def find_best_match(self, title_man, titles):
        best_score = 0
        best_title = ""

        for title in titles:
            score = Publications.similar(title_man.lower(), title.lower())
            if score > best_score:
                best_score = score
                best_title = title
        return best_score, best_title


