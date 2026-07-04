import { useCallback, useMemo } from 'react';
import {
  workTypes,
  houseWallTypes,
  housePackages,
  repairObjects,
  repairConditions,
  repairLevels,
  materialModes,
  commerceTypes,
  commerceLevels,
  reconstructionScopes,
  getOptionLabel,
  parseProjectArea,
  formatCompactMoney,
  publicCalcDefaults,
} from './publicSiteContent';

export const usePublicSiteCalculator = ({ calc, setCalc, sitePricingRules }) => {
  const pricingMap = useMemo(() => {
    const map = new Map();
    sitePricingRules.forEach((rule) => {
      if (!rule || rule.enabled === false) return;
      const value = Number(rule.value);
      if (!Number.isFinite(value)) return;
      map.set(`${rule.groupKey}.${rule.itemKey}`, value);
    });
    return map;
  }, [sitePricingRules]);

  const pricingValue = useCallback((groupKey, itemKey, fallback) => {
    const value = pricingMap.get(`${groupKey}.${itemKey}`);
    return Number.isFinite(value) && value > 0 ? value : fallback;
  }, [pricingMap]);

  const result = useMemo(() => {
    const typeMeta = workTypes.find((item) => item.value === calc.type) || workTypes[0];
    const area = Math.max(10, Number(calc.area) || 10);
    const roomsCount = Math.max(1, Number(calc.rooms) || 1);
    const deadlineMultiplier = calc.deadline === 'fast' ? 1.08 : 1;
    const uploadedBonus = calc.files ? 9 : 0;
    const stageBonus = calc.stage === 'estimate' ? 13 : calc.stage === 'project' ? 10 : calc.stage === 'start' ? 7 : 0;

    let total = 0;
    let packageLabel = '';
    let summary = '';
    let confidence = 58 + uploadedBonus + stageBonus;
    let spread = 0.14;
    let breakdown = [];
    let advice = [];

    if (calc.type === 'house') {
      const housePackage = housePackages.find((item) => item.value === calc.package) || housePackages[3];
      const wall = houseWallTypes.find((item) => item.value === calc.wallType) || houseWallTypes[0];
      const housePackageRate = pricingValue('house_package', housePackage.value, housePackage.rate);
      const wallMultiplier = pricingValue('house_wall', wall.value, wall.multiplier);
      const floorMultiplier = Number(calc.floors) > 1 ? 1.06 : 1;
      const coreWorks = area * housePackageRate * wallMultiplier * floorMultiplier;
      const roomPlanning = Math.max(0, roomsCount - Number(calc.floors || 1) * 3) * (calc.package === 'turnkey' ? 85000 : calc.package === 'engineering' ? 60000 : 35000);
      const foundation = calc.foundation ? area * 5200 + 180000 : 0;
      const communications = calc.communications ? area * 3400 + 140000 : 0;
      const management = (coreWorks + roomPlanning + foundation + communications) * 0.04;
      total = (coreWorks + roomPlanning + foundation + communications + management) * deadlineMultiplier;
      packageLabel = housePackage.label;
      summary = `${wall.label}, ${Number(calc.floors)} эт., ${roomsCount} комн., ${housePackage.label}`;
      confidence += 8;
      spread = calc.files ? 0.11 : 0.16;
      breakdown = [
        { label: 'Основные строительные работы', value: coreWorks },
        { label: 'Комнаты, перегородки и узлы', value: roomPlanning },
        { label: 'Фундамент', value: foundation },
        { label: 'Коммуникации', value: communications },
        { label: 'Организация и контроль', value: management },
      ];
      if (!calc.files) advice.push('Загрузите проект или план дома — точность расчёта вырастет.');
      if (calc.stage === 'idea') advice.push('На стадии идеи диапазон шире: нужно уточнить конструктив и участок.');
      if (!calc.foundation) advice.push('Фундамент не включён — проверьте, есть ли он уже на участке.');
    }

    if (calc.type === 'repair') {
      const object = repairObjects.find((item) => item.value === calc.repairObject) || repairObjects[0];
      const condition = repairConditions.find((item) => item.value === calc.repairCondition) || repairConditions[0];
      const level = repairLevels.find((item) => item.value === calc.repairLevel) || repairLevels[1];
      const materials = materialModes.find((item) => item.value === calc.materialMode) || materialModes[1];
      const objectMultiplier = pricingValue('repair_object', object.value, object.multiplier);
      const conditionMultiplier = pricingValue('repair_condition', condition.value, condition.multiplier);
      const levelRate = pricingValue('repair_level', level.value, level.rate);
      const materialsMultiplier = pricingValue('material_mode', materials.value, materials.multiplier);
      const roomComplexity = 1 + Math.max(0, roomsCount - 2) * 0.025;
      const base = area * levelRate * objectMultiplier * conditionMultiplier * roomComplexity;
      const roomWorks = roomsCount * 26000 + Math.max(0, roomsCount - 2) * 18000;
      const demolition = calc.demolition ? area * 2400 : 0;
      const engineering = (calc.electric ? area * 4300 : 0) + (calc.plumbing ? Number(calc.bathrooms || 1) * 95000 : 0);
      const surfaces = (calc.walls ? area * 2200 : 0) + (calc.floorsWork ? area * 2600 : 0) + (calc.ceiling ? area * 1700 : 0) + (calc.tiles ? Number(calc.bathrooms || 1) * 120000 : 0);
      const materialsPart = base * 0.32 * materialsMultiplier;
      const logistics = calc.trash ? area * 900 + 25000 : area * 300;
      total = (base + roomWorks + demolition + engineering + surfaces + materialsPart + logistics) * deadlineMultiplier;
      packageLabel = level.label;
      summary = `${object.label}, ${roomsCount} комн., ${level.label}, ${getOptionLabel(repairConditions, calc.repairCondition)}`;
      confidence += 5;
      spread = calc.files ? 0.12 : 0.2;
      breakdown = [
        { label: 'Черновые и основные работы', value: base },
        { label: 'Комнаты, двери и примыкания', value: roomWorks },
        { label: 'Демонтаж', value: demolition },
        { label: 'Электрика и сантехника', value: engineering },
        { label: 'Стены, полы, потолки, плитка', value: surfaces },
        { label: 'Материалы и логистика', value: materialsPart + logistics },
      ];
      if (!calc.files) advice.push('Для ремонта особенно нужны фото текущего состояния помещения.');
      if (!calc.demolition && calc.repairCondition !== 'new') advice.push('Если нужен демонтаж, включите его — он заметно влияет на сумму.');
      if (calc.materialMode === 'client') advice.push('Материалы клиента уменьшают расчёт, но точность зависит от фактических закупок.');
    }

    if (calc.type === 'commerce') {
      const object = commerceTypes.find((item) => item.value === calc.commerceType) || commerceTypes[0];
      const level = commerceLevels.find((item) => item.value === calc.commerceLevel) || commerceLevels[2];
      const objectMultiplier = pricingValue('commerce_type', object.value, object.multiplier);
      const levelRate = pricingValue('commerce_level', level.value, level.rate);
      const conditionMultiplier = calc.commerceCondition === 'old' ? 1.2 : calc.commerceCondition === 'ready' ? 0.82 : 1;
      const premisesComplexity = 1 + Math.max(0, roomsCount - 3) * 0.035;
      const fitout = area * levelRate * objectMultiplier * conditionMultiplier * premisesComplexity;
      const premisesWorks = Math.max(0, roomsCount - 1) * 65000;
      const ventilation = calc.ventilation ? area * 5200 : 0;
      const fire = calc.fireSafety ? area * 4300 : 0;
      const power = calc.powerEquipment ? area * 3600 : 0;
      const projectDocs = calc.designProject ? area * 1800 : area * 900;
      const schedule = calc.nightWork ? area * 1900 : 0;
      total = (fitout + premisesWorks + ventilation + fire + power + projectDocs + schedule) * deadlineMultiplier;
      packageLabel = level.label;
      summary = `${object.label}, ${roomsCount} помещ., ${level.label}`;
      confidence += 3;
      spread = calc.files ? 0.14 : 0.22;
      breakdown = [
        { label: 'Отделка и подготовка помещения', value: fitout },
        { label: 'Зонирование и отдельные помещения', value: premisesWorks },
        { label: 'Вентиляция', value: ventilation },
        { label: 'Пожарная безопасность', value: fire },
        { label: 'Электрика под оборудование', value: power },
        { label: 'Проектирование, график и запуск', value: projectDocs + schedule },
      ];
      if (!calc.files) advice.push('Для коммерции нужны план помещения и фото инженерных точек.');
      if (!calc.fireSafety) advice.push('Проверьте требования пожарки: для кафе, салона и медкабинета это часто обязательно.');
      if (!calc.designProject) advice.push('Без дизайн-проекта сроки и объёмы лучше уточнить на замере.');
    }

    if (calc.type === 'reconstruction') {
      const scope = reconstructionScopes.find((item) => item.value === calc.reconstructionScope) || reconstructionScopes[0];
      const scopeRate = pricingValue('reconstruction_scope', scope.value, scope.rate);
      const base = area * scopeRate;
      const roomSurvey = roomsCount * 22000;
      const demolition = (calc.demolition ? area * 3400 : area * 1200) + roomSurvey;
      const reinforcement = calc.reinforcement ? area * 5200 + 120000 : 0;
      const foundation = calc.foundationTouch ? area * 6200 + 180000 : 0;
      const roof = calc.roofTouch ? area * 4300 + 160000 : 0;
      const engineering = calc.engineeringNew ? area * 4800 : 0;
      const inspection = calc.inspectionNeeded ? 85000 : 0;
      total = (base + demolition + reinforcement + foundation + roof + engineering + inspection) * deadlineMultiplier;
      packageLabel = scope.label;
      summary = `${scope.label}, ${roomsCount} помещ., ${calc.keepsStructure ? 'часть конструкций сохраняем' : 'полная переделка'}`;
      confidence += calc.files ? 3 : -4;
      spread = calc.files ? 0.2 : 0.3;
      breakdown = [
        { label: 'Основной объём реконструкции', value: base },
        { label: 'Демонтаж и подготовка', value: demolition },
        { label: 'Усиление конструкций', value: reinforcement },
        { label: 'Фундамент и кровля', value: foundation + roof },
        { label: 'Инженерия и обследование', value: engineering + inspection },
      ];
      advice.push('Реконструкция всегда требует осмотра: скрытые дефекты могут изменить смету.');
      if (!calc.files) advice.push('Загрузите фото текущего состояния, фасада, кровли и проблемных мест.');
      if (!calc.inspectionNeeded) advice.push('Если объект старый, обследование лучше не отключать.');
    }

    const cleanBreakdown = breakdown.filter((item) => item.value > 0);
    const min = Math.round(total * (1 - spread) / 10000) * 10000;
    const max = Math.round(total * (1 + spread) / 10000) * 10000;

    return {
      min,
      max,
      confidence: Math.max(42, Math.min(92, Math.round(confidence))),
      typeLabel: typeMeta.label,
      packageLabel,
      summary,
      breakdown: cleanBreakdown,
      advice: advice.slice(0, 3),
    };
  }, [calc, pricingValue]);

  const updateCalc = (field, value) => {
    setCalc((current) => ({ ...current, [field]: value }));
  };

  const getReferenceProjectEstimate = useCallback((direction, project) => {
    const projectCalc = {
      ...publicCalcDefaults,
      ...(direction?.calcPatch || {}),
      ...(project?.calcPatch || {}),
      stage: 'project',
      files: 1,
    };
    const area = Math.max(1, Number(projectCalc.area) || parseProjectArea(project) || 1);
    const roomsCount = Math.max(1, Number(projectCalc.rooms) || 1);
    const floors = Math.max(1, Number(projectCalc.floors) || 1);
    let total = 0;
    let spread = 0.16;

    if (projectCalc.type === 'house') {
      const housePackage = housePackages.find((item) => item.value === projectCalc.package) || housePackages[3];
      const wall = houseWallTypes.find((item) => item.value === projectCalc.wallType) || houseWallTypes[0];
      const housePackageRate = pricingValue('house_package', housePackage.value, housePackage.rate);
      const wallMultiplier = pricingValue('house_wall', wall.value, wall.multiplier);
      const floorMultiplier = floors > 1 ? 1.06 : 1;
      const coreWorks = area * housePackageRate * wallMultiplier * floorMultiplier;
      const roomPlanning = Math.max(0, roomsCount - floors * 3) * (projectCalc.package === 'turnkey' ? 85000 : projectCalc.package === 'engineering' ? 60000 : 35000);
      const foundation = projectCalc.foundation ? area * 5200 + 180000 : 0;
      const communications = projectCalc.communications ? area * 3400 + 140000 : 0;
      const management = (coreWorks + roomPlanning + foundation + communications) * 0.04;
      total = coreWorks + roomPlanning + foundation + communications + management;
      spread = 0.13;
    } else if (projectCalc.type === 'repair') {
      const object = repairObjects.find((item) => item.value === projectCalc.repairObject) || repairObjects[0];
      const condition = repairConditions.find((item) => item.value === projectCalc.repairCondition) || repairConditions[0];
      const level = repairLevels.find((item) => item.value === projectCalc.repairLevel) || repairLevels[1];
      const materials = materialModes.find((item) => item.value === projectCalc.materialMode) || materialModes[1];
      const objectMultiplier = pricingValue('repair_object', object.value, object.multiplier);
      const conditionMultiplier = pricingValue('repair_condition', condition.value, condition.multiplier);
      const levelRate = pricingValue('repair_level', level.value, level.rate);
      const materialsMultiplier = pricingValue('material_mode', materials.value, materials.multiplier);
      const roomComplexity = 1 + Math.max(0, roomsCount - 2) * 0.025;
      const base = area * levelRate * objectMultiplier * conditionMultiplier * roomComplexity;
      const roomWorks = roomsCount * 26000 + Math.max(0, roomsCount - 2) * 18000;
      const demolition = projectCalc.demolition ? area * 2400 : 0;
      const engineering = (projectCalc.electric ? area * 4300 : 0) + (projectCalc.plumbing ? Number(projectCalc.bathrooms || 1) * 95000 : 0);
      const surfaces = (projectCalc.walls ? area * 2200 : 0) + (projectCalc.floorsWork ? area * 2600 : 0) + (projectCalc.ceiling ? area * 1700 : 0) + (projectCalc.tiles ? Number(projectCalc.bathrooms || 1) * 120000 : 0);
      const materialsPart = base * 0.32 * materialsMultiplier;
      const logistics = projectCalc.trash ? area * 900 + 25000 : area * 300;
      total = base + roomWorks + demolition + engineering + surfaces + materialsPart + logistics;
      spread = 0.16;
    } else if (projectCalc.type === 'commerce') {
      const object = commerceTypes.find((item) => item.value === projectCalc.commerceType) || commerceTypes[0];
      const level = commerceLevels.find((item) => item.value === projectCalc.commerceLevel) || commerceLevels[2];
      const objectMultiplier = pricingValue('commerce_type', object.value, object.multiplier);
      const levelRate = pricingValue('commerce_level', level.value, level.rate);
      const conditionMultiplier = projectCalc.commerceCondition === 'old' ? 1.2 : projectCalc.commerceCondition === 'ready' ? 0.82 : 1;
      const premisesComplexity = 1 + Math.max(0, roomsCount - 3) * 0.035;
      const fitout = area * levelRate * objectMultiplier * conditionMultiplier * premisesComplexity;
      const premisesWorks = Math.max(0, roomsCount - 1) * 65000;
      const ventilation = projectCalc.ventilation ? area * 5200 : 0;
      const fire = projectCalc.fireSafety ? area * 4300 : 0;
      const power = projectCalc.powerEquipment ? area * 3600 : 0;
      const projectDocs = projectCalc.designProject ? area * 1800 : area * 900;
      total = fitout + premisesWorks + ventilation + fire + power + projectDocs;
      spread = 0.18;
    } else if (projectCalc.type === 'reconstruction') {
      const scope = reconstructionScopes.find((item) => item.value === projectCalc.reconstructionScope) || reconstructionScopes[0];
      const scopeRate = pricingValue('reconstruction_scope', scope.value, scope.rate);
      const base = area * scopeRate;
      const demolition = (projectCalc.demolition ? area * 3400 : area * 1200) + roomsCount * 22000;
      const reinforcement = projectCalc.reinforcement ? area * 5200 + 120000 : 0;
      const foundation = projectCalc.foundationTouch ? area * 6200 + 180000 : 0;
      const roof = projectCalc.roofTouch ? area * 4300 + 160000 : 0;
      const engineering = projectCalc.engineeringNew ? area * 4800 : 0;
      const inspection = projectCalc.inspectionNeeded ? 85000 : 0;
      total = base + demolition + reinforcement + foundation + roof + engineering + inspection;
      spread = 0.24;
    }

    const min = Math.max(10000, Math.round(total * (1 - spread) / 10000) * 10000);
    const max = Math.max(min, Math.round(total * (1 + spread) / 10000) * 10000);
    return {
      min,
      max,
      rangeLabel: `${formatCompactMoney(min)} - ${formatCompactMoney(max)}`,
      fromLabel: `от ${formatCompactMoney(min)}`,
    };
  }, [pricingValue]);

  return {
    result,
    updateCalc,
    getReferenceProjectEstimate,
  };
};
