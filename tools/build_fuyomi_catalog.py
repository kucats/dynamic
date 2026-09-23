"""Build the static catalog page and bind artifact hashes from the manifest."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "project/catalog.json"
INDEX = ROOT / "public/index.html"


def main() -> None:
    catalog = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for item in catalog["artifacts"]:
        for link in item["links"]:
            path = (ROOT / link["path"]).resolve()
            if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
                raise SystemExit(f"Missing or unsafe artifact: {link['path']}")
            link["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    MANIFEST.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cards = []
    for item in catalog["artifacts"]:
        links = " ".join(
            f'<a href="{html.escape(Path(link["path"]).relative_to("public").as_posix())}">'
            f'{html.escape(link["label"])}</a>'
            for link in item["links"]
        )
        ready = item["playback"]["full_movement_authorized"]
        warning = "Continuous playback authorized" if ready else "Review incomplete · continuous playback not authorized"
        cards.append(
            '<article><p class="status">' + html.escape(item["status"]) + '</p>'
            '<h2>' + html.escape(item["work"]) + ' · ' + html.escape(item["part"]) + '</h2>'
            '<p>' + html.escape(item["summary"]) + '</p>'
            '<p class="warning">' + html.escape(warning) + '</p><nav>' + links + '</nav></article>'
        )
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    composer_catalog = json.loads((ROOT / "public/catalog.json").read_text(encoding="utf-8"))
    composer_cards = []
    seen_works = set()
    for item in composer_catalog["items"]:
        key = (item["composer_key"], item["work_key"])
        if key in seen_works:
            continue
        seen_works.add(key)
        href = f"composers/{key[0]}/{key[1]}/index.html"
        composer_cards.append(
            f'<li><a href="{html.escape(href)}">'
            f'{html.escape(item["composer"])} — {html.escape(item["work"])}</a></li>'
        )
    INDEX.write_text(
        '<!doctype html><html lang="ja"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Fuyomi 譜読みカタログ</title><style>'
        'body{max-width:1000px;margin:32px auto;padding:0 18px;font:16px/1.6 system-ui,"Yu Gothic",sans-serif;color:#172a3d;background:#f4f7fa}'
        'h1{line-height:1.3}article{background:white;border:1px solid #d5dfe6;border-radius:12px;padding:18px 22px;margin:16px 0}'
        '.status{font-size:.82rem;color:#566a7a}a{display:inline-block;margin:0 16px 4px 0;color:#075e9f;font-weight:650}'
        '.warning{color:#a84b00;font-weight:650}footer{color:#566a7a;font-size:.9rem}'
        '</style><header><h1>Fuyomi 譜読みカタログ</h1>'
        '<p>再利用ツールは tools/、曲・パート別の譜読み記録は project/、閲覧用HTML/PDFは artifacts/ に整理しています。'
        '検証状態と再生許可は別に表示しています。</p></header>'
        + "\n".join(cards)
        + '<article><h2>作曲家別ガイド</h2><p>先行する譜読み結果と追加の試作PDF/HTMLです。各ガイドに記載された監査状態と制約を確認してください。</p>'
        '<ul>' + "\n".join(composer_cards) + '</ul></article>'
        + '<footer><p>原譜PDF・生のページ画像・OMRデータはこのカタログに含めていません。合成音は録音と同期していません。</p></footer></html>\n',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
