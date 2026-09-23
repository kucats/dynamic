#!/usr/bin/env python3
"""Build static HTML pages for the composer-indexed score-reading catalog."""

from __future__ import annotations

import html
import posixpath
from pathlib import Path

from catalog_lib import load_catalog, repo_file


ROOT = Path(__file__).resolve().parents[1]
CSS = "public/assets/catalog.css"


def url_from(page_path: str, target_path: str) -> str:
    return posixpath.relpath(target_path, posixpath.dirname(page_path))


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def shell(title: str, description: str, stylesheet: str, home_url: str, body: str) -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(description)}">
  <title>{esc(title)} — Score Reading Catalog</title>
  <link rel="stylesheet" href="{esc(stylesheet)}">
</head>
<body>
  <header class="site-header"><a href="{esc(home_url)}">Score Reading Catalog</a></header>
  <main>{body}</main>
  <footer>Score-derived study material. Check the listed status and limitations before playing.</footer>
</body>
</html>
'''


def entry_html(item: dict, page_path: str) -> str:
    pdfs = [artifact for artifact in item["artifacts"] if artifact["kind"] == "PDF"]
    pdf_path = pdfs[0]["path"]
    pdf_url = url_from(page_path, pdf_path)
    stylesheet = url_from(page_path, CSS)
    home_url = url_from(page_path, "public/index.html")
    limits = "\n".join(f"<li>{esc(value)}</li>" for value in item["limitations"])
    sources = "\n".join(
        f'<li>{esc(source["label"])} — SHA-256 <code>{esc(source["sha256"])}</code> (input not included)</li>'
        for source in item["sources"]
    )
    body = f'''<nav class="breadcrumbs"><a href="{esc(home_url)}">Catalog</a> / {esc(item['composer'])} / {esc(item['work'])}</nav>
<article>
  <p class="status status-{esc(item['review_status'])}">{esc(item['review_status'])}</p>
  <h1>{esc(item['composer'])}: {esc(item['work'])}</h1>
  <h2>{esc(item['instrument'])}</h2>
  <p class="summary">{esc(item['summary'])}</p>
  <p class="actions"><a class="button" href="{esc(pdf_url)}" download>Download PDF</a>
  <a href="{esc(pdf_url)}">Open PDF directly</a></p>
  <section><h3>Limitations</h3><ul>{limits}</ul></section>
  <details><summary>Source provenance</summary><ul>{sources}</ul></details>
  <object class="pdf-viewer" data="{esc(pdf_url)}" type="application/pdf" aria-label="{esc(item['instrument'])} annotated reading PDF">
    <p>Your browser cannot display the PDF inline. <a href="{esc(pdf_url)}">Download the reading guide.</a></p>
  </object>
</article>'''
    return shell(f"{item['composer']} — {item['work']} — {item['instrument']}", item["summary"], stylesheet, home_url, body)


def build(root: Path = ROOT) -> list[Path]:
    catalog = load_catalog(root)
    items = catalog["items"]
    built: list[Path] = []
    css_file = root / CSS
    css_file.parent.mkdir(parents=True, exist_ok=True)
    css_file.write_text('''
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #172a36; background: #f5f8fa; }
* { box-sizing: border-box; }
body { margin: 0; line-height: 1.55; }
a { color: #075d82; }
.site-header { padding: 1rem max(calc((100% - 72rem) / 2), 1.25rem); background: #102f42; }
.site-header a { color: white; text-decoration: none; font-weight: 700; }
main { max-width: 72rem; margin: 2rem auto; padding: 0 1.25rem; }
footer { max-width: 72rem; margin: 2rem auto; padding: 1rem 1.25rem 2rem; color: #526673; font-size: .9rem; }
.breadcrumbs { color: #526673; font-size: .92rem; }
h1 { margin-bottom: .4rem; line-height: 1.2; }
h2 { margin-top: .4rem; color: #31566a; }
.catalog-card, article { padding: 1.25rem; margin: 1rem 0; border: 1px solid #d8e2e8; border-radius: .7rem; background: white; }
.catalog-card h2 { margin: 0 0 .4rem; }
.status { display: inline-block; border-radius: 999px; padding: .15rem .7rem; text-transform: uppercase; font-size: .76rem; font-weight: 750; letter-spacing: .04em; }
.status-reviewed { background: #d8f2e4; color: #145934; }
.status-draft { background: #fff0cf; color: #784700; }
.summary { font-size: 1.06rem; }
.button { display: inline-block; padding: .55rem .9rem; margin-right: .7rem; border-radius: .4rem; background: #075d82; color: white; text-decoration: none; font-weight: 700; }
.actions { margin: 1rem 0; }
code { overflow-wrap: anywhere; }
.pdf-viewer { width: 100%; height: min(78vh, 60rem); margin-top: 1rem; border: 1px solid #cbd7df; }
@media (max-width: 40rem) { main { margin-top: 1rem; } .pdf-viewer { height: 65vh; } }
'''.lstrip(), encoding="utf-8")
    built.append(css_file)

    grouped: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        grouped.setdefault((item["composer_key"], item["work_key"]), []).append(item)

    cards = []
    for (composer_key, work_key), work_items in sorted(grouped.items()):
        first = work_items[0]
        work_page = f"public/composers/{composer_key}/{work_key}/index.html"
        stylesheet = url_from(work_page, CSS)
        item_links = []
        for item in work_items:
            html_url = url_from(work_page, item["html"])
            pdf = next(a for a in item["artifacts"] if a["kind"] == "PDF")
            pdf_url = url_from(work_page, pdf["path"])
            item_links.append(
                f'''<li><span class="status status-{esc(item['review_status'])}">{esc(item['review_status'])}</span>
                <strong>{esc(item['instrument'])}</strong> — <a href="{esc(html_url)}">HTML guide</a> · <a href="{esc(pdf_url)}">PDF</a>
                <p>{esc(item['summary'])}</p></li>'''
            )
        work_body = f'''<nav class="breadcrumbs"><a href="../../../index.html">Catalog</a></nav>
<h1>{esc(first['composer'])}</h1><h2>{esc(first['work'])}</h2>
<section class="catalog-card"><h3>Reading guides</h3><ul>{''.join(item_links)}</ul></section>'''
        work_file = repo_file(root, work_page)
        work_file.parent.mkdir(parents=True, exist_ok=True)
        work_file.write_text(shell(f"{first['composer']} — {first['work']}", "Annotated trombone score-reading guides", stylesheet, "../../../index.html", work_body), encoding="utf-8")
        built.append(work_file)
        cards.append(
            f'''<section class="catalog-card"><h2><a href="{esc(url_from('public/index.html', work_page))}">{esc(first['composer'])} — {esc(first['work'])}</a></h2>
            <p>{len(work_items)} reading guides</p></section>'''
        )
        for item in work_items:
            page_file = repo_file(root, item["html"])
            page_file.parent.mkdir(parents=True, exist_ok=True)
            page_file.write_text(entry_html(item, item["html"]), encoding="utf-8")
            built.append(page_file)

    root_body = f'''<h1>{esc(catalog['title'])}</h1>
<p>Browse annotated reading guides by composer and work. Each item links to an HTML page and its PDF.</p>
{''.join(cards)}'''
    root_page = root / "public" / "index.html"
    root_page.write_text(shell(catalog["title"], "Composer-indexed annotated score-reading guides", "assets/catalog.css", "index.html", root_body), encoding="utf-8")
    built.append(root_page)
    return built


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(ROOT))
