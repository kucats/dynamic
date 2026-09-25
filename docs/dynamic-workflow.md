# DYNAMIC 譜読みの工程管理

Issue #26 の初期実装。`tools/dynamic/workflow.py` は既存の `part.json`、
`pages/bars_pNN.json`、`pages/notes_pNN.json` に **工程・入力の版・作業者・監査記録**を追加する。
Python 3.11 以降の標準ライブラリだけで動く。書き込みは Linux/macOS の `flock` が必要。

原譜を読んだり音符を推測したりするプログラムではない。**既存ファイルの存在、検算の成功、
過去の `part.status` の文章から、工程完了や独立監査済みを推定しない。**

## 工程と粒度

```text
ページごと: source → bars → pitch → rhythm → audit
                       │                    │
                       └ 全ページの小節地図 └ 前後ページも監査の入力
                         が確定するまで
                         pitch を開始しない
全ページ audit 完了 → ready_to_publish=true
実際の build / publish / deploy は別工程（この CLI は実行しない）
```

現行の「1ページ＝1担当」とファイル単位に合わせ、永続タスクは **物理ページ単位**。
段は小節・音の位置照合に使うが、段ごとの別 claim はまだ作らない。パートの状態はタスクから
決定的に集約し、手編集する別の全体ステータスは持たない。

| 工程 | 完了前に確認すること | 出力として版管理するもの |
| --- | --- | --- |
| `source` | 元PDFの実バイトの SHA-256 が manifest と一致。対象ページ・楽章・分割・DPIを確認 | 原譜識別と対象ページの設定。PDFや画像自体は保存しない |
| `bars` | 段内の区間、番号、複数小節休み、楽章の最終小節を確認 | 小節JSONと最終小節・楽章対応 |
| `pitch` | 音高・座標・小節所属を確認 | 音価を除いた音符データ、音部記号・移調等の設定 |
| `rhythm` | 有理数の音価・開始位置、拍子内に収まること、声部内の重なりを確認 | 音符JSON全体と拍子・テンポ・再生順等の設定 |
| `audit` | 転記担当とは異なる担当者が、原譜と採用データを照合 | 対象版、監査範囲、指摘、担当者を結び付けた receipt |

`complete` は **その工程の作業完了**。`source`～`rhythm` の完了は独立監査済みを意味しない。
読み取りに `uncertain` を残して音価まで進むことはできるが、そのページの監査を完了させることはできない。
構造検査で休符の欠落、臨時記号の正しさ、キューの見落とし、タイや反復の音楽的意味までは保証しない。
これらを照合するのが独立監査であり、耳での確認はさらに別。

## 状態と次の仕事

保存される各試行の状態は `running / complete / needs_review / failed / stale`。
試行がないタスクは `pending`。前提が未完了なら表示上は `blocked` になる。
`stale` は保存済みの入力・出力ハッシュと現データを照合して、読み取り時にも導出する。

集約の優先順は `stale > failed > needs_review > running > pending > complete`。
`next` は source、bars、pitch、rhythm、audit の順、各工程内は物理ページ昇順で、
開始可能な仕事だけを返す。実行中の仕事は再配布しない。`needs_review` は `action=review` として返す。
**`next` 自体は claim しない。取得後に他の担当者が claim する競合は、書き込み時に再判定する。**
`next=[]` は完了とは限らない。JSONの `running`、`blocked`、`numbering_errors`、
`ready_to_publish` を確認し、待機・差し戻しと全監査完了を区別する。

```sh
PART=project/dvorak/symphony-no-8/trombone-i/dynamic
python3 tools/dynamic/workflow.py status "$PART"
python3 tools/dynamic/workflow.py status "$PART" --json
python3 tools/dynamic/workflow.py next "$PART" --json
python3 tools/dynamic/workflow.py check "$PART"
```

この4つは読み取り専用。`workflow.json` がなければ **全工程未着手の仮想状態と既存成果物の有無**を返す。
ロックファイルも作らない。`notes_pNN.json` 内の古い `page` 値ではなく、ファイル名と
`part.json` の物理ページ対応を使う。既存データの書き換えはしない。

## 初期化から完了まで

まず `part.json` にパートID、原譜SHA-256、物理ページ一覧、楽章とページの対応を書く。
複数楽章が同じページに入る場合は既存の `splits` を明示する。原譜は未コミットの場所に置く。
この時点で楽章の `last` や拍子・テンポが未判明でもよい。`last` は bars の完了前に、
拍子は rhythm の完了前に記入する。新しい原譜の認識・レンダリングは既存ツール/担当者の役割。

```sh
python3 tools/dynamic/workflow.py init "$PART"
mkdir -p work
python3 tools/dynamic/workflow.py claim "$PART" \
  --page 1 --stage source --worker ingest-1 > work/source-claim.json
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["receipt"]["token"])' < work/source-claim.json)
python3 tools/dynamic/workflow.py finish "$PART" \
  --page 1 --stage source --worker ingest-1 --token "$TOKEN" \
  --source-pdf /private/original.pdf \
  --evidence '原譜ハッシュ、対象パート、物理1ページと楽章対応を確認'
```

`--source-pdf` は source 完了時に実バイトをハッシュするためだけに使い、パスも内容も receipt に入れない。
manifest の SHA-256 を読み出すだけでは source 完了にならない。

続いて `bars` を claim し、小節JSONを作成・確認してから同様に finish する。
`pitch`、`rhythm` も同じ手順。`--source-pdf` は source 以外には指定しない。
作業未完了なら `--result needs_review`、実行失敗なら `--result failed` と理由を記録する。
完了時は `--evidence` に実施内容・根拠を残す。秘密、絶対ローカルパス、原譜内容の転載は書かない。

**小節番号の工程は音高JSONがなくても開始・完了できる。** 印刷された番号、練習記号、
多小節休みの数、他パートの確認済みアンカーを用いる。従来の `barlines.assign_bars()` は
音符の既存小節番号を利用する補助機能なので、これだけを先行工程の根拠にはしない。
番号未確定のまま便宜的に pitch を完了させない。

## 監査の入力

対象ページと前後の物理ページの rhythm 完了後に audit を claim できる。
その範囲の現行 bars/pitch/rhythm 担当者と同じ worker ID では claim も完了もできない。
`work/audit-p01.json` を作り、`finish --stage audit --review work/audit-p01.json` に渡す。

```json
{
  "reviewer": "independent-reviewer-1",
  "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "scope": ["bars", "pitch", "rhythm", "cues", "ties", "repeats", "page-boundaries"],
  "findings": [
    {"id": "accidental-107-4", "status": "resolved", "detail": "原譜との照合結果と修正内容を記録"}
  ]
}
```

上記SHAは例。実際の原譜SHAに置き換える。`reviewer` は claim の worker と一致させる。
7項目すべての監査範囲が必要。指摘がなければ `findings=[]` とし、未解決なら `unresolved`。
未解決指摘や `uncertain` があれば `complete` は拒否される。`needs_review` として残せる。

監査の input hash はその時点の版に固定される。後で音や音価を直したら古い監査は再利用できない。
`structural_checks=passed`、`note_level_audit=passed`、`human_listening_test=not_recorded` を混同しない。
現在の CLI は人間の聴取テストを完了させる機能を持たない。

## 差し戻しと失効範囲

| 変更 | 再確認が必要になる範囲 |
| --- | --- |
| 原譜SHA、対象ページの設定、DPI、楽章分割 | source 以降。ページ集合やパートID変更は明示的な再初期化が必要 |
| 小節JSON、楽章の最終小節 | 当該/設定を共有する bars と、全ページの pitch 以降 |
| 音高・臨時記号・音符順序・座標・未知の音符項目 | 当該ページの pitch、rhythm と、当該/前後ページの audit |
| `dur / off / tie_from_prev / tie_to_next / tuplet`、既知の音価meta | 当該ページの rhythm と、当該/前後ページの audit。pitch は維持 |
| 共有の拍子・テンポ・再生順 | 影響する共有設定を持つ rhythm と audit。pitch は維持 |
| JS/CSSレンダラ、最上位の表示用title/subtitle/pdf | 譜読み工程は失効させない。表示・出力物の再検証は別途必要 |

ハッシュは JSON のキー順や空白では変わらず、配列の順序は保持する。
音価は音高の出力から分離するので、同じJSONへ音価を追記しても音高工程は失効しない。
各工程で初めて判明する設定もその工程の **出力** とする。小節数・移調・拍子・テンポを
作業中に記入しただけで、自分の入力が stale になる循環を避ける。

明示的にやり直す場合:

```sh
python3 tools/dynamic/workflow.py invalidate "$PART" \
  --page 1 --stage pitch --worker coordinator \
  --evidence '臨時記号の指摘により再読が必要'
```

過去の試行は残し、新しい失効記録を追加する。同じ内容を再承認しても試行IDが変わるため、
古い下流receiptは自動復活しない。小節番号と音符の序数は修正で変わり得るアドレスであって、
不変の音符IDではない。原譜の座標も残し、番号だけで修正を別の音に誤適用しない。

## 競合、停止、再開

書き込みはパート内の `.workflow.lock` を `flock` し、保存済み状態を読み直して遷移を検査する。
一時ファイルを fsync 後、`workflow.json` へ atomic replace する。
`--revision N` を指定すればパート全体の楽観的競合検査もできる。

claim が返す `token` は試行ごとに変わる。finish は worker と token の両方を要求する。
入力が変わった試行や、invalidate/reclaim で置き換わった担当者の完了報告は拒否する。
同じ有効な finish の再送は冪等。停止した仕事は自動タイムアウトで横取りせず、
担当者が failed を記録するか、管理者が理由付き invalidate を行う。

**ロックは workflow の記録を保護するもので、別プログラムによる notes/bars の直接書き込みまでは
禁止しない。** 担当範囲外のファイルを変更しない、親工程へ差し戻す前に古い担当を停止する、
変更を原子的に保存する、という運用が必要。検出できた入力変更時は receipt を保存しない。
この版には分散キュー、期限付きlease、生成物の昇格トランザクションはない。

seal は誤編集・破損の検出用の **非秘密ハッシュ**。認証・電子署名ではなく、worker ID を変えるだけで
真の独立性を保証できるわけでもない。監査担当者/セッションの分離は実行基盤側の責任。

## 既存データの導入と互換性

この変更では `project/**/dynamic/` や `public/` のデータを変更せず、既存パートを監査済みにもしない。
導入するパートだけ `init` し、既存成果物を再読・確認して各工程の receipt を記録する。
既存のビルダ、reader、Fuyomi workflow は変更しない。

新しいページや別のパートを導入した場合、古い履歴を勝手に付け替えない。
`workflow.json` を別名で保管・履歴を残したうえで、新しい manifest に明示的に `init` する。
原譜SHAだけの変更は同じページ集合なら stale として検出する。

JSON Schema は `tools/dynamic/schema/workflow.schema.json`。
タスクの網羅性、遷移、ハッシュ一致、独立監査などの意味検証は Python が行う。
意味を変える将来の変更では `SEMANTICS_VERSION` を上げ、過去のreceiptを無断で新ルールに昇格させない。

```sh
python3 tools/dynamic/workflow.py check "$PART" --require-audited
```

終了コード: `0` 正常、`1` stale/小節地図の不整合/要求された監査未完了、
`2` JSON破損・不正な遷移・競合などの操作エラー。
通常の `check` は未着手をエラーにしない。公開前のゲートには `--require-audited` が必要。
これが通っても、`build_reader.py`、既存validator、ブラウザ確認は別途実行する。
このMRでは既存公開物を一律に停止させるゲートは追加しない。

## 検証

```sh
python3 -m unittest discover -s tests -p 'test_dynamic_workflow.py' -v
python3 -m unittest discover -s tests -v
python3 tools/validate_catalog.py
python3 tools/dynamic/validate_reader.py
python3 tools/dynamic/validate_score.py
python3 -m compileall -q tools tests
git diff --check
```

人工の小節/音符fixtureで遷移・失効・並列claim・古い試行・監査条件・原子的保存を検証する。
既存4パートも読み取り専用アダプタで確認する。Schema照合テストは `jsonschema` があれば実行する
（CLI実行には不要）。これらは実譜の再監査や演奏の聴取を実施したという意味ではない。

次段階は各既存ツールによるreceipt更新、生成物の安全な提出、担当者の自動割当、
reader/catalogへの段階的な公開ゲート統合。まずこの明示的な契約を共通にする。
