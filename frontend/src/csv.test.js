import test from 'node:test';
import assert from 'node:assert/strict';
import { MAX_DESCRIPTION_LENGTH, parseCsv } from './csv.js';

test('accepts organizer and standard CSV headers with multiline text', () => {
  for (const idHeader of ['testcase', 'id']) {
    const rows = parseCsv(`${idHeader},description\r\ncase-001,"Монтаж розеток\r\nи выключателей"\r\n`);
    assert.deepEqual(rows, [{ id: 'case-001', description: 'Монтаж розеток\r\nи выключателей' }]);
  }
});

test('preserves long text for preview and exposes the service limit', () => {
  const description = 'А'.repeat(MAX_DESCRIPTION_LENGTH + 1);
  assert.equal(parseCsv(`id,description\n1,${description}`)[0].description.length, MAX_DESCRIPTION_LENGTH + 1);
});

test('rejects missing columns and duplicate identifiers', () => {
  assert.throws(() => parseCsv('testcase,text2\n1,Описание'), /столбцы/);
  assert.throws(() => parseCsv('id,description\n1,Первое\n1,Второе'), /Повторяется id/);
});
