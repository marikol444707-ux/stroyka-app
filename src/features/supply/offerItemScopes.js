export function offerItemRows(raw) {
  if (Array.isArray(raw)) return raw;
  try { const rows = JSON.parse(raw); return Array.isArray(rows) ? rows : []; } catch { return []; }
}

export const offerLineKey = item => JSON.stringify([item.materialName || item.name || '', item.unit || '', item.workPackage || item.work_package || 'Основная'].map(value => String(value).trim().toLowerCase()));

export function requestForOffer(request, offer) {
  if (!request) return request;
  const items = offerItemRows(offer.awardedItemsJson || offer.requestedItemsJson);
  if (!items.length) return request;
  return {...request, items, itemsJson: JSON.stringify(items), materialName: items.length === 1 ? items[0].materialName : `${items.length} позиций`, quantity: items.length === 1 ? items[0].quantity : items.length, unit: items.length === 1 ? items[0].unit : 'поз.'};
}
