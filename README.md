# DYNAMIC 譜読みアプリ

`public/` がそのまま公開サイトです（`dynamic.oke.jp`）。Cloudflare Workers の設定は `wrangler.jsonc` にあり、アップロード対象は `public/` 以下のみです。

- `public/index.html` — DYNAMIC のトップ。パートまたは作曲家から譜読みを選び、従来の Fuyomi カタログにも移動できます
- `public/reader/` — 譜読みアプリ本体。ホルンの記譜ドレミ・F管読み・実音、トロンボーンの音名・基本ポジション、タップ試聴・通し再生・ロングトーン練習・小節番号の位置切り替え・小節ジャンプ・拡大・印刷に対応。データは `public/reader/data/<id>.json`
- `worker/index.js` — Cloudflare Access ログイン（`/login`）とユーザー・パートごとの練習メモ API（R2）。設計と設定手順は `docs/reader-memos.md`
- 作り方と再現用のプロンプト・コード：`tools/dynamic/README.md`、`tools/dynamic/prompts/`
- 読み取りデータ：`project/dvorak/symphony-no-8/horn-ii/dynamic/`、`project/dvorak/symphony-no-8/horn-iii/dynamic/`

静的ファイルだけで動きます（ビルド不要・外部CDN不使用）。Cloudflare Workers の Static Assets として `public/` を配信します。認証済みの開発環境から `npx wrangler deploy` でデプロイできます。

将来の音声追従では、Workers を静的配信と WebSocket のシグナリング/API 入口に使えます。WebRTC の音声処理と TURN は別サービスとして扱い、実機・ネットワーク検証後に接続します。現時点の音声追従実験パッケージは `tools/score_following/` にあり、本番サイトには含まれません。

Cloudflare のデプロイ手順と将来の音声経路は [`docs/deployment/cloudflare-workers.md`](docs/deployment/cloudflare-workers.md) を参照してください。

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
