/* The AudioContext itself runs at 16kHz; no fake sample-rate header or lossy decimation. */
class Capture16k extends AudioWorkletProcessor {
  constructor() {
    super(); this.buffer = new Int16Array(320); this.used = 0; this.sample = 0; this.epoch = 0;
    this.port.onmessage = (e) => { if (e.data?.type === 'reset') { this.used=0; this.sample=0; this.epoch=e.data.epoch; } };
  }
  process(inputs) {
    const channel=inputs[0]?.[0];
    if (channel) for (const v of channel) {
      this.buffer[this.used++]=Math.round(Math.max(-1, Math.min(1, v))*32767);
      if (this.used===320) {
        const buffer=this.buffer;
        this.port.postMessage({sample:this.sample, epoch:this.epoch, buffer:buffer.buffer}, [buffer.buffer]);
        this.sample+=320; this.used=0; this.buffer=new Int16Array(320);
      }
    }
    return true;
  }
}
registerProcessor('capture16k', Capture16k);
