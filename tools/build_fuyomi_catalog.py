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
    reader_path = ROOT / "public/reader/parts.json"
    reader_parts = json.loads(reader_path.read_text(encoding="utf-8"))["parts"] if reader_path.exists() else []
    mv_num = {"I": "1", "II": "2", "III": "3", "IV": "4"}
    app_cards = []
    for part in reader_parts:
        base = "reader/index.html?part=" + html.escape(part["id"])
        chips = " ".join(
            f'<a class="chip" href="{base}#mv-{html.escape(m["key"])}">{mv_num.get(m["key"], m["key"])}楽章 <small>{m["notes"]}音</small></a>'
            for m in part["movements"]
        )
        pdf = f'<a class="ghost" href="{html.escape(part["pdf"])}">印刷用PDF</a>' if part.get("pdf") else ""
        app_cards.append(
            '<article class="app"><div class="app-head"><img src="assets/dynamic-icon.svg" alt="" width="44" height="44">'
            f'<div><h3>{html.escape(part["title"])}</h3><p>{html.escape(part["subtitle"])} · {html.escape(part["part"])}</p></div></div>'
            f'<p class="st">{html.escape(part["status"])}</p>'
            f'<nav class="chips">{chips}</nav>'
            f'<p class="go"><a class="btn" href="{base}">譜読みを開く</a>{pdf}</p></article>'
        )
    INDEX.write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<title>DYNAMIC 譜読みアプリ</title>'
        '<meta name="description" content="原譜の音符に記譜ドレミを付けて、クリックや通し再生で確かめられる譜読みアプリ">'
        '<meta name="theme-color" content="#0f7cf6"><link rel="icon" href="assets/dynamic-icon.svg" type="image/svg+xml">'
        '<link rel="manifest" href="manifest.webmanifest"><style>'
        ':root{--blue:#0f7cf6;--ink:#10233d;--mute:#5b6f86;--line:#d5e1ee;--grad:linear-gradient(120deg,#1b9bff,#0f7cf6 55%,#2fe3cf)}'
        '*{box-sizing:border-box}body{margin:0;font:16px/1.65 system-ui,-apple-system,"Hiragino Sans","Noto Sans CJK JP","Yu Gothic",sans-serif;color:var(--ink);background:#f3f7fc}'
        '.hero{text-align:center;padding:40px 18px 26px;background:radial-gradient(circle at 80% 0,#d9fbf6 0,transparent 45%),radial-gradient(circle at 10% 10%,#dcecff 0,transparent 50%),#fff;border-bottom:1px solid var(--line)}'
        '.hero img{width:min(300px,70vw);height:auto}.hero p{max-width:640px;margin:10px auto 0;color:var(--mute)}'
        '.wrap{max-width:1040px;margin:0 auto;padding:10px 18px 40px}h2{font-size:21px;margin:30px 0 10px}'
        '.apps{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}'
        '.app{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px 20px;box-shadow:0 8px 24px #0f7cf612}'
        '.app-head{display:flex;gap:12px;align-items:center}.app h3{margin:0;font-size:18px;line-height:1.35}.app-head p{margin:2px 0 0;color:var(--mute);font-size:13.5px}'
        '.st{font-size:12.5px;color:#8a5300;background:#fff6e2;border-radius:10px;padding:6px 10px;margin:12px 0}'
        '.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{border:1px solid #bcd7f5;border-radius:999px;padding:3px 12px;text-decoration:none;color:var(--blue);font-weight:700;font-size:14px}.chip small{color:var(--mute);font-weight:500}'
        '.go{display:flex;gap:10px;align-items:center;margin:14px 0 0}.btn{background:var(--grad);color:#fff;text-decoration:none;font-weight:800;border-radius:12px;padding:9px 18px;box-shadow:0 4px 14px #0f7cf644}'
        '.ghost{color:var(--ink);text-decoration:none;border:1px solid #c5d4e4;border-radius:12px;padding:8px 14px}'
        '.feat{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:8px}.feat div{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 14px;font-size:14px}.feat b{display:block;color:var(--blue)}'
        'details.old{margin-top:30px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 18px}details.old summary{cursor:pointer;font-weight:800}'
        'details.old article{border-top:1px solid var(--line);padding:12px 0}details.old h2{font-size:16px;margin:4px 0}.status{font-size:.8rem;color:var(--mute);margin:0}'
        'details.old a{display:inline-block;margin:0 14px 4px 0;color:#075e9f;font-weight:650}.warning{color:#a84b00;font-weight:650}'
        'footer{color:var(--mute);font-size:.88rem;max-width:1040px;margin:0 auto;padding:0 18px 40px}'
        '</style></head><body>'
        '<header class="hero"><img src="assets/dynamic-logo.svg" alt="DYNAMIC 譜読みアプリ" width="300" height="300">'
        '<p>原譜の音符ひとつひとつに記譜のドレミを付けました。音符をタップすると音が鳴り、▶で通し再生できます。小節番号・F管の読み替え・実音も切り替えられます。</p></header>'
        '<main class="wrap"><h2>譜読みを開く</h2><div class="apps">' + "\n".join(app_cards) + '</div>'
        '<div class="feat"><div><b>記譜ドレミ</b>字の大きさをそろえ、音符と線でつないで表示</div><div><b>タップで試聴・通し再生</b>音の長さデータ入り。テンポ変更・D.S.対応</div>'
        '<div><b>小節番号</b>すべての小節に番号。多小節休みは範囲で表示</div><div><b>スマホ対応</b>拡大・横スクロール、オフラインでも閲覧可</div></div>'
        '<details class="old"><summary>これまでの譜読み資料（Fuyomi カタログ）</summary>'
        '<p>再利用ツールは tools/、曲・パート別の譜読み記録は project/、閲覧用HTML/PDFは artifacts/ に整理しています。検証状態と再生許可は別に表示しています。</p>'
        + "\n".join(cards)
        + '<article><h2>作曲家別ガイド</h2><p>先行する譜読み結果と追加の試作PDF/HTMLです。各ガイドに記載された監査状態と制約を確認してください。</p>'
        '<ul>' + "\n".join(composer_cards) + '</ul></article></details></main>'
        + '<footer><p>原譜PDF・生のページ画像・OMRデータはこのサイトに含めていません（譜面は注釈付きの派生画像として表示）。合成音は録音と同期していません。</p></footer>'
        '<script>if("serviceWorker"in navigator&&location.protocol==="https:")navigator.serviceWorker.register("sw.js").catch(()=>{});</script></body></html>\n',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
