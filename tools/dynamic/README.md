# DYNAMIC 譜読みパイプライン

原譜PDF（コミットしない）から、音符ごとの記譜ドレミ・音価・小節番号を持つ閲覧データを作り、`public/reader/` の譜読みアプリで表示・再生します。

| ファイル | 役割 |
| --- | --- |
| `common.py` | 五線検出、音名・移調（ホルンの管）・綴りの計算 |
| `cand.py` | 符頭候補の検出と候補オーバーレイ（読み取りの下書き） |
| `zoom.py` / `check.py` | サブエージェント用：段の拡大図（音高ガイド付き）と読み取り結果の重ね描き |
| `check_rhythm.py` | 音価・開始位置が拍子からはみ出していないかの検査 |
| `barlines.py` / `bars_overlay.py` | 縦線（小節線）の自動検出・多小節休み判定・小節番号の推定と確認図 |
| `build_reader.py` | `project/**/dynamic/` のデータ＋原譜から `public/reader/data/<id>.json` を生成 |
| `validate_reader.py` | 閲覧データの整合性検査（小節番号と音符、タイムライン、画像形式、パス漏れ） |
| `render_pdfs.py` | 閲覧アプリの印刷モードからA3のPDFを作成 |
| `prompts/` | サブエージェントに渡した指示（00が全体の手順） |

## 再現手順

```sh
python3 -m pip install opencv-python-headless numpy Pillow playwright   # Chromium は playwright に付属のものを使用
python3 tools/dynamic/build_reader.py --pdf "/path/to/ホルン1～4.pdf" --work work
python3 tools/dynamic/validate_reader.py
python3 -m http.server 8765 -d public &      # 別ターミナル
python3 tools/dynamic/render_pdfs.py
python3 tools/build_catalog.py && python3 tools/validate_catalog.py
```

原譜PDFのSHA-256は各 `part.json` の `source.sha256` と一致する必要があります。
`public/reader/data/*.json` には注釈表示用に切り出した段の画像（派生画像、16階調PNG）が埋め込まれます。原譜PDF・ページ全体の画像は含みません。

## データ形式（project/**/dynamic/pages）

`notes_pNN.json` の `notes[]`: `sys`（ページ内の段）, `x`/`y`（300dpiのページ座標）, `pitch`（印刷どおりの記譜音、例 `Bb4`）, `clef`, `bar`, `dur`/`off`（全音符=1の分数）, `tie_from_prev`, `uncertain`, 任意で `horn_key`（管）と `notation: "old-bass-clef"`。
`bars_pNN.json`: 段ごとの小節区間 `{xa, xb, label}`（多小節休みは `"61–64"`）。
