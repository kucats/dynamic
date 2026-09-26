// Offline controls only. Preserve the input multiset, destroy long-range order.
export function controlOrder(length, control) {
  if (!Number.isInteger(length) || length < 0 || !['none', 'shuffle', 'shuffle-blocks'].includes(control))
    throw new Error('Invalid negative control');
  const block = control === 'shuffle-blocks' ? 10 : 1; // 2 s at the existing 200 ms hop
  const order = Array.from({ length: Math.ceil(length / block) }, (_, i) => i);
  if (control !== 'none') {
    let seed = 94731;
    for (let i = order.length - 1; i > 0; i--) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      const j = seed % (i + 1); [order[i], order[j]] = [order[j], order[i]];
    }
  }
  return order.flatMap((i) => Array.from({ length: Math.min(block, length - i * block) }, (_, j) => i * block + j));
}
