# 実録音によるScore Following実験 / 2026-09-24

## 対象と証拠の区別

ユーザー提供の「Dvořák 8、トロンボーン近傍」という録音1本。楽章・小節・奏者別の正解ラベルは未提供。音源、元のファイル名、私的な保存パス、録音の細粒度traceをGitHub/CIへアップロードしていません。以下はローカル計測の集約値です。元譜の音符監査でも、録音の正解alignmentでもありません。

入力AAC、48kHz stereo、コンテナー約470.848秒。実際の16kHz復号データは7,532,864samples=470.804秒、元PTS原点0.044秒。floatピーク約1.081。これはAAC復号のovershootを含み得るため原録音のclip率とは呼びません。L/R相関0.315。

## 単音ベースラインの診断

全録音を既存YIN経路へ入力。有声音判定率はL54.3%、R52.1%、mix58.6%。両方が有声のフレームでは、L/R音高が半音以内に一致する割合は78.0%。**これらは音高正解率・トロンボーン識別率ではありません。**

利用可能な未監査Horn II/IIIデータへの試行は、別パート参照の負の対照として扱いました。トロンボーンの参照譜面ではないため、そこで返るnote IDやconfidenceを正解位置とは呼びません。

## 参照演奏4楽章とのオフライン比較

DuPage Symphony Orchestra / Barbara Schubertの公開音源（出典・ライセンス・hashはtools/score_following/docs/reference-attribution.json）。公開ファイルのみを一時的なCI artifact経由で取得し、私的録音との比較はローカルで実行。OGGの短いPTS往復誤差は明示的なsample-clock正規化を使用し、strict入力では拒否されることも確認しました。

独自chroma→subsequence DTWで録音全体を比較。正規化距離（小さい方が一致しやすい）は第1楽章0.3213、第2楽章0.3326、第3楽章0.3014、第4楽章0.2030。**第4楽章の途中〜終盤が有力という推定**です。最良の全体pathは参照約150.8〜594.9秒へ対応しますが、終端には近い距離の別候補もあり、秒単位の正解を保証しません。譜面小節へは未変換。

## オンライン候補追従の改善

短い12秒window＋弱いcontinuity判定では、似たフレーズへの誤捕捉が多く発生。20秒windowと保守的な取得/維持ルールへ変更しました。同一録音で調整した開発実験であり、holdoutではありません。

最終実験: 451更新のうち186更新=41.2%をtracking_candidateとし、残りはuncertain。最初のtracking_candidateは録音時計約74.2秒。tracking_candidate区間のオフラインpathとの時間差は中央値0.20秒、95percentile3.425秒、2秒以内93.0%。**これは独立正解に対する精度ではなく、同じ特徴量による因果推定とオフライン推定の整合性です。** 全更新の差は95percentile492秒に達し、未確定候補をそのまま譜めくりに使うと危険です。生の最良候補の数字だけを見せず、uncertainを維持する必要があります。

## 実録音の通信経路試験

元録音の復号時計240.0秒から25秒、left channel、固定gain0.5を実時間送信。localhostで独立にWebSocket PCMとWebRTC/Opusを実行。

| 経路 | 結果通知 | 参照候補通知 | 最終参照候補 | エラー | 終了 |
|---|---:|---:|---:|---:|---|
| WebSocket PCM | 269 | 5 | 396.456秒 | 0 | session削除・registry空 |
| WebRTC Opus | 270 | 5 | 396.356秒 | 0 | peer終了・session削除・registry空 |

両経路とも最終候補のaudio_time=24.156秒。候補差0.100秒。PCM変換後clip割合0。**通信・復号・結果返却が通った証拠であり、小節や音符の精度検証とは別です。** WebRTCは実際のICE/DTLS/Opusを経由し、モックではありません。

## コード変更と検証境界

M4A浮動小数取り込み、stereo-power chroma、因果的候補追従、参照モードの同一WS/RTCサーバー統合、参照秒数と譜面位置の分離、誤音時の古いconfirmed解除、2種類の位置streamのrevision順序制御、実時間録音replay CLIを追加。

ローカルPython3.13: 89 pytest PASS、Node11 PASS。既存の単音/WS/WebRTC試験も含みます。録音をCIに入れず、CIは合成fixtureと既存公開readerデータのみで検証。最終commitのCI状況は今回の後続PRを参照。PR #5の合成データのみの結果とは区別します。

**未検証**: トロンボーンの個別音源分離、正解小節anchor、別録音holdout、iPhone/Safari実機、WAN/TURN、並列容量。自動譜めくり製品として完成したとは扱いません。次は正しいパート譜と独立にレビューした時間anchorを接続します。
