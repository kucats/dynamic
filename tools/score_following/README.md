# DYNAMIC Score Following Server

**演奏中の単旋律音声から譜面の位置を推定する、実行可能な独立実験サーバーです。**
WebRTC受信（ICE / DTLS / Opus復号）、WebSocket PCM・特徴量入力、状態を持つ追従器、ブラウザー試験画面、オフライン評価を含みます。既存の `public/reader/` は変更しません。

「試験用サーバーとしての実装」と「実楽器・合奏での精度保証」は別です。これは学習済み大規模モデルではなく、因果的YIN音高推定＋独自のイベント単位beam alignmentを使った **単旋律ベースライン** です。`confidence` は未較正の指標で、正解確率ではありません。実録音を使う次の段階で比較・置換できるようにしています。

## 起動

Linux / Python 3.13で検証。リポジトリからは `cd tools/score_following`、単独ZIPでは展開先をカレントにしてください。

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -c constraints-py313.txt '.[test,client]'
python -m scorefollow fixtures fixtures/demo
python -m scorefollow serve --dev
```

ブラウザーで `http://127.0.0.1:8765` を開き、**合成音声で接続テスト**。WebRTCとWebSocketを切り替えて同じ16音を追従します。スピーカーへの合成音出力はありません。「マイクで練習」はHTTPSまたはlocalhostで利用します。端末でマイク権限が必要です。

`--dev` はループバック限定・サービスキー不要です。LAN接続・外部提供では使用しません。`--workers` を増やさないでください。セッションは1プロセスのメモリー内にあり、再起動で消えます。

## 入っているもの

| 部分 | 実装 |
|---|---|
| 音声 | 16kHz mono、20ms hop、128ms trailing window、YIN、音量・音高変化・再アタック検出 |
| 追従 | 既知譜面、音高・onset間隔・テンポ推定、候補beam、誤音挿入・少数音飛ばし・再探索 |
| WebRTC | `aiortc`で実音声受信、PyAVで16kHzに再標本化、WSでSDP交換、任意のDataChannel位置返却 |
| WebSocket | PCM16バイナリ、50Hz特徴量、制御・位置通知・read-only observer |
| 状態管理 | 1入力所有者、token認証、epoch/generation fencing、sequence/sample clock、有限queue、TTL、切断破棄 |
| 入出力 | 譜面JSON、DYNAMIC reader変換、限定MusicXML変換、source_id/occurrence/anchor |
| 試験 | オリジナル合成WAV・正解ラベル、8シナリオ、HTTP/WS/実WebRTC/ブラウザー試験 |
| 運用 | 認証付きmetrics、容量制限、Dockerfile、TURN設定例、統合契約 |

## 試験と実録音評価

```sh
python -m pytest -q
python -m scorefollow benchmark evidence/local
python -m scorefollow evaluate fixtures/demo/score.json fixtures/demo/performance.wav \
  --labels fixtures/demo/labels.json --output evidence/replay
python -m scorefollow schema > docs/session.schema.json
```

実録音は**16kHz / mono / PCM16 WAV**に変換して上記evaluateへ渡します。`--labels` は省略でき、その場合も全推定の `trace.jsonl` が出ます。正解ラベルは評価だけで使用し、追従器へ渡しません。ラベル仕様は `docs/evaluation.md`。

```sh
# DYNAMICの既存reader JSONを取り込み。原譜画像は出力・送信しません。
python -m scorefollow import-dynamic ../../public/reader/data/dvorak8-horn2.json \
  score.json --movement II
# 変換は監査ではありません。実験利用を明示して評価します。
python -m scorefollow evaluate score.json your-private-recording.wav \
  --allow-unreviewed --output evidence/private-local-only
# 単一声部・単旋律・反復を展開済みのMusicXMLサブセット
python -m scorefollow import-musicxml part.musicxml score.json --part-id P1
```

未解決の `unc` があるDYNAMIC音符、未対応のMusicXML反復・和音・装飾音・複声部等は**黙って読み替えず拒否**します。独立監査済みとしては扱いません。詳細は `docs/integration.md`。

ブラウザースモーク試験（別端末でサーバーを起動）:

```sh
python -m pip install 'playwright==1.55.0'
python -m playwright install chromium --only-shell
python scripts/browser_smoke.py
```

試験用ブラウザーの起動引数 `--no-sandbox` は隔離したCI fixtureテスト用です。一般のWebページ巡回には利用しません。

## 次の統合

`scorefollow/web/client.js` の `ScoreClient` をアプリ側で利用できます。セッション作成→音声接続→`position`イベントの `source_id` / `anchor` を既存の譜面上の音符へ対応させます。大きいモデルへの差し替えは `create_app(settings, acoustic_factory=YourBackend)`。各セッションに返すオブジェクトは `audio.AcousticBackend` の `push(samples,start_sample)` / `reset()` を満たし、16kHz音声時計で `Observation` を出します。モデル名やPythonコードを外部クライアントから指定するAPIはありません。

最初は独奏／近接マイクで検証してください。合奏・伴奏混在、残響、非常に速い音符、弱い基音、長休符中の現在位置、任意の反復識別、ネットワーク込み遅延と収容人数は別途評価が必要です。開始直後や同じ音型では複数音を待つことがあり、無音から勝手に次の小節へ進めません。

- 通信・世代・セキュリティ: `docs/protocol.md`
- 既存画面への統合・移調・監査境界: `docs/integration.md`
- 評価指標・既知の失敗: `docs/evaluation.md`
- Linux / TLS / TURN / 多プロセスの制約: `docs/deployment.md`
- 実行結果と未実行事項: `evidence/VALIDATION.md`

## 参考（実装の一次資料）

- aiortc API: https://aiortc.readthedocs.io/en/latest/api.html
- PyAV audio: https://pyav.basswood.io/docs/stable/api/audio.html
- W3C Media Capture constraints: https://w3c.github.io/mediacapture-main/
- 関連研究: Nakamura et al., real-time audio-to-score alignment, https://arxiv.org/abs/1512.07748

追従器はこのリポジトリで作成した実験ベースラインであり、上記論文のアルゴリズム・性能を再現したという意味ではありません。

## v0.2: M4A実録音・合奏参照モード

`python -m scorefollow.recording_lab` でローカル録音の診断・参照比較・因果追従を実行できます。`serve --reference-audio REF` は同じWebSocket/WebRTC受信で参照演奏内の秒数を返します。参照モードでは小節・音符への対応を未監査のまま確定せず、`score_position=null` を維持します。手順・時計・privacy・未検証事項は [recording-lab.md](docs/recording-lab.md)。
