import { expect, test } from 'vitest';
import { repair } from '../src/repair';
test('regression', () => {
  expect(repair([{id: 'a', value: 1}, {id: 'b', value: 2}, {id: 'a', value: 3}])).toEqual([{id: 'a', value: 3}, {id: 'b', value: 2}]);
});
