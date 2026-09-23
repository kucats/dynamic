'use strict';
const DATA = __DATA__;
const NOTES = Object.values(DATA.pages).flatMap(ss=>ss.flatMap(s=>s.notes));
const byId=new Map(NOTES.map((n,i)=>[n.note_id,i]));
const $=id=>document.getElementById(id);
let movement=DATA.movements[0].id,index=-1,ctx=null,master=null,voices=[],playing=false,cursor=0,origin=0,raf=0,currentEvent=null,lastSection=null,events=[],spans=[],totalTicks=0,bpm=DATA.movements[0].practice_bpm||120,audioRequest=0;
const tpq=DATA.timing.ticks_per_quarter;
const secondsPerTick=()=>60/bpm/tpq;
function makeTimeline(mv,repeats){
 const events=DATA.playback[String(mv)][repeats?'repeats':'once'].map(e=>({...e}));
 const last=events.at(-1);return {events,totalTicks:last?last.play_tick+last.duration_ticks:0};
}
function makeSpans(es){const out=[];for(const e of es){if(e.kind!=='note')continue;const prev=out.at(-1);if(e.tie_from_previous&&prev&&prev.midi===e.midi&&prev.end===e.play_tick){prev.end=e.play_tick+e.duration_ticks;prev.note_ids.push(e.note_id)}else out.push({start:e.play_tick,end:e.play_tick+e.duration_ticks,midi:e.midi,note_ids:[e.note_id]});}return out;}
function rebuild(){({events,totalTicks}=makeTimeline(movement,$('repeats').checked));spans=makeSpans(events);cursor=Math.min(cursor,totalTicks);$('seek').max=totalTicks;update(cursor,false)}
function killVoices(){for(const v of voices){try{v.o.stop()}catch{}v.o.disconnect();v.g.disconnect()}voices=[];}
async function ensureAudio(){ctx??=new (window.AudioContext||window.webkitAudioContext)();if(!master){master=ctx.createGain();master.connect(ctx.destination)}master.gain.value=Number($('volume').value);await ctx.resume();}
function schedule(span,startTick,base,context=ctx,destination=master){
 const spt=secondsPerTick(),a=base+Math.max(0,span.start-startTick)*spt,b=base+(span.end-startTick)*spt;if(b<=a)return null;
 const o=context.createOscillator(),g=context.createGain();o.type=$('timbre').value;o.frequency.value=440*2**((span.midi-69)/12);
 const edge=Math.min(.008,(b-a)/4);g.gain.setValueAtTime(0,a);g.gain.linearRampToValueAtTime(1,a+edge);g.gain.setValueAtTime(1,b-edge);g.gain.linearRampToValueAtTime(0,b);o.connect(g);g.connect(destination);o.start(a);o.stop(b+.001);return {o,g,start:a,end:b,midi:span.midi};
}
function position(){return playing?Math.min(totalTicks,Math.max(cursor,(ctx.currentTime-origin)/secondsPerTick())):cursor;}
function pause(){audioRequest++;if(playing)cursor=position();playing=false;cancelAnimationFrame(raf);killVoices();$('play').textContent='▶ 再生';update(cursor,false);}
async function play(){if(playing){pause();return}const request=++audioRequest;if(cursor>=totalTicks)cursor=0;await ensureAudio();if(request!==audioRequest)return;const base=ctx.currentTime+.06;origin=base-cursor*secondsPerTick();killVoices();for(const s of spans)if(s.end>cursor){const v=schedule(s,cursor,base);if(v)voices.push(v)}playing=true;$('play').textContent='Ⅱ 一時停止';tick();}
function eventAt(t){let lo=0,hi=events.length-1;while(lo<=hi){const m=(lo+hi)>>1,e=events[m];if(t<e.play_tick)hi=m-1;else if(t>=e.play_tick+e.duration_ticks)lo=m+1;else return e}return null;}
function highlight(n,scroll){document.querySelectorAll('.note.active').forEach(el=>el.classList.remove('active'));if(!n)return;const el=document.querySelector(`[data-id="${n.note_id}"]`);el?.classList.add('active');if(scroll&&el){const section=el.closest('section');if(lastSection!==section){lastSection=section;const r=section.getBoundingClientRect();if(r.top<190||r.bottom>innerHeight-30)section.scrollIntoView({block:'center',behavior:'smooth'})}}}
function clockLabel(ticks){const sec=Math.floor(ticks*secondsPerTick());return `${Math.floor(sec/60)}:${String(sec%60).padStart(2,'0')}`;}
function update(t,scroll=true){const e=eventAt(t);$('seek').value=t;$('time').textContent=`${clockLabel(t)} / ${clockLabel(totalTicks)}`;if(e!==currentEvent){currentEvent=e;document.querySelectorAll('section.current').forEach(s=>s.classList.remove('current'));if(e){document.getElementById(`p${e.page}s${e.system}`)?.classList.add('current');const n=e.kind==='note'?NOTES[byId.get(e.note_id)]:null;if(n){index=byId.get(n.note_id);$('current').textContent=`${n.display_pitch} · ${n.position??'?'}ポジション`;highlight(n,scroll)}else{$('current').textContent='休符';highlight(null,false)}$('counter').textContent=`第${movement}楽章 · 原譜${e.page}p / ${e.system}段 · 内部小節${e.bar}`;}else{$('current').textContent=t>=totalTicks?'楽章の終わり':'—';highlight(null,false)}}if(e&&e.kind==='rest')$('duration').textContent=`休符 あと${Math.max(0,(e.play_tick+e.duration_ticks-t)/tpq).toFixed(1)}拍`;
 else if(e)$('duration').textContent=`${e.duration_ticks/tpq}拍${e.tie_to_next?' → タイ':''}${e.tie_from_previous?'（タイの続き）':''}`;else $('duration').textContent='';}
function tick(){const t=position();update(t);if(t>=totalTicks){pause();cursor=totalTicks;update(cursor);return}raf=requestAnimationFrame(tick);}
async function select(i,sound=true,scroll=true){if(i<0||i>=NOTES.length)return;pause();const n=NOTES[i];if(movement!==n.movement){movement=n.movement;$('movement').value=movement;rebuild()}index=i;if(!events.some(e=>e.note_id===n.note_id)){$('repeats').checked=true;rebuild();$('status').textContent='この音符を含む反復経路へ切り替えました'}cursor=events.find(e=>e.note_id===n.note_id).play_tick;currentEvent=null;update(cursor,scroll);if(sound){const request=++audioRequest;await ensureAudio();if(request!==audioRequest)return;const s=spans.find(s=>s.note_ids.includes(n.note_id));const v=schedule({...s,start:cursor},cursor,ctx.currentTime+.02);if(v)voices.push(v)}}
$('play').onclick=()=>play().catch(e=>{$('status').textContent=`再生できません: ${e.message}`;pause()});
$('stop').onclick=()=>{pause();cursor=0;currentEvent=null;update(cursor)};
$('nextEntry').onclick=()=>{const was=playing;pause();const e=events.find(e=>e.kind==='note'&&e.play_tick>cursor+.01);if(e){cursor=e.play_tick;currentEvent=null;update(cursor);if(was)play()} };
$('prev').onclick=()=>select(Math.max(0,index-1));$('next').onclick=()=>select(Math.min(NOTES.length-1,index+1));
$('single').onclick=()=>select(index<0?NOTES.findIndex(n=>n.movement===movement):index);
$('movement').onchange=()=>{pause();movement=Number($('movement').value);bpm=DATA.movements.find(m=>m.id===movement).practice_bpm||120;$('tempo').value=bpm;$('bpm').textContent=bpm;cursor=0;index=-1;lastSection=null;currentEvent=null;rebuild()};
$('seek').oninput=()=>{const target=Number($('seek').value);pause();cursor=target;currentEvent=null;update(cursor)};
$('tempo').oninput=()=>{const was=playing;pause();bpm=Number($('tempo').value);$('bpm').textContent=bpm;update(cursor,false);if(was)play()};
$('repeats').onchange=()=>{pause();cursor=0;currentEvent=null;rebuild()};
$('timbre').onchange=pause;$('volume').oninput=()=>{if(master)master.gain.value=Number($('volume').value)};
document.querySelectorAll('.note').forEach(el=>{el.onclick=()=>select(byId.get(el.dataset.id),true,false);el.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();select(byId.get(el.dataset.id),true,false)}}});
document.addEventListener('keydown',e=>{if(e.target.matches('input,button,select,summary'))return;if(e.code==='Space'){e.preventDefault();play()}else if(e.key==='ArrowRight'){e.preventDefault();select(Math.min(NOTES.length-1,index+1))}else if(e.key==='ArrowLeft'){e.preventDefault();select(Math.max(0,index-1))}});
$('showLabels').onchange=()=>document.body.classList.toggle('plain',!$('showLabels').checked);
$('tempo').value=bpm;$('bpm').textContent=bpm;rebuild();
window.__scoreQA={noteCount:NOTES.length,uniqueIds:byId.size,notes:NOTES,makeTimeline,makeSpans,eventAt,select,schedule,get state(){return {playing,cursor:position(),movement,index,totalTicks,event:currentEvent,contextState:ctx?.state,voiceCount:voices.length}},async offlineSample(seconds=12){const sr=22050,oc=new OfflineAudioContext(1,Math.ceil(sr*seconds),sr),gain=oc.createGain();gain.gain.value=.2;gain.connect(oc.destination);for(const s of makeSpans(makeTimeline(movement,false).events)){if(s.start*secondsPerTick()>=seconds)break;schedule(s,0,0,oc,gain)}const b=await oc.startRendering(),a=b.getChannelData(0);return {sampleRate:sr,length:a.length,peak:a.reduce((m,x)=>Math.max(m,Math.abs(x)),0),samples:Array.from(a)}}};
