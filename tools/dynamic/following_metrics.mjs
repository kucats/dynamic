// Coverage and uninterrupted spans, not correctness. Each state describes the
// following sample interval; a rejected update ends a run (no hidden bridging).
export function summarizeStates(frames, step, endTime = Infinity) {
  const seconds = {}, runs = [];
  for (const f of frames) {
    const end = Math.min(f.audio + step, endTime), duration = Math.max(0, end - f.audio);
    seconds[f.status] = (seconds[f.status] || 0) + duration;
    const last = runs.at(-1);
    if (last?.status === f.status && Math.abs(last.end - f.audio) < step * .01) {
      last.end = end; last.duration += duration;
    } else runs.push({ status: f.status, start: f.audio, end, duration });
  }
  for (const k of Object.keys(seconds)) seconds[k] = +seconds[k].toFixed(3);
  const longest = {};
  for (const r of runs) {
    const span = { start: +r.start.toFixed(3), end: +r.end.toFixed(3), seconds: +r.duration.toFixed(3) };
    if (!longest[r.status] || span.seconds > longest[r.status].seconds) longest[r.status] = span;
  }
  return { state_seconds: seconds, longest_uninterrupted: longest };
}
