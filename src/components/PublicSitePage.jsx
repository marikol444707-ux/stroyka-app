import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Calculator,
  Camera,
  Check,
  ChevronRight,
  Clock,
  FileText,
  Image,
  MapPin,
  Package,
  QrCode,
  Settings,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { API } from '../api';
import './PublicSitePage.css';
import {
  PUBLIC_CONSENT_VERSION,
  PUBLIC_SITE_OPERATOR,
  PROJECT_EXAMPLE_STATUS,
  publicFunnelSteps,
  workTypes,
  houseWallTypes,
  housePackages,
  stages,
  repairObjects,
  repairConditions,
  repairLevels,
  materialModes,
  commerceTypes,
  commerceLevels,
  reconstructionScopes,
  getOptionLabel,
  projectFilters,
  workProofItems,
  trustItems,
  faqItems,
  referenceDirections,
  getReferenceProjectCards,
  findReferenceProjectByCode,
  parseProjectArea,
  getProjectMediaOptions,
  getProjectSpecs,
  getProjectLayoutGroups,
  getReferenceObjectCard,
  getProjectMediaSequence,
  ProjectConceptThumb,
  ProjectCardMediaPreview,
  ProjectConceptVisual,
  partnerTypes,
  publicProjects,
  formatMoney,
  formatCompactMoney,
  publicCalcDefaults,
  normalizeSiteProject
} from '../features/public-site/publicSiteContent';
const PublicSitePage = ({ onLogin }) => {
  const [calc, setCalc] = useState(publicCalcDefaults);
  const [lead, setLead] = useState({ name: '', phone: '', comment: '' });
  const [leadConsent, setLeadConsent] = useState(false);
  const [leadWebsite, setLeadWebsite] = useState('');
  const [sent, setSent] = useState(false);
  const [leadSending, setLeadSending] = useState(false);
  const [leadError, setLeadError] = useState('');
  const [partnerLead, setPartnerLead] = useState({
    type: 'supplier',
    name: '',
    phone: '',
    comment: '',
  });
  const [partnerConsent, setPartnerConsent] = useState(false);
  const [partnerWebsite, setPartnerWebsite] = useState('');
  const [partnerSending, setPartnerSending] = useState(false);
  const [partnerSent, setPartnerSent] = useState(false);
  const [partnerError, setPartnerError] = useState('');
  const [siteProjects, setSiteProjects] = useState(publicProjects);
  const [projectCategory, setProjectCategory] = useState('all');
  const [selectedProjectId, setSelectedProjectId] = useState(publicProjects[0].id);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const [sitePricingRules, setSitePricingRules] = useState([]);
  const [selectedReferenceId, setSelectedReferenceId] = useState(referenceDirections[0].id);
  const [selectedReferenceExample, setSelectedReferenceExample] = useState(getReferenceProjectCards(referenceDirections[0])[0].title);
  const [selectedReferenceMediaId, setSelectedReferenceMediaId] = useState('render-front');
  const [isReferenceMirrored, setIsReferenceMirrored] = useState(false);
  const deepLinkedReferenceRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const loadSitePricing = async () => {
      try {
        const response = await fetch(API + '/site/pricing');
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled) return;
        setSitePricingRules(Array.isArray(data.rules) ? data.rules : []);
      } catch (_) {
        // Если backend ещё не обновлён, калькулятор работает по локальным дефолтам.
      }
    };
    const loadSiteProjects = async () => {
      try {
        const response = await fetch(API + '/site/projects');
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled || !Array.isArray(data) || data.length === 0) return;
        const normalized = data.map(normalizeSiteProject);
        setSiteProjects(normalized);
        setSelectedProjectId(normalized[0].id);
        setSelectedPhotoIndex(0);
      } catch (_) {
        // Если backend ещё не обновлён или опубликованных объектов нет, оставляем демо-галерею.
      }
    };
    loadSitePricing();
    loadSiteProjects();
    return () => { cancelled = true; };
  }, []);

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

  const filteredProjects = useMemo(() => (
    projectCategory === 'all'
      ? siteProjects
      : siteProjects.filter((project) => project.category === projectCategory)
  ), [projectCategory, siteProjects]);

  const selectedProject = filteredProjects.find((project) => project.id === selectedProjectId) || filteredProjects[0] || siteProjects[0] || publicProjects[0];
  const selectedPhoto = selectedProject.images[selectedPhotoIndex] || selectedProject.images[0];
  const selectedReference = referenceDirections.find((item) => item.id === selectedReferenceId) || referenceDirections[0];
  const selectedReferenceProjects = getReferenceProjectCards(selectedReference);
  const selectedReferenceProject = selectedReferenceProjects.find((project) => project.title === selectedReferenceExample) || selectedReferenceProjects[0];
  const selectedReferenceSpecs = getProjectSpecs(selectedReference, selectedReferenceProject);
  const selectedReferenceLayoutGroups = getProjectLayoutGroups(selectedReference, selectedReferenceProject);
  const selectedReferenceMediaOptions = getProjectMediaOptions(selectedReference, selectedReferenceProject);
  const selectedReferenceMedia = selectedReferenceMediaOptions.find((item) => item.id === selectedReferenceMediaId) || selectedReferenceMediaOptions[0];
  const selectedReferenceMediaIndex = Math.max(0, selectedReferenceMediaOptions.findIndex((item) => item.id === selectedReferenceMedia?.id));
  const selectedReferenceEstimate = getReferenceProjectEstimate(selectedReference, selectedReferenceProject);
  const selectedReferenceObjectCard = getReferenceObjectCard(selectedReference, selectedReferenceProject, selectedReferenceEstimate);
  const selectedReferenceRenderCount = selectedReferenceMediaOptions.filter((item) => item.role === 'render' || item.kind === 'render').length;
  const selectedReferencePlanCount = selectedReferenceMediaOptions.filter((item) => item.role === 'plan' || item.kind === 'plan').length;
  const selectedReferenceAssetSummary = [
    { icon: Camera, label: '3D ракурсы', value: `${Math.max(1, selectedReferenceRenderCount)} шт.` },
    { icon: FileText, label: 'Планировка', value: `${Math.max(1, selectedReferencePlanCount)} шт.` },
    { icon: Calculator, label: 'Ориентир', value: selectedReferenceEstimate.fromLabel },
    { icon: Check, label: 'Действие', value: 'в расчет' },
  ];
  const selectedReferenceDecisionFacts = [
    ['Направление', selectedReference.title],
    ['Проект', selectedReferenceProject?.code || 'карточка'],
    ['Ориентир', selectedReferenceEstimate.fromLabel],
    ['Медиа', `${selectedReferenceMediaOptions.length} вида`],
  ];
  const selectedReferenceDeepLink = selectedReferenceProject?.code
    ? `/?project=${encodeURIComponent(selectedReferenceProject.code)}#projects`
    : '/#projects';
  const selectedReferencePublicUrl = `https://stroyka26.pro${selectedReferenceDeepLink}`;
  const selectedLeadProject = {
    status: PROJECT_EXAMPLE_STATUS,
    directionId: selectedReference.id,
    directionTitle: selectedReference.title,
    projectCode: selectedReferenceProject?.code || '',
    projectTitle: selectedReferenceProject?.title || selectedReference.title,
    projectArea: selectedReferenceProject?.area || '',
    projectFloors: selectedReferenceProject?.floors || '',
    projectLayout: selectedReferenceProject?.layout || selectedReference.text,
    projectVisuals: selectedReferenceProject?.visuals || '',
    projectUrl: selectedReferencePublicUrl,
    estimateRange: selectedReferenceEstimate.rangeLabel,
    estimateFrom: selectedReferenceEstimate.fromLabel,
    mediaCount: selectedReferenceMediaOptions.length,
    media: selectedReferenceMediaOptions.map((item) => ({
      id: item.id,
      label: item.label,
      role: item.role,
      src: item.src || '',
    })),
  };

  const chooseProjectCategory = (category) => {
    const nextProjects = category === 'all'
      ? siteProjects
      : siteProjects.filter((project) => project.category === category);
    setProjectCategory(category);
    setSelectedProjectId(nextProjects[0]?.id || siteProjects[0]?.id || publicProjects[0].id);
    setSelectedPhotoIndex(0);
  };

  const chooseProject = (projectId) => {
    setSelectedProjectId(projectId);
    setSelectedPhotoIndex(0);
  };

  const scrollTo = useCallback((id) => {
    if (typeof document === 'undefined') return;
    const element = document.getElementById(id);
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const scrollToCurrentHash = useCallback(() => {
    if (typeof window === 'undefined') return;
    const id = decodeURIComponent(window.location.hash.replace(/^#/, ''));
    if (!id) return;
    [0, 120, 420].forEach((delay) => {
      setTimeout(() => scrollTo(id), delay);
    });
  }, [scrollTo]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    scrollToCurrentHash();
    window.addEventListener('hashchange', scrollToCurrentHash);
    return () => window.removeEventListener('hashchange', scrollToCurrentHash);
  }, [scrollToCurrentHash]);

  const chooseReference = useCallback((direction, project = getReferenceProjectCards(direction)[0], scrollTarget = '') => {
    const projectCard = typeof project === 'string'
      ? getReferenceProjectCards(direction).find((item) => item.title === project) || { title: project, calcPatch: {} }
      : project;
    setSelectedReferenceId(direction.id);
    setSelectedReferenceExample(projectCard.title);
    setSelectedReferenceMediaId('render-front');
    setIsReferenceMirrored(false);
    setCalc((current) => ({ ...current, ...direction.calcPatch, ...(projectCard.calcPatch || {}) }));
    setLead((current) => ({
      ...current,
      comment: `Интересует: ${direction.title}. Проект: ${projectCard.title}. Формат объекта: ${getReferenceObjectCard(direction, projectCard, getReferenceProjectEstimate(direction, projectCard)).format}. Планировка: ${projectCard.layout || direction.text}. Ссылка на карточку: https://stroyka26.pro/?project=${encodeURIComponent(projectCard.code || '')}#projects`,
    }));
    if (scrollTarget === 'calculator' || scrollTarget === true) {
      setTimeout(() => scrollTo('calculator'), 0);
    }
    if (scrollTarget === 'catalog') {
      setTimeout(() => document.querySelector('.public-project-catalog')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    }
  }, [getReferenceProjectEstimate, scrollTo]);

  useEffect(() => {
    if (deepLinkedReferenceRef.current) return;
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const projectCode = params.get('project') || params.get('ref');
    const match = findReferenceProjectByCode(projectCode);
    if (!match) return;
    deepLinkedReferenceRef.current = true;
    chooseReference(match.direction, match.project, 'catalog');
  }, [chooseReference]);

  const chooseSimilarReferenceProject = () => {
    const currentIndex = selectedReferenceProjects.findIndex((project) => project.title === selectedReferenceProject?.title);
    const nextProject = selectedReferenceProjects[(currentIndex + 1) % selectedReferenceProjects.length] || selectedReferenceProjects[0];
    chooseReference(selectedReference, nextProject);
  };

  const requestLayoutEditor = () => {
    setCalc((current) => ({ ...current, ...selectedReference.calcPatch, ...(selectedReferenceProject?.calcPatch || {}) }));
    setLead((current) => ({
      ...current,
      comment: `Нужна доработка планировки. Направление: ${selectedReference.title}. Проект: ${selectedReferenceProject?.title || selectedReference.title}. Планировка: ${selectedReferenceProject?.layout || selectedReference.text}`,
    }));
    setTimeout(() => scrollTo('calculator'), 0);
  };

  const submitLead = async (event) => {
    event.preventDefault();
    if (leadSending) return;
    setLeadError('');
    if (!leadConsent) {
      setLeadError('Подтвердите согласие на обработку персональных данных.');
      return;
    }
    setLeadSending(true);
    try {
      const response = await fetch(API + '/site/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...lead,
          source: 'Сайт',
          budget: result.max || result.min || 0,
          page: 'public-site',
          legalSource: typeof window !== 'undefined' ? window.location.href : 'public-site',
          referrer: typeof document !== 'undefined' ? document.referrer : '',
          userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
          submittedAt: new Date().toISOString(),
          utm: typeof window !== 'undefined'
            ? Object.fromEntries(new URLSearchParams(window.location.search).entries())
            : {},
          consentAccepted: leadConsent,
          consentVersion: PUBLIC_CONSENT_VERSION,
          website: leadWebsite,
          calculation: {
            typeLabel: result.typeLabel,
            summary: result.summary,
            rangeText: `${formatMoney(result.min)} - ${formatMoney(result.max)} ₽`,
          },
          selectedProject: selectedLeadProject,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || 'Не удалось отправить заявку');
      }
      setSent(true);
      setLead({ name: '', phone: '', comment: '' });
      setLeadConsent(false);
      setLeadWebsite('');
    } catch (error) {
      setLeadError(error.message || 'Не удалось отправить заявку');
    } finally {
      setLeadSending(false);
    }
  };

  const submitPartnerLead = async (event) => {
    event.preventDefault();
    if (partnerSending) return;
    setPartnerError('');
    setPartnerSent(false);
    if (!partnerConsent) {
      setPartnerError('Подтвердите согласие на обработку персональных данных.');
      return;
    }
    setPartnerSending(true);
    try {
      const partnerType = partnerTypes.find((item) => item.value === partnerLead.type) || partnerTypes[0];
      const response = await fetch(API + '/site/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: partnerLead.name || partnerType.label,
          phone: partnerLead.phone,
          comment: [
            'Тип заявки: ' + partnerType.label,
            partnerLead.comment ? 'Комментарий: ' + partnerLead.comment : '',
            'Заявка только на проверку. Активный доступ не выдавать автоматически.',
          ].filter(Boolean).join('\n'),
          source: 'Сайт: партнерская заявка',
          budget: 0,
          page: 'public-site-partners',
          legalSource: typeof window !== 'undefined' ? window.location.href : 'public-site-partners',
          referrer: typeof document !== 'undefined' ? document.referrer : '',
          userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
          submittedAt: new Date().toISOString(),
          consentAccepted: partnerConsent,
          consentVersion: PUBLIC_CONSENT_VERSION,
          website: partnerWebsite,
          partnerType: partnerLead.type,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || 'Не удалось отправить заявку');
      }
      setPartnerSent(true);
      setPartnerLead({ type: 'supplier', name: '', phone: '', comment: '' });
      setPartnerConsent(false);
      setPartnerWebsite('');
    } catch (error) {
      setPartnerError(error.message || 'Не удалось отправить заявку');
    } finally {
      setPartnerSending(false);
    }
  };

  return (
    <main className="public-site">
      <section className="public-hero">
        <header className="public-nav">
          <button className="public-brand" type="button" onClick={() => scrollTo('top')}>
            <span>Строй</span><strong>Ка</strong>
          </button>
          <nav className="public-nav-links" aria-label="Навигация по сайту">
            <button type="button" onClick={() => scrollTo('directions')}>Направления</button>
            <button type="button" onClick={() => scrollTo('projects')}>Проекты</button>
            <button type="button" onClick={() => scrollTo('calculator')}>Калькулятор</button>
            <button type="button" onClick={() => scrollTo('process')}>Как работаем</button>
            <button type="button" onClick={() => scrollTo('objects')}>Работы</button>
            <button type="button" onClick={() => scrollTo('request')}>Заявка</button>
          </nav>
          <button className="public-login" type="button" onClick={onLogin}>Вход в ERP</button>
        </header>

        <div id="top" className="public-hero-content">
          <div className="public-hero-copy">
            <p className="public-eyebrow">Строительная компания с цифровым контролем</p>
            <h1>Строим с понятной сметой и цифровым паспортом объекта</h1>
            <p className="public-lead">
              Расчёт стоимости, фотоотчёты, этапы работ, материалы и гарантия
              ведутся в одной системе.
            </p>
            <div className="public-hero-actions">
              <button className="public-primary" type="button" onClick={() => scrollTo('directions')}>
                Выбрать проект
                <ChevronRight size={18} />
              </button>
              <button className="public-secondary" type="button" onClick={() => scrollTo('calculator')}>
                Рассчитать стоимость
              </button>
            </div>
            <div className="public-hero-flow" aria-label="Путь клиента на сайте">
              {publicFunnelSteps.map((step) => (
                <button key={step.number} type="button" onClick={() => scrollTo(step.target)}>
                  <b>{step.number}</b>
                  <span>
                    <strong>{step.title}</strong>
                    <small>{step.text}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="public-hero-tools">
          <section id="calculator" className="public-calculator" aria-label="Калькулятор строительства">
            <div className="public-tool-header">
              <div>
                <p className="public-tool-kicker">Предварительный расчёт</p>
                <h2>Калькулятор стоимости</h2>
              </div>
              <div className="public-live-badge">
                <Calculator size={16} />
                Сумма обновляется
              </div>
            </div>

            <div className="public-type-grid" aria-label="Тип расчёта">
              {workTypes.map((item) => (
                <button
                  className={calc.type === item.value ? 'public-type-card active' : 'public-type-card'}
                  type="button"
                  key={item.value}
                  onClick={() => updateCalc('type', item.value)}
                >
                  <span>{item.short}</span>
                  <b>{item.label}</b>
                  <small>{item.description}</small>
                </button>
              ))}
            </div>

            <div className="public-stepper">
              {[
                '1 Тип объекта',
                calc.type === 'house' ? '2 Конструктив' : '2 Состояние',
                calc.type === 'house' ? '3 Комплектация' : '3 Работы',
                '4 Итог',
              ].map((step, index) => (
                <div className={index === 3 ? 'public-step active' : 'public-step'} key={step}>
                  {step}
                </div>
              ))}
            </div>

            <div className="public-calc-grid">
              <label className="public-field">
                <span>{calc.type === 'repair' ? 'Площадь ремонта, м2' : calc.type === 'commerce' ? 'Площадь помещения, м2' : 'Площадь, м2'}</span>
                <input
                  type="number"
                  min="10"
                  value={calc.area}
                  onChange={(event) => updateCalc('area', event.target.value)}
                />
              </label>

              {calc.type === 'house' && (
                <>
                  <label className="public-field">
                    <span>Этажей</span>
                    <select value={calc.floors} onChange={(event) => updateCalc('floors', event.target.value)}>
                      <option value="1">1 этаж</option>
                      <option value="2">2 этажа</option>
                      <option value="3">3 этажа</option>
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Комнат</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Материал стен</span>
                    <select value={calc.wallType} onChange={(event) => updateCalc('wallType', event.target.value)}>
                      {houseWallTypes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Комплектация</span>
                    <select value={calc.package} onChange={(event) => updateCalc('package', event.target.value)}>
                      {housePackages.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                </>
              )}

              {calc.type === 'repair' && (
                <>
                  <label className="public-field">
                    <span>Что ремонтируем</span>
                    <select value={calc.repairObject} onChange={(event) => updateCalc('repairObject', event.target.value)}>
                      {repairObjects.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Комнат</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Санузлов</span>
                    <input type="number" min="0" value={calc.bathrooms} onChange={(event) => updateCalc('bathrooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Состояние</span>
                    <select value={calc.repairCondition} onChange={(event) => updateCalc('repairCondition', event.target.value)}>
                      {repairConditions.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Уровень ремонта</span>
                    <select value={calc.repairLevel} onChange={(event) => updateCalc('repairLevel', event.target.value)}>
                      {repairLevels.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Материалы</span>
                    <select value={calc.materialMode} onChange={(event) => updateCalc('materialMode', event.target.value)}>
                      {materialModes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                </>
              )}

              {calc.type === 'commerce' && (
                <>
                  <label className="public-field">
                    <span>Тип бизнеса</span>
                    <select value={calc.commerceType} onChange={(event) => updateCalc('commerceType', event.target.value)}>
                      {commerceTypes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Формат работ</span>
                    <select value={calc.commerceLevel} onChange={(event) => updateCalc('commerceLevel', event.target.value)}>
                      {commerceLevels.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Помещений / зон</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Состояние помещения</span>
                    <select value={calc.commerceCondition} onChange={(event) => updateCalc('commerceCondition', event.target.value)}>
                      <option value="shell">Черновое</option>
                      <option value="ready">Почти готово</option>
                      <option value="old">Старое помещение</option>
                    </select>
                  </label>
                </>
              )}

              {calc.type === 'reconstruction' && (
                <>
                  <label className="public-field">
                    <span>Что реконструируем</span>
                    <select value={calc.reconstructionScope} onChange={(event) => updateCalc('reconstructionScope', event.target.value)}>
                      {reconstructionScopes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Конструкции</span>
                    <select value={calc.keepsStructure ? 'keep' : 'replace'} onChange={(event) => updateCalc('keepsStructure', event.target.value === 'keep')}>
                      <option value="keep">Часть сохраняем</option>
                      <option value="replace">Полная переделка</option>
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Помещений</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Сложность</span>
                    <select value={calc.inspectionNeeded ? 'inspect' : 'simple'} onChange={(event) => updateCalc('inspectionNeeded', event.target.value === 'inspect')}>
                      <option value="inspect">Нужно обследование</option>
                      <option value="simple">Понятный объём</option>
                    </select>
                  </label>
                </>
              )}

              <label className="public-field">
                <span>Срок</span>
                <select value={calc.deadline} onChange={(event) => updateCalc('deadline', event.target.value)}>
                  <option value="normal">Обычный график</option>
                  <option value="fast">Ускоренный старт</option>
                </select>
              </label>
              <label className="public-field">
                <span>Стадия</span>
                <select value={calc.stage} onChange={(event) => updateCalc('stage', event.target.value)}>
                  {stages.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                </select>
              </label>
            </div>

            <div className="public-check-grid">
              {calc.type === 'house' && (
                <>
                  <label><input type="checkbox" checked={calc.foundation} onChange={(event) => updateCalc('foundation', event.target.checked)} /> Фундамент нужен</label>
                  <label><input type="checkbox" checked={calc.communications} onChange={(event) => updateCalc('communications', event.target.checked)} /> Коммуникации нужны</label>
                </>
              )}

              {calc.type === 'repair' && (
                <>
                  <label><input type="checkbox" checked={calc.demolition} onChange={(event) => updateCalc('demolition', event.target.checked)} /> Демонтаж</label>
                  <label><input type="checkbox" checked={calc.electric} onChange={(event) => updateCalc('electric', event.target.checked)} /> Электрика</label>
                  <label><input type="checkbox" checked={calc.plumbing} onChange={(event) => updateCalc('plumbing', event.target.checked)} /> Сантехника</label>
                  <label><input type="checkbox" checked={calc.walls} onChange={(event) => updateCalc('walls', event.target.checked)} /> Стены</label>
                  <label><input type="checkbox" checked={calc.floorsWork} onChange={(event) => updateCalc('floorsWork', event.target.checked)} /> Полы</label>
                  <label><input type="checkbox" checked={calc.ceiling} onChange={(event) => updateCalc('ceiling', event.target.checked)} /> Потолки</label>
                  <label><input type="checkbox" checked={calc.tiles} onChange={(event) => updateCalc('tiles', event.target.checked)} /> Плитка</label>
                  <label><input type="checkbox" checked={calc.trash} onChange={(event) => updateCalc('trash', event.target.checked)} /> Вывоз мусора</label>
                </>
              )}

              {calc.type === 'commerce' && (
                <>
                  <label><input type="checkbox" checked={calc.ventilation} onChange={(event) => updateCalc('ventilation', event.target.checked)} /> Вентиляция</label>
                  <label><input type="checkbox" checked={calc.fireSafety} onChange={(event) => updateCalc('fireSafety', event.target.checked)} /> Пожарка</label>
                  <label><input type="checkbox" checked={calc.powerEquipment} onChange={(event) => updateCalc('powerEquipment', event.target.checked)} /> Электрика под оборудование</label>
                  <label><input type="checkbox" checked={calc.designProject} onChange={(event) => updateCalc('designProject', event.target.checked)} /> Есть дизайн-проект</label>
                  <label><input type="checkbox" checked={calc.nightWork} onChange={(event) => updateCalc('nightWork', event.target.checked)} /> Ночные работы</label>
                </>
              )}

              {calc.type === 'reconstruction' && (
                <>
                  <label><input type="checkbox" checked={calc.demolition} onChange={(event) => updateCalc('demolition', event.target.checked)} /> Большой демонтаж</label>
                  <label><input type="checkbox" checked={calc.reinforcement} onChange={(event) => updateCalc('reinforcement', event.target.checked)} /> Усиление конструкций</label>
                  <label><input type="checkbox" checked={calc.foundationTouch} onChange={(event) => updateCalc('foundationTouch', event.target.checked)} /> Трогаем фундамент</label>
                  <label><input type="checkbox" checked={calc.roofTouch} onChange={(event) => updateCalc('roofTouch', event.target.checked)} /> Трогаем кровлю</label>
                  <label><input type="checkbox" checked={calc.engineeringNew} onChange={(event) => updateCalc('engineeringNew', event.target.checked)} /> Новая инженерия</label>
                </>
              )}

              <label className="public-upload">
                <Upload size={16} />
                Проект / фото / план
                <input
                  type="file"
                  multiple
                  onChange={(event) => updateCalc('files', event.target.files?.length || 0)}
              />
              </label>
              {calc.files > 0 && <span className="public-file-count">Файлов: {calc.files}</span>}
            </div>

            <div className="public-result">
              <div className="public-result-main">
                <div>
                  <span>Предварительно</span>
                  <strong>{formatMoney(result.min)} - {formatMoney(result.max)} ₽</strong>
                  <small>{result.typeLabel}: {result.summary}</small>
                </div>
                <div className="public-confidence">
                  <div className="public-confidence-top">
                    <span>Точность расчёта</span>
                    <b>{result.confidence}%</b>
                  </div>
                  <div className="public-progress"><i style={{ width: `${result.confidence}%` }} /></div>
                </div>
                <button className="public-primary public-result-button" type="button" onClick={() => scrollTo('request')}>
                  Получить точную смету
                </button>
              </div>

              <div className="public-breakdown">
                {result.breakdown.map((item) => (
                  <div className="public-breakdown-row" key={item.label}>
                    <span>{item.label}</span>
                    <b>{formatMoney(item.value)} ₽</b>
                  </div>
                ))}
              </div>

              <div className="public-advice-list">
                {result.advice.map((item) => (
                  <p key={item}><Check size={15} /> {item}</p>
                ))}
              </div>
            </div>
          </section>

          <section id="passport" className="public-passport" aria-label="Цифровой паспорт объекта">
            <div className="public-passport-top">
              <div>
                <p className="public-tool-kicker">Пример контроля</p>
                <h2>Цифровой паспорт объекта</h2>
              </div>
              <div className="public-passport-status">
                <Check size={15} />
                Гарантия активна
              </div>
            </div>

            <div className="public-object-card">
              <div>
                <strong>Дом 142 м2, Михайловск</strong>
                <span><MapPin size={14} /> Этап: тёплый контур</span>
              </div>
              <b>68%</b>
            </div>

            <div className="public-passport-line">
              {['Смета', 'Материалы', 'Работы', 'Приёмка', 'Гарантия'].map((item, index) => (
                <div className={index < 3 ? 'done' : ''} key={item}>
                  <i />
                  <span>{item}</span>
                </div>
              ))}
            </div>

            <div className="public-passport-grid">
              <div className="public-passport-photo">
                <img
                  src="https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=700&q=80"
                  alt="Фотоотчёт со строительного объекта"
                />
                <span>Фотоотчёт за сегодня</span>
              </div>
              <div className="public-proof-list">
                <p><Package size={16} /> Материалы приняты: 12 позиций</p>
                <p><FileText size={16} /> Этапы подтверждены: 4</p>
                <p><Clock size={16} /> Отклонений по сроку нет</p>
                <p><QrCode size={16} /> QR-проверка паспорта</p>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section id="services" className="public-section public-services">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Что делаем</p>
          <h2>Берём объект от расчёта до гарантии</h2>
        </div>
        <div className="public-service-row">
          {[
            ['Строительство домов', 'Коробка, тёплый контур, под ключ'],
            ['Ремонт и реконструкция', 'Квартиры, дома, коммерческие помещения'],
            ['Инженерные системы', 'Электрика, вода, отопление, вентиляция'],
            ['Контроль объекта', 'Фото, этапы, материалы, гарантия'],
          ].map(([title, text]) => (
            <article className="public-service" key={title}>
              <Settings size={20} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="trust" className="public-section public-trust">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Почему удобно</p>
          <h2>Сайт связан с рабочим процессом, а не просто собирает телефоны</h2>
          <p>
            Клиент выбирает проект и отправляет его в расчёт, а команда получает
            понятную заявку с контекстом: что выбрано, какой ориентир стоимости и какие файлы приложены.
          </p>
        </div>
        <div className="public-trust-grid">
          {trustItems.map((item) => (
            <article className="public-trust-card" key={item.title}>
              <span><item.icon size={18} /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="objects" className="public-section public-objects">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Объекты</p>
          <h2>Галерея проектов с доказательствами работ</h2>
          <p>
            Сейчас это витрина для сайта. Дальше лучшие фото, цифры и статус объекта
            можно будет публиковать прямо из ERP после разрешения директора.
          </p>
        </div>

        <div className="public-gallery-tabs" aria-label="Фильтр проектов">
          {projectFilters.map((filter) => (
            <button
              className={projectCategory === filter.value ? 'active' : ''}
              type="button"
              key={filter.value}
              onClick={() => chooseProjectCategory(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="public-gallery">
          <article className="public-gallery-feature">
            <div className="public-gallery-image">
              <img src={selectedPhoto} alt={selectedProject.title} />
              <div className="public-gallery-image-badge">
                <Camera size={16} />
                {selectedProject.images.length} фото в объекте
              </div>
            </div>
            <div className="public-gallery-thumbs">
              {selectedProject.images.map((imageUrl, index) => (
                <button
                  className={selectedPhotoIndex === index ? 'active' : ''}
                  type="button"
                  key={imageUrl}
                  onClick={() => setSelectedPhotoIndex(index)}
                  aria-label={`Фото ${index + 1}: ${selectedProject.title}`}
                >
                  <img src={imageUrl} alt="" />
                </button>
              ))}
            </div>
          </article>

          <aside className="public-gallery-info">
            <div className="public-gallery-info-top">
              <div>
                <p className="public-tool-kicker">Выбранный проект</p>
                <h3>{selectedProject.title}</h3>
                <span><MapPin size={14} /> {selectedProject.location} · {selectedProject.year}</span>
              </div>
              <strong>{selectedProject.progress}%</strong>
            </div>

            <div className="public-gallery-progress">
              <i style={{ width: `${selectedProject.progress}%` }} />
            </div>

            <div className="public-gallery-metrics">
              <div><span>Площадь</span><b>{selectedProject.area}</b></div>
              <div><span>Срок</span><b>{selectedProject.term}</b></div>
              <div><span>Бюджет</span><b>{selectedProject.price}</b></div>
              <div><span>Этап</span><b>{selectedProject.stage}</b></div>
            </div>

            <div className="public-gallery-proof">
              <p><Image size={16} /> {selectedProject.result}</p>
              <p><ShieldCheck size={16} /> {selectedProject.passport}</p>
              <p><QrCode size={16} /> Можно открыть цифровой паспорт объекта</p>
            </div>

            <div className="public-gallery-tags">
              {selectedProject.tags.map((tag) => <span key={tag}>{tag}</span>)}
            </div>
          </aside>
        </div>

        <div className="public-project-strip">
          {filteredProjects.map((project) => (
            <button
              className={selectedProject.id === project.id ? 'active' : ''}
              type="button"
              key={project.id}
              onClick={() => chooseProject(project.id)}
            >
              <img src={project.images[0]} alt="" />
              <span>
                <b>{project.title}</b>
                <small>{project.area} · {project.stage}</small>
              </span>
            </button>
          ))}
        </div>

        <div id="work-proof" className="public-work-proof">
          <div className="public-section-head compact">
            <p className="public-eyebrow dark">Наши работы</p>
            <h2>Показываем не только красивый финал, а доказательства выполнения</h2>
            <p>
              Для сайта отдельно выводятся реальные работы и понятные этапы:
              фото, ход работ, материалы, результат и паспорт объекта.
            </p>
          </div>
          <div className="public-work-grid">
            {workProofItems.map((item) => (
              <article className="public-work-card" key={item.title}>
                <img src={item.image} alt={item.title} />
                <div>
                  <span><item.icon size={15} /> {item.metric}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div id="directions" className="public-reference-board">
          <div className="public-section-head compact">
            <p className="public-eyebrow dark">Идеи для проекта</p>
            <h2>15 направлений и готовые проектные карточки</h2>
            <p>
              Это не выполненные объекты, а понятные проект-идеи для заявки. Клиент выбирает
              направление, готовую планировку и отправляет ее в расчет.
            </p>
          </div>
          <div className="public-reference-layout">
            <div className="public-reference-grid" aria-label="Направления проектов">
              {referenceDirections.map((item) => {
                const isActive = selectedReference.id === item.id;
                const projectCards = getReferenceProjectCards(item);
                const directionEstimate = getReferenceProjectEstimate(item, projectCards[0]);
                const mediaCount = getProjectMediaSequence(item, projectCards[0]).length;
                const planCount = getProjectMediaSequence(item, projectCards[0])
                  .filter((media) => media.role === 'plan' || media.kind === 'plan').length;
                return (
                  <button
                    className={isActive ? 'public-reference-card active' : 'public-reference-card'}
                    key={item.id}
                    type="button"
                    onClick={() => chooseReference(item, projectCards[0], 'catalog')}
                    aria-pressed={isActive}
                  >
                    <ProjectConceptThumb direction={item} project={projectCards[0]} />
                    <span className="public-reference-count">{projectCards.length} проекта</span>
                    <span className="public-reference-price">{directionEstimate.fromLabel}</span>
                    <span className="public-reference-media-note">{mediaCount} вида · {planCount} план</span>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                    <div>
                      {item.tags.map((tag) => <span key={tag}>{tag}</span>)}
                    </div>
                    <span className="public-reference-open">Смотреть проекты</span>
                  </button>
                );
              })}
            </div>

	            <section id="projects" className="public-project-catalog" aria-label="Готовые проекты выбранного направления">
	              <div className="public-project-catalog-head">
	                <div>
	                  <p>Открытое направление</p>
	                  <h3>{selectedReference.title}</h3>
	                  <span>{selectedReference.text}</span>
	                </div>
	                <div className="public-project-catalog-badges" aria-label="Состав направления">
	                  <strong>{selectedReferenceProjects.length} проекта</strong>
                    <span>{selectedReferenceMediaOptions.length} вида</span>
                    <span>{selectedReferencePlanCount} план</span>
	                </div>
	              </div>
                <div className="public-project-decision-bar">
                  <div className="public-project-decision-copy">
                    <span>Выбрано для расчета</span>
                    <strong>{selectedReferenceProject?.title || selectedReference.title}</strong>
                    <small>{selectedReferenceProject?.layout || selectedReference.text}</small>
                  </div>
                  <div className="public-project-decision-facts" aria-label="Кратко по выбранному проекту">
                    {selectedReferenceDecisionFacts.map(([label, value]) => (
                      <span key={label}>
                        <small>{label}</small>
                        <b>{value}</b>
                      </span>
                    ))}
                  </div>
                  <div className="public-project-decision-actions">
                    <a
                      className="public-secondary dark public-project-share-link"
                      href={selectedReferenceDeepLink}
                    >
                      Ссылка
                    </a>
                    <button
                      className="public-secondary dark"
                      type="button"
                      onClick={() => chooseReference(selectedReference, selectedReferenceProject, 'calculator')}
                    >
                      К расчету
                    </button>
                    <button
                      className="public-primary"
                      type="button"
                      onClick={() => {
                        chooseReference(selectedReference, selectedReferenceProject);
                        setTimeout(() => scrollTo('request'), 0);
                      }}
                    >
                      Оставить заявку
                    </button>
                  </div>
                </div>
	              <div className="public-project-catalog-main">
	                <div className="public-project-visual-column">
	                  <div className="public-project-thumb-grid" aria-label="Варианты проекта">
	                    {selectedReferenceProjects.map((project) => {
	                      const projectEstimate = getReferenceProjectEstimate(selectedReference, project);
                        const projectMediaSequence = getProjectMediaSequence(selectedReference, project).slice(0, 4);
	                      return (
	                        <button
	                          className={selectedReferenceProject?.title === project.title ? 'active' : ''}
                          type="button"
	                          key={project.code}
	                          onClick={() => chooseReference(selectedReference, project)}
	                        >
	                          <ProjectCardMediaPreview direction={selectedReference} project={project} />
	                          <span className="public-project-card-copy">
	                            <b>{project.code}</b>
	                            <span className="public-project-card-status">{PROJECT_EXAMPLE_STATUS}</span>
	                            <strong>{project.title}</strong>
	                            <small>{project.area} · {project.floors}</small>
	                            <span className="public-project-card-price">Примерная стоимость: {projectEstimate.rangeLabel}</span>
                              <span className="public-project-card-sequence">
                                {projectMediaSequence.map((media) => (
                                  <i key={media.id}>
                                    <b>{media.number}</b>
                                    {media.compactLabel}
                                  </i>
                                ))}
                              </span>
	                            <em>{project.visuals}</em>
	                          </span>
	                        </button>
	                      );
	                    })}
	                  </div>
	                  <div className={isReferenceMirrored ? 'public-project-hero-visual mirrored' : 'public-project-hero-visual'}>
	                    <ProjectConceptVisual
	                      direction={selectedReference}
	                      project={selectedReferenceProject}
	                      media={selectedReferenceMedia}
	                    />
                    {(selectedReferenceMedia?.kind === 'render' || selectedReferenceMedia?.role === 'render') && (
	                      <>
	                        <span className="public-project-ready-ribbon">Проект-идея</span>
	                        <span className="public-project-discount">10%</span>
	                      </>
	                    )}
                      <span className="public-project-media-counter">
                        {selectedReferenceMediaIndex + 1} / {selectedReferenceMediaOptions.length}
                        <b>{selectedReferenceMedia?.label || 'Визуал'}</b>
                      </span>
	                  </div>
                    <div className="public-project-media-head">
                      <span>Состав проекта</span>
                      <strong>{selectedReferenceMediaOptions.length} материала для просмотра</strong>
                    </div>
	                  <div className="public-project-media-strip" aria-label="Медиа проекта">
	                    {selectedReferenceMediaOptions.map((media, index) => (
	                      <button
	                        className={selectedReferenceMedia.id === media.id ? 'active' : ''}
	                        type="button"
	                        key={media.id}
	                        onClick={() => setSelectedReferenceMediaId(media.id)}
	                      >
                          <span className="public-project-media-option-visual">
                            <ProjectConceptVisual
                              direction={selectedReference}
                              project={selectedReferenceProject}
                              media={media}
                            />
                            <b>{index + 1}</b>
                          </span>
	                        <span>{media.label}</span>
	                      </button>
	                    ))}
	                  </div>
                    <div className="public-project-asset-summary" aria-label="Комплектация карточки проекта">
                      {selectedReferenceAssetSummary.map((item) => {
                        const AssetIcon = item.icon;
                        return (
                          <span key={item.label}>
                            <AssetIcon size={15} />
                            <small>{item.label}</small>
                            <b>{item.value}</b>
                          </span>
                        );
                      })}
                    </div>
	                </div>

                <div className="public-project-spec-column">
                  <p className="public-tool-kicker">Каталог готовых проектов</p>
                  <h3>{selectedReferenceProject?.title || selectedReference.title}</h3>
                  <p>{selectedReferenceProject?.layout || selectedReference.text}</p>
                  <div className="public-project-layout-card">
                    <span>Планировочное решение</span>
                    {selectedReferenceLayoutGroups.map((group) => (
                      <div key={group.title}>
                        <strong>{group.title}</strong>
                        <ul>
                          {group.items.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                  <div className="public-project-cost-panel">
                    <span>Примерная стоимость этого проекта</span>
                    <strong>{selectedReferenceEstimate.rangeLabel}</strong>
                    <small>Ориентир для сайта. Точная сумма зависит от замера, проекта, грунтов, материалов и комплектации.</small>
                  </div>
                  <div className="public-generated-object-card">
                    <div className="public-generated-object-head">
                      <span>{selectedReferenceObjectCard.status}</span>
                      <b>{selectedReferenceObjectCard.code}</b>
                    </div>
                    <h4>{selectedReferenceObjectCard.format}</h4>
                    <p>{selectedReferenceObjectCard.summary}</p>
                    <div className="public-generated-object-facts">
                      {selectedReferenceObjectCard.facts.map(([label, value]) => (
                        <span key={label}>
                          <small>{label}</small>
                          <strong>{value}</strong>
                        </span>
                      ))}
                    </div>
                    <div className="public-generated-object-flow">
                      {selectedReferenceObjectCard.stages.map((stage, index) => (
                        <span key={stage}>
                          <b>{index + 1}</b>
                          {stage}
                        </span>
                      ))}
                    </div>
                    <div className="public-generated-object-output">
                      {selectedReferenceObjectCard.deliverables.map((item) => (
                        <span key={item}>
                          <Check size={14} />
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                  <dl className="public-project-spec-list">
                    {selectedReferenceSpecs.map(([label, value]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <button
                    className="public-project-outline"
                    type="button"
                    aria-pressed={isReferenceMirrored}
                    onClick={() => setIsReferenceMirrored((value) => !value)}
                  >
                    {isReferenceMirrored ? 'Вернуть обычный вариант' : 'Показать зеркальный вариант'}
                  </button>
                  <button className="public-project-editor" type="button" onClick={requestLayoutEditor}>
                    Редактор планировки
                  </button>
                  <button className="public-project-outline" type="button" onClick={chooseSimilarReferenceProject}>
                    Похожие по виду ({Math.max(3, selectedReferenceProjects.length)})
                  </button>
                  <button
                    className="public-primary public-reference-cta"
                    type="button"
                    onClick={() => chooseReference(selectedReference, selectedReferenceProject, 'calculator')}
                  >
                    Рассчитать такой проект
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>

      <section id="process" className="public-section public-process">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Как ведём объект</p>
          <h2>Заявка сразу превращается в управляемую стройку</h2>
        </div>
        <div className="public-process-grid">
          {[
            ['1', 'Заявка', 'Клиент оставляет расчёт и контакты'],
            ['2', 'Смета', 'Команда уточняет объём и стоимость'],
            ['3', 'Стройка', 'Работы, материалы и фото ведутся в ERP'],
            ['4', 'Паспорт и гарантия', 'Клиент получает историю объекта'],
          ].map(([num, title, text]) => (
            <article className="public-process-item" key={title}>
              <b>{num}</b>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="faq" className="public-section public-faq">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Частые вопросы</p>
          <h2>Чтобы перед заявкой было понятно, что именно считается</h2>
        </div>
        <div className="public-faq-grid">
          {faqItems.map((item) => (
            <article className="public-faq-card" key={item.question}>
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="suppliers" className="public-section public-suppliers">
        <div className="public-supplier-copy">
          <p className="public-eyebrow dark">Партнёрам</p>
          <h2>Поставщик, мастер, бригада или субподрядчик сначала оставляет заявку на проверку</h2>
          <p>
            Мы не создаём активный доступ с публичного сайта автоматически. Заявка попадает
            в CRM, директор или ответственный сотрудник проверяет данные и только потом
            выдаёт кабинет, договор или приглашение.
          </p>
          <div className="public-partner-types">
            {partnerTypes.map((item) => (
              <button
                key={item.value}
                type="button"
                className={partnerLead.type === item.value ? 'active' : ''}
                onClick={() => setPartnerLead({ ...partnerLead, type: item.value })}
              >
                <span><item.icon size={15} /> {item.label}</span>
                <small>{item.note}</small>
              </button>
            ))}
          </div>
        </div>
        <form className="public-partner-form" onSubmit={submitPartnerLead}>
          <label className="public-honeypot" aria-hidden="true">
            Сайт
            <input
              value={partnerWebsite}
              onChange={(event) => setPartnerWebsite(event.target.value)}
              autoComplete="off"
              tabIndex={-1}
            />
          </label>
          <label>
            Компания или ФИО
            <input value={partnerLead.name} onChange={(event) => setPartnerLead({ ...partnerLead, name: event.target.value })} placeholder="Название или имя" />
          </label>
          <label>
            Телефон
            <input value={partnerLead.phone} onChange={(event) => setPartnerLead({ ...partnerLead, phone: event.target.value })} placeholder="+7" required />
          </label>
          <label>
            Что предлагаете
            <textarea value={partnerLead.comment} onChange={(event) => setPartnerLead({ ...partnerLead, comment: event.target.value })} placeholder="Материалы, виды работ, регион, опыт" />
          </label>
          <label className="public-consent">
            <input
              type="checkbox"
              checked={partnerConsent}
              onChange={(event) => setPartnerConsent(event.target.checked)}
            />
            <span>
              Даю согласие на обработку данных для проверки заявки и понимаю,
              что кабинет не создаётся автоматически.
            </span>
          </label>
          <button className="public-primary" type="submit" disabled={partnerSending || !partnerConsent}>
            {partnerSending ? 'Отправляем...' : 'Отправить на проверку'}
          </button>
          <button className="public-secondary dark" type="button" onClick={onLogin}>Уже есть доступ</button>
          {partnerSent && <p className="public-form-success">Заявка отправлена в CRM на проверку.</p>}
          {partnerError && <p className="public-form-error">{partnerError}</p>}
        </form>
      </section>

      <section id="request" className="public-section public-request">
        <div>
          <p className="public-eyebrow dark">Точная смета</p>
          <h2>Оставьте заявку на расчёт</h2>
          <p>
            Мы сохраним параметры расчёта и дальше привяжем эту форму к CRM,
            чтобы заявка не терялась.
          </p>
        </div>
        <form className="public-request-form" onSubmit={submitLead}>
          <div className="public-request-selected">
            <span>В заявку попадёт</span>
            <strong>{selectedLeadProject.projectTitle}</strong>
            <small>
              {selectedLeadProject.directionTitle} · {selectedLeadProject.projectCode || 'проект'} · {selectedLeadProject.estimateRange}
            </small>
            <button type="button" onClick={() => scrollTo('projects')}>Изменить проект</button>
          </div>
          <label className="public-honeypot" aria-hidden="true">
            Сайт
            <input
              value={leadWebsite}
              onChange={(event) => setLeadWebsite(event.target.value)}
              autoComplete="off"
              tabIndex={-1}
            />
          </label>
          <label>
            Имя
            <input value={lead.name} onChange={(event) => setLead({ ...lead, name: event.target.value })} placeholder="Как к вам обращаться" />
          </label>
          <label>
            Телефон
            <input value={lead.phone} onChange={(event) => setLead({ ...lead, phone: event.target.value })} placeholder="+7" required />
          </label>
          <label>
            Комментарий
            <textarea value={lead.comment} onChange={(event) => setLead({ ...lead, comment: event.target.value })} placeholder="Адрес, сроки, что нужно построить" />
          </label>
          <label className="public-consent">
            <input
              type="checkbox"
              checked={leadConsent}
              onChange={(event) => setLeadConsent(event.target.checked)}
            />
            <span>
              Даю согласие на обработку имени, телефона, комментария и параметров расчёта
              для ответа на заявку. С{' '}
              <button
                className="public-consent-link"
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  scrollTo('privacy');
                }}
              >
                политикой обработки персональных данных
              </button>{' '}
              ознакомлен.
            </span>
          </label>
          <button className="public-primary" type="submit" disabled={leadSending || !leadConsent}>
            {leadSending ? 'Отправляем...' : 'Отправить заявку'}
          </button>
          {sent && <p className="public-form-success">Заявка отправлена в CRM. Менеджер или директор увидит её в разделе заявок.</p>}
          {leadError && <p className="public-form-error">{leadError}</p>}
        </form>
      </section>

      <section id="privacy" className="public-section public-legal">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Юридическая информация</p>
          <h2>Политика обработки персональных данных</h2>
          <p>
            Заявки с сайта передаются в CRM только для обратной связи, расчёта и подготовки предложения.
            Полные реквизиты исполнителя фиксируются в договоре и коммерческом предложении.
          </p>
        </div>
        <div className="public-legal-grid">
          <article>
            <h3>Что обрабатываем</h3>
            <p>
              Имя, телефон, комментарий к заявке, параметры предварительного расчёта,
              технические данные отправки формы и источник заявки.
            </p>
          </article>
          <article>
            <h3>Зачем</h3>
            <p>
              Чтобы ответить на обращение, подготовить расчёт, связать заявку с CRM
              и не потерять историю общения с клиентом.
            </p>
          </article>
          <article>
            <h3>Согласие</h3>
            <p>
              Заявка отправляется только после отметки согласия. Отозвать согласие можно
              через контакт оператора, указанный в этом разделе.
            </p>
          </article>
          <article>
            <h3>Реклама</h3>
            <p>
              Рекламные сообщения и массовые рассылки не отправляются без отдельного
              согласия пользователя.
            </p>
          </article>
        </div>
        <div className="public-legal-note">
          <strong>Не является публичной офертой.</strong>
          Предварительные расчёты на сайте носят информационный характер.
          Итоговая цена, сроки, состав работ и материалов фиксируются в договоре и смете.
        </div>
        <div className="public-requisites">
          <span>Оператор: {PUBLIC_SITE_OPERATOR.name}</span>
          <span>Сайт: {PUBLIC_SITE_OPERATOR.site}</span>
          <span>По персональным данным: {PUBLIC_SITE_OPERATOR.privacyEmail}</span>
          <span>Заявки: {PUBLIC_SITE_OPERATOR.leadEmail}</span>
          <span><a href="/project-catalog.html">Каталог проектов</a></span>
          <span><a href="/privacy.html">Политика</a></span>
          <span><a href="/terms.html">Условия</a></span>
          <span><a href="/contacts.html">Контакты</a></span>
        </div>
      </section>
    </main>
  );
};

export default PublicSitePage;
