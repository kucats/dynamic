import test from 'node:test';
import assert from 'node:assert/strict';
import {ScoreClient} from '../scorefollow/web/client.js';
const message=(type,revision,generation=1)=>({type,revision,generation,epoch:1});
test('independent position streams do not starve each other across WS/DataChannel',()=>{
  const c=new ScoreClient('http://localhost');const rows=[];
  c.addEventListener('position',e=>rows.push(e.detail.type));
  c.addEventListener('reference_position',e=>rows.push(e.detail.type));
  c.receive(message('position',12));c.receive(message('reference_position',11));
  c.receive(message('reference_position',11));c.receive(message('position',10));
  assert.deepEqual(rows,['position','reference_position']);
});
test('control acknowledgement fences both streams, even within one generation',()=>{
  const c=new ScoreClient('http://localhost');let count=0;
  c.addEventListener('reference_position',()=>count++);
  c.receive(message('ack',20));c.receive(message('reference_position',19));
  assert.equal(count,0);c.receive(message('reference_position',21));assert.equal(count,1);
});
test('old generations cannot move the new reference cursor',()=>{
  const c=new ScoreClient('http://localhost');let count=0;
  c.addEventListener('reference_position',()=>count++);
  c.receive(message('position',5,2));c.receive(message('reference_position',6,1));
  assert.equal(count,0);
});

test('late control acknowledgement cannot lower a newer media generation',()=>{
  const c=new ScoreClient('http://localhost');let count=0;
  c.addEventListener('reference_position',()=>count++);
  c.receive(message('position',30,3));c.receive(message('ack',20,2));
  c.receive(message('reference_position',29,2));
  assert.equal(count,0);assert.equal(c.generation,3);
});
test('late acknowledgement cannot lower an existing control revision barrier',()=>{
  const c=new ScoreClient('http://localhost');let count=0;
  c.addEventListener('reference_position',()=>count++);
  c.receive(message('ack',30));c.receive(message('ack',20));
  c.receive(message('reference_position',25));assert.equal(count,0);
});
