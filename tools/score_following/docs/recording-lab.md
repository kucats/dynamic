# 実録音・合奏の追従実験（v0.2）

## 単音追従と参照演奏追従を分離する

トロンボーンの近くで収録しても、マイクには他パート・倍音・残響が入ります。検出されたfundamentalを無条件にトロンボーンの音と呼ばない設計です。v0.1の単旋律ベースラインは残し、v0.2では合奏全体を既知の参照演奏に照合する独立経路を追加しました。

**参照演奏の秒数 ≠ 譜面の小節・拍 ≠ トロンボーンの個々の音符。** 参照モードは `reference_position` を返し、`score_position=null, confirmed=false` を維持します。楽譜への対応には、別途監査した参照秒数→楽章/小節/拍のanchorが必要です。ホルンの譜面をトロンボーン録音の正解データに流用しません。

## M4A/AACなどの取り込み

```sh
python -m scorefollow.recording_lab inspect YOUR_RECORDING.m4a --output evidence/private-local
```

ローカルのM4A/MP4/WAV/FLAC/OGG/MP3をPyAVで復号し、float32・16kHzへ変換。元のmono/stereoを維持します。ピークが1を超えるdecoder出力も捨てず、S16への暗黙クリッピングを避けます。AAC復号値のovershootだけから原録音のクリッピングを断定しません。

既定の上限は圧縮128MiB・復号1200秒・1音声stream・1〜2ch・元8〜192kHz。超過時に黙って切らず拒否します。URLやplaylistを開くAPIはなく、demuxerを明示したファイルオブジェクトのみを使用。これは一般の悪意あるメディアに対するOSサンドボックスではありません。公開アップロードサービスへ変える前に隔離・CPU/メモリー制限を別途設けてください。

`profile.json` はソースhash、復号サンプル数、音声時計の原点、ピーク、チャンネル別診断等。ファイル名・元パス・GPS・任意metadataは書き出しません。`accuracy=null` はラベルがないことを表します。有声音割合は精度ではありません。

音声時計は**復号された最初のサンプル=0**です。元ファイルのPTS原点は `source_origin_s` に保持します。AACのpriming/edit-listのため、コンテナーdurationと復号サンプルdurationが同じとは限りません。正解ラベルはこの時計に合わせてください。

既定 `--timestamp-policy strict` は不連続PTSを拒否します。古いOGG等のtimestamp揺れを、ユーザーが検討した上でサンプル数ベースへ正規化する場合だけ `samples` を明示。差異の件数と最大値をprofileへ記録し、「連続した元時計」と偽りません。参照だけの正規化は `--reference-timestamp-policy samples` で独立指定できます。

## オフラインの候補比較

```sh
OPENBLAS_NUM_THREADS=1 python -m scorefollow.recording_lab compare YOUR_RECORDING.m4a \
  --reference movement-1.ogg --reference movement-2.ogg \
  --reference movement-3.ogg --reference movement-4.ogg \
  --reference-timestamp-policy samples --output evidence/private-comparison
```

256ms窓・100ms hop。各チャンネルのスペクトルpowerを先に平均し、12音のchromaへ畳み込みます。波形のL+R平均を先に行わないので、逆相で消える問題を避けます。55〜4000Hz、半音近傍Gaussian weights、chromaの平均成分除去とL2正規化を使う実験的特徴量です。楽器分離ではありません。

Subsequence DTWの許可stepは(1,1)/(1,2)/(2,1)。query全体を見て候補を返す**オフライン**解析であり、オンライン遅延の測定ではありません。距離は2×queryフレーム数で正規化した比較指標で、正解確率ではありません。形状・finite値・最大3600万cellを検査します。処理量はquery長×reference長に依存します。

## 因果的な参照追従

```sh
OPENBLAS_NUM_THREADS=1 python -m scorefollow.recording_lab follow YOUR_RECORDING.m4a \
  --reference movement-4.ogg --reference-timestamp-policy samples \
  --output evidence/private-causal
```

`ReferenceTracker.consume(ChromaFrame)` は直前20秒の履歴だけを見て1秒ごとに更新。開始位置は渡しません。初期取得には20秒以上かかり得ます。候補距離・他の位置との差・音の変化量・3回以上の時間的連続性で取得を判定し、弱い区間はuncertainへ落とします。同一フレーズの反復、無音、音色差で候補が誤る可能性は残ります。途中のseek/通信gap時はresetが必要です。未来の音声を加えても既に返したprefixが変わらないことを回帰テストしています。

`tracking_candidate` は未監査の参照位置候補で、常に `confirmed=false`。不確かな候補を自動譜めくりへ直結しないでください。オフラインpathとの一致率も同じ特徴量同士の**整合性**であり、独立した正解率ではありません。

## 同じWebSocket/WebRTCサーバーで使う

```sh
OPENBLAS_NUM_THREADS=1 python -m scorefollow serve --dev \
  --reference-audio movement-4.ogg --reference-timestamp-policy samples
```

参照ファイルは運用者が起動時に指定し、各リクエストで任意のパスやURLを開かせません。固定参照chromaを共有し、各sessionの履歴は分離。REST作成レスポンスとWS readyの `reference_mode=true` で識別できます。

既存の認証・入力者1名・PCM/Opus・backpressure・epoch/generation/revisionを共用します。追加の `reference_position` をWS/DataChannelで返し、ブラウザーlabの専用欄へ表示。通常の `position` は参照モードでは `position=null, alternatives=[], confidence=0, status=reference_only` とし、無関係な譜面の音符を表示しません。REST GETも同じ境界を守ります。

互換性のためCreateSessionのscoreフィールドはまだ必要ですが、参照モードでは譜面位置の証明に利用しません。試験labのdemo scoreはこの入力文脈に限ったものです。note-IDへのseekは未監査anchorがないため拒否。pause/resumeで参照履歴を破棄し再取得します。特徴量入力modeは単音特徴しか含まないため参照モードでは拒否します。

WSとDataChannelの到着順が入れ替わっても一方の位置streamが他方を潰さないよう、クライアントはstream別revisionと制御ackの共通barrierを使います。旧世代は両streamで遮断します。

## 手元の録音を実時間で送る試験

```sh
python scripts/replay_recording.py YOUR_RECORDING.m4a \
  --transport pcm --start 240 --seconds 25 --channel left --gain 0.5 \
  --output evidence/private-pcm
python scripts/replay_recording.py YOUR_RECORDING.m4a \
  --transport webrtc --start 240 --seconds 25 --channel left --gain 0.5 \
  --output evidence/private-webrtc
```

サーバーを参照モードで起動してから実行。1試験最大60秒。録音は保存せず、結果traceと終了処理を記録。既定はloopbackのみです。外部サーバーへの送信には `--allow-remote-audio` の明示が必要。元floatのS16変換でclipした割合も残します。gainは固定値で、未来のピークを見て自動調整するオンラインAGCではありません。

参照経路のライブ入力は現行transport契約どおり16kHz monoです。オフラインstereo-power照合と同一条件ではありません。チャンネルを変えた性能差、Safari/iPhone、WAN/TURNは別途評価します。

## 次の実験

実録音を1本追加しても、楽器分離や小節精度が検証済みになったわけではありません。学習・調整に使わない別録音、独立に付けた楽章/小節anchor、再開/反復/静かな部分を含む正解ラベルを用意し、誤った確定・未確定率・再取得時間・実端末遅延を評価します。

参考: AudioLabs FMP Music Synchronization (chroma/DTW), https://www.audiolabs-erlangen.de/resources/MIR/FMP/C3/C3_MusicSynchronization.html 。特定論文の性能再現は主張しません。
