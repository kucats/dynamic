# 譜読みアプリの練習メモ（Cloudflare Access ログイン）

対象：`/reader/?part=dvorak8-trombone1`（`MEMO_PARTS` で他のパートにも広げられます）

## 目的

ログインした人ごと・パートごとに、譜面上の場所に紐づいた練習メモを残せるようにします。例：「練習記号C 吹けなかった」。
メモは個人の練習記録です。転記・監査データ（`public/reader/data/*.json`）は変更せず、監査状態や再生にも影響しません。

## 構成

```
ブラウザ ──/reader/*（静的）───────────────► Workers Assets（public/）
        ──/login ──► Cloudflare Access ──► Worker：JWT を検証し dyn_session Cookie を発行 → 元のページへ戻す
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
   "text": "練習記号C 吹けなかった。前の小節で吸う", "rehearsal": "C", "kind": "issue",
   "anchor": { "mvt": "I", "bar": 58, "page": 1, "sys": 4, "x": 1063, "y": 12, "note": 31 }
  }
 ]
}
```

`anchor` の x・y は、切り出した段の画像内の座標です。`page`・`sys` は原譜のページと段の番号です。リーダーのデータを作り直して段の構成が変わったときは、`mvt` と `bar` を頼りに、その小節の頭にメモを出します。どちらでも位置が決まらないメモは、一覧に「位置不明」と表示されます。`kind` は `note`（メモ）・`issue`（課題）・`good`（できた）のどれかです。

### API

| メソッドとパス | 内容 |
| --- | --- |
| `GET /api/me` | `{enabled, loggedIn, email, memoParts, expiresAt}` |
| `GET /api/memos/<part>` | 自分のメモの JSON ファイル（まだ無ければ空） |
| `POST /api/memos/<part>` | メモを作る `{text, rehearsal, kind, anchor}`。返り値は日時と ID の入ったメモ |
| `PUT /api/memos/<part>/<id>` | メモを直す（`createdAt` はそのまま、`updatedAt` を更新） |
| `DELETE /api/memos/<part>/<id>` | メモを消す |

## 画面の使い方

検討した入力方法と、採用したものです。

| 案 | 判断 |
| --- | --- |
| 右上の ✎ を押し、場所を 1 回タップするとメモ入力画面が開く | **メインにした**。スマホでも誤操作が起きにくく、音符のタップ（試聴）ともぶつからない |
| 譜面の空いたところ（音符以外）をダブルクリック／ダブルタップ | **ショートカットとして採用**。音符上のダブルクリックは今までどおりロングトーン練習を開く |
| 右クリックや長押しでメニューを出す | 不採用。右クリックはロングトーン練習に使っていて、長押しは iOS の選択操作とぶつかる |

- **入力画面**：場所（楽章・小節・原譜のページと段）を自動で入れます。練習記号は候補の A〜Z から選ぶか、自由に入力できます（8 文字まで）。種類はメモ／課題／できたの 3 つ。編集するときは作成日時と更新日時を表示し、削除もできます。
- **表示**：譜面上にピンを出し、練習記号があればピンにその文字を入れます。色は種類ごとで、メモ＝青、課題＝オレンジ、できた＝緑です。ピンを押すと編集画面が開きます。
- **一覧**：右上の「一覧 n」から、楽章・小節の順にメモを並べて表示します。そこから「移動」（ピンが光る）と「編集」ができ、ログアウトもここからです。
- **ログインしていないとき**：✎ を押すと、ログインページに移動するか確認します。ログイン後は元のパートに戻ります。
- **コードの置き場所**：`public/reader/memo.js` と `memo.css` に分けています。`app.js` に足したのは、小さな拡張用フック（`__dynamic.ext`：段の SVG への描き足し・再描画・停止・楽章の切り替え）だけです。

## 設定手順（運用者）

1. R2 バケットを作る：`npx wrangler r2 bucket create dynamic-memos`
2. Zero Trust → Access → Applications で **Self-hosted** のアプリを作る。
   - ドメイン：`dynamic.oke.jp`、パス：`login`（`/login` だけを守る）
   - ポリシー：`DYNAMIC Google accounts`（Allow / All authenticated users）を割り当てます。
   - Login methods：Google のみを有効にします。現在は Google アカウントを持つ人なら誰でもログインできます。
   - セッションの期間：24 時間に設定済みです。
3. アプリの **Application Audience (AUD) Tag** とチームドメイン（`<team>.cloudflareaccess.com`）を、`wrangler.jsonc` の `vars.ACCESS_AUD` と `vars.ACCESS_TEAM_DOMAIN` に入れる（どちらも秘密情報ではありません）。
4. `npx wrangler deploy`。`https://dynamic.oke.jp/login` を開いて認証し、元のページに戻ってから、✎ でメモが保存できることを確かめます。

現在の実環境：fs-admin Cloudflare アカウント（ID `29e8010570c1cef4764ba466ab6ebb55`）に R2 バケット `dynamic-memos` と Access アプリ `DYNAMIC Reader Memo Login` を作成済みです。アプリの対象は `dynamic.oke.jp/login`、IdP は Google のみ、ポリシーは全認証済みユーザーを許可します。管理者による承認画面は将来の追加予定で、現時点ではありません。

**元に戻すとき**：`ACCESS_AUD` を空にしてデプロイすると、メモ機能だけが止まります（保存したデータは R2 に残ります）。Worker そのものを外すには、`wrangler.jsonc` から `main` と `run_worker_first` を消します。

## 今後の案

- **練習記号をタップできるようにする**：今の reader データには練習記号の位置がありません。原譜を見て確認した練習記号（文字・楽章・小節・x 座標）を `build_reader.py` の出力に足せば、譜面上の練習記号を押してその場所にメモを付けたり、「C へ移動」したりできます。推測した位置は入れず、原譜で確かめたものだけにします。それまでは、メモ入力画面の練習記号欄で代わりにします。
- **Git の別リポジトリに保存する**：Worker の保存処理を差し替えて、ユーザーごとのブランチ（例：`users/<user-key>`）に `memos/<part>.json` としてコミットする形にできます。例えば GitHub App のトークンを Worker の secret に入れ、Contents API で書き込みます。今の JSON 形式とキーの構成は、そのまま 1 ファイル ＝ 1 パート、1 ブランチ ＝ 1 ユーザーに対応します。こうすると履歴も差分もバックアップも Git で扱えます。R2 から移すときは、`memos/v1/` の下を順に読んでコミットすれば済みます。
- 今は、オフラインで書いたメモの送信待ち（キュー）と、PDF への印刷には対応していません。
