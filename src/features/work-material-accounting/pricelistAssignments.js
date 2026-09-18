import { _normalizeUnit } from '../../utils/measureUtils';

export function pricelistAssignments(rows = [], project, item, companyId) {
  const name = value => String(value || '').trim().toLocaleLowerCase('ru');
  return rows.filter(row => row.projectName === project?.name
    && Number(row.companyId) === Number(companyId)
    && (row.workPackage || 'Основная') === 'Прайс'
    && name(row.name) === name(item.name)
    && _normalizeUnit(row.unit) === _normalizeUnit(item.unit));
}
