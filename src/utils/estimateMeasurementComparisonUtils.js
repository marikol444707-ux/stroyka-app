import {
  estimateMeasurementBasisMeta,
  estimateMeasurementBasisOf,
  estimatePackage,
  estimateSectionsOf,
  isEstimateWorkItem,
} from './estimateUtils';
import { _normalizeUnit, normalizeMeasure, toNum } from './measureUtils';
import {
  calcDoorArea,
  calcWindowArea,
  getRoomDoorRevealsTotal,
  getRoomWindowRevealsTotal,
} from './roomMeasurementUtils';

const AREA_MEASUREMENT_BASES = [
  'wall_net_area',
  'wall_gross_area',
  'wall_ceiling_area',
  'floor_area',
  'ceiling_area',
  'window_reveals',
  'door_reveals',
  'opening_reveals',
  'window_area',
  'door_area',
  'openings_area',
];

export const projectMeasurementBasisTotalsFor = (projectName, { rooms = [], roomWindows = [], roomDoors = [] } = {}) => {
  const projectRooms = (rooms || []).filter(r => r.project === projectName);
  const projectRoomIds = new Set(projectRooms.map(r => Number(r.id)));
  const projectWindows = (roomWindows || []).filter(w => projectRoomIds.has(Number(w.room_id)));
  const projectDoors = (roomDoors || []).filter(d => projectRoomIds.has(Number(d.room_id)));
  const wallGrossArea = projectRooms.reduce((s, r) => s + toNum(r.wallArea), 0);
  const windowArea = projectWindows.reduce((s, w) => s + calcWindowArea(w), 0);
  const doorArea = projectDoors.reduce((s, d) => s + calcDoorArea(d), 0);
  const wallNetArea = Math.max(0, Math.round((wallGrossArea - windowArea - doorArea) * 100) / 100);
  const ceilingArea = projectRooms.reduce((s, r) => s + toNum(r.ceilingArea), 0);
  const windowReveals = projectRooms.reduce((s, r) => s + getRoomWindowRevealsTotal(r, projectWindows), 0);
  const doorReveals = projectRooms.reduce((s, r) => s + getRoomDoorRevealsTotal(r, projectDoors), 0);

  return {
    roomCount: projectRooms.length,
    wall_net_area: wallNetArea,
    wall_gross_area: wallGrossArea,
    wall_ceiling_area: wallNetArea + ceilingArea,
    window_area: Math.round(windowArea * 100) / 100,
    door_area: Math.round(doorArea * 100) / 100,
    openings_area: Math.round((windowArea + doorArea) * 100) / 100,
    floor_area: projectRooms.reduce((s, r) => s + toNum(r.floorArea), 0),
    ceiling_area: ceilingArea,
    window_reveals: windowReveals,
    door_reveals: doorReveals,
    opening_reveals: windowReveals + doorReveals,
    window_count: projectWindows.length,
    door_count: projectDoors.length,
  };
};

export const measurementBasisExpectedUnit = (basis) => {
  if (AREA_MEASUREMENT_BASES.includes(basis)) return 'м2';
  if (['window_count', 'door_count'].includes(basis)) return 'шт';
  return '';
};

export const estimateMeasurementComparisonRowsFor = (project, { activeEstimates = [], totals = {} } = {}) => {
  if (!project) return [];
  const rows = [];

  (activeEstimates || []).forEach(est => estimateSectionsOf(est).forEach(section => (section.items || []).forEach((item, itemIdx) => {
    if (!isEstimateWorkItem(item, section.name)) return;
    const basis = estimateMeasurementBasisOf(item, section.name);
    const basisMeta = estimateMeasurementBasisMeta(basis);
    const expectedUnit = measurementBasisExpectedUnit(basis);
    const norm = normalizeMeasure(item.quantity, item.unit);
    const planQty = norm.qty;
    const planUnit = norm.unit || item.unit || '';
    const measuredQty = toNum(totals[basis]);
    const supported = Boolean(expectedUnit);
    if (!supported) return;
    const unitOk = supported ? _normalizeUnit(planUnit) === _normalizeUnit(expectedUnit) : false;
    const tolerance = expectedUnit === 'шт' ? 0.001 : Math.max(0.05, Math.abs(planQty) * 0.01);
    let status = 'Сходится';
    let diff = 0;

    if (!unitOk) status = 'Ед. изм.';
    else if (measuredQty <= 0) status = 'Нет обмера';
    else {
      diff = measuredQty - planQty;
      if (diff > tolerance) status = 'Сверх сметы';
      else if (diff < -tolerance) status = 'В смете больше';
      else status = 'Сходится';
    }

    const price = toNum(item.priceWork) + toNum(item.priceMaterial);
    rows.push({
      key: [est.id, section.name || '', itemIdx].join('|'),
      estimateId: est.id,
      estimateName: est.name || 'Смета',
      packageName: estimatePackage(est),
      sectionName: section.name || 'Без раздела',
      itemName: item.name || '',
      basis,
      basisLabel: basisMeta.label,
      basisIcon: basisMeta.icon,
      planQty,
      planUnit,
      measuredQty,
      expectedUnit,
      diff,
      overQty: Math.max(0, diff),
      shortageQty: Math.max(0, -diff),
      price,
      overSum: Math.max(0, diff) * price,
      status,
      supported,
      unitOk,
    });
  })));

  return rows.sort((a, b) => {
    const rank = {'Сверх сметы': 0, 'Нет обмера': 1, 'Ед. изм.': 2, 'В смете больше': 3, 'Сходится': 4};
    return (rank[a.status] ?? 9) - (rank[b.status] ?? 9) || Math.abs(b.diff) - Math.abs(a.diff);
  });
};

export const estimateMeasurementComparisonSummaryFor = (project, options = {}) => {
  const rows = options.rows || estimateMeasurementComparisonRowsFor(project, options);
  return {
    rows,
    overRows: rows.filter(r => r.status === 'Сверх сметы'),
    shortageRows: rows.filter(r => r.status === 'В смете больше'),
    missingRows: rows.filter(r => r.status === 'Нет обмера'),
    manualRows: rows.filter(r => r.status === 'Ед. изм.'),
    okRows: rows.filter(r => r.status === 'Сходится'),
    overSum: rows.reduce((s, r) => s + toNum(r.overSum), 0),
  };
};
