// Парсинг чисел с поддержкой запятой как разделителя (русская локаль): "0,027" -> 0.027
export const toNum = (v) => {
  if (v === null || v === undefined || v === '') return 0;
  const s = String(v).replace(',', '.').replace(/\s+/g, '');
  const n = Number(s);
  return isNaN(n) ? 0 : n;
};

export const normalizeUnit = (u) => {
  const raw = (u || '').toLowerCase().trim().replace(/[²]/g, '2').replace(/[³]/g, '3');
  const x = raw.replace(/^\d{2,}\s*/, '').replace(/\s+/g, '');
  if (x.startsWith('м2') || x.startsWith('квм')) return 'м2';
  if (x.startsWith('м3') || x.startsWith('кубм')) return 'м3';
  if (x.startsWith('м.п') || x.startsWith('пог.м') || x.startsWith('погм') || x.startsWith('п.м') || x.startsWith('пм')) return 'м';
  if (x.startsWith('шт')) return 'шт';
  if (x.startsWith('кг')) return 'кг';
  if (x.startsWith('тонн') || x.startsWith('тонна') || x.startsWith('тонны')) return 'т';
  if (['кг', 'kg', 'килограмм', 'килограмма', 'килограммов'].includes(x)) return 'кг';
  if (['м', 'м.п', 'пог.м', 'погм', 'п.м', 'пм', 'метр', 'метра', 'метров'].includes(x)) return 'м';
  if (['л', 'литр', 'литра', 'литров', 'l'].includes(x)) return 'л';
  if (['мешок', 'мешка', 'мешков', 'меш'].includes(x)) return 'мешок';
  if (['м3', 'м³', 'куб.м', 'кубм', 'куб'].includes(x)) return 'м3';
  if (['м2', 'м²', 'кв.м', 'квм'].includes(x)) return 'м2';
  if (['т', 'тонн', 'тонна', 'тонны'].includes(x)) return 'т';
  if (['шт', 'штук', 'штука', 'штуки', 'шт.'].includes(x)) return 'шт';
  if (['компл', 'комплект', 'комплекта', 'комплектов'].includes(x)) return 'компл';
  return x;
};

// Backward-compatible alias: many existing calculations still use the old name.
export const _normalizeUnit = normalizeUnit;

// Нормализация ГЭСН-единиц: "100 м2" x 0.23 -> "м2" x 23, "1000 шт" x 0.5 -> "шт" x 500.
// В рабочей смете храним нормальный объем, исходник импорта - в rawUnit/rawQuantity.
export const normalizeMeasure = (qty, unit) => {
  if (!unit) return { qty: toNum(qty), unit: unit || '', factor: 1 };
  const m = String(unit).trim().match(/^(\d{2,})\s*(.+)$/);
  if (!m) return { qty: toNum(qty), unit, factor: 1 };
  const factor = parseInt(m[1], 10);
  if (factor < 10) return { qty: toNum(qty), unit, factor: 1 };
  return { qty: toNum(qty) * factor, unit: m[2].trim(), factor };
};

// Обратное преобразование: пользователь ввел 23 м2, а unit сметы "100 м2" - сохраняем 0.23.
export const denormalizeMeasure = (qty, unit) => {
  const { factor } = normalizeMeasure(1, unit);
  if (factor <= 1) return toNum(qty);
  return toNum(qty) / factor;
};

// Красивое форматирование "qty unit" с автонормализацией.
export const fmtMeasure = (qty, unit) => {
  const n = normalizeMeasure(qty, unit);
  const q = n.qty;
  const qStr = Math.abs(q - Math.round(q)) < 0.001
    ? String(Math.round(q))
    : q.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
  return qStr + ' ' + (n.unit || '');
};
