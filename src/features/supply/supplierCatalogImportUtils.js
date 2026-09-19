export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;
export const MAX_IMPORT_ROWS = 500;
const normalized = value => String(value ?? '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('ru-RU');
export const catalogItemKey = item => JSON.stringify([normalized(item.materialName), normalized(item.unit)]);

function numberCell(value, fallback, label, positive = false, integer = false) {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  if (!/^\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?$/.test(text)) throw new Error(`${label}: укажите число`);
  const number = Number(text.replace(/[ \u00a0\u202f]/g, '').replace(',', '.'));
  if (!Number.isFinite(number) || (positive ? number <= 0 : number < 0) || (integer && (!Number.isSafeInteger(number) || number > 2147483647))) {
    throw new Error(`${label}: ${integer ? 'нужно целое число от 0' : positive ? 'число должно быть больше 0' : 'нужно число от 0'}`);
  }
  return number;
}

export function prepareCatalogImport(rows, existing = [], supplierId) {
  const first = rows.findIndex(row => row.some(cell => String(cell ?? '').trim()));
  if (first < 0) throw new Error('Файл пуст');
  const header = rows[first].map(normalized);
  if (!['наименование', 'название', 'материал', 'materialname'].includes(header[0]) ||
      !['ед.', 'ед', 'ед. изм.', 'единица', 'единица измерения', 'unit'].includes(header[1]) ||
      !['цена', 'цена за ед.', 'price'].includes(header[2]) ||
      !['мин. партия', 'минимальная партия', 'minquantity'].includes(header[3]) ||
      !['поставка', 'срок поставки', 'срок поставки (дней)', 'deliverydays'].includes(header[4]) ||
      !['примечание', 'примечания', 'notes'].includes(header[5])) {
    throw new Error('Первая строка: Наименование; Ед.; Цена; Мин. партия; Поставка; Примечание');
  }
  const data = rows.slice(first + 1).map((cells, index) => ({ cells, row: first + index + 2 }))
    .filter(({ cells }) => cells.some(cell => String(cell ?? '').trim()));
  if (!data.length) throw new Error('В файле нет позиций');
  if (data.length > MAX_IMPORT_ROWS) throw new Error(`Не более ${MAX_IMPORT_ROWS} позиций в одном файле`);
  const seen = new Set(existing.filter(item => String(item.supplierId) === String(supplierId)).map(catalogItemKey));
  const items = [], errors = [];
  let skipped = 0;
  for (const { cells, row } of data) {
    try {
      if ([cells[0], cells[1], cells[5]].some(value => String(value ?? '').includes('\u0000'))) throw new Error('текст содержит недопустимый нулевой символ');
      const materialName = String(cells[0] ?? '').trim();
      if (!materialName) throw new Error('укажите наименование');
      if (cells.slice(6).some(cell => String(cell ?? '').trim())) throw new Error('ожидается не более шести столбцов');
      const unit = String(cells[1] ?? '').trim() || 'шт';
      if (Array.from(unit).length > 50) throw new Error('единица измерения — не более 50 символов');
      const item = { materialName, unit,
        price: numberCell(cells[2], 0, 'Цена'), minQuantity: numberCell(cells[3], 1, 'Мин. партия', true),
        deliveryDays: numberCell(cells[4], 3, 'Поставка', false, true), notes: String(cells[5] ?? '').trim(), inStock: true };
      const key = catalogItemKey(item);
      if (seen.has(key)) { skipped++; continue; }
      seen.add(key); items.push({ row, item });
    } catch (error) { errors.push(`Строка ${row}: ${error.message}`); }
  }
  return { items, errors, skipped };
}

export async function catalogResponse(response, requireId = false) {
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Ошибка сервера (${response.status})`);
  if (requireId && (!Number.isSafeInteger(data?.id) || data.id <= 0)) throw new Error('Сервер не подтвердил сохранение');
  return data;
}
