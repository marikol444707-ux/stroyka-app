import { positiveStoredId } from '../estimates/projectEstimateOwnership';

export const ownedAliasesEnabled = () => process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED === '1';
export const aliasKey = value => String(value || '').toLowerCase().replace(/[.,;:()«»"'`/\\]+/g, ' ').replace(/\s+/g, ' ').trim();
export const aliasRef = value => typeof value === 'string' && /^cma:[1-9][0-9]{0,18}$/.test(value);
export const aliasScopeKey = owner => `${owner?.companyId || ''}:${owner?.projectId || ''}`;

export function aliasMembershipKey(context) {
  const member = context?.selectedCompany;
  if (context?.mode !== 'company' || context.loading || context.error
    || !positiveStoredId(context.selectedCompanyId) || Number(context.selectedCompanyId) !== Number(member?.companyId)
    || member?.source !== 'membership' || !member.membershipId || member.active !== true || member.companyActive !== true) return null;
  return JSON.stringify([member.companyId, member.membershipId, member.role, member.readOnly,
    member.assignedProjects, member.assignedPackages]);
}

export function validAliasScope(owner) {
  return positiveStoredId(owner?.companyId) !== null && (owner.projectId === null || positiveStoredId(owner.projectId) !== null);
}

export function findOwnedAlias(rows, owner, name) {
  if (!validAliasScope(owner)) return null;
  const matches = (rows || []).filter(row => aliasRef(row?.id) && row.active !== false
    && row.companyId === owner.companyId && aliasKey(row.aliasName) === aliasKey(name));
  const exact = owner.projectId === null ? [] : matches.filter(row => row.projectId === owner.projectId);
  const candidates = exact.length ? exact : matches.filter(row => row.projectId === null);
  return candidates.length === 1 ? candidates[0] : null;
}

async function request(API, path, options = {}) {
  const response = await fetch(API + path, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(typeof data?.detail === 'string' ? data.detail : 'Не удалось выполнить операцию со справочником');
    error.status = response.status;
    throw error;
  }
  return data;
}

function checkedRow(row, owner) {
  if (!aliasRef(row?.id) || row.companyId !== owner.companyId
    || !(row.projectId === null || row.projectId === owner.projectId)
    || typeof row.aliasName !== 'string' || typeof row.canonicalName !== 'string') {
    throw new Error('Ответ справочника не соответствует выбранной области');
  }
  return row;
}

export async function loadAliasPage(API, owner, {limit = 50, offset = 0, signal, version} = {}) {
  if (!validAliasScope(owner)) throw new Error('Выберите компанию и объект');
  const query = new URLSearchParams({companyId: owner.companyId, limit, offset});
  if (owner.projectId !== null) query.set('projectId', owner.projectId);
  const data = await request(API, '/company-material-aliases?' + query, {signal});
  if (!Array.isArray(data?.items) || data.limit !== limit || data.offset !== offset || data.items.length > limit) {
    throw new Error('Некорректная страница справочника');
  }
  if (version) {
    if (typeof data.revision !== 'string' || !data.revision) throw new Error('Сервер не поддерживает проверку версии справочника');
    if (version.current !== undefined && version.current !== data.revision) throw new Error('Справочник изменился во время загрузки. Повторите загрузку');
    version.current = data.revision;
  }
  return data.items.map(row => checkedRow(row, owner));
}

export async function loadAliasScope(API, owner, signal, version = {}) {
  const rows = [];
  for (let offset = 0; offset < 10000; offset += 500) {
    const page = await loadAliasPage(API, owner, {limit: 500, offset, signal, version});
    rows.push(...page);
    if (page.length < 500) return rows;
  }
  throw new Error('Справочник слишком большой для полной сверки. Нужна серверная сверка');
}

export async function saveOwnedAlias(API, input) {
  const {companyId, projectId = null, aliasName, canonicalName, canonicalUnit = '', expectedAliasId} = input;
  const owner = {companyId, projectId};
  if (!validAliasScope(owner) || !(expectedAliasId === null || aliasRef(expectedAliasId))) throw new Error('Не задана область или версия соответствия');
  const row = checkedRow(await request(API, '/company-material-aliases', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({companyId, projectId, aliasName, canonicalName, canonicalUnit, expectedAliasId})}), owner);
  if (row.projectId !== projectId) throw new Error('Ответ справочника не соответствует выбранной области');
  return row;
}

export async function deactivateOwnedAlias(API, owner, id) {
  if (!validAliasScope(owner) || !aliasRef(id)) throw new Error('Некорректная область или версия');
  return request(API, '/company-material-aliases/'+encodeURIComponent(id)+'?companyId='+owner.companyId, {method: 'DELETE'});
}

export function mergeOwnedAlias(rows, saved) {
  return [saved, ...(rows || []).filter(row => !(row.companyId === saved.companyId
    && row.projectId === saved.projectId && aliasKey(row.aliasName) === aliasKey(saved.aliasName)))];
}
