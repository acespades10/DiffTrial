export function repair(day: string): string {
  const date = new Date(day + 'T00:00:00Z');
  date.setUTCDate(date.getUTCDate() + 1);
  return day.slice(0, 8) + String(date.getUTCDate()).padStart(2, '0');
}
