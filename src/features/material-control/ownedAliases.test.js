import { aliasKey, findOwnedAlias, loadAliasPage, saveOwnedAlias } from './ownedAliases';

const owner = { companyId: 2, projectId: 7, projectName: 'Школа' };
const row = (id, companyId, projectId, canonicalName) => ({ id, companyId, projectId,
  aliasName: ' (Марка) ', canonicalName, canonicalUnit: 'шт', active: true });

test('normalization matches server punctuation, not fuzzy material matching', () => {
  expect(aliasKey(' (МАРКА), / шт. ')).toBe('марка шт');
});

test('matching requires exact company/project and ignores legacy rules', () => {
  const common = row('cma:1', 2, null, 'Общее');
  const exact = row('cma:2', 2, 7, 'Объект');
  const rows = [row('cma:3', 3, 7, 'Чужое'), {id: 1, aliasName: 'Марка', canonicalName: 'Legacy'}, common, exact];
  expect(findOwnedAlias(rows, owner, 'марка')).toEqual(exact);
  expect(findOwnedAlias(rows, {...owner, projectId: 8}, 'марка')).toEqual(common);
  expect(findOwnedAlias(rows, null, 'марка')).toBeNull();
  expect(findOwnedAlias([...rows, row('cma:4', 2, 7, 'Conflict')], owner, 'марка')).toBeNull();
});

test('HTTP client validates response ownership and propagates version conflicts', async () => {
  global.fetch = jest.fn(async () => ({ok: true, json: async () => ({items: [row('cma:2', 3, 7, 'Чужое')], limit: 50, offset: 0})}));
  await expect(loadAliasPage('/api', owner)).rejects.toThrow('области');
  global.fetch = jest.fn(async () => ({ok: false, status: 409, json: async () => ({detail: 'Обновите список'})}));
  await expect(saveOwnedAlias('/api', {...owner, aliasName: 'Марка', canonicalName: 'A', expectedAliasId: 'cma:1'}))
    .rejects.toMatchObject({status: 409});
  expect(JSON.parse(global.fetch.mock.calls[0][1].body).expectedAliasId).toBe('cma:1');
});
