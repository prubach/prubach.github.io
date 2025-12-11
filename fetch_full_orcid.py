#!/usr/bin/env python3
import requests
import json
import yaml
from time import sleep

ORCID_ID = "0000-0001-5487-609X"
API = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"
HEADERS = {"Accept": "application/vnd.orcid+json"}

def fetch_orcid_summary():
    r = requests.get(API, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def fetch_work_detail(putcode):
    url = f"https://pub.orcid.org/v3.0/{ORCID_ID}/work/{putcode}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def fetch_crossref_metadata(doi):
    r = requests.get(f"https://api.crossref.org/works/{doi}")
    if r.status_code != 200: return None
    return r.json()["message"]

def parse_authors(work, crossref=None):
    if crossref and "author" in crossref:
        return [f"{a.get('given','')} {a.get('family','')}".strip() for a in crossref["author"] if a.get('family','') != '']

    contributors = work.get("contributors", {}).get("contributor", [])
    names = []
    for c in contributors:
        name = c.get("credit-name", {}).get("value")
        if name: names.append(name)
    return names

def to_bibtex(entry):
    id = entry["id"]
    a = " and ".join(entry["authors"])
    return f"""@article{{{id},
  title   = {{{entry['title']}}},
  author  = {{{a}}},
  journal = {{{entry['journal']}}},
  year    = {{{entry['year']}}},
  doi     = {{{entry.get('doi','')}}}
}}
"""

def run():
    summary = fetch_orcid_summary()
    works = summary["group"]

    output = []

    for w in works:
        put = w["work-summary"][0]["put-code"]
        detail = fetch_work_detail(put)
        title = detail["title"]["title"]["value"]

        doi = None
        ids = detail.get("external-identifiers",{}).get("external-identifier",[])
        summary = w.get("work-summary", [{}])[0]
        link = summary.get("external-ids", {}).get("external-id", [])
        doi = None

        for i in link:
            if i.get("external-id-type") == "doi":
                doi = i.get("external-id-value")
#        for i in ids:
#            if i["external-id-type"] == "doi":
#                doi = i["external-id-value"].lower()

        crossref = fetch_crossref_metadata(doi) if doi else None
        journal = detail.get("journal-title", {}).get("value", "") if detail.get("journal-title", {}) else crossref.get("event", {}).get("name", "") if crossref.get("event", {}) else ''
        if not journal:
            if crossref.get('subtype','')=='preprint':
                journal = f'Preprint: {crossref.get('institution','')}'

        entry = {
            "id": f"orcid_{put}",
            "title": title,
            "journal": journal,
            "year": detail["publication-date"].get("year",{}).get("value",""),
            "doi": doi,
            "authors": parse_authors(detail, crossref),
            "publisher": crossref.get("publisher", "") if crossref else '',
            "citation": detail.get("citation",{}).get("citation","") if detail.get("citation",{}) else '',
        }

        output.append(entry)
        sleep(0.2)  # res
         
         # Save outputs
    with open("_data/publications.json","w") as f: json.dump(output,f,indent=2)
    with open("_data/publications.yaml","w") as f: yaml.dump(output,f,sort_keys=False)
    with open("assets/data/pawelrubach.bib","w") as f: f.write("\n".join(to_bibtex(x) for x in output))

    #print("Saved: publications.json, publications.yaml, publications.bib")

if __name__ == "__main__":
    run()
