# DYNAMIC 譜読み — オーケストレーション手順（再現用プロンプト）

メインのエージェントが次の順で作業し、ページ単位の読み取りはサブエージェント（1ページ＝1エージェント）に並列で任せました。
各サブエージェントは同じ会話を続けて使い、段階ごとに追加の指示ファイルを渡しています。

## 0. 準備（メイン）
1. 原譜PDFのページを 300dpi グレースケールで `work/pNN.png` に描画する（`pdftoppm -r 300 -gray`）。
2. `python3 tools/dynamic/cand.py 9 10 11 12 13 14 15` で符頭の候補（塗り／白抜き）と候補オーバーレイを作る。
3. 対象パート・ページと楽章の対応を決める（例：ホルン2番 = PDF 9〜15ページ）。

## 1. 音高の読み取り（サブエージェント × ページ数）
サブエージェント起動時のプロンプト（PAGEを置き換え、ページの位置づけを一言添える）:

> Read `tools/dynamic/prompts/01_transcribe_page.md` and carry out that task for PAGE = 9
> (this page is the first page of the Corno II part: title plus movement I).
> Work in the repository working directory. Only write work/final_p9.json plus your own zoom/check images.

→ 出力 `work/final_pNN.json`（音高・位置・タイ・要確認フラグ）。メインは要確認項目を原譜で目視確認する。

## 2. リズム（同じサブエージェントに続けて）
> Follow-up for your page 9: add rhythm and timing data for audio playback.
> Read `tools/dynamic/prompts/02_rhythm_timing.md` and do it for PAGE = 9.
> In "meters", also include the meter in force at the first bar of the page even if it is not reprinted there.

→ `dur`（音価）・`off`（小節内の開始位置）・`meta`（拍子・テンポ・管の指定・反復）。`check_rhythm.py` で小節からのはみ出しを検査。

## 3. 小節番号（同じサブエージェントに続けて）
メインが `bars_auto_pNN.json`（縦線の自動検出＋音符の小節番号からの推定）を作ってから:
> Next task for page 9: give every bar its bar number (barline segments).
> Read `tools/dynamic/prompts/03_bar_numbers.md` and do it for PAGE = 9, writing work/bars_p9.json.

→ 全小節の区間と番号（多小節休みは「61–64」）。

## 4. 統合（メイン）
1. `work/final_pNN.json` → `project/<作曲者>/<作品>/<パート>/dynamic/pages/notes_pNN.json`、
   `work/bars_pNN.json` → `.../pages/bars_pNN.json` にコピー。
2. `part.json` に楽章・ページ・拍子・テンポ（記号のない箇所は目安）・D.S.の順序・管の指定を書く。
3. `python3 tools/dynamic/build_reader.py --pdf <原譜PDF>` で `public/reader/data/<id>.json` を生成。
4. `python3 tools/dynamic/validate_reader.py`、`python3 -m unittest discover -s tests`。
5. `python3 -m http.server 8765 -d public` を起動して `python3 tools/dynamic/render_pdfs.py` で印刷用PDFを作る。
6. `python3 tools/build_catalog.py` でトップページ（DYNAMIC）を再生成し、`python3 tools/validate_catalog.py`。

## 注意（今回の作業で分かったこと）
- キュー（他楽器の小さい音符）は最も混入しやすい。音符が小さい／同じ小節に全休符がある／楽器名が書いてある、で判断する。
- ♭・♯・♮は小節内で持続し、タイで次の小節へ持ち越す。ユーザーから「フラットを落としている」と指摘があったので重点確認。
- 旧記譜のヘ音記号（ホルン）は1オクターブ下に書かれている。前後の自然倍音の流れで判断する。
- 縦線の自動検出は符幹を誤検出しやすい。小節番号は必ず人（エージェント）が原譜の印刷番号と多小節休みの数で確認する。
