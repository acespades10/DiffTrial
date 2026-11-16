import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('existing', () => {
  expect(repair([1, 2, 3], 2)).toEqual([1, 2]);
});
