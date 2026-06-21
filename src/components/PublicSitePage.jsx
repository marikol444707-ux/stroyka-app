import React, { useEffect, useMemo, useState } from 'react';
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

const PUBLIC_CONSENT_VERSION = 'public-site-pd-v1-2026-06-21';
const PUBLIC_SITE_OPERATOR = {
  name: 'СтройКа',
  site: 'stroyka26.pro',
  privacyEmail: 'privacy@stroyka26.pro',
  leadEmail: 'info@stroyka26.pro',
};

const workTypes = [
  { value: 'house', label: 'Дом', short: 'Строительство', description: 'Коробка, тёплый контур, инженерия, под ключ' },
  { value: 'repair', label: 'Ремонт', short: 'Отделка', description: 'Квартира, дом, офис, состояние и набор работ' },
  { value: 'commerce', label: 'Коммерция', short: 'Бизнес-объект', description: 'Офис, магазин, кафе, салон, запуск к дате' },
  { value: 'reconstruction', label: 'Реконструкция', short: 'Переделка', description: 'Демонтаж, усиление, кровля, инженерия' },
];

const houseWallTypes = [
  { value: 'gasblock', label: 'Газоблок', multiplier: 1 },
  { value: 'brick', label: 'Кирпич', multiplier: 1.18 },
  { value: 'monolith', label: 'Монолит', multiplier: 1.28 },
  { value: 'frame', label: 'Каркас', multiplier: 0.88 },
];

const housePackages = [
  { value: 'box', label: 'Коробка', rate: 38000 },
  { value: 'warm', label: 'Тёплый контур', rate: 52000 },
  { value: 'engineering', label: 'Инженерия', rate: 25000 },
  { value: 'turnkey', label: 'Под ключ', rate: 72000 },
];

const stages = [
  { value: 'idea', label: 'Есть идея' },
  { value: 'project', label: 'Есть проект' },
  { value: 'estimate', label: 'Есть смета' },
  { value: 'start', label: 'Нужно начать быстро' },
];

const repairObjects = [
  { value: 'apartment', label: 'Квартира', multiplier: 1 },
  { value: 'privateHouse', label: 'Дом', multiplier: 1.08 },
  { value: 'office', label: 'Офис', multiplier: 0.94 },
  { value: 'retail', label: 'Помещение', multiplier: 1.05 },
];

const repairConditions = [
  { value: 'new', label: 'Новостройка', multiplier: 1 },
  { value: 'secondary', label: 'Вторичка', multiplier: 1.12 },
  { value: 'old', label: 'Старый фонд', multiplier: 1.25 },
  { value: 'afterDemolition', label: 'После демонтажа', multiplier: 0.95 },
];

const repairLevels = [
  { value: 'cosmetic', label: 'Косметический', rate: 18000 },
  { value: 'capital', label: 'Капитальный', rate: 32000 },
  { value: 'designer', label: 'Дизайнерский', rate: 48000 },
  { value: 'commercial', label: 'Коммерческий ремонт', rate: 36000 },
];

const materialModes = [
  { value: 'client', label: 'Материалы клиента', multiplier: 0.72 },
  { value: 'partial', label: 'Частично через нас', multiplier: 0.88 },
  { value: 'company', label: 'Материалы через СтройКа', multiplier: 1 },
];

const commerceTypes = [
  { value: 'office', label: 'Офис', multiplier: 1 },
  { value: 'shop', label: 'Магазин', multiplier: 1.08 },
  { value: 'cafe', label: 'Кафе', multiplier: 1.22 },
  { value: 'warehouse', label: 'Склад', multiplier: 0.78 },
  { value: 'salon', label: 'Салон', multiplier: 1.12 },
  { value: 'medical', label: 'Медкабинет', multiplier: 1.32 },
];

const commerceLevels = [
  { value: 'base', label: 'Базовая подготовка', rate: 26000 },
  { value: 'standard', label: 'Рабочий формат', rate: 38000 },
  { value: 'opening', label: 'Под открытие', rate: 52000 },
  { value: 'special', label: 'Сложная инженерия', rate: 64000 },
];

const reconstructionScopes = [
  { value: 'house', label: 'Дом целиком', rate: 42000 },
  { value: 'extension', label: 'Пристройка', rate: 36000 },
  { value: 'roof', label: 'Кровля', rate: 19000 },
  { value: 'facade', label: 'Фасад', rate: 21000 },
  { value: 'inside', label: 'Внутри помещения', rate: 30000 },
];

const getOptionLabel = (options, value) => (
  options.find((item) => item.value === value)?.label || options[0]?.label || ''
);

const projectFilters = [
  { value: 'all', label: 'Все' },
  { value: 'house', label: 'Дома' },
  { value: 'repair', label: 'Ремонт' },
  { value: 'commerce', label: 'Коммерция' },
  { value: 'reconstruction', label: 'Реконструкция' },
];

const publicProjects = [
  {
    id: 'mihailovsk-house',
    category: 'house',
    title: 'Дом в Михайловске',
    location: 'Михайловск',
    area: '142 м2',
    year: '2026',
    stage: 'Тёплый контур',
    progress: 68,
    price: 'от 7,6 млн ₽',
    term: '5 месяцев',
    passport: 'Фотоотчёты, материалы, скрытые работы',
    result: 'Коробка, кровля, окна, инженерная подготовка',
    tags: ['Дом', 'Тёплый контур', 'Паспорт объекта'],
    images: [
      'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=900&q=82',
    ],
  },
  {
    id: 'office-repair',
    category: 'commerce',
    title: 'Ремонт офиса',
    location: 'Ставрополь',
    area: '310 м2',
    year: '2026',
    stage: 'Финишная приёмка',
    progress: 92,
    price: 'от 5,2 млн ₽',
    term: '62 дня',
    passport: 'Акты, фото, инженерия, документы',
    result: 'Офис под работу команды и приём клиентов',
    tags: ['Офис', 'Инженерия', 'Сроки'],
    images: [
      'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1497215842964-222b430dc094?auto=format&fit=crop&w=900&q=82',
    ],
  },
  {
    id: 'cottage-repair',
    category: 'repair',
    title: 'Коттеджный ремонт',
    location: 'Невинномысск',
    area: '188 м2',
    year: '2025',
    stage: 'Инженерия',
    progress: 45,
    price: 'от 4,1 млн ₽',
    term: '4 месяца',
    passport: 'Электрика, сантехника, фото скрытых работ',
    result: 'Капитальный ремонт с заменой инженерии',
    tags: ['Ремонт', 'Дом', 'Скрытые работы'],
    images: [
      'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1600607687644-c7171b42498b?auto=format&fit=crop&w=900&q=82',
    ],
  },
  {
    id: 'shop-fitout',
    category: 'commerce',
    title: 'Помещение под магазин',
    location: 'Пятигорск',
    area: '96 м2',
    year: '2025',
    stage: 'Сдано',
    progress: 100,
    price: 'от 2,4 млн ₽',
    term: '38 дней',
    passport: 'Сроки, отделка, документы для открытия',
    result: 'Торговый зал, подсобные зоны, освещение',
    tags: ['Коммерция', 'Под открытие', 'Гарантия'],
    images: [
      'https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1600210491892-03d54c0aaf87?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1600607688969-a5bfcd646154?auto=format&fit=crop&w=900&q=82',
    ],
  },
];

const formatMoney = (value) => new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
}).format(value);

const normalizeSiteProject = (project) => {
  const images = Array.isArray(project.images) && project.images.length
    ? project.images
    : (Array.isArray(project.publicImages) ? project.publicImages : []);
  return {
    id: String(project.id || project.projectId || project.title || project.projectName || Math.random()),
    category: project.category || project.publicCategory || 'house',
    title: project.title || project.publicTitle || project.projectName || 'Объект СтройКа',
    location: project.location || project.publicLocation || '',
    area: project.area || project.publicArea || '',
    year: project.year || project.publicYear || '',
    stage: project.stage || project.publicStage || '',
    progress: Math.max(0, Math.min(100, Number(project.progress ?? project.publicProgress ?? 0))),
    price: project.price || project.publicPriceLabel || '',
    term: project.term || project.publicTerm || '',
    passport: project.passport || project.publicPassport || 'Фото, документы и паспорт объекта',
    result: project.result || project.publicResult || project.publicSummary || '',
    tags: Array.isArray(project.tags) ? project.tags : (Array.isArray(project.publicTags) ? project.publicTags : []),
    images: images.length ? images : publicProjects[0].images,
    isLive: Boolean(project.isLive || project.publicIsLive),
    aiStatus: project.aiStatus || project.publicAiStatus || '',
  };
};

const PublicSitePage = ({ onLogin }) => {
  const [calc, setCalc] = useState({
    type: 'house',
    area: 140,
    floors: 2,
    wallType: 'gasblock',
    package: 'turnkey',
    stage: 'project',
    foundation: true,
    communications: true,
    deadline: 'normal',
    files: 0,
    repairObject: 'apartment',
    rooms: 3,
    bathrooms: 1,
    ceilingHeight: 2.7,
    repairCondition: 'new',
    repairLevel: 'capital',
    demolition: false,
    electric: true,
    plumbing: true,
    walls: true,
    floorsWork: true,
    ceiling: true,
    tiles: true,
    materialMode: 'partial',
    trash: true,
    commerceType: 'office',
    commerceLevel: 'opening',
    commerceCondition: 'shell',
    ventilation: true,
    fireSafety: false,
    powerEquipment: true,
    designProject: false,
    nightWork: false,
    reconstructionScope: 'house',
    keepsStructure: true,
    reinforcement: true,
    foundationTouch: false,
    roofTouch: true,
    engineeringNew: true,
    inspectionNeeded: true,
  });
  const [lead, setLead] = useState({ name: '', phone: '', comment: '' });
  const [leadConsent, setLeadConsent] = useState(false);
  const [leadWebsite, setLeadWebsite] = useState('');
  const [sent, setSent] = useState(false);
  const [leadSending, setLeadSending] = useState(false);
  const [leadError, setLeadError] = useState('');
  const [siteProjects, setSiteProjects] = useState(publicProjects);
  const [projectCategory, setProjectCategory] = useState('all');
  const [selectedProjectId, setSelectedProjectId] = useState(publicProjects[0].id);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
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
    loadSiteProjects();
    return () => { cancelled = true; };
  }, []);

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
      const floorMultiplier = Number(calc.floors) > 1 ? 1.06 : 1;
      const coreWorks = area * housePackage.rate * wall.multiplier * floorMultiplier;
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
      const roomComplexity = 1 + Math.max(0, roomsCount - 2) * 0.025;
      const base = area * level.rate * object.multiplier * condition.multiplier * roomComplexity;
      const roomWorks = roomsCount * 26000 + Math.max(0, roomsCount - 2) * 18000;
      const demolition = calc.demolition ? area * 2400 : 0;
      const engineering = (calc.electric ? area * 4300 : 0) + (calc.plumbing ? Number(calc.bathrooms || 1) * 95000 : 0);
      const surfaces = (calc.walls ? area * 2200 : 0) + (calc.floorsWork ? area * 2600 : 0) + (calc.ceiling ? area * 1700 : 0) + (calc.tiles ? Number(calc.bathrooms || 1) * 120000 : 0);
      const materialsPart = base * 0.32 * materials.multiplier;
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
      const conditionMultiplier = calc.commerceCondition === 'old' ? 1.2 : calc.commerceCondition === 'ready' ? 0.82 : 1;
      const premisesComplexity = 1 + Math.max(0, roomsCount - 3) * 0.035;
      const fitout = area * level.rate * object.multiplier * conditionMultiplier * premisesComplexity;
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
      const base = area * scope.rate;
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
  }, [calc]);

  const updateCalc = (field, value) => {
    setCalc((current) => ({ ...current, [field]: value }));
  };

  const filteredProjects = useMemo(() => (
    projectCategory === 'all'
      ? siteProjects
      : siteProjects.filter((project) => project.category === projectCategory)
  ), [projectCategory, siteProjects]);

  const selectedProject = filteredProjects.find((project) => project.id === selectedProjectId) || filteredProjects[0] || siteProjects[0] || publicProjects[0];
  const selectedPhoto = selectedProject.images[selectedPhotoIndex] || selectedProject.images[0];

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

  const scrollTo = (id) => {
    if (typeof document === 'undefined') return;
    const element = document.getElementById(id);
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

  return (
    <main className="public-site">
      <section className="public-hero">
        <header className="public-nav">
          <button className="public-brand" type="button" onClick={() => scrollTo('top')}>
            <span>Строй</span><strong>Ка</strong>
          </button>
          <nav className="public-nav-links" aria-label="Навигация по сайту">
            <button type="button" onClick={() => scrollTo('services')}>Услуги</button>
            <button type="button" onClick={() => scrollTo('calculator')}>Калькулятор</button>
            <button type="button" onClick={() => scrollTo('objects')}>Объекты</button>
            <button type="button" onClick={() => scrollTo('passport')}>Контроль</button>
            <button type="button" onClick={() => scrollTo('suppliers')}>Поставщикам</button>
            <button type="button" onClick={() => scrollTo('privacy')}>Политика</button>
          </nav>
          <button className="public-login" type="button" onClick={onLogin}>Вход в ERP</button>
        </header>

        <div id="top" className="public-hero-content">
          <div className="public-hero-copy">
            <p className="public-eyebrow">Строительная компания с цифровым контролем</p>
            <h1>Строим с понятной сметой и цифровым паспортом объекта</h1>
            <p className="public-lead">
              Расчёт стоимости, фотоотчёты, этапы работ, материалы, документы и гарантия
              ведутся в одной системе.
            </p>
            <div className="public-hero-actions">
              <button className="public-primary" type="button" onClick={() => scrollTo('calculator')}>
                Рассчитать стоимость
                <ChevronRight size={18} />
              </button>
              <button className="public-secondary" type="button" onClick={() => scrollTo('passport')}>
                Посмотреть пример паспорта
              </button>
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
                <p><FileText size={16} /> Документы подписаны: 4</p>
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
            ['Контроль объекта', 'Фото, акты, материалы, гарантия'],
          ].map(([title, text]) => (
            <article className="public-service" key={title}>
              <Settings size={20} />
              <h3>{title}</h3>
              <p>{text}</p>
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
      </section>

      <section className="public-section public-process">
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

      <section id="suppliers" className="public-section public-suppliers">
        <div className="public-supplier-copy">
          <p className="public-eyebrow dark">Поставщикам</p>
          <h2>Заявки на материалы будут приходить через единый кабинет</h2>
          <p>
            Поставщик сможет видеть потребности строительных компаний, отправлять КП,
            счета, документы и историю поставок в одном окне.
          </p>
        </div>
        <button className="public-secondary dark" type="button" onClick={onLogin}>Войти в кабинет</button>
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
        </div>
      </section>
    </main>
  );
};

export default PublicSitePage;
