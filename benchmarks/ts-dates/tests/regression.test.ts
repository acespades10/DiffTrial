import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('regression', () => {
  expect(repair('2024-02-29')).toBe('2024-03-01');
  expect(repair('2024-12-31')).toBe('2025-01-01');
});
