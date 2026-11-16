export function repair(a: string, b: string): number {
  const left = a.split('.');
  const right = b.split('.');
  for (let i = 0; i < Math.max(left.length, right.length); i++) {
    const x = left[i] ?? '0', y = right[i] ?? '0';
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}
