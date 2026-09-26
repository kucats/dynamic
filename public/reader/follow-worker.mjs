import { compileScore, PhraseMatcher } from './follow-model.mjs';
let matcher = null, generation = 0, revision = 0;
self.onmessage = ({ data: d }) => {
  if (d.type === 'init') { generation = d.generation; revision = d.revision; matcher = new PhraseMatcher(compileScore(d.reader, d.movement, d.profile)); }
  if (!matcher || d.generation !== generation || d.revision < revision) return;
  revision = d.revision;
  let result;
  if (d.type === 'frame') result = matcher.push(d.time, d.chroma);
  if (d.type === 'override') result = matcher.override(d.time, undefined, d.retainPhrase);
  if (d.type === 'reset') { matcher.reset(); result = matcher.result; }
  if (d.type === 'hold') result = matcher.hold();
  if (result) self.postMessage({ generation, revision, result });
};
