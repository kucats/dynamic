# 譜面追従（ローカル実験版）

Issue #4 のサーバー実験を踏まえた reader 側の実験機能。設定で有効にしてから「マイク開始」。初期設定は無効。ローカルだけが選択でき、リモートは準備中として無効になっている。サーバー、サービスキー、音声アップロードは使わない。

## 操作と表示

- 選択中の楽章だけを照合する。楽章変更時はマイクを停止し、位置・候補を初期化する。
- 小節を青く照らし、推定位置を縦線で示す。上部に候補と近くの練習番号を最大3件出す。記録のない楽章では小節番号を使い、練習記号を捏造しない。
- 候補ボタン、「現在地 → ここから追う」、小節メニューで上書きできる。タイムラインに同じ小節が複数回ある場合は回数を選ぶ。手動指定はセッション中の起点であり、譜面・監査・練習メモを変更しない。
- 位置が決まった後は近傍でのみ再捕捉する。遠方の候補は上部に提示するが、現在地を移さない。やり直しは手動指定または「再探索」。後者は位置・テンポ・候補履歴を明示的に破棄する。
- **見失っても最後の四分音符BPMで進む。** 休符・無音・雑音も同じ。点線、淡い範囲、予測中の表示で音響的な追従と区別する。元譜面の次のテンポ記号で勝手に速度を変えない。初回の手動指定でまだ推定テンポがない場合だけ、その小節の譜面テンポを初期値とする。
- 音が戻ったときの位相補正は1回あたり−0.15〜＋0.20譜面秒。進行座標は逆戻りさせない。位相差が大きい間は追従中と表示しない。
- 「マイク停止」はカーソルも止める。無効化、画面を離れる、音源切断、楽章変更、readerの合成音開始でもマイクを解放する。再開にはボタン操作が必要。
- 縦線の小節内位置と長休符内の幅は均等割りの目安。正確な音符・拍位置を原譜で監査した結果ではない。

## ローカルの照合

`follow-model.mjs` はDOMに依存しない。入力はWeb Audioの8192点FFT（平滑化なし、200 ms間隔）。局所スペクトルの背景を引き、複数の音高ピークを12音級へ集約・正規化する。単一の基本周波数を強制しない。A4=442 Hzの近辺を許容する。

`build_following.py` は同じ作品・同じ楽章・一致する小節長を持つ公開readerの実音を集め、小さな和音・フレーズ用データを生成する。ドヴォルザーク第4楽章ではHorn IIとTrombone I。総譜全声部の転記ではない。`unc` の音と元データにないキューを使わない。実音 `snd[2]` を二重に移調しない。既存のreader JSONや画像は変更しない。

最初の短い候補には4〜8秒の窓と9種類の速度を使う。通常の長さの楽章では、それだけで自動的に現在地を決めない。12秒以上の履歴ができたら、直近最大32秒の因果的なsubsequence DTWへ切り替える。途中の伸び縮みを(1,1)/(1,2)/(2,1)の進行で扱い、長いフレーズの音の順番で候補を比較する。過去の録音全体は保持しない。

長窓では有音フレーム60%以上、譜面側の有効な手掛かり35%以上かつ4秒以上、複数の音級・変化を要求する。加えて直近1.2秒の音響一致、別候補との差、候補の連続した進行を確認する。自動取得には5回の継続した照合が必要。反復箇所は別候補に残す。費用は消費した入力フレーム数で正規化し、ゆっくり進む候補が計算上だけ有利にならないようにする。

途中の休符は時刻を残して履歴に保持し、先頭の無音はフレーズに含めない。取りこぼした短い入力間隔は無音の証拠なしフレームで埋め、0.65秒を超える収録中断では音響履歴を破棄する。無音時は長窓に良い一致が残っていても「予測中」。取得後は予測位置の近傍だけを採用し、遠い高得点候補へ自動で移らない。再捕捉幅の上限は12譜面秒で、校正済みの信頼区間ではない。カーソルが音響候補に追いつくまで、予測の不確かさを小さく戻さない。

Workerが照合を担当し、メインスレッドは音響特徴抽出と描画を行う。入力は最大1フレームを処理待ちとし、古い録音を溜めない。楽章世代と手動操作のrevisionで古い応答を捨てる。録音の全長から小節を比例配分する方法は使わない。相対類似度・濃淡は正答確率ではない。

Web Audioの挙動は [W3C Web Audio仕様](https://www.w3.org/TR/webaudio-1.0/#AnalyserNode) に準拠する。時間ずれを含めたフレーズ照合の背景資料は [Dixon/Widmer, MATCH (2005)](https://www.cp.jku.at/people/widmer/papers/ismir2005_dixon_widmer.pdf)。本実装は有界のローリング窓を使う独自の実験であり、同論文のアルゴリズムや性能の再現を主張しない。

## データ・再現

```sh
python3 tools/dynamic/build_following.py
python3 tools/dynamic/build_following.py --check
python3 tools/dynamic/validate_reader.py
node --test tests/reader/*.test.mjs
```

譜面を変更したら `build_reader.py` の後に `build_following.py` を実行する。出力は `public/reader/following/`（schema 2）。画像・音声・PDFは含まない。プロフィールには選択パートのタイムラインも含め、readerの実音・発音位置・音価・タイ・不確実音の除外・反復順との一致を検査する。PDFのhashが同じでも転記を修正したら古いプロフィールを拒否し、現在のパートのデータを使う。オンラインでは小さなプロフィールをネットワーク優先で取得する。

`project/**/dynamic/following.json` に練習番号と出典を持つ。第4楽章C/Dは、古いページ転記の58/74ではなく `part.json` に記録された修正後の59/75を使う。対応する他パートでも同じ小節体系の記号を引用し、元パートを残す。

私的な録音での再現にはNumPy、ffmpeg、Nodeが必要。音声ファイルと出力先はローカルで指定する。音声・特徴・時刻別トレースはリポジトリに追加しない。

```sh
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --part dvorak8-trombone1 --movement IV --out /tmp/follow-result.json
```

音響フロントエンドは48 kHzのモノラル混合、8192点Blackman窓、200 ms hopを使い、browserと同じJS特徴抽出・追従器を呼ぶ。時刻はFFT窓の中心で、その特徴が利用可能になるのは85.333 ms後。実ブラウザーのマイク処理やiOSのサスペンド動作を再現した試験ではない。追従中・予測中・未捕捉を別集計し、**途切れない最長区間**も出す。間の未確定をつないで長い一致と呼ばない。最後の集計区間は解析済みの音声範囲に切り詰める。正解ラベルがない録音の小節正解率は `null` のままにする。

別演奏がある場合は、同じDTWの実装で録音間の長時間照合を診断できる。ブラウザーには参照音源を同梱せず、入力録音も外部へ送らない。出力は参照音源上の秒数だけで、`score_position=null`。譜面追従の小節精度や自動譜めくりの根拠に転用しない。

```sh
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --reference '<local-reference.ogg>' --out /tmp/reference-32.json
# 同じ条件で短窓を比較
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --reference '<local-reference.ogg>' --reference-window 8 --out /tmp/reference-8.json
# 音色・音級分布を保ち、時系列を崩した対照（固定seed）
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --reference '<local-reference.ogg>' --reference-control shuffle --out /tmp/reference-shuffled.json
```

参照診断は32秒の履歴で1秒ごとに更新し、現在までの入力だけを使う。参照候補の連続性を3回要求する。すべての候補は未監査。8秒・32秒で同じ連続区間が得られた場合は、その録音で長窓の優位を主張しない。

### 近接パート・誤音を含む演奏の診断

残タスクは [Issue #52](https://github.com/kucats/dynamic/issues/52)。全声部の整備を待たず、単独パート・音域を保った倍音特徴・左右チャンネルを比較する評価経路がある。**この比較方式はreaderでは有効にしていない**。既定の合奏照合と手動指定・テンポ予測は維持する。

```sh
# 開いているパートだけの譜面を使う（Dvořák Trombone I / IV が既定）
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --out /tmp/part-chroma.json
# オクターブを潰さず、複数の音高仮説を保つ倍音特徴
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --features harmonic --out /tmp/part-harmonic.json
# 矛盾する観測の負の寄与を0で止める。正の一致へは変換しない
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --features harmonic --tolerate-errors --out /tmp/part-errors.json
# 同条件で左右を比較。right は2ch以上が必要
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --channel left --out /tmp/part-left.json
# 音の順番を壊した対照は、すべての方式で比較できる
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --control shuffle --out /tmp/part-shuffle.json
```

`--features harmonic` はMIDI 36〜84の49次元、各候補音の1〜6倍音の局所ピークを使う。最大ピークをトロンボーンと断定しない。分離モデルや楽器識別器ではない。音の抜けや誤音を含む人工例では位置維持を検査できるが、主録音ではこの方式の改善を確認できなかった。異なる特徴に同じ判定基準を適用した初期比較であり、特徴方式一般の優劣やトロンボーン単独照合の不可能性を示す結果ではない。

発音した音符列と発音間隔を使う試作を追加した（次節）。負の寄与の制限だけの方式とは別に比較する。参考となる [Nakamura et al., Real-Time Audio-to-Score Alignment (2016)](https://eita-nakamura.github.io/articles/TNakamura_etal_AudioScofo_ACMIEEE_TASLP_2015.pdf) は、それらの演奏誤りを分けてモデル化した単音演奏の研究。合奏トロンボーンの精度は別途評価する。

主録音の集約結果は `project/dvorak/symphony-no-8/trombone-i/reviews/score-following-trombone-20260926.md`。音符密度の低いパートの扱い、演奏中の音だけでの再取得、休符中の予測を分けて改善する。

### 音符列と発音間隔の試作

`tools/dynamic/following_events.mjs` はオフライン専用。倍音特徴の最大成分が2フレーム続いたときに新しい音高領域として分割し、49次元の特徴は保持する。最大32秒・直近24イベントを使い、譜面イベント列との置換・挿入・削除を評価する。予期しない音は、別楽器や抽出誤りの可能性もあり、奏者のミスと断定しない。

時間間隔は、途中で飛ばした観測と譜面イベントの両方を含めて計算する。7種類の速度仮説に対する間隔のずれと編集費用を、観測イベント数で正規化する。休符フレームの比率を一致点へ掛けない。少なくとも8観測・6つの支持・4種類の音高、直近の音響支持、費用から得る類似度0.68以上を要求し、その後に既存の連続取得・手動優先・近傍補正の制御を通す。各閾値は合成例による試作値で、実演で校正済みではない。

```sh
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --features events --out /tmp/part-events.json
python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' \
  --template part --features events --control shuffle-blocks --out /tmp/part-events-control.json
```

`shuffle-blocks` は固定seedで2秒ずつのブロック順を崩す。各ブロック内の音高持続を保ち、長い音の並びを壊した対照。フレームごとの `shuffle` では発音候補自体がほぼ消えたため、対照を追加した。いずれも正解小節のラベルにはならない。

主電話録音ではイベント試作も追従確定0秒。readerに採用していない。200 ms間隔では短音・同音連打を十分分離できず、最大成分による区切りが合奏でトロンボーンの発音に対応する保証もない。次は独立した小節アンカーと発音候補のレビュー、より短いhop/複数の区切り仮説を比較する。集約記録: `project/dvorak/symphony-no-8/trombone-i/reviews/score-following-events-20260926.md`。

## 「落ちた🎙️」と合奏同期への組み込み

右メニューから前・後・この辺を指定する探索、右下の候補表示、ルームA〜Dの多数決は [Issue #53](https://github.com/kucats/dynamic/issues/53) と [組み込み設計](score-following-integration.md) にまとめた。新UIとルーム同期は未実装。ローカル音声処理とルームへの位置候補共有を別設定にし、本人の手動指定・範囲制約・最後のBPMによる予測を全段階で維持する。

## 現時点の限界と次のリモート接続

実録音での自動追従の持続時間はまだ短く、合奏の小節精度を達成したとはいえない。特に弦・木管主体、長休符、同じ主題、拍内のテンポ変動で候補が曖昧になる。元の再生タイムラインに省略された反復は復元していない。必要な戻りは現在地を指定する。iPhone/iPadの実機精度・遅延・電池負荷は未検証。

次の音響改善には総譜のより多くの声部、または音声参照と**別途レビューした**録音時刻→小節アンカーが必要。録音の再生秒だけを小節の証拠にしない。持ち出さない評価用ラベルに録音時刻、小節、回数、不確実区間を付け、正しい小節の割合・予測だけの割合・再捕捉時間・誤った移動数を別集計する。

リモートを有効にする前に、既存 `tools/score_following` のセッション発行を認証付きバックエンドへ置き、ブラウザーには短命トークンだけを渡す。WebRTC/WS切断・応答revision・端末差を検証する。音響処理を差し替えても、手動指定の優先、テンポ予測、遠方へ自動移動しない制約はreader側で保持する。
