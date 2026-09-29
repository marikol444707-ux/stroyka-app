import { estimateSectionsOf, estimateItemTotal, isEstimateWorkItem, estimatePackage } from '../../utils/estimateUtils';
import { customerProjectRecord } from './projectSelection';

const invalid = () => { throw new Error('Не все подтверждённые работы связаны с актуальными условиями. Подрядчику нужно проверить строки и объёмы перед формированием расчёта.'); };
const positive = value => Number.isFinite(Number(value)) && Number(value) > 0;

export function customerActRows(project, estimates = [], journal = [], offers = []) {
  if (estimates.some(row => row.sectionsLoaded !== true || !customerProjectRecord(row, project))
      || new Set(estimates.map(estimatePackage)).size !== estimates.length) invalid();
  const lines = new Map();
  for (const estimate of estimates) {
    for (const [sectionIndex, section] of estimateSectionsOf(estimate).entries()) {
      for (const [itemIndex, item] of (section.items || []).entries()) {
        if (!isEstimateWorkItem(item, section.name)) continue;
        const amount = Number(estimateItemTotal(item));
        lines.set(`${estimate.id}:${sectionIndex}:${itemIndex}`, { description: item.name,
          section: section.name, unit: item.unit, planned: Number(item.quantity), amount, kind: 'sourceItems' });
      }
    }
  }
  const extra = new Map(offers.filter(row => customerProjectRecord(row, project)
    && ['Утверждено', 'Утверждено отдельной допработой'].includes(row.status)).map(row => [Number(row.id), row]));
  const grouped = new Map();
  for (const entry of journal) {
    if (!customerProjectRecord(entry, project) || entry.status !== 'Подтверждено') continue;
    if (!positive(entry.quantity)) invalid();
    let line, key;
    if (entry.unexpectedWorkId) {
      const offer = extra.get(Number(entry.unexpectedWorkId));
      if (!offer || offer.changeType === 'Исключение объёма' || offer.includedInEstimateId) invalid();
      key = `extra:${offer.id}`;
      line = { description: offer.description, unit: offer.unit, planned: Number(offer.quantity), amount: Number(offer.total),
        kind: offer.changeType === 'Дополнительный объём к строке сметы' ? 'additionalVolumeItems' : 'outsideEstimateItems' };
    } else {
      key = entry.estimateItemKey;
      line = lines.get(key);
    }
    if (!line || !positive(line.planned) || !Number.isFinite(line.amount) || line.amount < 0) invalid();
    const row = grouped.get(key) || { ...line, quantity: 0 };
    row.quantity += Number(entry.quantity);
    if (row.quantity > row.planned + 1e-8) invalid();
    grouped.set(key, row);
  }
  const result = { sourceItems: [], additionalVolumeItems: [], outsideEstimateItems: [] };
  for (const row of grouped.values()) {
    result[row.kind].push({ description: row.description, section: row.section, unit: row.unit,
      quantity: row.quantity, pricePerUnit: row.amount / row.planned,
      total: Math.round(row.quantity / row.planned * row.amount * 100) / 100 });
  }
  return result;
}
