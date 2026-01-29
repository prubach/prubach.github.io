import os
import re
import requests
import json
from pathlib import Path
from citations import CitingWork, Publication, CitationSource
from fetch_web_of_science import WebOfScience

import logging

PUBS_JSON = "_data/publications.json"
AUTHOR_NAME="Rubach"
OPENALEX_SEARCH_URL = "https://api.openalex.org/works"

SCOPUS_API_KEY = os.getenv("SCOPUS_API_KEY")


class Citations:
    def __init__(self, doi: str):
        self.doi = doi

    def normalize_title(self, s: str) -> str:
        # Remove non-alphanumeric, lower-case, collapse whitespace
        s = re.sub(r"\W+", " ", s)
        return " ".join(s.lower().split())


class OpenAlexCitations(Citations):

    def get_citation_count(self):
        return self.get_openalex_citation_count()[0]

    def get_openalex_citation_count(self) -> tuple[int, str]:
        url = f"https://api.openalex.org/works/doi:{self.doi}"
        r = requests.get(url, timeout=20)
        if not r.ok:
            return 0, ''
        data = r.json()
        alex_id = data.get("id", '').replace('https://openalex.org/', '')
        citation_count = data.get("cited_by_count", 0)
        logging.debug(f'Got: {self.doi}: {alex_id}: {citation_count}')
        return citation_count, alex_id

    def get_openalex_citation_count_by_title(self, title: str) -> tuple[int, str]:
        work = self.get_openalex_by_title(title)
        if work:
            res = self.extract_openalex_info(work, target_author_name=AUTHOR_NAME)
            if res and res['author_present']:
                return res["citation_count"], res['alex_id']
        return 0, ''

    def extract_openalex_info(self, work, target_author_name=None):
        """
        Given an OpenAlex work JSON result, extract:
          - citation count
          - list of authors
          - whether target_author_name appears in authors
        """
        if not work:
            return None

        citation_count = work.get("cited_by_count", 0)
        alex_id = work.get("id", '').replace('https://openalex.org/', '')

        authorships = work.get("authorships") or []
        author_names = [
            a.get("author", {}).get("display_name") for a in authorships
            if a.get("author", {}).get("display_name")
        ]

        # check presence of the specific author
        author_present = False
        if target_author_name:
            norm_target = self.normalize_title(target_author_name)
            for n in author_names:
                if norm_target in self.normalize_title(n):
                    author_present = True
                    break

        return {
            "alex_id": alex_id,
            "citation_count": citation_count,
            "author_names": author_names,
            "author_present": author_present
        }


    def get_openalex_by_title(self, title: str):
        """
        Searches OpenAlex by title and returns the top hit (if any).
        """
        params = {
            "filter": f"title.search:{title}",
            "per-page": 5  # get top few, we'll pick best match
        }

        r = requests.get(OPENALEX_SEARCH_URL, params=params, timeout=15)
        r.raise_for_status()

        data = r.json()
        results = data.get("results", [])

        if not results:
            return None

        # Normalize the query title
        normalized_query = self.normalize_title(title)

        # Find best match by simple normalized title compare
        best = None
        best_score = 0

        for work in results:
            candidate_title = work.get("title", "")
            normalized_candidate = self.normalize_title(candidate_title)

            # compute simple overlap: # matching tokens
            set_q = set(normalized_query.split())
            set_c = set(normalized_candidate.split())

            score = len(set_q & set_c)
            if score > best_score:
                best_score = score
                best = work
        return best

    def get_openalex_citing_works(self, alex_id, max_results: int = 200) -> list[CitingWork]:
        works = []
        cursor = "*"

        while len(works) < max_results:
            # url = (
            #     "https://api.openalex.org/works"
            #     f"?filter=cites:doi:{self.doi}"
            #     "&per-page=25"
            #     f"&cursor={cursor}"
            # )
            url = (
                "https://api.openalex.org/works"
                f"?filter=cites:id:{alex_id}"
                "&per-page=25"
                f"&cursor={cursor}"
            )

            r = requests.get(url, timeout=20)
            if not r.ok:
                break

            data = r.json()
            for w in data.get("results", []):
                works.append(
                    CitingWork(
                        title=w.get("title"),
                        doi=w.get("doi"),
                        year=w.get("publication_year"),
                        alex_id=w.get("id", '').replace('https://openalex.org/', ''),
                        publisher=w.get("primary_location", {}).get("raw_source_name", ''),
                        source="OpenAlex",
                    )
                )

            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
        return works


class CrossRefCitations(Citations):
    def get_citation_count(self) -> int:
        url = f"https://api.crossref.org/works/{self.doi}"
        r = requests.get(url, timeout=20)
        if not r.ok:
            return 0

        data = r.json()
        return data["message"].get("is-referenced-by-count", 0)


# def get_crossref_citing_works(doi: str, rows: int = 200) -> list[CitingWork]:
#     url = (
#         "https://api.crossref.org/works"
#         f"?filter=references:{doi}"
#         f"&rows={rows}"
#     )
#
#     r = requests.get(url, timeout=20)
#     if not r.ok:
#         return []
#
#     items = r.json()["message"].get("items", [])
#     works = []
#
#     for item in items:
#         works.append(
#             CitingWork(
#                 title=(item.get("title") or [None])[0],
#                 doi=item.get("DOI"),
#                 year=(item.get("published", {})
#                       .get("date-parts", [[None]])[0][0]),
#                 alex_id='',
#                 publisher=(item.get("container-title") or [None])[0],
#                 source="Crossref",
#             )
#         )
#     return works

class ScopusCitations(Citations):
    def get_citation_count(self) -> int:
        headers = {
            "X-ELS-APIKey": SCOPUS_API_KEY,
            "Accept": "application/json"
        }

        params = {
            "query": f"DOI({self.doi})",
            "field": "citedby-count",
            "count": 1
        }

        r = requests.get(
            "https://api.elsevier.com/content/search/scopus",
            headers=headers,
            params=params,
            timeout=10
        )

        if r.status_code != 200:
            return 0

        data = r.json()
        entries = data.get("search-results", {}).get("entry", [])

        if not entries:
            return 0

        return int(entries[0].get("citedby-count", 0))


class SemanticScholarCitations(Citations):
    def get_citation_count(self) -> int:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{self.doi}"
        params = {
            "fields": "citationCount"
        }

        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return 0
        return r.json().get("citationCount")



def enrich_publication(pub: Publication) -> Publication:
    doi = pub['doi']
    if doi:
        oac = OpenAlexCitations(doi)
        oa_count, alex_id = oac.get_openalex_citation_count()
        crc = CrossRefCitations(doi)
        cr_count = crc.get_citation_count()
        sc_count = ScopusCitations(doi).get_citation_count()
        ss_count = SemanticScholarCitations(doi).get_citation_count()
    else:
        oac = OpenAlexCitations(None)
        oa_count, alex_id = oac.get_openalex_citation_count_by_title(pub['title'])
        cr_count = 0
        sc_count = 0
        ss_count = 0
    oa_works = oac.get_openalex_citing_works(alex_id) if oa_count > 0 else []
    pub['alex_id'] = alex_id

    if not 'citations' in pub:
        pub['citations'] = {}

    pub['citations']["scopus"] = CitationSource(
        count=sc_count,
        citing_works=[]
    )
    pub['citations']["semanticscholar"] = CitationSource(
        count=ss_count,
        citing_works=[]
    )
    pub['citations']["openalex"] = CitationSource(
        count=oa_count,
        citing_works=oa_works
    )
    pub['citations']["crossref"] = CitationSource(
        count=cr_count,
        citing_works = []
    )
    return pub


def compare_citing_works(
    openalex: list[CitingWork],
    crossref: list[CitingWork],
):
    oa_dois = {w.doi for w in openalex if w.doi}
    cr_dois = {w.doi for w in crossref if w.doi}

    return {
        "common": sorted(oa_dois & cr_dois),
        "openalex_only": sorted(oa_dois - cr_dois),
        "crossref_only": sorted(cr_dois - oa_dois),
    }


from datetime import date

def publication_to_jekyll_dict(pub):
    return {
        "id": pub['id'],
        "title": pub['title'],
        "doi": pub['doi'],
        "year": pub['year'],
        "alex_id": pub.get('alex_id', None),
        "wos_id": pub.get('wos_id', None),
        "journal": pub['journal'],
        "authors": pub['authors'],
        "publisher": pub['publisher'],

        "citation_counts": {
            source: data.count
            for source, data in pub['citations'].items() if 'citations' in pub
        },

        "citations": {
            source: [
                {
                    "title": w.title,
                    "doi": w.doi,
                    "year": w.year,
                    "alex_id": w.alex_id
                }
                for w in data.citing_works
            ]
            for source, data in pub['citations'].items() if 'citations' in pub
        },
    }


def export_jekyll_json(publications, output_path):
    payload = {
        "generated_at": date.today().isoformat(),
        "sources": [
            "scopus",
            "semanticscholar",
            "openalex",
            "crossref",
            "webofscience"
        ],
        "publications": [
            publication_to_jekyll_dict(p) for p in publications
        ],
    }

    Path(output_path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def process():
    with open(PUBS_JSON, "r", encoding="utf-8") as f:
        publications = json.load(f)
        #publications = [x for x in publications if x['title'].startswith('Semantic') or x['title'].startswith('Alpha')]
        #publications = [x for x in publications if x['title'].startswith('Semantic') or x['title'].startswith('AlphaKn')]
        publications = [enrich_publication(p) for p in publications]

        gsc = WebOfScience()
        gsc.run(citations=None, pubs=publications)

        export_jekyll_json(
            publications,
            "_data/publications_citations.json"
        )


if __name__=="__main__":
    process()