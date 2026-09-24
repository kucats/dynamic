# 実験サーバーの配置

## ローカルからLAN/TLSへ

`--dev`はloopback以外を拒否します。外部接続はサービスキーと許可Originを設定。

```sh
export SF_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SF_ORIGINS='https://your-reader.example.invalid'
python -m scorefollow serve --host 0.0.0.0 --port 8765
```

例示ドメインは自分のドメインへ置換します。TLS reverse proxyでHTTPS/WSSにし、HTTP body 2MiB、WS frame64KiB、接続数/接続前認証timeout/ユーザー別セッション作成rateを制限してください。CORSは認証の代わりではありません。Originなしのnativeクライアントもtoken認証が必要です。proxy_headersは無効でX-Forwarded-Forを信用しません。リバースプロキシから認証なし開発モードへ接続してはいけません。

既定: 最大8セッション、idle90秒、絶対TTL1800秒、音声queue8。`SF_MAX_SESSIONS`, `SF_IDLE_TIMEOUT`, `SF_SESSION_TTL`で調整。8という値は収容人数のベンチマーク結果ではなく資源上限です。ブラウザーはpingを15秒ごとに送ります。絶対TTLはpingで延長されません。

## WebRTCのUDP/NAT

HTTPS/WSSが通ってもWebRTCメディアが通るとは限りません。aiortcはICE用UDP socketを動的に作成します。この実装には固定ポート範囲の割当やSDPのIP書き換えを行う独自パッチはありません。必要な経路を実ネットワークで検証してください。

最初のLinux実験ではhost networkまたはUDP到達可能なVMを使い、TLSでWSをproxy。NAT越えにはSTUN/TURNを構成し、失敗時には同じlabのPCM/WebSocketへ手動切替できます。黙った自動切替はsample clock/位置誤認の原因になるため行いません。

```sh
export SF_STUN_URLS='stun:turn.your-domain.example:3478'
export SF_TURN_URLS='turn:turn.your-domain.example:3478?transport=udp,turns:turn.your-domain.example:5349?transport=tcp'
export SF_TURN_SECRET='同じTURNサーバーと共有する32文字以上の秘密値'
```

値は例で、そのままでは接続しません。サーバーはTURN REST形式の期限付きHMAC-SHA1資格情報をセッションごとに生成し、browser/server双方に渡します。TURN secretそのものをブラウザーへ渡しません。v1の資格情報はセッションTTL+30秒で失効し、更新しません。coturn側も同じrealm/secret、正しい証明書、公開IP、relay用ポート範囲、認証と帯域/割当上限を設定します。`deploy/turnserver.conf.example` は雛形で未デプロイです。

ICE候補へのUDP送信はWebRTCの動作に必要です。マルチテナント公開前には、メタデータIP/管理ネットワーク/不要なRFC1918への送信をnetwork policyで遮断し、許可したTURN/クライアント経路だけ通します。API認証だけでネットワーク探索リスクが消えるわけではありません。

## Docker

```sh
docker build -t dynamic-scorefollow:experiment .
# Linuxのhost network例。--devを使わずAPI認証を維持する。
docker run --rm --network host --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  -e SF_API_KEY -e SF_ORIGINS -e SF_STUN_URLS -e SF_TURN_URLS -e SF_TURN_SECRET \
  dynamic-scorefollow:experiment
```

コンテナーは非root。host networkは単一ホスト実験の便宜で、隔離・UDP・NAT・TLS設計の代わりではありません。DockerビルドおよびWAN/TURN疎通は別途検証対象です。HTTPポートを公開する前にファイアウォールとTLSを設定してください。

## スケール・保存・終了

メモリー内セッションなのでASGI workers=1。複数workerへ無作為に振るとREST/WSが別プロセスへ到達してsessionが見つかりません。水平分割するならsession_id→workerのroutingを用意し、REST/WS/RTC peerの所有者を一致させます。RedisにJSONを入れるだけでRTCPeerConnectionを移動できるわけではありません。

worker終了でpeer/track/queueを閉じます。音声は保存せず、APIキー・SDP・音声・score bodyをアプリログへ出しません。ASGI access_logもCLIで無効。ただしproxy/ホスト/ブラウザー側のログ方針は別途管理が必要です。クラッシュ時のcore dumpや収集agentについても公開前に確認してください。

## 未実施の公開ゲート

WAN上のWebRTC/relay-only、IPv6/モバイル回線切替、iPhone/Safariのマイク/AudioWorklet、実際の楽器・合奏、セッション並列負荷、侵入テスト、依存関係のCVE監査、録音同意/保持方針、公開課金/ユーザー認証。これらを試験合格扱いにしてデプロイしません。
