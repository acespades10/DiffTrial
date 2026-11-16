export function repair<T>(items: T[], size: number): T[][] {
  if (!Number.isInteger(size) || size <= 0) throw new RangeError('invalid size');
  const result: T[][] = [];
  for (let i = 0; i + size <= items.length; i += size) result.push(items.slice(i, i + size));
  return result;
}
