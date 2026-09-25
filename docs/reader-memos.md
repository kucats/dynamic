# 譜読みアプリの練習メモ（Cloudflare Access ログイン）

対象：`/reader/?part=dvorak8-trombone1`（`MEMO_PARTS` で他のパートにも広げられます）

## 目的

ログインした人ごと・パートごとに、楽章と小節番号に紐づいた練習メモを残します。例：1楽章59小節に「前の小節で息を吸う」。
「練習記号」は原譜に印刷済みの H・J などのことです。メモの入力項目ではなく、独自の記号も追加しません。
メモは個人の練習記録です。転記・監査データ（`public/reader/data/*.json`）は変更せず、監査状態や再生にも影響しません。

## 構成

```
ブラウザ ──/reader/*（静的）───────────────► Workers Assets（public/）
        ──/login ──► Cloudflare Access ──► Worker：JWT を検証し dyn_session Cookie を発行 → identity を確認する完了画面 → 元のページへ戻す
        ──/api/me, /api/memos/<part> ─────► Worker：Cookie の JWT を検証 → R2 memos/v1/<user>/<part>.json
```

- **Worker スクリプトが動くのは `/login` `/logout` `/api/*` だけ**です（`wrangler.jsonc` の `assets.run_worker_first`）。それ以外は今までどおり静的配信です。
- **ログイン**：Access で守るのは `/login` だけ。Access が付ける `Cf-Access-Jwt-Assertion` を Worker が検証し（RS256、`aud`・`iss`・`exp`、チームの公開鍵）、同じトークンを `dyn_session`（`HttpOnly; Secure; SameSite=Lax; Path=/`）に入れます。これでサイト全体（Worker 全体）が同じログイン状態を共有します。有効期限は Access のセッション期限（JWT の `exp`）と同じです。
- **ログアウト**：`/logout` が Cookie を消して Access のログアウト（`/cdn-cgi/access/logout`）に移ります。
- **保存先**：R2 バケット `dynamic-memos` に、ユーザーごと・パートごとに 1 つの JSON ファイルを置きます。キーは `memos/v1/<user>/<part>.json` です。`<user>` は Access の `sub` から作った SHA-256 の先頭 128 ビットなので、キーにメールアドレスは入りません。
- **日時**：`createdAt`・`updatedAt` はサーバーが UTC の ISO 8601 で記録します。クライアントから送った日時と ID は使いません。
- **同時保存**：R2 の etag を条件にして書き込みます（最大 3 回再試行）。2 台の端末から同時に保存しても、どちらかのメモが消えることはありません。
- **安全対策**：更新系（POST/PUT/DELETE）では `Origin` が同じサイトであることと `Content-Type: application/json` を必須にしています。パート ID は `parts.json` に載っているものだけ受け付けます。メモは 1 件 2000 文字まで、1 パート 500 件までです。Service Worker は `/api/*`、`/login`、`/logout` をキャッシュしません。
- **設定していないとき**：`ACCESS_TEAM_DOMAIN`、`ACCESS_AUD`、R2 のどれかが無いと `/api/me` は `{"enabled":false}` を返し、リーダーはメモ用のボタンを出しません。

### ファイル形式（`dynamic-memos/1`）

```json
{
 "schema": "dynamic-memos/1",
 "part": "dvorak8-trombone1",
 "user": { "key": "3f2a…（sub のハッシュ）", "email": "player@example.com" },
 "updatedAt": "2026-09-24T12:01:00.000Z",
 "memos": [
  {
   "id": "q7X…", "createdAt": "2026-09-24T12:00:00.000Z", "updatedAt": "2026-09-24T12:01:00.000Z",
   "text": "前の小節で息を吸う", "rehearsal": "", "kind": "issue",
   "anchor": { "mvt": "I", "bar": 59, "page": null, "sys": null, "x": null, "y": null, "note": null }
  }
 ]
}
```

新規作成時にブラウザが送る `anchor` は `{mvt, bar}` だけです。ページ・段・座標・音符 ID は入力も保存要求もしません。Worker の既存形式との互換性のため、返却・保存される JSON には省略項目が `null`、`rehearsal` が空文字として入ります。`kind` は `note`（メモ）・`issue`（課題）・`good`（できた）です。API・R2 の形式や認証方式は変更しません。

**既存メモの互換性**：`mvt` と `bar` を常に優先し、旧 x・y は表示に使いません。段の再構成やズームに依存せず、小節の下に表示します。小節番号のない旧メモだけは、旧ページ・段・x が単一小節に一意に入る場合に限って解決します。複数小節の休みなど特定できないもの、明示された小節が譜面に存在しないものは、勝手に別小節へ移さず一覧に「位置不明」として残します。編集・削除は引き続き可能です。旧 `rehearsal` は表示せず、既存メモを編集するときだけ非表示の互換情報として保持します。読込時に R2 データを一括書き換えたり、旧メモを削除したりしません。

### API

| メソッドとパス | 内容 |
| --- | --- |
| `GET /api/me` | `{enabled, loggedIn, email, memoParts, expiresAt}` |
| `GET /api/memos/<part>` | 自分のメモの JSON ファイル（まだ無ければ空） |
| `POST /api/memos/<part>` | メモを作る `{text, kind, anchor: {mvt, bar}}`。返り値は日時と ID の入ったメモ |
| `PUT /api/memos/<part>/<id>` | メモを直す（`createdAt` はそのまま、`updatedAt` を更新） |
| `DELETE /api/memos/<part>/<id>` | メモを消す |

## 画面の使い方

**小節をクリック／タップ →「この59小節目にメモを追加」→ 入力 → 保存**が基本操作です。「59小節目のスコアを見る」と同じ小節メニューに入っています。上部のメモ／ペンボタン、ペンモード、自由座標への配置、空白ダブルタップでのメモ作成は廃止しました。

- **小節の選択**：小節番号または音符以外の譜面部分から開きます。複数小節の休み（例：61〜76）ではメニュー内の「対象の小節」で65などの正確な小節を指定できます。範囲外・小数・空欄は保存先にできません。小節にキーボードでフォーカスして Enter／Space でもメニューを開けます。
- **入力画面**：楽章・小節は選択先で固定され、内容と種類だけを入力します。練習記号欄はありません。作成・更新日時を表示し、既存メモは編集・削除できます。保存失敗時は入力内容を残します。
- **表示**：譜面・譜読みラベルの下の固定欄に表示します。小節線と同じ位置の列を使い、同じ小節への複数メモは縦に並びます。長い内容は3行までのプレビューで、押すと全文を編集できます。印刷済みの H・J や音符は覆いません。ズーム・小節番号の上下／オフ切替でも紐付けは不変です。保存・再描画時も段の横スクロール位置を保持します。
- **一覧・アカウント**：小節メニューから「この小節のメモを見る」または「練習メモ一覧」を開きます。全体一覧は「設定」にもあり、ログイン状態・メールアドレスは設定内にまとめました。一覧から移動・編集・ログアウトできます。
- **未ログイン**：小節メニューの追加からログイン案内を開きます。Googleログイン後の確認画面を経て元のパートに戻ると、対象小節の入力を再開します。復帰用の `{part, anchor}` だけを一時的に `sessionStorage` に入れます（メモ内容は保存しません）。ブラウザが保存を拒否した場合は元の譜面へ戻るだけです。
- **既存機能**：音符クリックは試聴、音符のダブルクリック／右クリックはロングトーンのままです。総譜は実際に開くまでデータを取得しません。印刷モードではメモAPIを取得せず、メモも印刷しません。

コードは `public/reader/memo.js`・`memo-model.mjs`・`memo.css` に分離しています。`app.js` の小さな拡張フック `__dynamic.ext.addBarMenuHook` が小節別の項目を提供し、`addSystemHook` が段の下の固定欄を追加します。既存のSVG・音符フックはそのままです。

### 検証

`node --test tests/reader/*.test.mjs tests/worker/*.test.mjs` で小節アンカー・旧形式互換・既存Worker/APIを検証します。`python tests/reader/memo-browser.py --out /tmp/memo-evidence` はローカルHTTP配信と合成APIを使うPlaywrightテストです。Chromiumは事前に `python -m playwright install chromium` で用意します。PC1440px／スマホ390pxで小節メニュー、CRUD、複数小節休み、保存エラー・401、ズームと固定表示、旧メモ、音符操作を確認し、画像と `results.json` を出力します。さらに通常のURL配信では無効化・対象外パート・印刷・ログイン復帰・総譜への小節引渡しを確認します。Google/Access/R2への本番通信は行いません。

制限されたコンテナ用の `--offline --browser /usr/bin/chromium` は同じソースをインラインで実行します。これは画面操作の検証で、ネイティブなES module読込やページ遷移の検証には数えません。

## 設定手順（運用者）

1. R2 バケットを作る：`npx wrangler r2 bucket create dynamic-memos`
2. Zero Trust → Access → Applications で **Self-hosted** のアプリを作る。
   - ドメイン：`dynamic.oke.jp`、パス：`login`（`/login` だけを守る）
   - ポリシー：`DYNAMIC Google accounts`（Allow / All authenticated users）を割り当てます。
   - Login methods：Google のみを有効にします。現在は Google アカウントを持つ人なら誰でもログインできます。
   - セッションの期間：24 時間に設定済みです。
3. アプリの **Application Audience (AUD) Tag** とチームドメイン（`<team>.cloudflareaccess.com`）を、`wrangler.jsonc` の `vars.ACCESS_AUD` と `vars.ACCESS_TEAM_DOMAIN` に入れる（どちらも秘密情報ではありません）。
4. `npx wrangler deploy`。`https://dynamic.oke.jp/login` を開いて認証し、元のページに戻ってから、小節をクリックしてメモが保存できることを確かめます。

現在の実環境：fs-admin Cloudflare アカウント（ID `29e8010570c1cef4764ba466ab6ebb55`）に R2 バケット `dynamic-memos` と Access アプリ `DYNAMIC Reader Memo Login` を作成済みです。アプリの対象は `dynamic.oke.jp/login`、IdP は Google のみ、ポリシーは全認証済みユーザーを許可します。管理者による承認画面は将来の追加予定で、現時点ではありません。

**元に戻すとき**：`ACCESS_AUD` を空にしてデプロイすると、メモ機能だけが止まります（保存したデータは R2 に残ります）。Worker そのものを外すには、`wrangler.jsonc` から `main` と `run_worker_first` を消します。

## 今後の案

- **練習記号をタップできるようにする**：今の reader データには練習記号の位置がありません。原譜を見て確認した練習記号（文字・楽章・小節・x 座標）を `build_reader.py` の出力に足せば、譜面上の練習記号を押してその場所にメモを付けたり、「C へ移動」したりできます。推測した位置は入れず、原譜で確かめたものだけにします。メモに練習記号を自由入力する方式にはしません。
- **Git の別リポジトリに保存する**：Worker の保存処理を差し替えて、ユーザーごとのブランチ（例：`users/<user-key>`）に `memos/<part>.json` としてコミットする形にできます。例えば GitHub App のトークンを Worker の secret に入れ、Contents API で書き込みます。今の JSON 形式とキーの構成は、そのまま 1 ファイル ＝ 1 パート、1 ブランチ ＝ 1 ユーザーに対応します。こうすると履歴も差分もバックアップも Git で扱えます。R2 から移すときは、`memos/v1/` の下を順に読んでコミットすれば済みます。
- 今は、オフラインで書いたメモの送信待ち（キュー）と、PDF への印刷には対応していません。
