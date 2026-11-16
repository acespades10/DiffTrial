import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('existing', () => {
  expect(repair('1.2', '1.3')).toBe(-1);
});
