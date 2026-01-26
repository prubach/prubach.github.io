import json
from datetime import date
import requests

PUBS_JSON = "_data/publications.json"
OUTPUT_JSON = "_data/citations.json"
CRED_JSON = "_credentials.json"

creds = {}

WOS_ENDPOINT = "https://api.clarivate.com/api/woslite"

def get_wos_citations(doi):
    headers = {
        "X-ApiKey": creds['WOS_API_KEY'],
        "Accept": "application/json"
    }

    params = {
        "databaseId": "WOS",
        "usrQuery": f"DO={doi}",
        "count": 1,
        "firstRecord": 1
    }

    r = requests.get(WOS_ENDPOINT, headers=headers, params=params, timeout=10)
    r.raise_for_status()

    data = r.json()
    records = data.get("Data", {}).get("Records", {}).get("records", [])

    if not records:
        return None

    return records[0]["dynamic_data"]["citation_related"]["tc_list"]["silo_tc"]["local_count"]


def get_scopus_citations(doi):
    headers = {
        "X-ELS-APIKey": creds['SCOPUS_API_KEY'],
        "Accept": "application/json"
    }

    params = {
        "query": f"DOI({doi})",
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
        return None

    data = r.json()
    entries = data.get("search-results", {}).get("entry", [])

    if not entries:
        return None

    return int(entries[0].get("citedby-count", 0))


def get_semantic_scholar_citations(doi):
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {
        "fields": "citationCount"
    }

    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        return None

    return r.json().get("citationCount")


def enrich_publications(publications):
    citations = {}

    for pub in publications:
        doi = pub.get("doi")
        if not doi:
            continue

        citations[doi] = {
            "semantic_scholar": get_semantic_scholar_citations(doi),
            # "wos": get_wos_citations(doi),  # enable if available
            "last_updated": str(date.today())
        }

    return citations


def process():
    with open(PUBS_JSON, "r", encoding="utf-8") as f:
        publications = json.load(f)

    if publications:
        citations = enrich_publications(publications)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(citations, f, indent=2)


def get_credentials():
    with open(CRED_JSON, "r", encoding="utf-8") as f:
        creds = json.load(f)

if __name__=="__main__":
    get_credentials()
    process()