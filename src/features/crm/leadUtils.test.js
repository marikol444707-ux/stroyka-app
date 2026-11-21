import { buildLeadPayload, publicComparisonUrlFromLeadNotes } from './leadUtils';

test('extracts a trusted public project comparison URL from CRM notes', () => {
  const notes = [
    'Сравнение клиента: H1-01; H1-02 — выбран',
    'Ссылка на сравнение: https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects',
  ].join('\n');

  expect(publicComparisonUrlFromLeadNotes(notes)).toBe(
    'https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects',
  );
});

test('marks only a new manual lead as an external owner notification', () => {
  expect(buildLeadPayload({ name: 'Иван', external: true }, {
    createdBy: 'Директор',
    createdAt: '2026-11-21',
    includeCreateMeta: true,
  }).external).toBe(true);
  expect(buildLeadPayload({ name: 'Иван', external: true }).external).toBeUndefined();
});

test('rejects external or incomplete comparison URLs from CRM notes', () => {
  expect(publicComparisonUrlFromLeadNotes(
    'Ссылка на сравнение: https://evil.example/?project=H1-02&compare=H1-01',
  )).toBe('');
  expect(publicComparisonUrlFromLeadNotes(
    'Ссылка на сравнение: https://stroyka26.pro/?project=H1-02',
  )).toBe('');
});
