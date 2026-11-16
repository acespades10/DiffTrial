import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('existing', () => {
  expect(repair([2, 4], 1)).toEqual([2, 4]);
});
