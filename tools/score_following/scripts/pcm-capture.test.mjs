import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {PcmFramer,createPcmCapture} from '../scorefollow/web/pcm-capture.js';

test('compatibility blocks become bounded, continuous PCM packets',()=>{
  const rows=[],f=new PcmFramer(x=>rows.push(x));f.reset(7);
  f.push(new Float32Array(2048).fill(.5),0);
  f.push(new Float32Array(2048).fill(-.5),2048);
  assert.equal(rows.length,12);
  rows.forEach((r,i)=>{assert.equal(r.sample,i*320);assert.equal(r.epoch,7);assert.equal(r.buffer.byteLength,640);});
  assert.equal(new Int16Array(rows[0].buffer)[0],16384);
});
test('seek fences and discards partial old capture',()=>{
  const rows=[],f=new PcmFramer(x=>rows.push(x));f.reset(2);
  f.push(new Float32Array(200).fill(1),0);f.reset(3);
  f.push(new Float32Array(320),0);
  assert.equal(rows.length,1);assert.equal(rows[0].sample,0);assert.equal(rows[0].epoch,3);
  assert.ok(new Int16Array(rows[0].buffer).every(v=>v===0));
});
test('capture gaps are not squeezed into a continuous clock',()=>{
  const rows=[],f=new PcmFramer(x=>rows.push(x));
  f.push(new Float32Array(100),0);f.push(new Float32Array(320),1600);
  assert.equal(rows[0].sample,1600);
  assert.throws(()=>f.push(new Float32Array(320),1600),/regression/);
  assert.throws(()=>f.push(new Float32Array([NaN]),1920),/nonfinite/);
});
test('actual AudioWorklet processor code reframes samples and fences epochs',()=>{
  let Processor;const rows=[];
  const sandbox={AudioWorkletProcessor:class{constructor(){this.port={postMessage:m=>rows.push(m)};}},
    registerProcessor:(name,C)=>{assert.equal(name,'capture16k');Processor=C;}};
  vm.runInNewContext(readFileSync(new URL('../scorefollow/web/pcm-worklet.js',import.meta.url),'utf8'),sandbox);
  const p=new Processor();p.port.onmessage({data:{type:'reset',epoch:5}});
  for(let i=0;i<5;i++)p.process([[new Float32Array(128).fill(.25)]]);
  assert.equal(rows.length,2);assert.equal(rows[1].sample,320);assert.equal(rows[1].epoch,5);
  p.process([[new Float32Array(128).fill(1)]]);p.port.onmessage({data:{type:'reset',epoch:6}});
  p.process([[new Float32Array(320)]]);
  assert.equal(rows[2].sample,0);assert.equal(rows[2].epoch,6);
  assert.ok(new Int16Array(rows[2].buffer).every(v=>v===0));
});
test('compatibility initialization explicitly reports its buffer and cleans up',async()=>{
  const rows=[],warnings=[],node={disconnect(){this.disconnected=true;}};
  const context={sampleRate:16000,state:'running',createScriptProcessor(size){assert.equal(size,2048);return node;}};
  const capture=await createPcmCapture(context,x=>rows.push(x),x=>warnings.push(x),e=>{throw e;});
  assert.equal(capture.kind,'script-processor-compat');assert.equal(capture.bufferMs,128);assert.equal(warnings.length,1);
  capture.reset(4);
  const event=t=>({playbackTime:t,inputBuffer:{getChannelData:()=>new Float32Array(2048)}});
  node.onaudioprocess(event(1));node.onaudioprocess(event(1.12));
  assert.equal(rows.length,12);assert.equal(rows[11].sample,3520);
  capture.disconnect();assert.equal(node.onaudioprocess,null);assert.equal(node.disconnected,true);
});
test('capture does not mislabel unsupported sampling rates',async()=>{
  await assert.rejects(createPcmCapture({sampleRate:48000},()=>{},()=>{},()=>{}),/16kHz/);
});
