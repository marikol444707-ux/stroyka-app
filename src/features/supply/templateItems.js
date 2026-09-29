export function templateItemsForProject(items, packages = []) {
  const fallback = packages.length === 1 ? packages[0] : '';
  return items.map(item => ({
    materialName: item.materialName,
    quantity: String(item.quantity ?? ''),
    unit: item.unit,
    workPackage: packages.includes(item.workPackage) ? item.workPackage : fallback,
  }));
}

function validQuantity(value) {
  if (!['string', 'number'].includes(typeof value)) return false;
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount <= 0 || amount >= 100000000) return false;
  const parts = String(value).trim().match(/^\+?(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/);
  if (!parts) return false;
  const fraction = parts[2] || parts[3] || '';
  const digits = (parts[1] || '') + fraction;
  const trailingZeros = digits.length - digits.replace(/0+$/, '').length;
  return fraction.length - Number(parts[4] || 0) - trailingZeros <= 6;
}

const validText = (value, maximum, required = false) => typeof value === 'string'
  && !value.includes('\0') && value.length <= maximum && (!required || Boolean(value.trim()));

export function templatePayload(name, draft) {
  if (!validText(name, 255, true)) throw new Error('Укажите название шаблона до 255 символов.');
  if (!Array.isArray(draft.items) || !draft.items.length || draft.items.length > 200) {
    throw new Error('Шаблон должен содержать от 1 до 200 строк.');
  }
  if (!validText(draft.category ?? '', 100)) {
    throw new Error('Категория шаблона должна быть текстом до 100 символов.');
  }
  const items = draft.items.map((item, index) => {
    if (!item || !validText(item.materialName, 500, true) || !validQuantity(item.quantity)
      || !validText(item.unit, 40, true) || !validText(item.workPackage ?? '', 255)) {
      throw new Error(`Проверьте материал, количество (до 6 знаков после запятой), единицу и раздел в строке ${index + 1}.`);
    }
    return { materialName: item.materialName.trim(), quantity: item.quantity, unit: item.unit.trim(), workPackage: item.workPackage || '' };
  });
  return { name: name.trim(), category: draft.category || '', items };
}
