#!/usr/bin/env python3
"""Render print PDFs of the DYNAMIC reader (A3 portrait) with headless Chromium.

Serve public/ first:  python3 -m http.server 8765 -d public
Then:                 python3 tools/dynamic/render_pdfs.py [--base http://127.0.0.1:8765/]
"""
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
ROWS = {"dvorak8-horn2": "w", "dvorak8-horn3-mvt3": "wfs", "dvorak8-trombone1": "wp", "dvorak8-viola": "w",
        "verdi-nabucco-trombone2": "wp"}


async def main(base: str, selected_parts: list[str] | None = None) -> None:
    parts = json.loads((ROOT / "public/reader/parts.json").read_text(encoding="utf-8"))["parts"]
    if selected_parts:
        missing = set(selected_parts) - {part["id"] for part in parts}
        if missing:
            raise SystemExit(f"unknown reader part(s): {', '.join(sorted(missing))}")
        parts = [part for part in parts if part["id"] in selected_parts]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for part in parts:
            if not part.get("pdf"):
                continue
            pg = await b.new_page(viewport={"width": 1200, "height": 1600})
            await pg.goto(f"{base}reader/index.html?part={part['id']}&print=1&rows={ROWS.get(part['id'], 'w')}&size=m")
            await pg.wait_for_function("window.__dynamic")
            await pg.wait_for_timeout(800)
            out = ROOT / "public" / part["pdf"]
            out.parent.mkdir(parents=True, exist_ok=True)
            await pg.pdf(path=str(out), format="A3", print_background=True,
                         margin={"top": "9mm", "bottom": "9mm", "left": "8mm", "right": "8mm"})
            print("wrote", out.relative_to(ROOT))
        await b.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765/")
    ap.add_argument("--part", action="append", help="render only this reader part; may be repeated")
    args = ap.parse_args()
    asyncio.run(main(args.base, args.part))
