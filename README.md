# dynamic · 譜読みカタログ

vEdit の Fuyomi 特別モードから、再利用可能な譜読み処理と今回の譜読みデータ・監査記録・成果物をこのリポジトリへ移しました。実行エンジンも `tools/fuyomi/` にあり、vEdit パッケージに依存しません。

## 配置

- `tools/` — Fuyomi処理、静的カタログ生成、検証コードとテスト
- `project/<作曲者>/<作品>/<パート>/` — 音高・長さ・ポジション、出典ハッシュ、レビュー、監査状態、処理記録
- `public/` — 閲覧用HTMLと譜読み注釈PDF。元譜PDF、原ページ画像、OMR生データ、個人録音は含みません

`public/catalog.json` は作曲家別の譜読みガイドを、`project/catalog.json` はFuyomi成果物と再生・監査状態を記録します。トップページからDvořákのトロンボーン各パート、Horn II、VerdiのNabuccoを閲覧できます。

## 再現と検証

Python 3.11以降が必要です。PDF処理にはPillow、pypdf、ReportLabを使います。AudiverisとPopplerは候補認識・ページ描画を行う場合だけ必要です。

```sh
python3 -m pip install Pillow pypdf reportlab
python3 tools/build_catalog.py
python3 tools/validate_catalog.py
python3 -m unittest discover -s tests -v
python3 -m tools.fuyomi --help
node --check tools/fuyomi/player.js
```

個々の譜読みの正確さは、該当する `project/` の原譜照合記録を確認してください。ツールテストの成功だけで音符監査や再生許可を意味しません。
