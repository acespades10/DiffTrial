import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('existing', () => {
  expect(repair('2024-02-10')).toBe('2024-02-11');
});
