export function repair(values: number[], window: number): number[] {
  if (!Number.isInteger(window) || window <= 0) throw new RangeError('invalid window');
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - window + 1), i + 1);
    return slice.reduce((a, b) => a + b, 0) / window;
  });
}
