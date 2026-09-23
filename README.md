# DYNAMIC 譜読みアプリ

`public/` がそのまま公開サイトです（dynamic.oke.jp 想定。公開対象は `public/` 以下のみ）。

- `public/index.html` — トップ（DYNAMIC）。譜読みアプリの各パートと、従来の Fuyomi カタログへの入口
- `public/reader/` — 譜読みアプリ本体。原譜の各段に記譜ドレミ（任意でF管読み・実音）を付け、タップ試聴・通し再生・小節番号・小節ジャンプ・拡大・印刷に対応。データは `public/reader/data/<id>.json`
- 作り方と再現用のプロンプト・コード：`tools/dynamic/README.md`、`tools/dynamic/prompts/`
- 読み取りデータ：`project/dvorak/symphony-no-8/horn-ii/dynamic/`、`project/dvorak/symphony-no-8/horn-iii/dynamic/`

静的ファイルだけで動きます（ビルド不要・外部CDN不使用）。任意のWebサーバーで `public/` を配信してください。

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
