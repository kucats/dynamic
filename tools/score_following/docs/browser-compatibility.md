# ブラウザーのPCM互換経路

AudioWorkletを優先し、初期化できない場合だけScriptProcessorの互換経路を明示して使用します。互換経路は128msブロックを20msの送信パケットへ分割するため、取り込み段だけで追加の遅延が生じます。接続ログとbrowser evidenceの`capture`/`captureBufferMs`で識別できます。AudioWorklet自体の実ブラウザー試験合格と、互換経路の合格を混同しません。標準の低遅延経路はWebRTCです。ScriptProcessorは非推奨APIなので恒久的な製品依存にはせず、実端末でAudioWorkletを再検証してください。

```sh
node --test scripts/pcm-capture.test.mjs
```

## Clock and transport details

The lab attempts AudioWorklet first. If module initialization fails or exceeds two seconds, it reports `script-processor-compat` in the diagnostics and uses 2048-sample (128ms) blocks, reframed into the same 320-sample wire packets. This does not change the transport or consent boundary. The compatibility capture uses exact delivered sample counts within 32ms of legacy playbackTime jitter, preserving larger forward gaps and rejecting backwards discontinuities. It cannot establish sample-perfect microphone loss telemetry under a heavily blocked main thread. WebRTC remains the preferred path. ScriptProcessor is deprecated in the Web Audio specification: https://www.w3.org/TR/webaudio/#the-scriptprocessornode-interface .
