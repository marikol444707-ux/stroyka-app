import {
  ESTIMATE_ITEM_TYPE_BY_ID,
  ESTIMATE_MEASUREMENT_BASE_BY_ID,
  ESTIMATE_STRONG_WORK_TOKENS,
  ESTIMATE_TYPE_TOKENS,
  ESTIMATE_WORK_ACTION_TOKENS,
  ESTIMATE_WORK_START_TOKENS,
} from '../constants/estimateConstants';
import { _normalizeUnit, normalizeMeasure, toNum } from './measureUtils';

export const estimateTextKey = (value) => String(value||'').toLowerCase().replace(/ё/g,'е').replace(/[.,;:()[\]{}«»"'`]/g,' ').replace(/[-–—]/g,' ').replace(/\s+/g,' ').trim();
export const estimateTextHasAny = (text, tokens=[]) => {
  const t = estimateTextKey(text);
  return tokens.some(token => t.includes(estimateTextKey(token)));
};
export const estimateTextStartsWithAny = (text, tokens=[]) => {
  const t = estimateTextKey(text);
  return tokens.some(token => {
    const k = estimateTextKey(token);
    return t === k || t.startsWith(k + ' ');
  });
};
export const estimateWorkKeyForItem = (item={}, sectionName='', index='') => {
  const code = String(item.sourceCode || item.obosn || item.code || item.reason || '').trim();
  const base = [sectionName, code || item.name || '', index].filter(v=>String(v||'').trim()).join('|');
  return estimateTextKey(base).replace(/[^a-zа-я0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,160);
};
export const estimateCodeLooksResource = (value) => {
  const raw = String(value||'').trim();
  return /^\d{2,}[-/]\d+/.test(raw) || /^\d{3,}$/.test(raw) || /^тц[_-]/i.test(raw) || /^фс[сб]ц/i.test(raw);
};
export const estimateImportedLineTotalRaw = (it={}) => toNum(it.lineTotal ?? it.currentTotal ?? it.total ?? it.sum ?? it.amount ?? it.totalSum ?? it.totalMaterial ?? it.materialTotal ?? it.materialSum);
export const estimateItemLooksResourceAdjustment = (it={}, sectionName='') => {
  const raw = estimateTextKey(it.itemType || it.type || it.kind);
  const qty = toNum(it.quantity);
  const lineTotal = estimateImportedLineTotalRaw(it);
  const sourceCode = String(it.sourceCode || it.obosn || it.code || it.reason || '').trim();
  const text = estimateTextKey([sectionName, it.section, it.name].filter(Boolean).join(' '));
  const rawResource = ['material','materials','материал','материалы','equipment','оборудование','delivery','доставка','transport'].includes(raw);
  const looksResource = rawResource || estimateCodeLooksResource(sourceCode) || estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.material) || estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.equipment) || estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.transport);
  const looksStrongWork = estimateTextStartsWithAny(estimateTextKey(it.name), ESTIMATE_WORK_START_TOKENS) || estimateTextHasAny(estimateTextKey(it.name), ESTIMATE_STRONG_WORK_TOKENS);
  return looksResource && !looksStrongWork && (qty < 0 || lineTotal < 0 || it.importKind === 'resource_adjustment');
};
export const normalizeEstimateItemType = (it={}, sectionName='') => {
  const explicit = estimateTextKey(it.itemType || it.type);
  const nameText = estimateTextKey(it.name);
  const sourceCode = String(it.sourceCode || it.obosn || it.code || it.reason || '').trim();
  const nameStartsWithWork = estimateTextStartsWithAny(nameText, ESTIMATE_WORK_START_TOKENS);
  const nameLooksStrongWork = nameStartsWithWork || estimateTextHasAny(nameText, ESTIMATE_STRONG_WORK_TOKENS);
  const nameLooksWork = estimateTextHasAny(nameText, ESTIMATE_WORK_ACTION_TOKENS);
  const nameLooksMaterial = estimateTextHasAny(nameText, ESTIMATE_TYPE_TOKENS.material);
  const nameLooksEquipment = estimateTextHasAny(nameText, ESTIMATE_TYPE_TOKENS.equipment);
  const nameLooksTransport = estimateTextHasAny(nameText, ESTIMATE_TYPE_TOKENS.transport);
  const codeLooksWork = /^(ГЭСН|ФЕР|ТЕР)/i.test(sourceCode);
  const codeLooksResource = estimateCodeLooksResource(sourceCode);
  const explicitKnown = ESTIMATE_ITEM_TYPE_BY_ID[explicit] ? explicit : '';
  const lineTotalLike = estimateImportedLineTotalRaw(it);
  const nameMaterialShouldWin = nameLooksMaterial && !nameStartsWithWork;
  const nameEquipmentShouldWin = nameLooksEquipment && !nameStartsWithWork;
  const nameTransportShouldWin = nameLooksTransport && !nameStartsWithWork;
  const weakExplicitMaterial = explicitKnown === 'material' && (codeLooksWork || nameLooksStrongWork);
  const weakExplicitWork = explicitKnown === 'work' && !nameLooksStrongWork && (codeLooksResource || nameMaterialShouldWin || nameEquipmentShouldWin || nameTransportShouldWin || toNum(it.quantity) < 0 || lineTotalLike < 0);
  if (estimateItemLooksResourceAdjustment(it, sectionName)) return 'adjustment';
  if ((toNum(it.quantity) < 0 || lineTotalLike < 0) && ['material','equipment','transport'].includes(explicitKnown)) return 'adjustment';
  if ((toNum(it.quantity) < 0 || lineTotalLike < 0) && (codeLooksResource || nameLooksMaterial || nameLooksEquipment || nameLooksTransport) && !nameLooksStrongWork) return 'adjustment';
  if (explicitKnown && !weakExplicitWork && !weakExplicitMaterial) return explicitKnown;
  if (weakExplicitMaterial) return 'work';
  if (explicit.includes('коррект') || explicit.includes('adjust')) return 'adjustment';
  if (explicit.includes('мат') && !weakExplicitMaterial) return 'material';
  if (explicit.includes('оборуд') || explicit.includes('механизм')) return 'equipment';
  if (explicit.includes('достав') || explicit.includes('транспорт')) return 'transport';
  if (explicit.includes('проч') || explicit.includes('наклад')) return 'overhead';
  if (explicit.includes('работ') && !weakExplicitWork) return 'work';
  if (codeLooksWork || nameLooksStrongWork) return 'work';
  if (it.isImported && (toNum(it.quantity) < 0 || lineTotalLike < 0) && (codeLooksResource || nameLooksMaterial || nameLooksEquipment || nameLooksTransport) && !nameLooksStrongWork) return 'adjustment';
  if (toNum(it.priceMaterial)>0 && toNum(it.priceWork)===0) return 'material';
  if (codeLooksResource && !nameLooksStrongWork) return 'material';
  if (nameTransportShouldWin && !nameLooksWork) return 'transport';
  if (nameEquipmentShouldWin && !nameLooksWork) return 'equipment';
  if (nameMaterialShouldWin) return 'material';
  if (nameLooksWork) return 'work';
  const text = estimateTextKey([sectionName, it.section, it.name].filter(Boolean).join(' '));
  if (estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.transport)) return 'transport';
  if (estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.equipment)) return 'equipment';
  if (estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.overhead)) return 'overhead';
  if (estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.material)) return 'material';
  if (estimateTextHasAny(text, ESTIMATE_TYPE_TOKENS.work)) return 'work';
  return 'work';
};
export const estimateItemTypeMeta = (type) => ESTIMATE_ITEM_TYPE_BY_ID[type] || ESTIMATE_ITEM_TYPE_BY_ID.work;
export const isEstimateMaterialItem = (it, sectionName='') => normalizeEstimateItemType(it, sectionName)==='material';
export const isEstimateWorkItem = (it, sectionName='') => normalizeEstimateItemType(it, sectionName)==='work';
export const estimateUnitLooksUnknown = (unit) => {
  const u = estimateTextKey(unit).replace(/\s+/g,'');
  return !u || ['1','ед','единица','шт','штука','штук','штуки'].includes(u);
};

const executionPercentValue = (value) => {
  const percent = toNum(String(value ?? '').replace(',', '.'));
  if (percent < 1 || percent > 100) return 0;
  return Math.round(percent * 100) / 100;
};

export const estimateExecutionFillPercentOf = (estimate) => {
  const counts = new Map();
  (estimate?.sections || []).forEach(section => {
    (section.items || []).forEach(item => {
      if (!isEstimateWorkItem(item, section.name)) return;
      const mode = String(item.executionPriceMode || '').trim().toLowerCase();
      if (!mode.startsWith('percent')) return;
      const fromMode = mode.match(/^percent[_:\s-]*(\d+(?:[.,]\d+)?)/);
      const percent = executionPercentValue(fromMode ? fromMode[1] : item.executionPricePercent);
      if (!percent) return;
      counts.set(percent, (counts.get(percent) || 0) + 1);
    });
  });
  let bestPercent = 0;
  let bestCount = 0;
  counts.forEach((count, percent) => {
    if (count > bestCount) {
      bestCount = count;
      bestPercent = percent;
    }
  });
  return bestPercent ? String(bestPercent) : '';
};

export const isEstimatePricelist = (pl={}) => {
  const name = String(pl.name || '').toLowerCase();
  const description = String(pl.description || '').toLowerCase();
  return name.startsWith('прайс из') || description.includes('создан из сметы');
};

export const estimateIssueDomId = (estimateId, sectionIdx, itemIdx) => 'estimate-row-'+String(estimateId||'new')+'-'+String(sectionIdx)+'-'+String(itemIdx);

export const inferEstimateUnit = (it={}, sectionName='') => {
  const current = String(it.unit || '').trim();
  const explicitType = estimateTextKey(it.itemType || it.type);
  const itemType = ESTIMATE_ITEM_TYPE_BY_ID[explicitType] ? explicitType : '';
  const text = estimateTextKey([sectionName, it.section, it.name].filter(Boolean).join(' '));
  if (it.isImported && current && !['1','ед','единица'].includes(estimateTextKey(current).replace(/\s+/g,''))) return current;
  const currentBaseUnit = _normalizeUnit(normalizeMeasure(1, current).unit || current || '');
  const looksAreaWork = itemType !== 'material' && estimateTextHasAny(text, ['поверхност','фасад','стен','перегород','потолк','потолоч','обои','облицов','окраск','штукатур','шпатлев','шпаклев','грунтов','плитк','керамогранит','гранит','линолеум','покрытие пола','полы','пола','гкл','гипсокартон','сетка']);
  const looksLinearWork = estimateTextHasAny(text, ['кабель','провод','труба','трубопровод','лоток','короб','уголок','уголк','угол','плинтус','наличник','профиль маяч','маяк','подоконник','погон']);
  if (!it.isImported && currentBaseUnit === 'м' && looksAreaWork && !looksLinearWork) return '100 м2';
  if (!estimateUnitLooksUnknown(current)) return current;
  if (itemType === 'material') {
    if (estimateTextHasAny(text, ['смесь','штукатурная','шпатлевка','шпатлевк','шпаклевка','шпаклевк','клей','затирка','цемент','пескобетон','сухая смесь'])) return 'кг';
    if (estimateTextHasAny(text, ['краска','грунтовка','эмаль','лак','акрил'])) return 'кг';
    if (estimateTextHasAny(text, ['уголок','уголк','угол','плинтус','наличник','кабель','провод','труба','трубопровод','лоток','короб','профиль','маяк','подоконник'])) return 'м';
    if (estimateTextHasAny(text, ['плитк','керамогранит','гранит','линолеум','покрытие пола','обои','лист гипсокартон','листы гипсокартон','гкл','панель','плита'])) return 'м2';
    if (estimateTextHasAny(text, ['кирпич','блок','саморез','дюбель','гвозд','светильник','розетка','выключатель','прибор','радиатор','решетк'])) return 'шт';
  }
  if (estimateTextHasAny(text, ['розет','выключател','светильник','табло','прибор','радиатор','решетк','унитаз','раковин','смесител','коробка ответвительная','дверной блок','оконный блок','полотно','шкаф','стол'])) return 'шт';
  if (estimateTextHasAny(text, ['уголок','уголк','угол','плинтус','наличник','кабель','провод','труба','трубопровод','лоток','короб','профиль маяч','профиль','маяк','подоконник'])) return 'м';
  if (estimateTextHasAny(text, ['бетон','каркас из брус','брусьев','брус'])) return 'м3';
  if (itemType !== 'material' && estimateTextHasAny(text, ['поверхност','фасад','стен','перегород','потолк','потолоч','обои','облицов','окраск','штукатур','шпатлев','шпаклев','грунтов','плитк','керамогранит','гранит','линолеум','покрытие пола','полы','пола','гкл','гипсокартон','сетка'])) return '100 м2';
  return 'шт';
};
export const estimateMeasurementBasisMeta = (basis) => ESTIMATE_MEASUREMENT_BASE_BY_ID[basis] || ESTIMATE_MEASUREMENT_BASE_BY_ID.manual;
export const suggestEstimateMeasurementBasis = (it={}, sectionName='') => {
  const text = estimateTextKey([sectionName, it.section, it.name].filter(Boolean).join(' '));
  const inferredUnit = inferEstimateUnit(it, sectionName);
  const unit = _normalizeUnit(normalizeMeasure(1, inferredUnit).unit || inferredUnit || '');
  const isDemolition = estimateTextHasAny(text, ['демонтаж','разбор','разборка','снятие','удаление','отбивка']);
  if (unit === 'м') return 'linear';
  if (unit === 'шт') {
    if (estimateTextHasAny(text, ['окно','оконный блок','подоконник'])) return 'window_count';
    if (estimateTextHasAny(text, ['двер','дверной блок','полотно'])) return 'door_count';
    if (estimateTextHasAny(text, ['розет','выключател','светильник','точк','прибор','радиатор','решетк','унитаз','раковин','смесител','коробка ответвительная'])) return 'point';
    return 'manual';
  }
  if (unit !== 'м2') return 'manual';
  const hasFloorWord = /(^| )пол( |$)/.test(text) || /(^| )пола( |$)/.test(text) || /(^| )полы( |$)/.test(text);
  const hasWindowWord = estimateTextHasAny(text, ['окно','окон','оконный блок','оконные блоки','стеклопакет']);
  const hasDoorWord = estimateTextHasAny(text, ['двер','дверной блок','дверные блоки','полотно']);
  const hasRevealWord = estimateTextHasAny(text, ['откос']);
  const hasOpeningBlockWord = estimateTextHasAny(text, ['проем','проём','блок','блоков','замена']);
  const hasWallWord = estimateTextHasAny(text, ['стен','перегород','фасад']);
  const hasCeilingWord = estimateTextHasAny(text, ['потолок','потолк','потолоч']);
  if (hasRevealWord && hasWindowWord && hasDoorWord) return 'opening_reveals';
  if (estimateTextHasAny(text, ['оконный откос','откос окон','откосы окон','оконные откосы'])) return 'window_reveals';
  if (estimateTextHasAny(text, ['дверной откос','откос двер','откосы двер','дверные откосы'])) return 'door_reveals';
  if (hasWindowWord && hasDoorWord && hasOpeningBlockWord) return 'openings_area';
  if (hasWindowWord && hasOpeningBlockWord) return 'window_area';
  if (hasDoorWord && hasOpeningBlockWord) return 'door_area';
  if (hasWallWord && hasCeilingWord) return 'wall_ceiling_area';
  if (estimateTextHasAny(text, ['потолок','потолк','потолоч','подвесной потолок','натяжной потолок'])) return 'ceiling_area';
  if (hasFloorWord || estimateTextHasAny(text, ['стяжк','плитка пола','ламинат','линолеум','покрытие пола'])) return 'floor_area';
  if (estimateTextHasAny(text, ['окно','оконный блок','оконные блоки','замена окон','стеклопакет'])) return 'window_area';
  if (estimateTextHasAny(text, ['двер','дверной блок','дверные блоки','полотно','замена двер'])) return 'door_area';
  if (estimateTextHasAny(text, ['штукатур','шпатлев','шпаклев','окраск','обои','облицовка стен','стен','перегород','фасад'])) return 'wall_net_area';
  if (isDemolition) return 'demolition';
  return 'manual';
};
export const estimateMeasurementBasisOf = (it={}, sectionName='') => (it.measurementBasis && ESTIMATE_MEASUREMENT_BASE_BY_ID[it.measurementBasis]) ? it.measurementBasis : suggestEstimateMeasurementBasis(it, sectionName);
export const estimateItemLooksImported = (item={}) => {
  if (item?.isImported) return true;
  return [
    'rawUnit','rawQuantity','unitFactor','quantityBase','quantityCoefficient','quantityFinal',
    'baseUnitPrice','costCoefficient','baseTotal','costIndex','currentTotal','lineTotalSource',
    'lineTotal','totalWork','totalMaterial','parentWorkKey','parentWorkName','resourceRole'
  ].some(key => item?.[key] !== undefined && item?.[key] !== null && item?.[key] !== '');
};
export const authoritativeImportedUnit = (item={}) => {
  const current = String(item.unit || '').trim();
  const raw = String(item.rawUnit || '').trim();
  const currentInfo = estimateUnitScaleInfo(current);
  const rawInfo = estimateUnitScaleInfo(raw);
  const currentBase = _normalizeUnit(currentInfo.unit || current || '');
  const rawBase = _normalizeUnit(rawInfo.unit || raw || '');
  if (raw && rawInfo.factor > 1) return raw;
  if (raw && estimateUnitLooksUnknown(current)) return raw;
  if (raw && current && rawBase && currentBase && rawBase !== currentBase) return raw;
  const candidates = [current, raw].filter(Boolean);
  return candidates.find(u => !estimateUnitLooksUnknown(u)) || candidates[0] || '';
};
export const estimateUnitScaleInfo = (unit) => {
  const raw = String(unit || '').trim();
  const m = raw.match(/^(\d{2,})\s*(.+)$/);
  if (!m) return {factor: 1, unit: raw};
  const factor = parseInt(m[1], 10);
  return factor >= 10 ? {factor, unit: m[2].trim()} : {factor: 1, unit: raw};
};
export const normalizeImportedMeasure = (item={}, unitForMeasure='') => {
  const current = normalizeMeasure(item.quantity, unitForMeasure);
  const unitInfo = estimateUnitScaleInfo(unitForMeasure || item.unit || '');
  const rawUnitInfo = estimateUnitScaleInfo(item.rawUnit || '');
  const rawQtySource = [item.rawQuantity, item.quantityFinal, item.quantityBase]
    .find(v => v !== undefined && v !== null && v !== '');
  const rawQty = rawQtySource !== undefined ? toNum(rawQtySource) : null;
  const factor = toNum(item.unitFactor) || unitInfo.factor || rawUnitInfo.factor || current.factor || 1;
  const currentQty = Number(current.qty);
  let qty = currentQty;
  let unit = current.unit || unitInfo.unit || rawUnitInfo.unit || unitForMeasure || item.unit || '';
  if (unitInfo.factor > 1) unit = unitInfo.unit;
  else if (rawUnitInfo.factor > 1 && (!unit || String(unit).trim() === String(item.rawUnit || '').trim())) unit = rawUnitInfo.unit;

  if (factor > 1) {
    const sourceQty = rawQty !== null ? rawQty : toNum(item.quantity);
    const alreadyNormalized = Math.abs(sourceQty) >= factor;
    const expected = alreadyNormalized ? sourceQty : sourceQty * factor;
    const inflated = Math.abs(currentQty) > Math.max(1000, Math.abs(expected) * 10);
    const missing = !Number.isFinite(currentQty) || currentQty === 0;
    const scaledUnitStillVisible = unitInfo.factor > 1 || rawUnitInfo.factor > 1;
    if (missing || inflated || scaledUnitStillVisible) qty = expected;
  }

  return {qty, unit, factor};
};
export const normalizeImportedEstimateItem = (item={}, sectionName='') => {
  const base = {...item, isImported:true};
  const total = toNum(item.lineTotal ?? item.total ?? item.sum ?? item.amount ?? item.totalSum);
  const totalWork = toNum(item.totalWork ?? item.workTotal ?? item.workSum);
  const totalMaterial = toNum(item.totalMaterial ?? item.materialTotal ?? item.materialSum);
  const detectedType = normalizeEstimateItemType(base, sectionName);
  const itemType = (total < 0 || totalWork < 0 || totalMaterial < 0) && !['material','equipment','transport','overhead'].includes(detectedType)
    ? 'adjustment'
    : detectedType;
  const importedUnit = authoritativeImportedUnit(base);
  const unitForMeasure = importedUnit || inferEstimateUnit({...base,itemType}, sectionName);
  const normalizedMeasure = normalizeImportedMeasure(base, unitForMeasure);
  const normalizedUnit = _normalizeUnit(normalizedMeasure.unit || unitForMeasure || '');
  const normalizedDoneMeasure = (base.doneQuantity !== undefined && base.doneQuantity !== null && base.doneQuantity !== '')
    ? normalizeMeasure(base.doneQuantity, unitForMeasure)
    : null;
  let priceWork = toNum(item.priceWork);
  let priceMaterial = toNum(item.priceMaterial);
  const normalizedQty = Math.abs(toNum(normalizedMeasure.qty));
  const workLineTotal = totalWork || (itemType === 'work' ? total : 0);
  const materialLineTotal = totalMaterial || (['material','equipment','transport'].includes(itemType) ? total : 0);
  const unitPriceFromTotal = (lineTotal) => normalizedQty > 0 ? lineTotal / normalizedQty : lineTotal;
  const priceLooksLikeLineTotal = (price, lineTotal) => price > 0 && lineTotal > 0 && Math.abs(price - lineTotal) <= Math.max(1, Math.abs(lineTotal) * 0.001);
  if (!priceWork && !priceMaterial) {
    if (itemType === 'work') priceWork = unitPriceFromTotal(workLineTotal);
    else if (['material','equipment','transport'].includes(itemType)) priceMaterial = unitPriceFromTotal(materialLineTotal);
  } else if (itemType === 'work' && priceLooksLikeLineTotal(priceWork, workLineTotal)) {
    priceWork = unitPriceFromTotal(workLineTotal);
  } else if (['material','equipment','transport'].includes(itemType) && priceLooksLikeLineTotal(priceMaterial, materialLineTotal)) {
    priceMaterial = unitPriceFromTotal(materialLineTotal);
  }
  if (itemType === 'material' && priceWork > 0 && !priceMaterial) {
    priceMaterial = priceLooksLikeLineTotal(priceWork, materialLineTotal) ? unitPriceFromTotal(materialLineTotal) : priceWork;
    priceWork = 0;
  }
  if (itemType === 'work' && priceMaterial > 0 && !priceWork) {
    priceWork = priceLooksLikeLineTotal(priceMaterial, workLineTotal) ? unitPriceFromTotal(workLineTotal) : priceMaterial;
    priceMaterial = 0;
  }
  if (itemType === 'adjustment') {
    priceWork = 0;
    priceMaterial = 0;
  }
  return {
    ...base,
    itemType,
    unit: normalizedUnit,
    quantity: normalizedMeasure.qty,
    doneQuantity: normalizedDoneMeasure ? normalizedDoneMeasure.qty : base.doneQuantity,
    rawUnit: base.rawUnit || unitForMeasure,
    rawQuantity: base.rawQuantity ?? base.quantity,
    unitFactor: toNum(base.unitFactor) || normalizedMeasure.factor || 1,
    quantityBase: base.quantityBase,
    quantityCoefficient: base.quantityCoefficient,
    quantityFinal: base.quantityFinal,
    baseUnitPrice: base.baseUnitPrice,
    costCoefficient: base.costCoefficient,
    baseTotal: base.baseTotal,
    costIndex: base.costIndex,
    currentTotal: base.currentTotal,
    lineTotalSource: base.lineTotalSource,
    priceWork: priceWork || '',
    priceMaterial: priceMaterial || '',
    workKey: item.workKey || (itemType === 'work' ? estimateWorkKeyForItem(item, sectionName, item.id || '') : ''),
    workName: item.workName || (itemType === 'work' ? item.name : ''),
    workSourceCode: item.workSourceCode || (itemType === 'work' ? (item.sourceCode || item.obosn || '') : ''),
    parentWorkKey: itemType === 'work' ? '' : (item.parentWorkKey || item.workKey || ''),
    parentWorkName: item.parentWorkName || '',
    parentWorkSourceCode: item.parentWorkSourceCode || '',
    resourceRole: item.resourceRole || (['material','equipment','transport'].includes(itemType) ? itemType : ''),
    measurementBasis: itemType === 'work' ? suggestEstimateMeasurementBasis({...base,itemType,unit:normalizedUnit}, sectionName) : 'manual',
    importKind: itemType === 'adjustment' ? 'resource_adjustment' : (item.importKind || '')
  };
};
export const normalizeEstimateWorkingItem = (item={}, sectionName='') => {
  if (estimateItemLooksImported(item)) return normalizeImportedEstimateItem(item, sectionName);
  const itemType = normalizeEstimateItemType(item, sectionName);
  const inferredUnit = inferEstimateUnit({...item,itemType}, sectionName);
  return {
    ...item,
    itemType,
    unit: inferredUnit,
    measurementBasis: itemType === 'work' ? suggestEstimateMeasurementBasis({...item,itemType,unit:inferredUnit}, sectionName) : 'manual'
  };
};
export const linkEstimateResourcesToWorks = (sections=[]) => (sections||[]).map(section => {
  let currentWork = null;
  return {
    ...section,
    items: (section.items||[]).map((rawItem, idx) => {
      const item = normalizeEstimateWorkingItem(rawItem, section.name);
      const itemType = normalizeEstimateItemType(item, section.name);
      if (itemType === 'work') {
        currentWork = {
          key: item.workKey || estimateWorkKeyForItem(item, section.name, idx),
          name: item.workName || item.name || '',
          sourceCode: item.workSourceCode || item.sourceCode || item.obosn || '',
        };
        return {...item, workKey: currentWork.key, workName: currentWork.name, workSourceCode: currentWork.sourceCode};
      }
      if (['material','equipment','transport'].includes(itemType) && currentWork && !(item.parentWorkKey || item.parentWorkName)) {
        return {
          ...item,
          parentWorkKey: currentWork.key,
          parentWorkName: currentWork.name,
          parentWorkSourceCode: currentWork.sourceCode,
          resourceRole: item.resourceRole || itemType,
        };
      }
      return item;
    })
  };
});
export const normalizeEstimateImportSections = (sections=[]) => linkEstimateResourcesToWorks((sections||[]).map(section => ({
  ...section,
  items: (section.items||[]).map(item => normalizeEstimateWorkingItem(item, section.name))
})));
export const enrichEstimateMeasurementBasis = (sections=[]) => normalizeEstimateImportSections(sections);
export const normalizeEstimateRecord = (estimate={}) => ({
  ...estimate,
  sections: normalizeEstimateImportSections(estimate.sections || []),
});
export const normalizeEstimateList = (list=[]) => (Array.isArray(list) ? list.map(normalizeEstimateRecord) : []);
export const estimateImportedWorkTotal = (it, itemType) => {
  const priceWork = toNum(it?.priceWork);
  const totalWork = toNum(it?.totalWork);
  const totalMaterial = toNum(it?.totalMaterial);
  const lineTotal = toNum(it?.lineTotal ?? it?.currentTotal);
  const total = toNum(it?.total);
  if (totalWork) return totalWork;
  if (itemType === 'work' && lineTotal && !totalMaterial) return lineTotal;
  if (itemType === 'overhead') return total;
  if (priceWork && toNum(it?.quantity) > 0) return priceWork * toNum(it.quantity);
  if (priceWork) return priceWork;
  return itemType === 'work' && !totalMaterial ? total : 0;
};
export const estimateImportedMaterialTotal = (it, itemType) => {
  const priceMaterial = toNum(it?.priceMaterial);
  const totalMaterial = toNum(it?.totalMaterial);
  const totalWork = toNum(it?.totalWork);
  const lineTotal = toNum(it?.lineTotal ?? it?.currentTotal);
  const total = toNum(it?.total);
  if (estimateItemLooksResourceAdjustment(it, it?.sectionName||it?.section||'')) return 0;
  if (['material','equipment','transport'].includes(itemType) && (toNum(it?.quantity) < 0 || totalMaterial < 0 || lineTotal < 0 || total < 0)) return 0;
  if (totalMaterial) return totalMaterial;
  if (['material','equipment','transport'].includes(itemType) && lineTotal && !totalWork) return lineTotal;
  if (priceMaterial && toNum(it?.quantity) > 0) return priceMaterial * toNum(it.quantity);
  if (priceMaterial) return priceMaterial;
  return ['material','equipment','transport'].includes(itemType) && !totalWork ? total : 0;
};
export const estimateImportedAdjustmentTotal = (it={}) => {
  const lineTotal = toNum(it?.lineTotal ?? it?.currentTotal);
  if (lineTotal) return lineTotal;
  return toNum(it?.total ?? it?.sum ?? it?.amount ?? it?.totalSum);
};
export const estimateItemWorkSum = (it) => { const itemType=normalizeEstimateItemType(it, it?.sectionName||it?.section||''); return ['adjustment','note'].includes(itemType) ? 0 : (it?.isImported ? estimateImportedWorkTotal(it,itemType) : toNum(it?.quantity) * toNum(it?.priceWork)); };
export const estimateItemMaterialSum = (it) => { const itemType=normalizeEstimateItemType(it, it?.sectionName||it?.section||''); return ['adjustment','note'].includes(itemType) ? 0 : (it?.isImported ? estimateImportedMaterialTotal(it,itemType) : toNum(it?.quantity) * toNum(it?.priceMaterial)); };
export const estimateItemTotal = (it) => normalizeEstimateItemType(it, it?.sectionName||it?.section||'') === 'adjustment' ? estimateImportedAdjustmentTotal(it) : estimateItemWorkSum(it) + estimateItemMaterialSum(it);
export const estimateWorkGroupNameKey = (name='') => estimateTextKey(name);
export const buildEstimateWorkSummary = (estimate={}) => {
  const groupsByKey = new Map();
  const estimateId = estimate?.id || '';
  const estimateName = estimate?.name || '';
  const estimateVersion = estimate?.version || estimate?.versionLabel || estimate?.displayVersion || '';
  const workPackage = estimate?.workPackage || estimate?.package || 'Основная';
  (estimate?.sections || []).forEach((section, sectionIndex) => {
    const sectionName = section?.name || '';
    (section?.items || []).forEach((rawItem, itemIndex) => {
      const item = normalizeEstimateWorkingItem({...rawItem, sectionName}, sectionName);
      if (!isEstimateWorkItem(item, sectionName) || estimateItemLooksResourceAdjustment(item, sectionName)) return;
      const name = String(item.name || '').trim();
      if (!name) return;
      const qty = toNum(item.quantity);
      const doneQty = toNum(item.doneQuantity);
      const unit = _normalizeUnit(normalizeMeasure(1, item.unit).unit || item.unit || '') || String(item.unit || '').trim();
      const basis = estimateMeasurementBasisOf(item, sectionName);
      const nameKey = estimateWorkGroupNameKey(name);
      const groupKey = [estimateId, workPackage, nameKey, unit, basis].map(v=>String(v||'')).join('|');
      const workSum = estimateItemWorkSum({...item, sectionName});
      const unitPrice = qty > 0 && workSum ? workSum / qty : 0;
      const source = {
        estimateId,
        estimateName,
        estimateVersion,
        workPackage,
        sectionName,
        sectionIndex,
        itemIndex,
        rowNumber: item.rowNumber || item.number || item.sourceRow || itemIndex + 1,
        name,
        originalName: rawItem?.name || name,
        quantity: qty,
        doneQuantity: doneQty,
        unit,
        basis,
        priceWork: toNum(item.priceWork),
        workSum,
      };
      if (!groupsByKey.has(groupKey)) {
        groupsByKey.set(groupKey, {
          key: groupKey,
          name,
          nameKey,
          unit,
          basis,
          basisLabel: estimateMeasurementBasisMeta(basis).label,
          workPackage,
          quantity: 0,
          doneQuantity: 0,
          workSum: 0,
          sourceCount: 0,
          sectionNames: new Set(),
          priceMin: unitPrice || 0,
          priceMax: unitPrice || 0,
          sources: [],
        });
      }
      const group = groupsByKey.get(groupKey);
      group.quantity += qty;
      group.doneQuantity += doneQty;
      group.workSum += workSum;
      group.sourceCount += 1;
      if (sectionName) group.sectionNames.add(sectionName);
      if (unitPrice) {
        group.priceMin = group.priceMin ? Math.min(group.priceMin, unitPrice) : unitPrice;
        group.priceMax = Math.max(group.priceMax, unitPrice);
      }
      group.sources.push(source);
    });
  });
  const groups = Array.from(groupsByKey.values()).map(group => ({
    ...group,
    remainingQuantity: Math.max(0, group.quantity - group.doneQuantity),
    unitPriceAvg: group.quantity > 0 ? group.workSum / group.quantity : 0,
    sectionNames: Array.from(group.sectionNames),
  })).sort((a,b) => {
    if ((b.sourceCount > 1) !== (a.sourceCount > 1)) return (b.sourceCount > 1 ? 1 : 0) - (a.sourceCount > 1 ? 1 : 0);
    if (b.sourceCount !== a.sourceCount) return b.sourceCount - a.sourceCount;
    return a.name.localeCompare(b.name, 'ru');
  });
  return {
    groups,
    totalGroups: groups.length,
    duplicateGroups: groups.filter(group => group.sourceCount > 1).length,
    totalSourceRows: groups.reduce((sum, group) => sum + group.sourceCount, 0),
    totalQuantity: groups.reduce((sum, group) => sum + group.quantity, 0),
    totalWorkSum: groups.reduce((sum, group) => sum + group.workSum, 0),
  };
};
export const estimateItemDoneTotal = (it) => {
  const q = toNum(it?.quantity);
  const d = toNum(it?.doneQuantity);
  if (it?.isImported) return q > 0 ? (d / q) * estimateItemTotal(it) : 0;
  return d * (toNum(it?.priceWork) + toNum(it?.priceMaterial));
};
export const estimateLineTotalSourceLabel = (source) => ({
  current_total: 'сумма из сметы',
  direct_total: 'сумма из строки',
  total_column: 'итоговая колонка',
  unit_price_x_quantity: 'цена × объем',
  base_total_x_index: 'база × индекс',
  base_total_x_summary_index: 'база × индекс раздела',
  base_total: 'базовая сумма',
  contract_total: 'сумма договора',
  fallback_scan: 'найдено рядом',
  reconciliation_to_declared_total: 'сверка до итога',
})[String(source || '').trim()] || String(source || '').trim();
export const estimateImportLineMeta = (item={}, qtyNorm={}) => {
  if (!item?.isImported) return '';
  const rawQtyPresent = item.rawQuantity !== undefined && item.rawQuantity !== null && item.rawQuantity !== '';
  const rawQty = rawQtyPresent ? toNum(item.rawQuantity) : null;
  const rawUnit = String(item.rawUnit || '').trim();
  const unitFactor = toNum(item.unitFactor) || 1;
  const quantityCoefficient = toNum(item.quantityCoefficient) || 0;
  const workingQty = Number.isFinite(Number(qtyNorm.qty)) ? Number(qtyNorm.qty) : normalizeMeasure(item.quantity, item.unit).qty;
  const workingUnit = qtyNorm.unit || item.unit || '';
  const parts = [];
  if (rawQtyPresent) parts.push(`исх. объем ${rawQty.toLocaleString('ru-RU', {maximumFractionDigits: 6})}`);
  if (rawUnit) parts.push(`исх. ед. ${rawUnit}`);
  if (unitFactor > 1) parts.push(`множитель ед. ×${unitFactor.toLocaleString('ru-RU')}`);
  if (quantityCoefficient && Math.abs(quantityCoefficient - 1) > 0.000001) parts.push(`кф. объема ${quantityCoefficient.toLocaleString('ru-RU', {maximumFractionDigits: 6})}`);
  if (Number.isFinite(workingQty)) parts.push(`раб. объем ${workingQty.toLocaleString('ru-RU', {maximumFractionDigits: 3})} ${workingUnit}`.trim());
  if (item.lineTotalSource) parts.push(`сумма: ${estimateLineTotalSourceLabel(item.lineTotalSource)}`);
  if (item.currentTotal) parts.push(`тек. ${toNum(item.currentTotal).toLocaleString('ru-RU', {maximumFractionDigits: 2})}`);
  else if (item.lineTotal) parts.push(`строка ${toNum(item.lineTotal).toLocaleString('ru-RU', {maximumFractionDigits: 2})}`);
  if (item.baseTotal) parts.push(`база ${toNum(item.baseTotal).toLocaleString('ru-RU', {maximumFractionDigits: 2})}`);
  if (item.costIndex) parts.push(`инд. ${toNum(item.costIndex).toLocaleString('ru-RU', {maximumFractionDigits: 4})}`);
  return parts.filter(Boolean).join(' · ');
};
export const estimateImportedPlanMeasure = (item={}) => {
  if (!estimateItemLooksImported(item)) {
    const regular = normalizeMeasure(item.quantity, item.unit);
    return {qty: regular.qty, unit: regular.unit || item.unit || '', factor: regular.factor || 1};
  }
  const importedUnit = authoritativeImportedUnit(item) || item.unit || '';
  return normalizeImportedMeasure(item, importedUnit);
};
export const estimateMaterialPlanIssue = (it={}, sectionName='') => {
  if (!isEstimateMaterialItem(it, sectionName)) return '';
  const planMeasure = estimateImportedPlanMeasure(it);
  const qty = toNum(planMeasure.qty);
  const unit = _normalizeUnit(planMeasure.unit || it.unit || '');
  if (!Number.isFinite(qty)) return 'Количество материала не является числом';
  if (qty <= 0) return 'Количество материала не задано или меньше нуля';
  const hasRawQuantity = [it.rawQuantity, it.quantityFinal, it.quantityBase].some(v=>v!==undefined&&v!==null&&v!=='');
  const hasScale = (toNum(it.unitFactor)>1) || estimateUnitScaleInfo(it.unit).factor>1 || estimateUnitScaleInfo(it.rawUnit).factor>1;
  if (estimateItemLooksImported(it) && hasScale && !hasRawQuantity && Math.abs(toNum(it.quantity)) > Math.max(100000, Math.abs(qty) * 100)) {
    return 'Импортная ресурсная строка потеряла исходный объём. Проверьте строку перед закупкой';
  }
  // Старые импортированные сметы могли сохранить ресурс уже умноженным несколько раз.
  // Такие строки нельзя превращать в заявку, пока сметчик не пересчитает/переимпортирует смету.
  if (Math.abs(qty) > 10000000) return 'Подозрительно большое количество. Проверь импорт сметы и исходную единицу измерения';
  if ((unit === 'шт' || unit === 'компл') && Math.abs(qty) > 1000000) return 'Подозрительно большое штучное количество. Проверь ресурсную строку сметы';
  if (!unit || unit === '1') return 'Не распознана единица измерения материала';
  return '';
};
