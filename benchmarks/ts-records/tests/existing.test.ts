import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('existing', () => {
  expect(repair([{id: 'a', value: 1}])).toEqual([{id: 'a', value: 1}]);
});
