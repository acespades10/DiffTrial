export function repair(items: {id: string; value: number}[]) {
  const found = new Map<string, {id: string; value: number}>();
  for (const item of items) {
    if (!found.has(item.id)) found.set(item.id, item);
  }
  return [...found.values()];
}
