# DYNAMICへの接続と譜面契約

本変更はサーバーと独立labだけです。既存readerの再生・青い記譜・PDF・監査記録を変更していません。次の統合PRでは、まず1パート/1楽章を対象に手動カーソルとserverカーソルを併存させます。

## ReaderからScoreへ

`import-dynamic` はreader schema=1の `movements[].timeline` を順に処理します。`[bar,meter_whole,seconds_per_whole,dsflag]` の並びが演奏順です。notesの `off` / `dur` とmeterは全音符単位なので4倍し、四分音符単位へ変換。初期tempoは `240/seconds_per_whole`。演奏中の変速は追従器がonset間隔から適応します（楽曲のテンポマップそのものをモデル化するv1仕様ではありません）。

`snd[2]` は**既に実音のMIDI**です。ここへさらにF管の-7を足してはいけません。`w/f` の表示名から音高を推測しません。Scoreはconcert/transpose=0。記譜音で作った別JSONではwritten/transpose_semitones=-7がF管の例です。調号・臨時記号・オクターブの読み取りは入力データ側で解決済みである必要があります。

安定ID:

- event_id: 楽章＋source note ID＋演奏上の出現番号。反復ごとに一意。
- source_id: 元readerのnote.id文字列。これで `reader.notes.find(...)` と対応。
- occurrence: 同じ元音符の演奏上の出現回数（最大64）。
- anchor: `dynamic:<reader-id>:<source-id>`。サーバーは解釈/URL取得しない。
- page: readerのsystemページ番号。原譜画像をサーバーへ渡さない。

タイ継続は同音・隙間なしの場合だけ前音に結合し、最初の音のsource_idを残します。継続側の譜面描画位置を厳密に変える必要があれば、次のreader統合でtie chainをreader側から参照します。

sourceの `unc` がある音は拒否します。Horn IIのI/IVなど実際に未解決フラグが残る入力を勝手に演奏可能にしません。`status` という自由記述が「自己チェック済み」でも、変換結果はunreviewed。使用する場合はセッションの `options.allow_unreviewed=true` を明示し、画面にも残します。audit_statusは送信者の申告であり、サーバーが原譜を監査した証明ではありません。

## Browser SDK

```js
import {ScoreClient} from './client.js';
const client = new ScoreClient('https://score.example.invalid');
client.addEventListener('position', ({detail: p}) => {
  if (p.position && p.status === 'tracking' && p.position.confirmed) {
    // reader側で対応するnoteの位置へカーソルを移す。いきなりページを飛ばさない。
    highlightBySourceId(p.position.source_id, p.position.occurrence);
  } else {
    showTentative(p.position);
  }
});
// 試験用SDK openはサービスキーを受け取る。公開アプリではtrusted backendで
// POST /v1/sessionsを代理し、利用者へはsession tokenだけ返すよう分離する。
await client.open(score, 'webrtc', serviceKey, true);
const stream = await navigator.mediaDevices.getUserMedia({audio: {
  echoCancellation: false, noiseSuppression: false, autoGainControl: false
}});
await client.rtc(stream);
// 終了時は両方必要。client.closeだけでは取得元マイクは止まらない。
stream.getTracks().forEach(track => track.stop());
await client.close();
```

これは構成例で、example.invalidへ実接続する設定ではありません。ブラウザーファイルのWebRTC実装は初回SDP交換をWSで行い、server→positionはWS/DataChannelをrevisionで統合します。端末のメインスレッドが遅い場合でも古い結果を描画し直さないようにしてください。

## 大きなモデルへの差し替え

`create_app(settings, acoustic_factory=Factory)` はPython側の信頼した設定です。Factory(A4周波数)が各セッションにbackendを返します。`push(float32_mono_samples,start_sample) -> list[Observation]`、`reset()` を実装。入力16kHz、timeはその音声時計で単調増加、pitchは実音MIDI、clarity/rmsは0..1、onsetは1音の初めに1回。未来の正解・譜面位置をObservationへ混入させません。

モデルをGPU共有する際は、sessionごとの状態を分離し、バッチ待ちdeadlineと最大同時数を追加してから実測します。現在のCPUベースラインの計測からGPU収容人数を推定してはいけません。polyphonicモデルへ替える場合、単音Observationだけでは和音分布を表せないためwire version/追従器も別途設計が必要です。

## 次の受け入れゲート

実奏者・楽器・録音セッションが重ならないholdoutを用意。目視で付けたnote/measure alignment、途中開始、停止、吹き直し、誤音、背景伴奏、低音、同音連打、長い休符、通信欠落を含めます。採用判定はフレーム正解率だけでなく、確定位置の誤り率、未確定率、再捕捉時間、誤改ページ数、実端末の音声→画面遅延で行います。主観的confidence閾値を本番の安全保証として扱いません。
