# Work library v1: 作品・版・原譜・対応関係

Tracking: [Issue #55](https://github.com/kucats/dynamic/issues/55)

**Status: reviewable foundation; not wired into the published reader.**
`tools/dynamic/work_library.py` は標準ライブラリだけで動く、読み取り専用の
validation / resolution と明示的なalignment forkの実装である。
`tests/test_work_library.py::make_bundle()` は完全に架空の作品・版・出典を使う。
このテストを実譜の小節対応・音符・演奏の監査結果として扱ってはならない。

## 1. 前案から変えたこと

「作品共通の小節番号」をopaque IDに置き換えるだけでは十分ではない。
異稿、編曲、挿入、カット、再分割がある作品に単一の小節列を強制すると、
名前だけ変えたcanonical-bar問題が残る。**Structureは比較用の座標系のrevision**とし、
同じWorkでも異なるstructureを保持できるようにした。
異なるstructure間の橋渡しは別のレビュー対象であり、v1は暗黙に接続しない。

同様に「1:Nの対応」が分かっても、そのうちのどの一点が対応するかは分からない。
対応行は集合全体の関係であり、sourceとtargetの直積ではない。
長休符、分割小節、結合小節では最初の小節へ勝手にジャンプしない。

`in 2 / in 4` の指揮の振り方は、`Horn in F` の移調指定とも、練習記号とも異なる。
拍のグルーピングを変えても、原譜、小節番号、音価、音高は書き換えない。

## 2. レイヤーと所有権

| レイヤー | v1での役割 | 同一性にしないもの |
| --- | --- | --- |
| Work / movement / part | 作品、楽章、音楽上のパートの識別 | 作曲家名・曲名の表示文字列 |
| Edition | 出版・校訂版の識別。現段階はid/title。未知はwitness側でnull | PDFハッシュだけから推定した出版社 |
| Asset | bytesのSHA-256。原譜のbytes自体は含まない | 楽曲、版、パートそのもの |
| Witness | 具体的なスコア／パート譜、出典ページの選択、局所小節ID | PDF内のページ位置や印刷小節番号 |
| Structure | 楽章ごとのrevisionと順序付きopaque location ID列 | 全版で唯一の正解の小節列 |
| Alignment | Witnessの小節群とStructureの場所群の、入力hash固定の対応 | 音高の同一性、演奏時刻の一致 |
| Printed/editorial mark | Witness内の練習記号。scheme・楽章・mark IDを持つ | 全版共通のH、同ラベルの最初の出現 |
| Performance set | 採用する総譜／各パートのalignment snapshot、指揮・追加記号 | 出版版の上書き、音符監査の根拠 |

AssetとWitnessは分ける。同一のパート集PDFを複数Witnessが参照してよい。
逆に複数PDFのページを順につなぐWitnessも`source_spans`で表す。
ページ範囲は物理ページの1始まり、両端を含む。これは出典の構成順であり、
印刷ページ番号でも、演奏の反復順でもない。
版が途中で混在する資料はedition_idを無理に一つへ断定せずnullにする。
将来のsegment単位の出版書誌を加えるまでは、混合出典を単一出版版と呼ばない。

## 3. JSON契約

v1のvalidatorはunknown fieldsとunknown enumを拒否する。別形式を黙って解釈しない。
以下の全collectionは省略せず、未登録は`[]`とする。

```text
schema_version: 1
work: {id, title, movements: [{id, title}], parts: [{id, title}]}
editions: [{id, title}]
assets: [{id, sha256}]
witnesses: [{
  id, edition_id: ID | null, role: "score" | "part", part_ids: [ID],
  source_spans: [{asset_id, first_page, last_page}],
  measures: [{id, movement_id, number: string | null,
              kind: "measure" | "multimeasure_rest" | "tacet" | "unmeasured"}],
  marks: [{id, movement_id, measure_id, scheme, label,
           origin: "printed" | "editorial", status, review}]
}]
structures: [{id, movement_id, locations: [ID]}]
alignments: [{
  id, witness_id, structure_id, witness_sha256, structure_sha256,
  derived_from?: {id, sha256},
  rows: [{id, source: [local measure ID], target: [location ID],
          relation, status, review}]
}]
sets: [{
  id, title, structure_id, structure_sha256,
  bindings: [{part_id: ID | null, alignment: {id, sha256}}],
  overlays: [{id, kind, locations: [ID], by, label? , beat_groups?}]
}]
```

IDs are ASCII tokens matching `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`.
表示名はUnicode可。measure IDはWitness内、location IDはStructure内で一意。
順序は配列にあり、ID文字列を辞書順ソートして音楽の順序を推測しない。
measureの`number`は既定の表示ラベルであり、`0`、`105a`、空文字、重複を許す。
複数の小節番号体系を同時に格納する拡張はv1では実装していない。

`measures`は図形の位置ではなくsource-localな論理単位である。
長休符はまだ展開が確定していなければ一つの`multimeasure_rest`にしてよい。
空のmeasuresは「未読取」を表せるが、tacetを意味しない。
ページ、段、bounding boxは別のlayout artifactからlocal IDへ結び付ける。
単なる再レンダーでIDを振り直さない。小節の分割・結合を直す場合は新しい
Witness/address revisionと明示的な旧→新ID対応を発行する。

### 対応行

| relation | source | target | 意味 |
| --- | --- | --- | --- |
| equivalent | 1件以上 | 1件以上 | その小節群全体と場所群全体の位置対応 |
| source_only | 1件以上 | 空 | このStructureには相当箇所がないという明示的判断 |
| target_only | 空 | 1件以上 | このWitnessには相当箇所がないという明示的判断 |
| unresolved | 1件以上 | 空 | 未対応。欠落・カット・不在と断定しない |

各側の配列は、当該Witnessの同一楽章／当該Structure内で連続・順序付き・重複なし。
全範囲を網羅する必要はなく、読めた部分だけを登録できる。
候補の重複を禁止せず、`candidate | reviewed | rejected`で分ける。
複数のreviewed行が同じ対象を主張した場合、resolverは`ambiguous`を返す。
明示的にreviewedになった選択を、candidateの仮説が勝手に上書きすることはない。
`unresolved`をreviewedにすることはできない。

`equivalent`は位置の対応であり、「音符、アーティキュレーション、強弱も同一」ではない。
別版のDとD♯の差を、位置が一致するというだけで上書きしてはならない。

### reviewとhashの境界

reviewは未確認ならnull、確認済みなら次の形式。

```text
{by, note, subject_sha256, evidence: [{asset_id, page}]}
```

evidenceは対象Witnessの出典ページ内を指す必要がある。
`review_subject(alignment, row)`は入力hashと対応行を含む。
行を変更して古いreviewを残すとstaleになる。新しいreviewは別途原譜を照合して記録する。
練習記号も`Library.mark_subject(witness_id, mark)`で独立に固定する。
記号の位置変更が小節alignmentのreviewまで無効にすることはない。

`witness_digest`はwork ID、Witnessのaddress情報、参照Assetのハッシュを含む。
marksは独立レビューのため除く。`structure_digest`もwork IDを含む。
入力が変われば、ID名が同じでも古いalignmentを使わない。
このv1はalignment単位で保守的にstaleにする。行ごとの細粒度失効は将来の最適化。

JSON hashは本Python実装のUTF-8、sorted keys、compact separatorsプロファイル。
RFC 8785/JCS互換を主張しない。JS側への移植にはgolden hashテストが必要。
ハッシュは署名や認可ではない。書込権限がある者はreviewを再計算できるため、
「誰が承認できるか」は将来の認可／監査ログの境界で別途制御する。
ソフトウェアはevidenceの存在形式を検証するだけで、そのページの内容を監査しない。

## 4. Resolverの契約

`Library`は入力をdeep copyし、exportや結果も内部状態を露出しない。
JSON読込はduplicate key、NaN、Infinityを拒否する。

```python
from tools.dynamic.work_library import load

library = load("work-library.json")
source = library.alignment_ref("map-a")   # {id, sha256}
target = library.alignment_ref("map-b")
result = library.resolve(source, target, "source-local-measure-id")
# result.status == "exact" のときだけ、一点への自動ジャンプを許す。
```

| status | 呼出側の扱い |
| --- | --- |
| exact | 確認済み・全範囲一致・両側1通常小節。小節へのジャンプ可 |
| range | 対応する範囲のみ。source_scopeとtargetsを表示し、先頭へ自動選択しない |
| partial | 必要範囲の一部しか対応していない。全範囲一致とは表示しない |
| unreviewed | 候補のみ。ジャンプの根拠にしない |
| unmapped | 登録がない。番号の一致でfallbackしない |
| ambiguous | 確認済みの主張が競合している。選択・修正が必要 |
| absent | 明示的なsource_only／target_only。未読取と区別 |
| stale | snapshot、入力、reviewのどれかが変わった。再確認が必要 |
| incompatible | Structure revisionが異なる。自動変換しない |

結果はwhole-measure/whole-spanの関係であり、音符、拍、秒、反復の何回目かを特定しない。
多対多のsource群から一つ選んでも、全target群への一点対応には昇格しない。
曖昧な結果や不完全な結果には、安全な一点を捏造しない。

## 5. 明示的コピー

```python
candidate = library.fork(
    library.alignment_ref("map-a"),
    "map-c", "part-c",
    {"s1": "u1", "s2": "u2", "s3": "u3"},
)
```

コピー先Witnessは先に登録する。ID mapはactiveなsource IDsを過不足なく指定し、
既存のコピー先IDへ1:1でseedする。番号一致や配列順序で自動推定しない。
分割／結合を含む新対応は、コピー後にcandidate行を明示的に編集する。
review、出典ページ、mark、memo、音符はコピーしない。
rejected行は復活させず、残りもすべてcandidateにする。
親の`{id, sha256}`を来歴として保持し、実行時のinheritsは作らない。
親が後から変更されても子の配列や承認状態は変わらない。
親snapshotがstaleならforkを拒否する。コピー元の誤りを黙って増殖させない。

forkは新しいdictを返すだけで保存しない。旧IDへ上書きせず、保存・レビュー・公開を
別の明示的操作とする。親snapshotはGit等で保存し、来歴を後から再現できるようにする。

## 6. 合奏で採用する版と指揮者の指示

Performance setの`part_id: null`は指揮者の総譜、他はパートID。
総譜Aとパート譜Bが混在してよいが、同じStructure revisionを使う。
`resolve_in_set(set_ref, source_part, target_part, measure_id)`はset全体の
binding snapshotを確認し、古い選択を勝手に最新版へ追従させない。

`rehearsal_alias`はset内の追加ラベル。原譜のHは消さず、指揮者のXを別に表示する。
`find_mark`はWitness、楽章、scheme、ラベルで検索し、重複したラベルを先勝ちにしない。
正確に選ぶUIはmark IDも保持する。

`conducting.beat_groups`は**記譜された拍単位のまとめ方の提案**。
例えば4/4の`[2,2]`は二つ振り、`[1,1,1,1]`は四つ振り。
v1は正の整数列を保持するだけで、拍子との総和・BPM単位・指揮アニメーションは
検証・実行しない。将来のメトロノーム接続では範囲ごとの拍子と単位を必ず確認する。
移調情報はこのoverlayに入れない。記譜音と実音の変換は楽器／譜表／有効範囲に属する。
カット、反復展開、volta、D.C./D.S.は別のplayback planとして将来実装する。
譜面の箇所と演奏の訪問回を分け、`plan revision + visit ID + location + offset`を持たせる。

## 7. 現行DYNAMICへの移行順序

参照したbase: `323cc24892641d59d1e0ffac58b78fe062d61b06`。
現行`public/reader/score-viewer.js`は作品／作曲家で総譜を選び、楽章＋小節番号を検索する。
`public/reader/memo-model.mjs`の固定小節メモUXは維持する。
このPRでは`public/`、`worker/`、生成JSON、実譜の音符を変更しない。

1. **Inventory**: 各part.json／score.jsonからWork、Asset、Witnessの候補を収集するdry run。
   版不明、同名別作品、小節数差、長休符未展開を報告。番号だけでWorkLocationを生成しない。
2. **First reviewed bridge**: 同じ箇所と原譜で確かめた小範囲だけalignmentを登録する。
   過去に記録された387対389の差の原因は未確認。この数字だけで一律±2補正しない。
3. **Build sidecar**: `build_reader.py`／`build_score.py`から明示的なrevision付き参照を出す。
   readerのlazy loadingを維持し、exact以外のジャンプを止める。#54の読取集約と分離して導入。
4. **Marks/workflow**: #49の練習記号selectorと接続。#26ではbars段階はlocal IDを確定し、
   版間alignmentは別の依存・監査項目にする。alignment修正が原譜の音高判定を変更しない。
5. **Memos**: 旧メモは旧part＋楽章＋番号のlegacy anchorで保持。
   確実なときだけwitness-local IDへ移行し、曖昧な長休符メモを先頭へ吸着させない。
   他版へのメモ移植は、元anchor、先anchor、alignment snapshot、本人の承認を記録。
   メモUIに練習記号入力や自由配置を再導入しない。
6. **Playback/ensemble**: #53の共有位置にはstructure、plan、visitを含める。
   alignmentがexactでも音符監査や実演追従の精度を承認したことにはしない。

## 8. 検証と残るゲート

```sh
python3 -m unittest discover -s tests -p 'test_work_library.py' -v
python3 -m compileall -q tools/dynamic/work_library.py tests/test_work_library.py
python3 tools/dynamic/work_library.py path/to/work-library.json
git diff --check
```

CLIは書き込まず、構造エラーでexit 2、staleな入力／mark／setでexit 1、その他はexit 0。
exit 0はすべての対応がexactという意味ではない。範囲・候補・競合はresolve時にも確認する。
`note_audit`は常に`not_assessed`。専用CIはPython 3.11 / 3.13で同じテストを実行する。

本PRに含むのは上記モデル、validator、resolver、コピー、setとmarkの基盤である。
実譜importer、原譜による対応監査、fractional beat alignment、ブラウザへの組込、
メモmigration、MusicXML/MEI round-trip、録音追従、認可／共同編集は未実装。
Issue #55はこれらの導入ゲートまでopenに保つ。

## 9. 標準との整合（互換実装を主張しない）

MusicXML 4.0はmeasureのnumberと表示用text、文書内idを区別し、弱起、
非数値番号、non-controlling barlineを表せる。
[measure仕様](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/measure-partwise/)
を参考に、DYNAMICでも番号を作品の主キーにしない。
[rehearsal仕様](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/rehearsal/)
の文字・番号・節名はsource-boundな表示記号に対応する。
[transpose仕様](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/transpose/)
は記譜音から実音への変換であり、conducting overlayではない。
v1はこれらのXMLをimport/exportする実装ではなく、その上に載せる来歴・対応関係の契約である。
