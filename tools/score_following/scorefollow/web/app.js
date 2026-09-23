import {ScoreClient} from './client.js';
import {createPcmCapture} from './pcm-capture.js';
const $=(id)=>document.getElementById(id);
let score=null,client=null,context=null,mic=null,capture=null,source=null,timer=null,paused=false;
let running=false,lastPosition=0,logLines=[];
const tones=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const pitchName=(m)=>m==null?'休符':tones[((Math.round(m)%12)+12)%12]+(Math.floor(Math.round(m)/12)-1);
function log(text){logLines.push(text);logLines=logLines.slice(-12);$('log').textContent=logLines.join('\n');}
function failure(error){$('error').hidden=false;$('error').textContent=error.message;log(`ERROR: ${error.message}`);void stop();}
function setButtons(active){
  running=active;for(const id of ['synthetic','microphone','transport','score-file','demo'])$(id).disabled=active;
  for(const id of ['stop','pause','seek'])$(id).disabled=!active;
}
function displayScore(){
  $('score-info').textContent=`${score.title} / ${score.part} · ${score.audit_status} · ${score.events.filter(n=>n.pitch!=null).length}音`;
  $('notes').replaceChildren();$('anchor').replaceChildren();
  score.events.filter(n=>n.pitch!=null).forEach((n,i)=>{
    const option=document.createElement('option');option.value=n.event_id;option.textContent=`${n.measure}小節 / ${n.beat}拍 — ${n.event_id}`;$('anchor').append(option);
    // Bounded preview only; the full score stays in the session and anchor selector.
    if(i<256){const el=document.createElement('div');el.className='note';el.dataset.event=n.event_id;
      el.append(document.createTextNode(pitchName(n.pitch)));const small=document.createElement('small');small.textContent=`${n.measure}:${n.beat}`;el.append(small);$('notes').append(el);}
  });
}
function position(m){
  lastPosition=performance.now();$('status').textContent=m.status;
  $('confidence').textContent=m.confidence.toFixed(2);$('pitch').textContent=m.pitch_midi==null?'—':`${pitchName(m.pitch_midi)} / ${m.pitch_midi.toFixed(1)}`;
  $('timing').textContent=`${m.processing_ms.toFixed(1)} / ${m.queue_ms.toFixed(1)} ms`;
  $('drops').textContent=`${m.dropped_packets} / ${m.generation}`;
  const p=m.position;
  $('measure').textContent=p?p.measure:'—';$('beat').textContent=p?`${p.beat}拍目${p.confirmed?'':'（暫定）'}`:'位置を探索中';
  $('event').textContent=p?`${p.event_id} · ${p.tempo_bpm} BPM · ${m.score_audit_status}`:'まだ位置は確定していません';
  document.querySelectorAll('.note').forEach(el=>{const on=el.dataset.event===p?.event_id;el.classList.toggle('active',on);el.classList.toggle('confirmed',on&&p.confirmed);});
  $('alternatives').textContent=m.alternatives.map(x=>`${x.event_id.padEnd(18)} Δlog=${x.relative_log_weight.toFixed(2)}  evidence=${x.evidence_notes}`).join('\n')||'候補なし';
  $('freshness').textContent=`音声時計 ${m.audio_time_s.toFixed(2)} s · gap ${m.gap_count} · ${p?.confirmed?'連続音から推定中':'自動改ページには使わず、暫定位置として扱ってください'}`;
  // An explicit, bounded diagnostics surface for automated browser verification; no tokens or audio.
  window.labState={event:p?.event_id??null,status:m.status,confirmed:p?.confirmed??false,revision:m.revision,generation:m.generation,capture:capture?.kind??'webrtc-opus',captureBufferMs:capture?.bufferMs??null};
}
async function loadDemo(){const r=await fetch('/v1/demo-score');if(!r.ok)throw new Error('demo load failed');score=await r.json();displayScore();}
async function stop(){
  if(timer){clearTimeout(timer);timer=null;}capture?.disconnect();capture=null;source?.disconnect();source=null;
  mic?.getTracks().forEach(t=>t.stop());mic=null;
  const ctx=context;context=null;if(ctx&&ctx.state!=='closed')await ctx.close();
  const c=client;client=null;if(c)await c.close();
  setButtons(false);paused=false;$('pause').textContent='追従を一時停止';$('connection').textContent='未接続';log('入力を停止し、セッションを破棄');
}
function makeSynthetic(ctx){
  // Generate PCM, then let WebRTC perform actual Opus encoding or AudioWorklet capture it.
  const duration=Math.min(180,score.events.at(-1).start*60/score.tempo_bpm+4);
  if(score.events.at(-1).start*60/score.tempo_bpm>176)throw new Error('合成接続テストは176秒以内の抜粋にしてください');
  const buffer=ctx.createBuffer(1,Math.ceil(duration*ctx.sampleRate),ctx.sampleRate),data=buffer.getChannelData(0);
  for(const n of score.events){
    if(n.pitch==null)continue;
    const midi=n.pitch+(score.pitch_domain==='written'?score.transpose_semitones:0),freq=440*2**((midi-69)/12);
    const begin=.4+n.start*60/score.tempo_bpm,len=n.duration*60/score.tempo_bpm;
    const count=Math.round(len*ctx.sampleRate),start=Math.round(begin*ctx.sampleRate);
    for(let i=0;i<count&&start+i<data.length;i++){
      const t=i/ctx.sampleRate,phase=2*Math.PI*freq*t,env=Math.min(1,t/.008)*Math.min(1,(len-t)/.02);
      data[start+i]=.23*(Math.sin(phase)+.32*Math.sin(2*phase)+.12*Math.sin(3*phase))*env;
    }
  }
  const node=ctx.createBufferSource();node.buffer=buffer;return {node,duration};
}
async function start(useMic){
  if(running)return;
  $('error').hidden=true;lastPosition=0;window.labState=null;setButtons(true);
  for(const id of ['stop','pause','seek'])$(id).disabled=true;
  try{
    const mode=$('transport').value;
    // Create/resume in the user gesture before network awaits (Safari gesture boundary).
    context=new AudioContext({sampleRate:mode==='pcm'?16000:48000,latencyHint:'interactive'});
    await context.resume();
    if(mode==='pcm'&&context.sampleRate!==16000)throw new Error('このブラウザーは16kHz AudioContextを提供しません。WebRTCを選択してください');
    if(useMic)mic=await navigator.mediaDevices.getUserMedia({video:false,audio:{channelCount:1,
      echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
    client=new ScoreClient();client.addEventListener('failure',e=>failure(e.detail));client.addEventListener('position',e=>position(e.detail));
    client.addEventListener('client-drop',()=>log('送信バッファ上限: 古い音声を破棄'));
    client.addEventListener('rtc-state',e=>{$('connection').textContent=`WebRTC ${e.detail.state}`;});
    client.addEventListener('reset-audio-clock',e=>capture?.reset(e.detail.epoch));
    await client.open(score,mode,$('api-key').value,$('allow-unreviewed').checked);
    source=useMic?context.createMediaStreamSource(mic):makeSynthetic(context).node;
    if(mode==='webrtc'){
      const destination=context.createMediaStreamDestination();source.connect(destination);
      await client.rtc(destination.stream);
    }else{
      capture=await createPcmCapture(context,data=>{if(client&&data.epoch===client.epoch)client.pcm(new Int16Array(data.buffer),data.sample);},log,failure);
      capture.reset(client.epoch);
      source.connect(capture.node);const muted=context.createGain();muted.gain.value=0;capture.node.connect(muted);muted.connect(context.destination);
    }
    if(!useMic)source.start();
    for(const id of ['stop','pause','seek'])$(id).disabled=false;
    $('connection').textContent=mode==='webrtc'?'WebRTC 接続中':'WebSocket 接続中';
    log(`${useMic?'マイク':'合成PCM'} → ${mode} → Score Follower`);
  }catch(error){failure(error);}
}
$('synthetic').addEventListener('click',()=>void start(false));$('microphone').addEventListener('click',()=>void start(true));$('stop').addEventListener('click',()=>void stop());
$('pause').addEventListener('click',async()=>{try{await client.control(paused?'resume':'pause');paused=!paused;$('pause').textContent=paused?'追従を再開':'追従を一時停止';}catch(e){failure(e);}});
$('seek').addEventListener('click',async()=>{try{$('seek').disabled=true;await client.control('seek',$('anchor').value);log(`基準位置: ${$('anchor').value}`);}catch(e){failure(e);}finally{$('seek').disabled=!running;}});
$('demo').addEventListener('click',()=>loadDemo().catch(failure));
$('score-file').addEventListener('change',async(e)=>{try{const file=e.target.files[0];if(!file)return;if(file.size>2*1024*1024)throw new Error('譜面JSONは2MiB以下にしてください');const candidate=JSON.parse(await file.text());if(candidate.schema_version!==1||!Array.isArray(candidate.events)||!candidate.events.length||candidate.events.length>4096)throw new Error('Score schema_version=1 / events=1..4096が必要です');score=candidate;displayScore();}catch(error){failure(error);}});
setInterval(()=>{if(running&&lastPosition&&performance.now()-lastPosition>2000){$('status').textContent='stale';document.querySelectorAll('.note.confirmed').forEach(el=>el.classList.remove('confirmed'));if(window.labState)window.labState.confirmed=false;$('freshness').textContent='推定更新が途切れています。位置は確定扱いにしないでください。';}},500);
window.addEventListener('pagehide',()=>{mic?.getTracks().forEach(t=>t.stop());context?.close();client?.close();});
loadDemo().catch(failure);
