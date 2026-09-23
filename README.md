# dynamic · 譜読みカタログ

vEdit の Fuyomi 特別モードから、再利用可能な譜読みワークフローと今回の譜読みデータ・成果物をこのリポジトリへ移しました。元の vEdit 作業ツリーには依存せず、ここで再現・監査できる構成です。

## 配置

- `tools/` — Fuyomi 処理、静的カタログ生成、検証コードとテスト
- `project/<作曲者>/<作品>/<パート>/` — 音高・長さ・ポジション、出典ハッシュ、レビュー、監査状態、処理記録
- `public/` — 閲覧用 HTML と譜読み注釈 PDF。元譜 PDF、原ページ画像、OMR 生データ、個人録音は含みません

`public/catalog.json` は従来の作曲家別ガイドを、`project/catalog.json` は Fuyomi 成果物と監査・再生状態を記録します。トップページから両方を閲覧できます。

## 再現と検証

Python 3.11 以降が必要です。PDF 処理には Pillow、pypdf、ReportLab を使います。Audiveris と Poppler は候補認識・ページ描画を行う場合だけ必要です。

```sh
python3 -m pip install Pillow pypdf reportlab
python3 tools/build_catalog.py
python3 tools/validate_catalog.py
python3 -m unittest discover -s tests -v
python3 -m tools.fuyomi --help
node --check tools/fuyomi/player.js
```

個々の譜読みの正確さは、該当する `project/` 内の原譜照合記録を確認してください。ツールテストの成功だけで音符監査や再生許可を意味しません。
