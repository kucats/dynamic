# Wire protocol: sfs.v1

## REST

`POST /v1/sessions` は `Authorization: Bearer <service-key>` とJSON `{"score":...,"options":...}`。`--dev`時のみサービスキー不要。JSON schemaは `session.schema.json`、実行中は `/openapi.json`。既定のSwagger UIは外部CDNを避けるため無効です。

成功201: `session_id, token, ws_path, protocol, ttl_s, ice_servers, score_sha256`。
401は認証失敗、403はOrigin/開発接続元違反、413は実データ2MiB超、422は譜面やoption違反、429はセッション容量不足。サービスキーはサーバー側の信頼したアプリが保管し、利用者ごとのセッショントークンだけ端末へ渡す構成を推奨します。試験画面のサービスキー欄は管理者のローカル動作確認用です。

`GET /v1/sessions/{id}` / `DELETE /v1/sessions/{id}` は **セッショントークン** のBearer認証。DELETEは音声・peer・workerを破棄。`GET /healthz` は公開、`GET /metrics` はサービスキーが必要。生音声や譜面を保存しません。推定を保存したいときはクライアントが同意を得て保存してください。

## WebSocket

RESTの `ws_path` に接続。トークンはURLに入れず、5秒以内の最初のテキストメッセージで渡します。

```json
{"type":"auth","protocol":"sfs.v1","token":"SESSION_TOKEN","mode":"pcm"}
```

mode: `pcm` / `features` / `webrtc` / `observe`。1セッションに入力者1つ、全購読者最大3つ。observeは読み取り専用で音声や制御を送れません。再接続は明示的に行い、過去のフレームを自動再送しません。旧入力者がまだ生きていれば `input_already_owned` で拒否されます。

`ready` に `epoch, generation, sample_rate=16000,channels=1,format=s16le,hop_samples=320,max_packet_samples=1600,score_sha256` が返ります。

### PCMのバイナリ

全整数はlittle endian。コンテナ形式のWAV/Opus/WebMをこの経路へ送らないでください。

| offset | bytes | 内容 |
|---:|---:|---|
| 0 | 4 | ASCII `SFS1` |
| 4 | 4 | uint32 epoch（ready/ackで取得） |
| 8 | 4 | uint32 seq、世代内で単調増加 |
| 12 | 8 | uint64 sample_index、16kHzでのチャンク先頭位置 |
| 20 | 320〜3200 | signed int16 mono、160〜1600 samples（10〜100ms） |

通常は320 samples/20ms。先頭sample_index=0、次は320。音声を捨てたときは**欠けた分もsample_indexに反映**し、時刻を詰めないこと。重複seq、時刻逆行、旧epoch、30秒超の飛び、2^48超の位置は拒否。平均1.25倍速以内、最大300msのburstに制限しています。高速ファイル送信はoffline evaluatorを使います。PCM入力の音声時計は端末が申告する時計であり、信頼された壁時計ではありません。

### 特徴量

50Hzで**無音も含め連続して**送ります。音が鳴った時だけ送る形式ではありません。

```json
{"type":"feature","epoch":1,"seq":12,"sample_index":3840,
 "pitch_midi":62.04,"clarity":0.94,"rms":0.12,"onset":true}
```

pitchは実音MIDI（小数はチューニング差）、無音はnull。0..1のclarityとrms、onsetは立ち上がりに一度だけtrue。NaN/Infinity/未知フィールドを拒否。feature経路はクライアント算出特徴量を信用する研究用APIで、演奏の真正性を証明するものではありません。

### WebRTC

mode=webrtcで認証後、1本の音声トラックと任意のDataChannel `positions` を持つRTCPeerConnectionを作成します。RESTの `ice_servers` を利用。**ICE gathering completeまで待った完全なoffer** を送信します（v1はtrickle ICE / renegotiation / ICE restartに非対応）。

```json
{"type":"offer","sdp":"v=0\r\n..."}
```

`answer` メッセージのsdpをsetRemoteDescription。途中にrtc_stateが来るため、次の1メッセージを無条件にanswerとして読まないこと。SDPは48kB/512行/64候補まで、audio1本＋application最大1本、video拒否。Opus受信をPyAVの継続的resamplerで16kHz monoへ変換して**PCM経路と同じqueue/DSP/follower**へ流します。

DataChannelは任意。`positions`、unordered/maxRetransmits=0を推奨。サーバー→クライアント専用で、クライアントから送信すると閉じます。WSにも同一のpositionが来るため、重複をrevisionで捨てます。RTPの損失補償で生成されたサンプルと、本来収録した音声を完全に区別できるわけではありません。`gap_count` は検出できたサンプル時計の不連続であり、RTP損失率ではありません。

## 制御・結果の順序

```json
{"type":"pause"}
{"type":"resume"}
{"type":"seek","event_id":"n005"}
{"type":"ping"}
```

制御は入力者のWSのみ。pause/resume/seekにack。**同時に複数の制御リクエストを飛ばさず、ackを待つ**設計です。pauseは追従だけを止めます。マイクの送信を止める操作ではありません。送信終了はクライアントの停止・切断を使います。

PCM/featuresのseekはepochとgenerationを更新し、seq/sample clockを0から再開。ack後にAudioWorkletも世代を切り替え、旧世代のpostMessageを捨てます。WebRTCのseekはRTP clock/接続を維持してgenerationだけ更新します。generationは処理待ち・すでにdequeue済みの旧音声を遮断します。断線からの新入力者は必ず新epoch。

結果は `type=position`、`epoch/generation/revision`、`audio_time_s`、`status`、`confidence_kind=uncalibrated_heuristic`、`confidence`、`position|null`、`alternatives`、音高・音量・各種counter。

`position` は `event_id,source_id,occurrence,measure,beat,page,anchor,note_index,score_quarter,predicted_quarter,tempo_bpm,confirmed`。beatとstart/durationは四分音符単位、measureは文字列。複合拍子の「何拍目」という見た目への変換はreader側が行います。`predicted_quarter` は現在の音符内だけの予測で、次の音符・長休符を越えて確定しません。

- `acquiring/uncertain/lost`: 自動改ページの根拠にしない。
- `tracking`: 3音以上の連続証拠＋候補分離指標が閾値以上。正解保証ではない。
- `holding`: 無音が規定時間を超過。直前位置を保つがconfidence=0。
- `paused`: 推論停止、confidence=0。

クライアントはscore digest不一致、旧epoch、旧generation、同一/旧revisionを捨てます。2秒以上更新がなければstaleとして表示を解除します。絶対TTLの満了・不正入力・rate超過時はerror/closed後に切断。再開する場合は新しいセッションまたは新しい入力接続を明示的に作ります。

## 計測とバックプレッシャー

音声queueは既定8チャンク（20msなら160ms、100msなら800ms）。満杯時は最古を捨て、時計の不連続として追従の確信を解除します。購読queueは16メッセージ、位置通知は新しいものに集約、制御は順序保持。遅い送信先は2秒timeoutで切断。computeはワーカースレッドで実行し、セッションごとのlockで直列化します。event loopに重い推論を直接置きません。

`processing_ms` はqueue取り出し後の処理時間（thread dispatch含む）、`queue_ms` はqueue滞留、`window_ms=128` はDSP窓長。どれも単体で「マイクから画面までの遅延」を表しません。エンドツーエンド遅延は別途端末とサーバーの時計、入力実時刻、画面描画時刻を記録して測定してください。
