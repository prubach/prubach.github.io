import json
from datetime import date

import requests
from scholarly import scholarly, ProxyGenerator
from _credentials import SCOPUS_API_KEY, WOS_STARTER_API_KEY, WOS_API_KEY

PUBS_JSON = "_data/publications.json"
OUTPUT_JSON = "_data/citations_comparison.json"

WOS_ENDPOINT = "https://api.clarivate.com/api/woslite"


def normalize_paper(title, year=None, doi=None):
    return {
        "title": title.strip().lower(),
        "year": year,
        "doi": doi.lower() if doi else None
    }


def get_wos_citing_papers(doi):
    headers = {
        "X-ApiKey": WOS_STARTER_API_KEY
    }

    params = {
        "databaseId": "WOS",
        "usrQuery": f"DO={doi}",
        "count": 100
    }

    r = requests.get(
        "https://api.clarivate.com/api/woslite",
        headers=headers,
        params=params,
        timeout=10
    )

    if r.status_code != 200:
        return []

    records = r.json().get("Data", {}).get("Records", {}).get("records", [])

    citing = []
    for rec in records:
        citing.append(normalize_paper(
            title=rec["title"]["value"],
            year=rec.get("source", {}).get("publishYear"),
            doi=rec.get("doi")
        ))

    return citing


def get_scopus_citing_papers(doi):
    headers = {
        "X-ELS-APIKey": SCOPUS_API_KEY,
        "Accept": "application/json"
    }

    params = {
        "query": f"REFDOI({doi})",
        "count": 25
    }

    r = requests.get(
        "https://api.elsevier.com/content/search/scopus",
        headers=headers,
        params=params,
        timeout=10
    )

    if r.status_code != 200:
        return []

    entries = r.json().get("search-results", {}).get("entry", [])

    citing = []
    for e in entries:
        citing.append(normalize_paper(
            title=e.get("dc:title", ""),
            year=e.get("prism:coverDate", "")[:4],
            doi=e.get("prism:doi")
        ))

    return citing


def get_gs_citing_papers(pub_det):
    pub = next(scholarly.search_pubs(pub_det['title']))
    #search = scholarly.search_pubs(title)
    #pub = next(search, None)
    if not pub:
        return []

    citing = []
    try:
        for cite in scholarly.citedby(pub):
            citing.append(normalize_paper(
                title=cite.get("bib", {}).get("title", ""),
                year=cite.get("bib", {}).get("year"),
                doi = None
            ))
    except KeyError:
        print(f'Problem obtaining cited by for: {pub_det['title']}')
    return citing


def compare_sources(a, b):
    set_a = {(p["doi"] or p["title"]) for p in a}
    set_b = {(p["doi"] or p["title"]) for p in b}

    return {
        "only_in_a": sorted(set_a - set_b),
        "only_in_b": sorted(set_b - set_a),
        "in_both": sorted(set_a & set_b)
    }

def analyze_publication(doi, title):
    #wos = get_wos_citing_papers(doi)
    scopus = get_scopus_citing_papers(doi)
    gs = get_gs_citing_papers(normalize_paper(title))

    return {
        "counts": {
            #"wos": len(wos),
            "scopus": len(scopus),
            "gs": len(gs)
        },
        "comparisons": {
            #"wos_vs_scopus": compare_sources(wos, scopus),
            #"gs_vs_wos": compare_sources(gs, wos),
            "gs_vs_scopus": compare_sources(gs, scopus)
        },
        "last_updated": str(date.today())
    }


def enrich_publications(publications):
    citations = {}

    for pub in publications:
        doi = pub.get("doi")
        if not doi:
            continue

        citations[doi] = analyze_publication(doi, pub["title"])
            # "wos": get_wos_citations(doi),  # enable if available
    return citations


def process():
    #pg = ProxyGenerator()
    #pg.FreeProxies()
    #scholarly.use_proxy(pg)
    with open(PUBS_JSON, "r", encoding="utf-8") as f:
        publications = json.load(f)

    if publications:
        citations = enrich_publications(publications)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(citations, f, indent=2)


if __name__=="__main__":
    process()