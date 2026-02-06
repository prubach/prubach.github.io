import os

import requests
import time


INPUT_JSON = "_data/publications_citations.json"
OUTPUT_JSON = "_data/publications_not_wos.json"

WOS_API_KEY = os.getenv("WOS_STARTER_API_KEY")
#WOS_API_KEY = "YOUR_WOS_API_KEY"
WOS_ENDPOINT = "https://api.clarivate.com/apis/wos-starter/v2/documents"

HEADERS = {
    "X-ApiKey": WOS_API_KEY,
    "Accept": "application/json"
}

def wos_query(query, limit=1):
    params = {
        "q": query,
        "limit": limit
    }
    r = requests.get(WOS_ENDPOINT, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def wos_by_doi(doi):
    # DOI may be full URL → normalize
    doi = doi.replace("https://doi.org/", "").strip()
    return wos_query(f"DO={doi}")


def wos_by_title(title):
    return wos_query(f'TI="{title}"')

def check_citing_paper_in_wos(citing):
    """
    citing = {
        title, doi, year, alex_id
    }
    """
    result = {
        **citing,
        "wos_found": False,
        "wos_uid": None,
        "wos_match_type": None
    }

    try:
        # 1️⃣ Try DOI first
        if citing.get("doi"):
            resp = wos_by_doi(citing["doi"])
            if resp.get("metadata", {}).get("total", 0) > 0:
                hit = resp["hits"][0]
                result.update({
                    "wos_found": True,
                    "wos_uid": hit.get("uid"),
                    "wos_match_type": "doi"
                })
                return result

        # 2️⃣ Fallback: title search
        resp = wos_by_title(citing["title"])
        if resp.get("metadata", {}).get("total", 0) > 0:
            hit = resp["hits"][0]
            result.update({
                "wos_found": True,
                "wos_uid": hit.get("uid"),
                "wos_match_type": "title"
            })

    except Exception as e:
        result["wos_error"] = str(e)

    return result

def enrich_openalex_citations_with_wos(publications):
    for pub in publications:
        openalex_citations = pub.get("citations", {}).get("openalex", [])
        enriched = []

        for citing in openalex_citations:
            enriched.append(check_citing_paper_in_wos(citing))
            time.sleep(0.2)  # Starter API friendly rate

        pub["citations"]["openalex_wos_checked"] = enriched

    return publications


import json
from datetime import date

if __name__ == "__main__":
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    publications = data["publications"]

    publications = enrich_openalex_citations_with_wos(publications)

    output = {
        **data,
        "wos_crosscheck": {
            "generated_at": date.today().isoformat(),
            "method": "OpenAlex citing papers checked in Web of Science Starter API"
        },
        "publications": publications
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
