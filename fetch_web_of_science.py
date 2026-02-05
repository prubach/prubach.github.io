import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Self
from citations import Publications, CitationSource

import requests

logger = logging.getLogger(__name__)

OUTPUT_JSON = "_data/publications_wos.json"

WOS_API_URL: Final = "https://api.clarivate.com/apis/wos-starter/v2/documents"
WOS_DB: Final = "WOS"
WOS_AUTHOR_QUERY: Final = "AI=(MBU-9207-2025)"

WOS_STARTER_API_KEY = os.getenv("WOS_STARTER_API_KEY")

class UpdateStatus(StrEnum):
    UPDATED = "updated"
    ERROR = "error"
    MISSING = "missing"
    SKIPPED = "skipped"


@dataclass
class WOKItem:
    uid: str
    citations: int

    @staticmethod
    def _get_wos_citations(uid: str, citations: list[dict]) -> int:
        for citation in citations:
            if citation["db"] == WOS_DB:
                return citation["count"]
        logger.error("No WOS citations found for UID: %s citations: %s", uid, citations)
        return 0

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        uid = data["uid"]
        citations = cls._get_wos_citations(uid, data["citations"])

        return cls(uid=uid, citations=citations)


def fetch_page_data(page: int = 1) -> dict:
    headers = {
        "accept": "application/json",
        "X-ApiKey": WOS_STARTER_API_KEY,
    }
    params = {
        "q": WOS_AUTHOR_QUERY,
        "db": WOS_DB,
        "limit": 50,
        "page": page,
    }
    response = requests.get(WOS_API_URL, headers=headers, params=params, timeout=10)
    logger.info("Fetching data from %s", response.url)
    response.raise_for_status()
    return response.json()


def fetch_data() -> list:
    all_hits = []

    # Fetch the first page to get the total number of items
    first_page = fetch_page_data(page=1)
    total = first_page["metadata"]["total"]
    total_pages = total // 50 + 1

    first_page_hits = first_page["hits"]
    all_hits.extend(first_page_hits)

    for page in range(2, total_pages + 1):
        hits = fetch_page_data(page=page)["hits"]
        all_hits.extend(hits)

    logger.info("Fetched %s items", len(all_hits))
    return all_hits


class WebOfScience(Publications):

    def get_title_to_web_of_science_id_mapping(self, data: dict) -> dict[str, str]:
        mapping = {}
        for publication_data in data:
            mapping[publication_data["title"]] = publication_data['uid']
        return mapping


    def try_match_publications(self, data):
        self.wos_id_doi = {}
        logger.info("Trying to match publications with WOS id")
        title_to_google_scholar_id_mapping = self.get_title_to_web_of_science_id_mapping(data)
        pubs = [x for x in self.publications if not 'wos_id' in x]
        publications_without_google_scholar_id = pubs
        for publication in publications_without_google_scholar_id:
            score, title = self.find_best_match(publication['title'], title_to_google_scholar_id_mapping)
            if score > self.threshold:
                wos_id = title_to_google_scholar_id_mapping[title]
                publication['wos_id'] = wos_id
                self.wos_id_doi[wos_id] = publication['doi']
                #publication.save()
                logger.info(
                    "Found WOS match for publication %s with score %s - %s",
                    publication['title'],
                    round(score, 4),
                    wos_id,
                )
            else:
                logger.info("Could not find WOS match for publication title:%s", publication['title'])
        logger.info("Finished matching publications")

    def update_citations_json(self, data: list, citations) -> None:
        statuses = defaultdict(list)
        for item_data in data:
            item = WOKItem.from_dict(item_data)
            doi = self.wos_id_doi.get(item.uid)
            pos = citations.get(doi)
            pos['wos'] = item.citations

        for status, uids in statuses.items():
            logger.info("Update statuses: %s for %s items", status, len(uids))


    def update_publications_json(self, data: list, pubs) -> None:
        statuses = defaultdict(list)
        for item_data in data:
            item = WOKItem.from_dict(item_data)
            doi = self.wos_id_doi.get(item.uid)
            for p in pubs:
                if doi == p.get('doi'):
                    p['wos_id'] = item.uid
                    p["citations"]['webofscience'] = CitationSource(count=item.citations,citing_works=[])

        for status, uids in statuses.items():
            logger.info("Update statuses: %s for %s items", status, len(uids))

    def save_publications(self):
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(self.publications, f, indent=2)

    def run(self, citations=None, pubs=None, *args, **options):
        self.publications = pubs
        data = fetch_data()
        self.try_match_publications(data)
        print(self.publications)
        self.save_publications()
        if citations:
            self.update_citations_json(data, citations)
        if pubs:
            self.update_publications_json(data, pubs)


if __name__ == "__main__":
    gsc = WebOfScience()
    gsc.run(None)