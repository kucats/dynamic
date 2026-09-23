"""Fail-closed validation for catalog references, hashes and source path leakage."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "project/catalog.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def main() -> None:
    catalog = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("artifacts"), list):
        raise SystemExit("Unsupported catalog schema")
    ids = set()
    linked = set()
    for item in catalog["artifacts"]:
        if item["id"] in ids:
            raise SystemExit(f"Duplicate artifact id: {item['id']}")
        ids.add(item["id"])
        if not HEX64.fullmatch(item.get("source_sha256", "")):
            raise SystemExit(f"Invalid source digest: {item['id']}")
        playback = item.get("playback", {})
        if playback.get("full_movement_authorized") and item["status"].startswith(("provisional", "trial", "incomplete")):
            raise SystemExit(f"Unsafe playback authorization: {item['id']}")
        if not item.get("links"):
            raise SystemExit(f"Artifact has no links: {item['id']}")
        for link in item["links"]:
            rel = Path(link["path"])
            if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "public":
                raise SystemExit(f"Unsafe catalog path: {rel}")
            path = (ROOT / rel).resolve()
            if not path.is_relative_to(ROOT / "public") or not path.is_file():
                raise SystemExit(f"Missing or unsafe public artifact: {rel}")
            if not HEX64.fullmatch(link.get("sha256", "")):
                raise SystemExit(f"Missing artifact digest: {rel}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != link["sha256"]:
                raise SystemExit(f"Artifact hash mismatch: {rel}")
            blob = path.read_bytes()
            if any(marker in blob for marker in (b"/Users/", b"/private/tmp/", b"file://")):
                raise SystemExit(f"Machine-local path leaked in artifact: {rel}")
            if rel.suffix.lower() == ".pdf" and link.get("derivative") is not True:
                raise SystemExit(f"PDF must be explicitly identified as a derivative: {rel}")
            if rel.suffix.lower() == ".pdf" and any(token in rel.name.lower() for token in ("source_part", "original_score", "source-score")):
                raise SystemExit(f"Raw source PDF name not allowed: {rel}")
            linked.add(rel.relative_to("public").as_posix())
    index = (ROOT / "public/index.html").read_text(encoding="utf-8")
    for rel in linked:
        if f'href="{rel}"' not in index:
            raise SystemExit(f"Catalog page does not link artifact: {rel}")
    for base in (ROOT / "public", ROOT / "project"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".omr", ".png", ".jpg", ".jpeg", ".m4a", ".wav"}:
                raise SystemExit(f"Raw page/audio/OMR file is not allowed: {path.relative_to(ROOT)}")
            if not path.is_file() or path.suffix.lower() not in {".html", ".json", ".md", ".csv", ".js", ".css"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(marker in text for marker in ("/Users/", "/private/tmp/", "file://")):
                raise SystemExit(f"Machine-local path leaked: {path.relative_to(ROOT)}")
    horn = json.loads((ROOT / "project/dvorak/symphony-no-8/horn-ii/project.json").read_text(encoding="utf-8"))
    if horn["playback"]["full_movements_authorized"]:
        raise SystemExit("Horn II playback must remain blocked until every movement is audited")
    audits = [
        ("reviews/movement-1-gpt6sol-independent.json", lambda d: d.get("source_pdf_sha256")),
        ("reviews/movement-2-gpt6sol-independent.json", lambda d: d.get("source", {}).get("sha256")),
        ("reviews/movement-3-gpt6sol-independent.json", lambda d: d.get("source", {}).get("sha256")),
        ("reviews/movement-4-gpt6sol-independent.json", lambda d: d.get("source", {}).get("sha256_observed")),
    ]
    for relative, get_hash in audits:
        path = ROOT / "project/dvorak/symphony-no-8/horn-ii" / relative
        audit = json.loads(path.read_text(encoding="utf-8"))
        if get_hash(audit) != horn["source"]["sha256"]:
            raise SystemExit(f"Horn II audit/source mismatch: {relative}")
    print(f"PASS: {len(catalog['artifacts'])} catalog items; {len(linked)} verified artifacts; Horn II playback fail-closed")


if __name__ == "__main__":
    main()
