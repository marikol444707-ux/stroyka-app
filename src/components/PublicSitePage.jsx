import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BriefcaseBusiness,
  Building2,
  Calculator,
  Camera,
  Check,
  ChevronRight,
  Clock,
  ClipboardCheck,
  FileText,
  Hammer,
  Handshake,
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

const workProofItems = [
  {
    title: 'Скрытые работы',
    text: 'Фото до закрытия, исполнитель и привязка к этапу работ.',
    image: 'https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=900&q=82',
    metric: 'Этап + фото',
    icon: ClipboardCheck,
  },
  {
    title: 'Материалы на объекте',
    text: 'Поставки, остатки и движение материалов под внутренним контролем.',
    image: 'https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=900&q=82',
    metric: 'Склад',
    icon: Package,
  },
  {
    title: 'Ежедневный ход работ',
    text: 'Работы мастеров, объёмы, замечания и подтверждения.',
    image: 'https://images.unsplash.com/photo-1581094271901-8022df4466f9?auto=format&fit=crop&w=900&q=82',
    metric: 'Журнал работ',
    icon: Hammer,
  },
];

const referenceDirections = [
  {
    id: 'one-floor-modern',
    title: 'Одноэтажный современный дом',
    text: 'Компактные дома 90-160 м2 с террасой, светлой гостиной и понятной планировкой.',
    image: '/site-assets/projects/h1-01/facade.png',
    tags: ['1 этаж', 'современный фасад', 'терраса'],
    calcPatch: { type: 'house', floors: 1, wallType: 'gasblock', package: 'turnkey', area: 120, rooms: 4 },
    examples: [
      'Дом 90-110 м2 с плоской кровлей и террасой',
      'Дом 120-140 м2 с панорамным остеклением гостиной',
      'L-образный дом с закрытым внутренним двориком',
      'Дом с навесом для автомобиля вместо гаража',
      'Минималистичный дом с фасадом из штукатурки и дерева',
      'Дом с большой кухней-гостиной и выходом на участок',
      'Компактный дом для молодой семьи на узком участке',
      'Дом с мастер-спальней и двумя детскими',
      'Дом с отдельной котельной и хозяйственным входом',
      'Дом с летней кухней/террасой как главным сценарием',
    ],
  },
  {
    id: 'one-floor-brick',
    title: 'Одноэтажный дом из кирпича',
    text: 'Классические капитальные дома для постоянного проживания.',
    image: '/site-assets/projects/b1-01/facade.png',
    tags: ['кирпич', 'классика', 'надежность'],
    calcPatch: { type: 'house', floors: 1, wallType: 'brick', package: 'turnkey', area: 135, rooms: 4 },
    examples: [
      'Классический кирпичный дом с вальмовой кровлей',
      'Дом из светлого кирпича с темной кровлей',
      'Дом из темного кирпича с белыми откосами',
      'Кирпичный дом с высоким цоколем',
      'Дом с крыльцом и аккуратной входной группой',
      'Дом с эркером в гостиной',
      'Кирпичный дом с пристроенной террасой',
      'Дом с теплой кровлей и утепленным чердаком',
      'Дом с фасадным декором без перегруза',
      'Кирпичный дом для постоянного проживания',
    ],
  },
  {
    id: 'family-cottage',
    title: 'Семейный коттедж',
    text: 'Загородные дома с общей семейной зоной, террасой и удобной логикой жизни.',
    image: 'https://images.unsplash.com/photo-1600573472550-8090b5e0745e?auto=format&fit=crop&w=900&q=82',
    tags: ['коттедж', 'семья', 'двор'],
    calcPatch: { type: 'house', floors: 1, wallType: 'gasblock', package: 'turnkey', area: 155, rooms: 5 },
    examples: [
      'Коттедж с большой кухней-гостиной',
      'Коттедж с террасой для семьи и гостей',
      'Коттедж с детскими комнатами на солнечной стороне',
      'Коттедж с отдельной гостевой комнатой',
      'Коттедж с каминной зоной',
      'Коттедж с навесом и хозяйственным блоком',
      'Коттедж со вторым светом в гостиной',
      'Коттедж с выходом из кухни на двор',
      'Коттедж с большой прихожей и гардеробной',
      'Коттедж с готовым сценарием "заехать и жить"',
    ],
  },
  {
    id: 'two-floor-modern',
    title: 'Двухэтажный современный дом',
    text: 'Современная архитектура, больше площади на компактном участке.',
    image: 'https://images.unsplash.com/photo-1600047509358-9dc75507daeb?auto=format&fit=crop&w=900&q=82',
    tags: ['2 этажа', 'современный', 'панорама'],
    calcPatch: { type: 'house', floors: 2, wallType: 'gasblock', package: 'turnkey', area: 180, rooms: 5 },
    examples: [
      'Кубический дом с плоской кровлей',
      'Дом с балконом и террасой на втором этаже',
      'Дом со вторым светом и панорамными окнами',
      'Дом на узком участке с вытянутой планировкой',
      'Дом с комбинированным фасадом: штукатурка, дерево, камень',
      'Дом с приватной спальней на втором этаже',
      'Дом с кабинетом на первом этаже',
      'Дом с выходом гостиной на задний двор',
      'Дом с минималистичной входной группой',
      'Дом с современной вечерней подсветкой фасада',
    ],
  },
  {
    id: 'two-floor-brick',
    title: 'Двухэтажный дом из кирпича',
    text: 'Капитальные дома с классическим фасадом и долгим сроком службы.',
    image: 'https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=900&q=82',
    tags: ['кирпич', '2 этажа', 'статус'],
    calcPatch: { type: 'house', floors: 2, wallType: 'brick', package: 'turnkey', area: 205, rooms: 6 },
    examples: [
      'Классический кирпичный дом с симметричным фасадом',
      'Дом из клинкерного кирпича',
      'Дом с кирпичным фасадом и каменным цоколем',
      'Дом с гаражом в общем объеме',
      'Дом с колоннами/крыльцом без лишнего декора',
      'Дом с мансардным вторым этажом',
      'Дом с эркером и большой гостиной',
      'Дом с теплой кровлей и полноценным вторым этажом',
      'Дом с кирпичным забором и единой входной группой',
      'Дом в классическом стиле для постоянного проживания',
    ],
  },
  {
    id: 'garage-house',
    title: 'Двухэтажный дом с гаражом',
    text: 'Дом, гараж и хозяйственные зоны в одной удобной схеме.',
    image: 'https://images.unsplash.com/photo-1600607688969-a5bfcd646154?auto=format&fit=crop&w=900&q=82',
    tags: ['гараж', 'хозблок', 'семья'],
    calcPatch: { type: 'house', floors: 2, wallType: 'gasblock', package: 'turnkey', area: 220, rooms: 5 },
    examples: [
      'Дом с встроенным гаражом на одну машину',
      'Дом с гаражом на две машины',
      'Дом с гаражом и мастерской',
      'Дом с гаражом и кладовой для инструмента',
      'Дом с жилой комнатой над гаражом',
      'Дом с навесом перед гаражом',
      'Дом с боковым въездом в гараж',
      'Дом с отдельным входом из гаража в дом',
      'Дом с хозяйственным блоком рядом с гаражом',
      'Дом с гаражом, котельной и прачечной в одном блоке',
    ],
  },
  {
    id: 'townhouse',
    title: 'Компактный таунхаус',
    text: 'Секции для городской жизни, инвестиций или семейного формата.',
    image: 'https://images.unsplash.com/photo-1600566752229-250ed79470f8?auto=format&fit=crop&w=900&q=82',
    tags: ['таунхаус', 'секции', 'компактно'],
    calcPatch: { type: 'house', floors: 2, wallType: 'brick', package: 'warm', area: 115, rooms: 4 },
    examples: [
      'Таунхаус на 2 секции',
      'Таунхаус на 4 секции',
      'Угловая секция с увеличенным участком',
      'Секция с индивидуальным парковочным местом',
      'Секция с маленьким задним двориком',
      'Таунхаус под сдачу в аренду',
      'Таунхаус для молодой семьи',
      'Таунхаус с общей архитектурной линией фасада',
      'Таунхаус с отдельными входными группами',
      'Таунхаус с отделкой white box',
    ],
  },
  {
    id: 'cottage-reconstruction',
    title: 'Реконструкция коттеджа',
    text: 'Обновление старого дома: фасад, кровля, инженерия, планировка.',
    image: 'https://images.unsplash.com/photo-1581094288338-2314dddb7ece?auto=format&fit=crop&w=900&q=82',
    tags: ['реконструкция', 'до/после', 'инженерия'],
    calcPatch: { type: 'reconstruction', reconstructionScope: 'house', area: 170, rooms: 5, roofTouch: true, engineeringNew: true },
    examples: [
      'Обновление старого кирпичного фасада',
      'Усиление и замена кровли',
      'Пристройка террасы к существующему дому',
      'Переделка холодного чердака в жилую мансарду',
      'Замена окон и утепление откосов',
      'Утепление фасада с новой финишной отделкой',
      'Перепланировка первого этажа под кухню-гостиную',
      'Замена инженерных коммуникаций',
      'Обновление входной группы и крыльца',
      'Комплексная реконструкция до/после',
    ],
  },
  {
    id: 'facade',
    title: 'Ремонт и отделка фасада',
    text: 'Фасад, утепление, декоративная отделка и аккуратный внешний вид дома.',
    image: 'https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=900&q=82',
    tags: ['фасад', 'утепление', 'отделка'],
    calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 180, rooms: 1, roofTouch: false, engineeringNew: false },
    examples: [
      'Декоративная штукатурка фасада',
      'Утепление фасада под штукатурку',
      'Вентилируемый фасад',
      'Фасад из клинкерной плитки',
      'Отделка цоколя камнем',
      'Покраска фасада с восстановлением трещин',
      'Обновление откосов, отливов и водостока',
      'Комбинированный фасад: штукатурка + дерево',
      'Фасад с наружной подсветкой',
      'Ремонт фасада после усадки/трещин',
    ],
  },
  {
    id: 'roof',
    title: 'Ремонт кровли',
    text: 'Замена покрытия, утепление, водосток, примыкания и безопасность.',
    image: 'https://images.unsplash.com/photo-1541976590-713941681591?auto=format&fit=crop&w=900&q=82',
    tags: ['кровля', 'утепление', 'водосток'],
    calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 150, rooms: 1, roofTouch: true, engineeringNew: false },
    examples: [
      'Замена старого покрытия на металлочерепицу',
      'Замена покрытия на мягкую кровлю',
      'Ремонт протечек и примыканий',
      'Усиление стропильной системы',
      'Утепление кровли и чердака',
      'Монтаж водосточной системы',
      'Установка снегозадержателей',
      'Монтаж мансардных окон',
      'Ремонт карнизов и подшивы',
      'Полная кровля под ключ с демонтажом старой',
    ],
  },
  {
    id: 'apartment-repair',
    title: 'Ремонт квартиры',
    text: 'Новостройка, вторичка, капитальный или быстрый ремонт под задачу.',
    image: 'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=900&q=82',
    tags: ['квартира', 'ремонт', 'чистовая'],
    calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 72, rooms: 3, bathrooms: 1 },
    examples: [
      'Ремонт квартиры в новостройке',
      'Ремонт квартиры под сдачу',
      'Капитальный ремонт старой квартиры',
      'Ремонт студии',
      'Ремонт однокомнатной квартиры',
      'Ремонт двухкомнатной квартиры',
      'Ремонт квартиры с перепланировкой',
      'Ремонт квартиры с заменой электрики',
      'Ремонт квартиры с выравниванием стен и полов',
      'Чистовая отделка после черновых работ',
    ],
  },
  {
    id: 'private-house-finish',
    title: 'Отделка частного дома',
    text: 'Дом после коробки: черновая, чистовая отделка и подготовка к проживанию.',
    image: 'https://images.unsplash.com/photo-1600566753151-384129cf4e3e?auto=format&fit=crop&w=900&q=82',
    tags: ['частный дом', 'отделка', 'заехать жить'],
    calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 150, rooms: 5, bathrooms: 2 },
    examples: [
      'Отделка дома после коробки',
      'Черновая отделка дома',
      'Чистовая отделка дома',
      'Монтаж гипсокартона и перегородок',
      'Устройство теплых полов',
      'Укладка плитки и напольных покрытий',
      'Монтаж лестницы и ограждений',
      'Отделка гостиной и кухни',
      'Отделка спален и санузлов',
      'Комплексная отделка заехать и жить',
    ],
  },
  {
    id: 'bathroom',
    title: 'Ремонт ванной комнаты',
    text: 'Плитка, сантехника, гидроизоляция и аккуратные узлы.',
    image: 'https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=900&q=82',
    tags: ['санузел', 'плитка', 'сантехника'],
    calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 8, rooms: 1, bathrooms: 1, tiles: true },
    examples: [
      'Маленькая ванная в квартире',
      'Совмещенный санузел',
      'Гостевой санузел',
      'Ванная с душевой зоной',
      'Ванная с полноценной чашей',
      'Гидроизоляция и подготовка основания',
      'Укладка керамогранита крупного формата',
      'Скрытые люки и ревизии',
      'Теплый пол и полотенцесушитель',
      'Полный санузел под ключ',
    ],
  },
  {
    id: 'kitchen-living',
    title: 'Ремонт кухни и гостиной',
    text: 'Главная семейная зона: свет, электрика, полы, стены и финишная отделка.',
    image: 'https://images.unsplash.com/photo-1600210491892-03d54c0aaf87?auto=format&fit=crop&w=900&q=82',
    tags: ['кухня-гостиная', 'свет', 'семья'],
    calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 42, rooms: 1, bathrooms: 0 },
    examples: [
      'Кухня-гостиная в квартире',
      'Кухня-гостиная в частном доме',
      'Кухня с островом',
      'Гостиная с ТВ-зоной',
      'Зонирование кухни и отдыха освещением',
      'Отделка стен под покраску',
      'Укладка пола в едином контуре',
      'Подготовка электрики под кухонный гарнитур',
      'Монтаж фартука и рабочей зоны',
      'Комплексная отделка семейной зоны',
    ],
  },
  {
    id: 'office',
    title: 'Ремонт офисных помещений',
    text: 'Офисы и коммерческие помещения под работу команды и прием клиентов.',
    image: 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=82',
    tags: ['офис', 'коммерция', 'сроки'],
    calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 180, rooms: 6 },
    examples: [
      'Open space для команды',
      'Кабинетный офис',
      'Ресепшен и входная зона',
      'Переговорная комната',
      'Ремонт офиса без остановки работы',
      'Замена напольных покрытий',
      'Потолки, свет и рабочие зоны',
      'Электрика и слаботочные сети',
      'Стеклянные перегородки',
      'Офис под ключ для заезда сотрудников',
    ],
  },
];

const readyProjectCardsByDirection = {
  'one-floor-modern': [
    {
      code: 'H1-01',
      title: 'Дом 105 м2 с террасой',
      area: '105 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная, 3 спальни, санузел, котельная, терраса.',
      visuals: 'Фасад, боковой ракурс и план 105 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/h1-01/facade.png' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/h1-01/side.png' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/h1-01/plan.png' },
      ],
      calcPatch: { area: 105, floors: 1, rooms: 4, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' },
    },
    {
      code: 'H1-02',
      title: 'Дом 128 м2 с панорамной гостиной',
      area: '128 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная, мастер-спальня, 2 спальни, 2 санузла, гардероб.',
      visuals: 'Длинный панорамный фасад, второй ракурс и план 128 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/h1-02/facade.png' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/h1-02/side.png' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/h1-02/plan.png' },
      ],
      calcPatch: { area: 128, floors: 1, rooms: 4, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' },
    },
    {
      code: 'H1-03',
      title: 'L-образный дом 145 м2',
      area: '145 м2',
      floors: '1 этаж',
      layout: 'Закрытый двор, кухня-гостиная, 4 спальни, 2 санузла, постирочная.',
      visuals: 'L-фасад, приватный двор и план с внутренней террасой.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D двор', src: '/site-assets/projects/h1-03/facade.png' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/h1-03/side.png' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/h1-03/plan.png' },
      ],
      calcPatch: { area: 145, floors: 1, rooms: 5, bedrooms: 4, wallType: 'gasblock', package: 'turnkey' },
    },
  ],
  'one-floor-brick': [
    {
      code: 'B1-01',
      title: 'Кирпичный дом 120 м2',
      area: '120 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная, 3 спальни, санузел, котельная, тамбур.',
      visuals: 'Кирпичный фасад, второй ракурс и план 120 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/b1-01/facade.png' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/b1-01/side.png' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/b1-01/plan.png' },
      ],
      calcPatch: { area: 120, floors: 1, rooms: 4, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'B1-02',
      title: 'Дом 138 м2 с эркером',
      area: '138 м2',
      floors: '1 этаж',
      layout: 'Гостиная с эркером, 3 спальни, кабинет, 2 санузла.',
      visuals: 'Кирпичный фасад с эркером, второй ракурс и план 138 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/b1-02/facade.png' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/b1-02/side.png' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/b1-02/plan.png' },
      ],
      calcPatch: { area: 138, floors: 1, rooms: 5, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'B1-03',
      title: 'Кирпичный дом 155 м2 с террасой',
      area: '155 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная с выходом на террасу, 4 спальни, 2 санузла.',
      visuals: 'Кирпич, терраса, второй ракурс и план 155 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/b1-03/facade.png' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D терраса', src: '/site-assets/projects/b1-03/side.png' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/b1-03/plan.png' },
      ],
      calcPatch: { area: 155, floors: 1, rooms: 5, bedrooms: 4, wallType: 'brick', package: 'turnkey' },
    },
  ],
  'family-cottage': [
    { code: 'FAM-01', title: 'Коттедж 150 м2 для семьи', area: '150 м2', floors: '1 этаж', layout: 'Кухня-гостиная, 4 спальни, 2 санузла, кладовая.', visuals: 'Семейный фасад + план 150 м2.', calcPatch: { area: 150, floors: 1, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'FAM-02', title: 'Коттедж 170 м2 со вторым светом', area: '170 м2', floors: '1 этаж', layout: 'Гостиная со вторым светом, 3 спальни, кабинет, 2 санузла.', visuals: 'Фасад + интерьер гостиной + план.', calcPatch: { area: 170, floors: 1, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'FAM-03', title: 'Коттедж 185 м2 с гостевой комнатой', area: '185 м2', floors: '1 этаж', layout: '4 спальни, гостевая, кухня-гостиная, постирочная.', visuals: 'Фасад с террасой + план 185 м2.', calcPatch: { area: 185, floors: 1, rooms: 6, wallType: 'gasblock', package: 'turnkey' } },
  ],
  'two-floor-modern': [
    { code: 'H2-01', title: 'Дом 165 м2 на узкий участок', area: '165 м2', floors: '2 этажа', layout: '1 этаж: кухня-гостиная и кабинет. 2 этаж: 3 спальни.', visuals: 'Современный фасад + планы 1/2 этажа.', calcPatch: { area: 165, floors: 2, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'H2-02', title: 'Дом 190 м2 со вторым светом', area: '190 м2', floors: '2 этажа', layout: 'Второй свет, мастер-спальня, 2 детские, 3 санузла.', visuals: 'Фасад + разрез/план.', calcPatch: { area: 190, floors: 2, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'H2-03', title: 'Дом 215 м2 с балконом', area: '215 м2', floors: '2 этажа', layout: 'Большая гостиная, 4 спальни, балкон, терраса.', visuals: 'Фасад с балконом + планы этажей.', calcPatch: { area: 215, floors: 2, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
  ],
  'two-floor-brick': [
    { code: 'B2-01', title: 'Кирпичный дом 180 м2', area: '180 м2', floors: '2 этажа', layout: 'Кухня-гостиная, 4 спальни, 2 санузла, котельная.', visuals: 'Кирпичный фасад + планы этажей.', calcPatch: { area: 180, floors: 2, rooms: 5, wallType: 'brick', package: 'turnkey' } },
    { code: 'B2-02', title: 'Дом 210 м2 с гаражной зоной', area: '210 м2', floors: '2 этажа', layout: '1 этаж: общая зона. 2 этаж: спальни. Отдельный хозблок.', visuals: 'Фасад + план 1/2 этажа.', calcPatch: { area: 210, floors: 2, rooms: 5, wallType: 'brick', package: 'turnkey' } },
    { code: 'B2-03', title: 'Классический дом 240 м2', area: '240 м2', floors: '2 этажа', layout: '5 спален, кабинет, большая кухня-гостиная, 3 санузла.', visuals: 'Классический фасад + планы.', calcPatch: { area: 240, floors: 2, rooms: 6, wallType: 'brick', package: 'turnkey' } },
  ],
  'garage-house': [
    { code: 'GAR-01', title: 'Дом 190 м2 с гаражом', area: '190 м2', floors: '2 этажа', layout: 'Гараж, кухня-гостиная, 4 спальни, котельная.', visuals: 'Фасад с гаражом + планы.', calcPatch: { area: 190, floors: 2, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'GAR-02', title: 'Дом 230 м2 с гаражом на 2 авто', area: '230 м2', floors: '2 этажа', layout: 'Гараж на 2 авто, мастер-спальня, кабинет, хоззона.', visuals: 'Фасад + планы этажей.', calcPatch: { area: 230, floors: 2, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'GAR-03', title: 'Дом 210 м2 с мастерской', area: '210 м2', floors: '2 этажа', layout: 'Гараж, мастерская, кухня-гостиная, 3 спальни.', visuals: 'Фасад + план с мастерской.', calcPatch: { area: 210, floors: 2, rooms: 5, wallType: 'gasblock', package: 'turnkey' } },
  ],
  townhouse: [
    { code: 'TOWN-01', title: 'Таунхаус 95 м2', area: '95 м2', floors: '2 этажа', layout: '1 этаж: кухня-гостиная. 2 этаж: 2 спальни.', visuals: 'Фасад секции + план.', calcPatch: { area: 95, floors: 2, rooms: 3, wallType: 'brick', package: 'warm' } },
    { code: 'TOWN-02', title: 'Таунхаус 120 м2 для семьи', area: '120 м2', floors: '2 этажа', layout: '3 спальни, кухня-гостиная, 2 санузла.', visuals: 'Фасад секции + планы.', calcPatch: { area: 120, floors: 2, rooms: 4, wallType: 'brick', package: 'warm' } },
    { code: 'TOWN-03', title: 'Таунхаус 135 м2 с кабинетом', area: '135 м2', floors: '2 этажа', layout: 'Кабинет, 3 спальни, кухня-гостиная.', visuals: 'Фасад + план.', calcPatch: { area: 135, floors: 2, rooms: 5, wallType: 'brick', package: 'warm' } },
  ],
  'cottage-reconstruction': [
    { code: 'REC-01', title: 'Реконструкция дома 140 м2', area: '140 м2', floors: '1-2 этажа', layout: 'Фасад, кровля, окна, обновление планировки.', visuals: 'До/после фасада + схема изменений.', calcPatch: { type: 'reconstruction', reconstructionScope: 'house', area: 140, rooms: 4, roofTouch: true, engineeringNew: true } },
    { code: 'REC-02', title: 'Мансарда вместо чердака', area: '80 м2 мансарды', floors: '2 этаж', layout: 'Спальни или кабинет на мансарде, лестница, утепление.', visuals: 'Кровля + план мансарды.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 80, rooms: 3, roofTouch: true, engineeringNew: true } },
    { code: 'REC-03', title: 'Пристройка террасы и кухни', area: '+35 м2', floors: '1 этаж', layout: 'Расширение кухни-гостиной и новая терраса.', visuals: 'Фасад с пристройкой + план.', calcPatch: { type: 'reconstruction', reconstructionScope: 'house', area: 35, rooms: 1, roofTouch: false, engineeringNew: false } },
  ],
  facade: [
    { code: 'FAC-01', title: 'Утепление фасада 180 м2', area: '180 м2 фасада', floors: 'дом', layout: 'Утепление, армирование, декоративная штукатурка.', visuals: 'Фасад до/после + узел стены.', calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 180, rooms: 1, roofTouch: false, engineeringNew: false } },
    { code: 'FAC-02', title: 'Фасад штукатурка + дерево', area: '220 м2 фасада', floors: 'дом', layout: 'Комбинированная отделка, подсветка, откосы.', visuals: 'Фасад + цветовая схема.', calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 220, rooms: 1, roofTouch: false, engineeringNew: false } },
    { code: 'FAC-03', title: 'Клинкерный фасад', area: '200 м2 фасада', floors: 'дом', layout: 'Клинкерная плитка, цоколь, отливы.', visuals: 'Фасад + узел цоколя.', calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 200, rooms: 1, roofTouch: false, engineeringNew: false } },
  ],
  roof: [
    { code: 'ROOF-01', title: 'Замена кровли 160 м2', area: '160 м2 кровли', floors: 'дом', layout: 'Демонтаж, обрешетка, металлочерепица, водосток.', visuals: 'Кровля + схема скатов.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 160, rooms: 1, roofTouch: true, engineeringNew: false } },
    { code: 'ROOF-02', title: 'Утепленная мансардная кровля', area: '190 м2 кровли', floors: 'мансарда', layout: 'Утепление, пароизоляция, окна, подшива.', visuals: 'Кровля + разрез утепления.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 190, rooms: 2, roofTouch: true, engineeringNew: false } },
    { code: 'ROOF-03', title: 'Мягкая кровля 145 м2', area: '145 м2 кровли', floors: 'дом', layout: 'Основание, подкладочный ковер, мягкая черепица.', visuals: 'Кровля + узел примыкания.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 145, rooms: 1, roofTouch: true, engineeringNew: false } },
  ],
  'apartment-repair': [
    { code: 'APT-01', title: 'Ремонт квартиры 45 м2', area: '45 м2', floors: 'квартира', layout: 'Кухня, спальня, санузел, прихожая.', visuals: 'Интерьер + план квартиры.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 45, rooms: 2, bathrooms: 1 } },
    { code: 'APT-02', title: 'Ремонт квартиры 72 м2', area: '72 м2', floors: 'квартира', layout: 'Кухня-гостиная, 2 спальни, санузел.', visuals: 'Интерьер + план 72 м2.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 72, rooms: 3, bathrooms: 1 } },
    { code: 'APT-03', title: 'Ремонт квартиры 95 м2', area: '95 м2', floors: 'квартира', layout: '3 спальни, кухня-гостиная, 2 санузла.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 95, rooms: 4, bathrooms: 2 } },
  ],
  'private-house-finish': [
    { code: 'FIN-01', title: 'Отделка дома 120 м2', area: '120 м2', floors: 'дом', layout: 'Черновая и чистовая отделка, 3 спальни, кухня-гостиная.', visuals: 'Интерьер + план дома.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 120, rooms: 4, bathrooms: 1 } },
    { code: 'FIN-02', title: 'Отделка дома 160 м2', area: '160 м2', floors: 'дом', layout: 'Теплые полы, лестница, 4 спальни, 2 санузла.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 160, rooms: 5, bathrooms: 2 } },
    { code: 'FIN-03', title: 'Отделка дома 210 м2', area: '210 м2', floors: '2 этажа', layout: 'Лестница, 5 комнат, 3 санузла.', visuals: 'Интерьер + планы этажей.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'designer', area: 210, rooms: 6, bathrooms: 3 } },
  ],
  bathroom: [
    { code: 'BATH-01', title: 'Санузел 4 м2', area: '4 м2', floors: 'квартира', layout: 'Душ, унитаз, раковина, стиральная зона.', visuals: 'Интерьер + план раскладки.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 4, rooms: 1, bathrooms: 1, tiles: true } },
    { code: 'BATH-02', title: 'Ванная 6 м2', area: '6 м2', floors: 'квартира', layout: 'Ванна, инсталляция, тумба, теплый пол.', visuals: 'Интерьер + план раскладки плитки.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 6, rooms: 1, bathrooms: 1, tiles: true } },
    { code: 'BATH-03', title: 'Санузел 9 м2 в доме', area: '9 м2', floors: 'дом', layout: 'Душ, ванна, две раковины, скрытые люки.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 9, rooms: 1, bathrooms: 1, tiles: true } },
  ],
  'kitchen-living': [
    { code: 'KIT-01', title: 'Кухня-гостиная 28 м2', area: '28 м2', floors: 'квартира', layout: 'Кухонная линия, столовая, ТВ-зона.', visuals: 'Интерьер + план мебели.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 28, rooms: 1, bathrooms: 0 } },
    { code: 'KIT-02', title: 'Кухня-гостиная 42 м2', area: '42 м2', floors: 'квартира', layout: 'Остров, диванная зона, световые сценарии.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 42, rooms: 1, bathrooms: 0 } },
    { code: 'KIT-03', title: 'Кухня-гостиная в доме 55 м2', area: '55 м2', floors: 'дом', layout: 'Остров, камин/ТВ-зона, выход на террасу.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'designer', area: 55, rooms: 1, bathrooms: 0 } },
  ],
  office: [
    { code: 'OFF-01', title: 'Офис open space 120 м2', area: '120 м2', floors: 'коммерция', layout: '18 рабочих мест, переговорная, кухня, санузел.', visuals: 'Интерьер офиса + план рабочих мест.', calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 120, rooms: 4 } },
    { code: 'OFF-02', title: 'Кабинетный офис 180 м2', area: '180 м2', floors: 'коммерция', layout: '8 кабинетов, ресепшен, переговорная, архив.', visuals: 'Интерьер + план.', calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 180, rooms: 10 } },
    { code: 'OFF-03', title: 'Офис 260 м2 с клиентской зоной', area: '260 м2', floors: 'коммерция', layout: 'Ресепшен, open space, кабинеты, переговорные.', visuals: 'Интерьер + план зонирования.', calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 260, rooms: 12 } },
  ],
};

const getReferenceProjectCards = (direction) => {
  const cards = readyProjectCardsByDirection[direction.id];
  if (cards?.length) return cards;
  return direction.examples.map((example, index) => ({
    code: `${direction.id}-${index + 1}`,
    title: example,
    area: `${direction.calcPatch.area || ''} м2`.trim(),
    floors: direction.calcPatch.floors ? `${direction.calcPatch.floors} этаж` : 'объект',
    layout: direction.text,
    visuals: 'Фасад/интерьер + планировка.',
    calcPatch: direction.calcPatch,
  }));
};

const parseProjectArea = (project) => {
  const match = String(project?.area || '').replace(',', '.').match(/(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : Number(project?.calcPatch?.area || 120);
};

const getProjectProfile = (direction, project) => {
  const calc = { ...(direction.calcPatch || {}), ...(project?.calcPatch || {}) };
  const rawFloors = String(project?.floors || '');
  const floors = Number(calc.floors || (rawFloors.includes('2') || rawFloors.includes('мансарда') ? 2 : 1));
  const isRepair = calc.type === 'repair';
  const isCommerce = calc.type === 'commerce';
  const isFacade = calc.reconstructionScope === 'facade';
  const isRoof = calc.reconstructionScope === 'roof';
  const isGarage = direction.id === 'garage-house' || project?.code?.startsWith('GAR-') || /гараж/i.test(project?.title || '');
  const isBrick = calc.wallType === 'brick' || direction.id.includes('brick');
  const visualType = isCommerce
    ? 'office'
    : direction.id === 'bathroom'
      ? 'bathroom'
      : direction.id === 'kitchen-living'
        ? 'kitchen'
        : isRepair
          ? 'interior'
          : isRoof
            ? 'roof'
            : isFacade
              ? 'facade'
              : 'house';
  return {
    floors: Math.max(1, floors || 1),
    isGarage,
    isBrick,
    visualType,
    title: project?.title || direction.title,
  };
};

const getProjectMediaOptions = (direction, project) => {
  if (Array.isArray(project?.media) && project.media.length) {
    return project.media.map((item, index) => ({
      id: item.id || `media-${index + 1}`,
      kind: item.kind || 'image',
      role: item.role || (item.id?.startsWith('plan') ? 'plan' : 'render'),
      angle: item.angle,
      floor: item.floor,
      label: item.label || `Вид ${index + 1}`,
      src: item.src,
    }));
  }
  const profile = getProjectProfile(direction, project);
  const renderLabel = profile.visualType === 'house'
    ? '3D фасад'
    : profile.visualType === 'roof'
      ? 'Ракурс кровли'
      : profile.visualType === 'facade'
        ? 'Фасад'
        : 'Визуал';
  const secondLabel = profile.visualType === 'house'
    ? '3D боковой'
    : profile.visualType === 'roof'
      ? 'Узел кровли'
      : profile.visualType === 'facade'
        ? 'Фасад сбоку'
        : 'Второй ракурс';
  const planLabel = profile.floors > 1 ? 'План 1 этажа' : 'Планировка';
  return [
    { id: 'render-front', kind: 'render', angle: 'front', label: renderLabel },
    { id: 'render-side', kind: 'render', angle: 'side', label: secondLabel },
    { id: 'plan-1', kind: 'plan', floor: 1, label: planLabel },
    ...(profile.floors > 1 ? [{ id: 'plan-2', kind: 'plan', floor: 2, label: 'План 2 этажа' }] : []),
  ];
};

const getProjectSpecs = (direction, project) => {
  const area = parseProjectArea(project);
  const floors = Number(project?.calcPatch?.floors || direction.calcPatch?.floors || 1);
  const rooms = Number(project?.calcPatch?.rooms || direction.calcPatch?.rooms || 1);
  const type = project?.calcPatch?.type || direction.calcPatch?.type || 'house';
  const isHouse = type === 'house';
  const isRepair = type === 'repair';
  const isFacade = project?.calcPatch?.reconstructionScope === 'facade';
  const isRoof = project?.calcPatch?.reconstructionScope === 'roof';
  const isGarage = direction.id === 'garage-house' || project?.code?.startsWith('GAR-');
  const explicitBedrooms = Number(project?.calcPatch?.bedrooms ?? direction.calcPatch?.bedrooms);
  const bedroomMatches = String(project?.layout || '').toLowerCase().matchAll(/(\d+)\s*(?:спальн|детск)/g);
  const layoutBedrooms = [...bedroomMatches].reduce((sum, match) => sum + Number(match[1] || 0), 0)
    + (/мастер[-\s]?спальн/.test(String(project?.layout || '').toLowerCase()) ? 1 : 0);
  const bedrooms = Number.isFinite(explicitBedrooms)
    ? explicitBedrooms
    : layoutBedrooms || (isHouse ? Math.max(1, rooms - 2) : Math.max(0, rooms - 1));
  const width = Math.max(8.5, Math.sqrt(area * 0.85)).toFixed(1).replace('.', ',');
  const length = Math.max(9.5, area / Number(width.replace(',', '.'))).toFixed(1).replace('.', ',');
  const wallMaterial = project?.calcPatch?.wallType === 'brick'
    ? 'кирпич / клинкер'
    : isRepair
      ? 'существующее основание'
      : 'пеноблок / газобетон';
  const finish = isFacade
    ? 'утепление / штукатурка'
    : isRoof
      ? 'кровельное покрытие'
      : isRepair
        ? 'чистовая / инженерия'
        : 'панели / штукатурка';

  return [
    ['Общая площадь', project?.area || `${area} м2`],
    ['Жилая площадь', isHouse ? `${Math.round(area * 0.42)} м2` : `${Math.round(area * 0.72)} м2`],
    ['Размеры', isHouse ? `${width} x ${length} м` : project?.floors || 'по объекту'],
    ['Высота здания', isHouse ? `${floors === 1 ? '4,1' : '7,9'} м` : 'по месту'],
    ['Количество комнат', String(Math.max(rooms, 1))],
    ['Количество спален', isHouse ? String(bedrooms) : 'по задаче'],
    ['Гараж', isGarage ? 'есть' : 'нет'],
    ['Отделка', finish],
    ['Материал стен', wallMaterial],
    ['Фундамент', isHouse ? 'монолитная плита' : 'существующий'],
    ['Перекрытия', floors > 1 ? 'монолитные' : 'по проекту'],
  ];
};

const getPlanRooms = (project, floor = 1) => {
  const rawParts = String(project?.layout || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  const secondFloor = ['Холл', 'Мастер-спальня', 'Спальня', 'Спальня', 'Санузел', 'Гардероб'];
  const firstFloor = ['Кухня-гостиная', 'Спальня', 'Спальня', 'Санузел', 'Холл'];
  const fallback = floor > 1 ? secondFloor : firstFloor;
  const parts = floor > 1 ? secondFloor : (rawParts.length ? rawParts : fallback);
  const sizes = floor > 1 ? ['12 м2', '18 м2', '15 м2', '14 м2', '6 м2', '5 м2'] : ['34 м2', '16 м2', '13 м2', '12 м2', '7 м2', '5 м2'];
  return parts.slice(0, 6).map((name, index) => ({
    name,
    size: sizes[index] || '',
    wide: index === 0,
  }));
};

const ProjectPlanGraphic = ({ project, title, floor = 1 }) => {
  const rooms = getPlanRooms(project, floor);
  return (
    <div className="public-project-plan-hero">
      <strong>{title}</strong>
      <div className="public-project-plan-grid" aria-label={title}>
        {rooms.map((room, index) => (
          <span className={room.wide ? 'wide' : ''} key={`${room.name}-${index}`}>
            <b>{room.name}</b>
            <small>{room.size}</small>
          </span>
        ))}
      </div>
    </div>
  );
};

const ProjectConceptVisual = ({ direction, project, media }) => {
  const profile = getProjectProfile(direction, project);
  if (media?.src) {
    return (
      <img
        className={`public-project-media-image ${media.role === 'plan' ? 'is-plan' : 'is-render'}`}
        src={media.src}
        alt={`${media.label || 'Визуал'}: ${profile.title}`}
      />
    );
  }
  if (media?.kind === 'plan') {
    return <ProjectPlanGraphic project={project} title={media.label} floor={media.floor} />;
  }
  const className = [
    'public-project-render',
    `render-${profile.visualType}`,
    profile.floors > 1 ? 'floors-2' : 'floors-1',
    profile.isGarage ? 'has-garage' : '',
    profile.isBrick ? 'is-brick' : '',
    media?.angle === 'side' ? 'angle-side' : 'angle-front',
  ].filter(Boolean).join(' ');
  return (
    <div className={className} aria-label={`${media?.label || 'Визуал'}: ${profile.title}`}>
      <span className="render-sky" />
      <span className="render-ground" />
      <span className="render-shadow" />
      <span className="render-main" />
      <span className="render-upper" />
      <span className="render-wing" />
      <span className="render-garage" />
      <span className="render-roof" />
      <span className="render-window window-a" />
      <span className="render-window window-b" />
      <span className="render-window window-c" />
      <span className="render-door" />
      <span className="render-interior-wall" />
      <span className="render-interior-floor" />
      <span className="render-interior-feature feature-a" />
      <span className="render-interior-feature feature-b" />
      <span className="render-interior-feature feature-c" />
      <span className="render-label">{media?.label || 'Визуал'}</span>
    </div>
  );
};

const ProjectConceptThumb = ({ direction, project }) => {
  const profile = getProjectProfile(direction, project);
  const imageMedia = Array.isArray(project?.media) ? project.media.find((item) => item.src) : null;
  if (imageMedia?.src) {
    return (
      <img
        className="public-project-concept-thumb image-thumb"
        src={imageMedia.src}
        alt=""
      />
    );
  }
  const className = [
    'public-project-concept-thumb',
    `thumb-${profile.visualType}`,
    profile.floors > 1 ? 'floors-2' : 'floors-1',
    profile.isGarage ? 'has-garage' : '',
    profile.isBrick ? 'is-brick' : '',
  ].filter(Boolean).join(' ');
  return (
    <span className={className} aria-hidden="true">
      <i className="thumb-main" />
      <i className="thumb-upper" />
      <i className="thumb-wing" />
      <i className="thumb-garage" />
      <i className="thumb-window one" />
      <i className="thumb-window two" />
    </span>
  );
};

const partnerTypes = [
  { value: 'supplier', label: 'Поставщик', note: 'Материалы, счета, КП, документы', icon: Handshake },
  { value: 'master', label: 'Мастер', note: 'Сдельные работы, объекты, акты', icon: Hammer },
  { value: 'brigade', label: 'Бригада', note: 'Пакеты работ, закрытия, расчёты', icon: BriefcaseBusiness },
  { value: 'subcontractor', label: 'Субподрядчик', note: 'Договор, объёмы, исполнительная документация', icon: Building2 },
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
    passport: 'Фотоотчеты, материалы, этапы работ',
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
    passport: 'Фото, инженерия, этапы приемки',
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
    passport: 'Сроки, отделка, готовность к открытию',
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
    passport: project.passport || project.publicPassport || 'Фото, этапы и паспорт объекта',
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
  const selectedReferenceMediaOptions = getProjectMediaOptions(selectedReference, selectedReferenceProject);
  const selectedReferenceMedia = selectedReferenceMediaOptions.find((item) => item.id === selectedReferenceMediaId) || selectedReferenceMediaOptions[0];

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

  const chooseReference = (direction, project = getReferenceProjectCards(direction)[0], shouldScroll = false) => {
    const projectCard = typeof project === 'string'
      ? getReferenceProjectCards(direction).find((item) => item.title === project) || { title: project, calcPatch: {} }
      : project;
    setSelectedReferenceId(direction.id);
    setSelectedReferenceExample(projectCard.title);
    setSelectedReferenceMediaId('render-front');
    setCalc((current) => ({ ...current, ...direction.calcPatch, ...(projectCard.calcPatch || {}) }));
    setLead((current) => ({
      ...current,
      comment: `Интересует: ${direction.title}. Проект: ${projectCard.title}. Планировка: ${projectCard.layout || direction.text}`,
    }));
    if (shouldScroll) {
      setTimeout(() => scrollTo('calculator'), 0);
    }
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
            <button type="button" onClick={() => scrollTo('services')}>Услуги</button>
            <button type="button" onClick={() => scrollTo('calculator')}>Калькулятор</button>
            <button type="button" onClick={() => scrollTo('objects')}>Объекты</button>
            <button type="button" onClick={() => scrollTo('work-proof')}>Работы</button>
            <button type="button" onClick={() => scrollTo('passport')}>Контроль</button>
            <button type="button" onClick={() => scrollTo('suppliers')}>Партнёрам</button>
            <button type="button" onClick={() => scrollTo('privacy')}>Политика</button>
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

        <div className="public-reference-board">
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
                return (
                  <button
                    className={isActive ? 'public-reference-card active' : 'public-reference-card'}
                    key={item.id}
                    type="button"
                    onClick={() => chooseReference(item)}
                    aria-pressed={isActive}
                  >
                    <ProjectConceptThumb direction={item} project={projectCards[0]} />
                    <span className="public-reference-count">{projectCards.length} проекта</span>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                    <div>
                      {item.tags.map((tag) => <span key={tag}>{tag}</span>)}
                    </div>
                  </button>
                );
              })}
            </div>

	            <section className="public-project-catalog" aria-label="Готовые проекты выбранного направления">
	              <div className="public-project-catalog-main">
	                <div className="public-project-visual-column">
	                  <div className="public-project-hero-visual">
	                    <ProjectConceptVisual
	                      direction={selectedReference}
	                      project={selectedReferenceProject}
	                      media={selectedReferenceMedia}
	                    />
                    {(selectedReferenceMedia?.kind === 'render' || selectedReferenceMedia?.role === 'render') && (
	                      <>
	                        <span className="public-project-ready-ribbon">Готовый проект</span>
	                        <span className="public-project-discount">10%</span>
	                      </>
	                    )}
	                  </div>
	                  <div className="public-project-media-strip" aria-label="Медиа проекта">
	                    {selectedReferenceMediaOptions.map((media) => (
	                      <button
	                        className={selectedReferenceMedia.id === media.id ? 'active' : ''}
	                        type="button"
	                        key={media.id}
	                        onClick={() => setSelectedReferenceMediaId(media.id)}
	                      >
	                        {media.label}
	                      </button>
	                    ))}
	                  </div>
	                  <div className="public-project-thumb-grid" aria-label="Варианты проекта">
	                    {selectedReferenceProjects.map((project) => (
	                      <button
	                        className={selectedReferenceProject?.title === project.title ? 'active' : ''}
                        type="button"
	                        key={project.code}
	                        onClick={() => chooseReference(selectedReference, project)}
	                      >
	                        <ProjectConceptThumb direction={selectedReference} project={project} />
	                        <b>{project.code}</b>
	                        <span>{project.area}</span>
	                      </button>
	                    ))}
	                  </div>
	                </div>

                <div className="public-project-spec-column">
                  <p className="public-tool-kicker">Каталог готовых проектов</p>
                  <h3>{selectedReferenceProject?.title || selectedReference.title}</h3>
                  <p>{selectedReferenceProject?.layout || selectedReference.text}</p>
                  <dl className="public-project-spec-list">
                    {selectedReferenceSpecs.map(([label, value]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <button className="public-project-outline" type="button">
                    Показать зеркальный вариант
                  </button>
                  <button className="public-project-editor" type="button">
                    Редактор планировки
                  </button>
                  <button className="public-project-outline" type="button">
                    Похожие по виду ({Math.max(3, selectedReferenceProjects.length)})
                  </button>
                  <button
                    className="public-primary public-reference-cta"
                    type="button"
                    onClick={() => chooseReference(selectedReference, selectedReferenceProject, true)}
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
          <span><a href="/privacy.html">Политика</a></span>
          <span><a href="/terms.html">Условия</a></span>
          <span><a href="/contacts.html">Контакты</a></span>
        </div>
      </section>
    </main>
  );
};

export default PublicSitePage;
