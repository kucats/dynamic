/* Reusable transport client: session credentials stay in memory, never URLs/storage. */
export class ScoreClient extends EventTarget {
  constructor(base=location.origin) {
    super(); this.base=base.replace(/\/$/,''); this.epoch=0; this.generation=0;
    this.controlQueue=Promise.resolve(); this.revision=0; this.seq=0; this.closed=false; this.waiters=new Map(); this.heartbeat=null;
  }
  emit(type,detail) { this.dispatchEvent(new CustomEvent(type,{detail})); }
  wait(type, timeout=15000) {
    return new Promise((resolve,reject)=>{
      const id=setTimeout(()=>{this.waiters.delete(type);reject(new Error(`${type}: timeout`));},timeout);
      this.waiters.set(type,{resolve:(v)=>{clearTimeout(id);resolve(v);},reject:(e)=>{clearTimeout(id);reject(e);}});
    });
  }
  async open(score, mode, apiKey='', allowUnreviewed=false) {
    this.mode=mode;
    const headers={'Content-Type':'application/json'};
    if(apiKey) headers.Authorization=`Bearer ${apiKey}`;
    const response=await fetch(`${this.base}/v1/sessions`,{method:'POST',headers,
      body:JSON.stringify({score,options:{allow_unreviewed:allowUnreviewed}})});
    if(!response.ok) throw new Error(`Session HTTP ${response.status}: ${(await response.text()).slice(0,500)}`);
    this.info=await response.json();
    const url=new URL(this.info.ws_path,this.base); url.protocol=url.protocol==='https:'?'wss:':'ws:';
    const ready=this.wait('ready');
    this.ws=new WebSocket(url);
    this.ws.addEventListener('open',()=>this.ws.send(JSON.stringify({type:'auth',protocol:'sfs.v1',
      mode,token:this.info.token})));
    this.ws.addEventListener('message',(e)=>{
      try { this.receive(JSON.parse(e.data)); } catch(error) { this.fail(error); }
    });
    this.ws.addEventListener('error',()=>this.fail(new Error('WebSocket connection failed')));
    this.ws.addEventListener('close',()=>{ if(!this.closed) this.fail(new Error('Connection closed; audio stopped, reconnect explicitly')); });
    await ready;
    this.heartbeat=setInterval(()=>{if(this.ws?.readyState===1)this.ws.send('{"type":"ping"}');},15000);
    return this.info;
  }
  receive(message) {
    if(message.score_sha256 && this.info && message.score_sha256 !== this.info.score_sha256) {
      this.fail(new Error('score digest mismatch')); return;
    }
    if(message.type==='error') { this.fail(new Error(message.code)); return; }
    if(message.type==='position') {
      // DataChannel may be unordered and race ordered WebSocket. One version order for both.
      if(message.epoch<this.epoch || message.generation<this.generation || message.revision<=this.revision) return;
      this.epoch=message.epoch; this.generation=message.generation; this.revision=message.revision;
    } else if(['ready','ack'].includes(message.type)) {
      if(message.epoch>this.epoch) { this.seq=0; this.emit('reset-audio-clock',{epoch:message.epoch}); }
      this.epoch=message.epoch; this.generation=message.generation;
      if(message.revision) this.revision=Math.max(this.revision,message.revision);
    }
    const waiter=this.waiters.get(message.type);
    if(waiter) { this.waiters.delete(message.type);waiter.resolve(message); }
    this.emit(message.type,message);
  }
  fail(error) {
    if(this.closed) return;
    for(const waiter of this.waiters.values()) waiter.reject(error);
    this.waiters.clear(); this.emit('failure',error);
    // Consumers must close microphone/AudioContext; transports close here as well.
    void this.close();
  }
  pcm(samples, sampleIndex) {
    if(this.ws?.readyState!==1 || this.closed) return false;
    const seq=this.seq++;
    if(this.ws.bufferedAmount>16000) { this.emit('client-drop',{samples:samples.length});return false; }
    const raw=new ArrayBuffer(20+samples.length*2), v=new DataView(raw);
    v.setUint32(0,0x31534653,true); v.setUint32(4,this.epoch,true);v.setUint32(8,seq,true);
    v.setBigUint64(12,BigInt(sampleIndex),true);
    for(let i=0;i<samples.length;i++)v.setInt16(20+i*2,samples[i],true);
    this.ws.send(raw);return true;
  }
  async rtc(stream) {
    this.pc=new RTCPeerConnection({iceServers:this.info.ice_servers});
    for(const track of stream.getAudioTracks()) this.pc.addTrack(track,stream);
    const dc=this.pc.createDataChannel('positions',{ordered:false,maxRetransmits:0});
    dc.addEventListener('message',(e)=>{try{this.receive(JSON.parse(e.data));}catch(error){this.fail(error);}});
    this.pc.addEventListener('connectionstatechange',()=>{
      this.emit('rtc-state',{state:this.pc.connectionState});
      if(this.pc.connectionState==='failed')this.fail(new Error('ICE/DTLS failed; check UDP/TURN and reconnect'));
    });
    await this.pc.setLocalDescription(await this.pc.createOffer());
    if(this.pc.iceGatheringState!=='complete')await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pc?.removeEventListener('icegatheringstatechange',onState);reject(new Error('ICE gathering timeout'));},12000);
      const onState=()=>{if(this.pc?.iceGatheringState==='complete'){clearTimeout(timer);this.pc.removeEventListener('icegatheringstatechange',onState);resolve();}};
      this.pc.addEventListener('icegatheringstatechange',onState);onState();
    });
    const answer=this.wait('answer');this.ws.send(JSON.stringify({type:'offer',sdp:this.pc.localDescription.sdp}));
    const received=await answer;
    await this.pc.setRemoteDescription({type:'answer',sdp:received.sdp});
    if(this.pc.connectionState!=='connected')await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pc?.removeEventListener('connectionstatechange',onState);reject(new Error('WebRTC connect timeout'));},15000);
      const onState=()=>{if(this.pc?.connectionState==='connected'){clearTimeout(timer);this.pc.removeEventListener('connectionstatechange',onState);resolve();}};
      this.pc.addEventListener('connectionstatechange',onState);onState();
    });
  }
  control(type,event_id) {
    const operation=this.controlQueue.then(async()=>{
      if(this.closed||!this.ws)throw new Error('not connected');
      const response=this.wait('ack',5000);
      this.ws.send(JSON.stringify(event_id?{type,event_id}:{type}));
      return response;
    });
    this.controlQueue=operation.catch(()=>{});
    return operation;
  }
  async close() {
    if(this.closed)return;
    this.closed=true;clearInterval(this.heartbeat);
    for(const waiter of this.waiters.values())waiter.reject(new Error('client closed'));
    this.waiters.clear();this.ws?.close();this.pc?.close();
    if(this.info) {
      try { await fetch(`${this.base}/v1/sessions/${this.info.session_id}`,{method:'DELETE',
        headers:{Authorization:`Bearer ${this.info.token}`},signal:AbortSignal.timeout(3000)}); } catch { /* TTL is the backstop. */ }
      this.info=null;
    }
  }
}
