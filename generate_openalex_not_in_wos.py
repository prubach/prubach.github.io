import json
from datetime import date
from html import escape
from pathlib import Path


INPUT_JSON = "_data/publications_not_wos.json"
OUTPUT_HTML = "openalex_citations_not_in_wos.html"


def html_header(title):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  margin: 2rem;
  background: #fafafa;
  color: #111;
}}

h1 {{
  margin-bottom: 0.3rem;
}}

.meta {{
  color: #555;
  margin-bottom: 2rem;
}}

.pub {{
  border-left: 4px solid #4f46e5;
  padding-left: 1rem;
  margin-top: 2.5rem;
}}

.citation {{
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 0.8rem 1rem;
  margin: 0.6rem 0;
}}

.citation-title {{
  font-weight: 600;
}}

.badge {{
  display: inline-block;
  font-size: 0.75em;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 0.4rem;
  background: #fee2e2;
  color: #991b1b;
}}

.small {{
  font-size: 0.85em;
  color: #555;
}}

a {{
  color: #2563eb;
  text-decoration: none;
}}

a:hover {{
  text-decoration: underline;
}}
</style>
</head>
<body>
"""


def html_footer():
    return "</body></html>"


def is_preprint(citation):
    """
    Returns True if the citation points to arXiv or bioRxiv
    (based on DOI or URL).
    """
    text = " ".join([
        str(citation.get("doi", "")).lower(),
        str(citation.get("url", "")).lower(),
        str(citation.get("title", "")).lower()
    ])

    return any(x in text for x in [
        "arxiv.org",
        "arxiv:",
        "biorxiv.org",
        "bioarxiv",
        "10.1101"
    ])


def generate_html(data):
    out = []
    out.append(html_header("OpenAlex citations not found in Web of Science"))

    out.append(f"""
<h1>OpenAlex citations not found in Web of Science</h1>
<div class="meta">
Generated on {date.today().isoformat()}<br>
Source comparison: <b>OpenAlex → Web of Science (Starter API)</b>
</div>
""")

    missing_total = 0

    for pub in data.get("publications", []):
        citing = pub.get("citations", {}).get("openalex_wos_checked", [])
        missing = [
            c for c in citing
            if not c.get("wos_found") and not is_preprint(c)
        ]

        if not missing:
            continue

        missing_total += len(missing)

        out.append(f"""
<div class="pub">
  <h2>{escape(pub.get("title", "Unknown publication"))}</h2>
  <div class="small">
    DOI: {pub.get("doi", "—") if pub.get("doi", "—") else "—"}<br>
    Journal: {escape(pub.get("journal", "—"))}
  </div>
""")

        for c in missing:
            out.append(f"""
  <div class="citation">
    <div class="citation-title">
      {escape(c.get("title", "Untitled"))}
      <span class="badge">not in WoS</span>
    </div>
    <div class="small">
      Year: {c.get("year", "—")}<br>
      DOI: {"<a href='" + escape(c["doi"]) + "' target='_blank'>" + escape(c["doi"]) + "</a>" if c.get("doi") else "—"}<br>
      OpenAlex ID: {escape(c.get("alex_id", "—"))}
    </div>
  </div>
""")

        out.append("</div>")

    if missing_total == 0:
        out.append("<p><b>All OpenAlex citing works were found in Web of Science.</b></p>")
    else:
        out.append(f"""
<hr>
<p><b>Total OpenAlex citing works NOT found in Web of Science:</b> {missing_total}</p>
""")

    out.append(html_footer())
    return "\n".join(out)


if __name__ == "__main__":
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = generate_html(data)

    Path(OUTPUT_HTML).write_text(html, encoding="utf-8")
    print(f"HTML page written to {OUTPUT_HTML}")
