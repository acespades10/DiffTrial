import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('regression', () => {
  expect(repair('1.10', '1.2')).toBe(1);
  expect(repair('1', '1.0.0')).toBe(0);
});
