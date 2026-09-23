/* Prefer AudioWorklet. Bounded, explicitly reported compatibility capture is slower. */
export class PcmFramer {
  constructor(onFrame) { this.onFrame=onFrame; this.reset(0); }
  reset(epoch) { this.epoch=epoch; this.buffer=new Int16Array(320); this.used=0; this.cursor=0; this.end=0; }
  push(channel,start) {
    if(!Number.isSafeInteger(start)||start<this.end)throw new Error(`capture clock regression ${start}/${this.end}`);
    if(start!==this.end) { this.used=0; this.cursor=start; }
    for(const value of channel) {
      if(!Number.isFinite(value))throw new Error('nonfinite captured sample');
      this.buffer[this.used++]=Math.round(Math.max(-1,Math.min(1,value))*32767);
      if(this.used===320) {
        const buffer=this.buffer;
        this.onFrame({sample:this.cursor,epoch:this.epoch,buffer:buffer.buffer});
        this.cursor+=320;this.used=0;this.buffer=new Int16Array(320);
      }
    }
    this.end=start+channel.length;
  }
}
export async function createPcmCapture(context,onFrame,onWarning,onError) {
  if(context.sampleRate!==16000)throw new Error('PCM capture requires a real 16kHz AudioContext');
  let timeout;
  try {
    if(!context.audioWorklet)throw new Error('AudioWorklet unavailable');
    await Promise.race([
      context.audioWorklet.addModule(new URL('./pcm-worklet.js',import.meta.url)),
      new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('AudioWorklet initialization timeout')),2000);})
    ]);
    const node=new AudioWorkletNode(context,'capture16k');
    node.port.onmessage=e=>onFrame(e.data);
    node.onprocessorerror=()=>onError(new Error('AudioWorklet processor failed; reconnect'));
    return {node,kind:'audio-worklet',bufferMs:20,
      reset:(epoch)=>node.port.postMessage({type:'reset',epoch}),
      disconnect:()=>{node.port.onmessage=null;node.disconnect();}};
  } catch(error) {
    if(context.state==='closed')throw error;
    if(typeof context.createScriptProcessor!=='function')throw new Error('AudioWorklet unavailable; select WebRTC');
    // Deprecated API used only as a declared experimental compatibility path.
    // 2048 samples = 128ms blocks, reframed to bounded 20ms wire packets.
    const node=context.createScriptProcessor(2048,1,1);
    const framer=new PcmFramer(onFrame);
    let origin=null;
    node.onaudioprocess=e=>{
      try {
        if(origin===null)origin=e.playbackTime;
        const observed=Math.round((e.playbackTime-origin)*16000);
        // Legacy playbackTime may jitter by render quanta. Preserve exact delivered
        // sample counts within 32ms; larger forward gaps remain explicit.
        const start=Math.abs(observed-framer.end)<=512?framer.end:observed;
        framer.push(e.inputBuffer.getChannelData(0),start);
      }catch(err){onError(err);}
    };
    onWarning('互換PCM取り込み: AudioWorklet初期化不可。128msバッファを使用（低遅延用途はWebRTC推奨）');
    return {node,kind:'script-processor-compat',bufferMs:128,
      reset:(epoch)=>{origin=null;framer.reset(epoch);},
      disconnect:()=>{node.onaudioprocess=null;node.disconnect();}};
  } finally {clearTimeout(timeout);}
}
