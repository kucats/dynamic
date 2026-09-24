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

## 中間データから再生成する（途中からやり直す）

各段階の出力はそのまま次の段階の入力なので、どこからでもやり直せます。

| 手元にあるもの | やること |
| --- | --- |
| 原譜PDFだけ | `pdftoppm -r 300 -gray`（トロンボーンは `-r 340`）でページを `work/pNN.png` に描画 → `cand.py` → サブエージェントに `prompts/01`（ホルン）または `prompts/11`（トロンボーン）→ `02` → `03` |
| `work/final_pNN.json`（音高・音価） | `bars_overlay.py` で小節線を確認し `prompts/03` で小節番号を付ける |
| `final_pNN.json` と `bars_pNN.json` | `project/.../dynamic/pages/notes_pNN.json`・`bars_pNN.json` にコピー（PDFのページ番号で2桁） → `build_reader.py --pdf ...` |
| `project/**/dynamic/`（リポジトリにあるデータ） | 原譜PDFを用意して `build_reader.py --pdf ...` を実行するだけ。閲覧データ・PDFを完全に再現できます |
| `public/reader/data/<id>.json` だけ | 表示・再生・PDF出力はこれだけで可能（原譜不要）。サーバーで `public/` を配信して `render_pdfs.py` |

- 読み取りの修正は `notes_pNN.json`（音高 `pitch`、音価 `dur`、開始位置 `off`、小節 `bar`、タイ `tie_from_prev`）を直して `build_reader.py` を再実行します。
- 小節番号の修正は `bars_pNN.json` の `label` を直します。`validate_reader.py` が、音符とその小節番号の食い違いを検出します。
- 楽器ごとの表示：ホルンは記譜ドレミ（任意でF管読み・実音）、トロンボーン（`"instrument": "trombone"`）はドイツ式音名（H＝シ）＋B♭テナーの基本ポジション（`common.py` の `TROMBONE_POS`）。
- ラベルの配置：1列に収まらない箇所は、音の高い方を上段、低い方を下段（少し小さい字）に分けます（`public/reader/app.js` の `layout`）。
- 未解決の読みは `uncertain` に残し、生成 JSON では `unc` と `review_items` に出力します。`review_items[].playback` は `false` で、アプリは該当音を単音試聴・ロングトーン・通し再生から除外します。
- 既存の切り出し画像を保ったまま出典・制約・要確認情報だけ更新する場合は、`python3 tools/dynamic/build_reader.py --refresh-metadata project/<composer>/<work>/<part>/dynamic` を使います。完全な画像再生成には元PDFが必要です。
