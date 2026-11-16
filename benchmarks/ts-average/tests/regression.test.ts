import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('regression', () => {
  expect(repair([2, 4, 6], 3)).toEqual([2, 3, 4]);
  expect(repair([], 3)).toEqual([]);
});
