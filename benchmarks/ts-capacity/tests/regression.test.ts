import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('regression', () => {
  expect(repair([1, 2], 0)).toEqual([]);
  expect(() => repair([1], -1)).toThrow(RangeError);
});
