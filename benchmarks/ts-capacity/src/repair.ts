export function repair<T>(items: T[], capacity: number): T[] {
  if (capacity < 0) throw new RangeError('negative capacity');
  return items.slice(0, capacity || items.length);
}
